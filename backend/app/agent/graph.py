"""InspectionAgent - LangGraph state machine (Appendix A, Figure A2).

START -> parse_and_plan -> execute_tool -> observe/decide --(more steps)--> execute_tool
                                               |--(error, retry left)-----> execute_tool
                                               |--(error)-----------------> fallback -> generate_report
                                               '--(done)------------------> generate_report -> END
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ..config import Settings
from ..memory import SemanticMemory
from ..mqtt_bridge import RobotBridge
from ..report import render_markdown
from ..schemas import AgentStep, ChatResponse, InspectionReport
from ..store import Store
from ..vlm import VisionAnalyzer
from .llm import get_chat_model
from .planner import llm_plan, plan_ack, quick_reply, rule_plan, summarize_with_llm
from .text import spoken_zone, to_speech
from .tools import RobotTools, ToolError, short_finding

log = logging.getLogger(__name__)


MOVING_TOOLS = {"inspect_zone", "go_to_zone", "return_home", "move", "turn", "check_ac", "find_sound"}


class AgentState(TypedDict, total=False):
    request: str
    plan: list[dict]
    idx: int
    steps: list[dict]
    observations: list[dict]
    error: str | None
    retries: int
    escalated: bool
    reply: str
    planner: str
    report_id: str | None
    speech: str
    ack: str | None
    context_zone: str | None


class InspectionAgent:
    def __init__(self, settings: Settings, bridge: RobotBridge, memory: SemanticMemory | None, store: Store):
        self.s, self.bridge, self.memory, self.store = settings, bridge, memory, store
        self.vision = VisionAnalyzer(settings)
        self.llm = get_chat_model(settings)
        self.lock = asyncio.Lock()   # one mission at a time per backend (single robot)
        self.context: dict[str, str] = {}   # user -> zone talked about last ("go there")
        from ..monitor import ExamMonitor

        self.monitor = ExamMonitor(self._make_tools, store=store)

    def _make_tools(self, robot_id: str, user: str | None = None) -> RobotTools:
        t = RobotTools(self.s, self.bridge, self.memory, self.vision, robot_id, user, store=self.store)
        t.monitor = self.monitor
        return t

    @property
    def planner_name(self) -> str:
        return f"llm:{self.s.llm_provider}" if self.llm else "rules"

    # ------------------------------------------------------------------ graph
    def _build(self, tools: RobotTools, emit):
        async def parse_and_plan(state: AgentState) -> AgentState:
            zones = tools.zones()
            ctx = state.get("context_zone")
            plan, reply, planner = [], quick_reply(state["request"]), "rules"
            if reply is None and self.llm is not None:
                try:
                    plan, reply = await llm_plan(self.llm, state["request"], zones, ctx)
                    planner = self.planner_name
                except Exception as e:  # noqa: BLE001
                    log.warning("LLM planner failed (%s) - rule-based fallback", e)
            if not plan and not reply:
                plan = rule_plan(state["request"], zones, ctx)
                planner = "rules"
            if self.monitor.active:
                if any(p["tool"] == "stop" for p in plan):
                    plan = [{"tool": "stop_monitoring", "args": {}}] + plan
                busy = [p for p in plan if p["tool"] in MOVING_TOOLS]
                if busy:
                    zone = spoken_zone(self.monitor.session.get("zone")) if self.monitor.session.get("zone") else "here"
                    plan, reply = [], (f"I'm monitoring the exam in {zone} right now, so I'll stay where I am. "
                                       "Say \"stop monitoring\" first, or ask \"how is the exam going?\"")
            steps = [AgentStep(tool=p["tool"], args=p["args"]).model_dump() for p in plan]
            ack = plan_ack(plan)
            here = tools.current_zone()
            if ack and plan and all(p["tool"] == "go_to_zone" and p["args"].get("zone") == here for p in plan):
                ack = None
            await emit({"type": "plan", "steps": steps, "planner": planner, "ack": ack})
            return {"plan": plan, "idx": 0, "steps": steps, "observations": [], "error": None, "retries": 0,
                    "planner": planner, "reply": reply or "", "ack": ack}

        async def execute_tool(state: AgentState) -> AgentState:
            i = state["idx"]
            step = dict(state["steps"][i])
            step.update(status="running", started=time.time())
            await emit({"type": "step", "index": i, "step": step})
            steps = list(state["steps"])
            try:
                obs = await tools.call(step["tool"], step["args"])
                step.update(status="done", summary=obs["summary"], finished=time.time())
                steps[i] = step
                await emit({"type": "step", "index": i, "step": step})
                if obs.get("report_id"):
                    tools.linked_report = obs["report_id"]
                return {"steps": steps, "idx": i + 1, "error": None, "retries": 0,
                        "observations": state["observations"] + [{"tool": step["tool"], "args": step["args"],
                                                                  "summary": obs["summary"]}]}
            except (ToolError, Exception) as e:  # noqa: BLE001
                msg = str(e) or e.__class__.__name__
                step.update(status="error", summary=msg, finished=time.time())
                steps[i] = step
                await emit({"type": "step", "index": i, "step": step})
                return {"steps": steps, "error": msg, "retries": state.get("retries", 0) + 1}

        def decide(state: AgentState) -> str:
            if state.get("error"):
                transient = any(w in state["error"] for w in ("timeout", "blocked"))
                return "retry" if transient and state["retries"] <= 1 else "fallback"
            return "next" if state["idx"] < len(state["plan"]) else "done"

        async def fallback(state: AgentState) -> AgentState:
            # human escalation: make the robot safe and report what happened
            try:
                await tools.stop()
            except Exception:  # noqa: BLE001
                pass
            failed = state["steps"][state["idx"]]
            await emit({"type": "escalation", "error": state["error"]})
            return {"escalated": True,
                    "observations": state["observations"] + [{"tool": failed["tool"], "error": state["error"]}]}

        async def generate_report(state: AgentState) -> AgentState:
            reply_parts: list[str] = []
            speech_parts: list[str] = []
            report_id = None
            if tools.inspections:
                rep = InspectionReport(robot_id=tools.robot_id, request=state["request"], requested_by=tools.user,
                                       zones=tools.inspections)
                rep.markdown = render_markdown(rep)
                self.store.save_report(rep)
                report_id = rep.id
                if self.memory is not None:
                    for z in tools.inspections:
                        try:
                            await asyncio.to_thread(self.memory.add_inspection, z, rep.id, tools.robot_id)
                        except Exception as e:  # noqa: BLE001
                            log.warning("memory write failed: %s", e)
                names = [spoken_zone(z.zone) for z in tools.inspections]
                total = sum(len(z.anomalies) for z in tools.inspections)
                reply_parts.append(f"Inspected **{len(names)} room{'s' if len(names) > 1 else ''}** - "
                                   + ("everything is compliant." if not total else f"**{total} finding{'s' if total > 1 else ''}** to act on."))
                speech_parts.append("I've finished the inspection." if len(names) == 1
                                    else f"I've finished inspecting {len(names)} rooms.")
                for z in tools.inspections:
                    zn = spoken_zone(z.zone)
                    if z.compliant:
                        reply_parts.append(f"✅ **{zn}** - all clear.")
                        speech_parts.append(f"{zn} is all clear.")
                    else:
                        reply_parts.append(f"⚠️ **{zn}**\n" + "\n".join(f"- {a.description}" for a in z.anomalies))
                        n = len(z.anomalies)
                        speech_parts.append(f"{zn} has {n} issue{'s' if n > 1 else ''}: "
                                            + "; ".join(short_finding(a.description) for a in z.anomalies[:3]) + ".")
                other = [o for o in state["observations"] if o.get("tool") not in ("inspect_zone", "return_home")
                         and o.get("summary")]
                for o in other:
                    reply_parts.append(o["summary"])
                if any(o.get("tool") == "return_home" and o.get("summary") for o in state["observations"]):
                    reply_parts.append("Back at home.")
                reply_parts.append("The full audit report is saved in Reports.")
                speech_parts.append("The full report is saved.")
            elif state.get("reply") and not state["plan"]:
                reply_parts.append(state["reply"])
                speech_parts.append(to_speech(state["reply"].split("\n")[0]))
            elif not state["plan"]:
                zones = ", ".join(spoken_zone(z) for z in tools.zones() if z.lower() != "home") or "the configured rooms"
                extra = ("" if self.llm is not None else " To follow any wording, an admin can connect a free AI model "
                         "in More > AI settings.")
                reply_parts.append("Sorry, I didn't catch an action in that. Try \"Inspect the IoT Lab\", "
                                   "\"Go forward 2 meters and tell me what you see\", \"Who is talking?\", "
                                   "\"Monitor the exam in Exam Hall\" or say \"help\". "
                                   f"Rooms I know: {zones}.{extra}")
                speech_parts.append("Sorry, I didn't catch an action in that. Say help to hear what I can do.")
            else:
                text = None
                if self.llm is not None and state["observations"]:
                    text = await summarize_with_llm(self.llm, state["request"], state["observations"])
                if not text:
                    obs = [o for o in state["observations"] if o.get("summary") or o.get("error")]
                    # "Arrived at X." is implied when a later step reports about X
                    if len(obs) > 1 and obs[0].get("tool") == "go_to_zone" and not obs[0].get("error"):
                        obs = obs[1:]
                    text = " ".join(o.get("summary") or f"❌ {o.get('error')}" for o in obs)
                reply_parts.append(text)
                speech_parts.append(to_speech(text))
            if state.get("escalated"):
                reply_parts.append(f"❗ I stopped the robot and need human help: {state.get('error')}")
                speech_parts.append("I had a problem and stopped the robot. " + to_speech(str(state.get("error"))) +
                                    " Please check on me.")
            for img in tools.images[:4]:
                reply_parts.append(f"![photo](/images/{img})")
            return {"reply": "\n\n".join(p for p in reply_parts if p), "report_id": report_id or tools.linked_report,
                    "speech": " ".join(p for p in speech_parts if p)}

        g = StateGraph(AgentState)
        g.add_node("parse_and_plan", parse_and_plan)
        g.add_node("execute_tool", execute_tool)
        g.add_node("fallback", fallback)
        g.add_node("generate_report", generate_report)
        g.add_edge(START, "parse_and_plan")
        g.add_conditional_edges("parse_and_plan", lambda s: "execute" if s["plan"] else "report",
                                {"execute": "execute_tool", "report": "generate_report"})
        g.add_conditional_edges("execute_tool", decide, {"next": "execute_tool", "retry": "execute_tool",
                                                         "fallback": "fallback", "done": "generate_report"})
        g.add_edge("fallback", "generate_report")
        g.add_edge("generate_report", END)
        return g.compile()

    # ------------------------------------------------------------------ public
    async def run(self, request: str, robot_id: str, user: str | None = None, emit=None,
                  zone_hint: str | None = None) -> ChatResponse:
        async def _emit(ev: dict[str, Any]):
            if emit:
                await emit(ev)

        async with self.lock:
            t0 = time.time()
            tools = self._make_tools(robot_id, user)
            tools.progress = lambda ev: _emit({"type": "progress", **ev})
            tools.linked_report = None
            graph = self._build(tools, _emit)
            ctx = zone_hint or self.context.get(user or "")
            final = await graph.ainvoke({"request": request, "context_zone": ctx}, config={"recursion_limit": 80})
            last = tools.inspections[-1].zone if tools.inspections else tools.last_zone
            if last and user:
                self.context[user] = last
            resp = ChatResponse(reply=final.get("reply", ""), steps=[AgentStep(**s) for s in final.get("steps", [])],
                                report_id=final.get("report_id"), planner=final.get("planner", "rules"),
                                duration_s=round(time.time() - t0, 2), speech=final.get("speech", ""),
                                ack=final.get("ack"), images=tools.images)
            await _emit({"type": "done", "response": resp.model_dump()})
            return resp

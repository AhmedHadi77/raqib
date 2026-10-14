"""Multimodal fusion (vision + environment + audio) and audit-report generation (Appendix D2/D3 format)."""
from __future__ import annotations

import time
from datetime import datetime

from .schemas import Anomaly, InspectionReport, VisionAnalysis, ZoneInspection

COMFORT_TEXT = {
    "COMFORTABLE": "COMFORTABLE - within the optimal range",
    "UNCOMFORTABLE_HOT_HUMID": "UNCOMFORTABLE (Hot & Humid)",
    "UNCOMFORTABLE_HOT": "UNCOMFORTABLE (Too Hot)",
    "UNCOMFORTABLE_HUMID": "UNCOMFORTABLE (Too Humid)",
    "UNCOMFORTABLE_COLD": "UNCOMFORTABLE (Too Cold)",
    "UNCOMFORTABLE_DRY": "UNCOMFORTABLE (Too Dry)",
    "OVERCOOLED_ENERGY_WASTE": "OVER-COOLED (Energy Waste)",
}
COMFORT_PLAIN = {
    "UNCOMFORTABLE_HOT_HUMID": "Hot and humid",
    "UNCOMFORTABLE_HOT": "Too warm",
    "UNCOMFORTABLE_HUMID": "Too humid",
    "UNCOMFORTABLE_COLD": "Too cold",
    "UNCOMFORTABLE_DRY": "Too dry",
    "OVERCOOLED_ENERGY_WASTE": "Over-cooled",
}
GAS_TEXT = {
    "NORMAL": "NORMAL",
    "ELEVATED": "ELEVATED - monitor",
    "WARNING": "WARNING (Discomfort Hazard) - ventilation required",
    "HAZARD": "HAZARD - ventilate immediately and evacuate if needed",
}


def classify_env(temp: float, rh: float, aqi: float | None, cfg_min=22.0, cfg_max=26.0, rh_min=40.0, rh_max=60.0,
                 occupied: bool | None = None) -> str:
    """Re-evaluate comfort with the VLM occupancy (same rules as edge/robot/environmental_sensor.py)."""
    if temp > cfg_max and rh > rh_max:
        return "UNCOMFORTABLE_HOT_HUMID"
    if temp > cfg_max:
        return "UNCOMFORTABLE_HOT"
    if temp < cfg_min:
        return "OVERCOOLED_ENERGY_WASTE" if temp < 20.0 and occupied is not True else "UNCOMFORTABLE_COLD"
    if rh > rh_max:
        return "UNCOMFORTABLE_HUMID"
    if rh < rh_min:
        return "UNCOMFORTABLE_DRY"
    return "COMFORTABLE"


def fuse(zone: str, vision: VisionAnalysis | None, env: dict | None, audio: dict | None,
         image_file: str | None = None) -> ZoneInspection:
    z = ZoneInspection(zone=zone, vision=vision, environment=env, audio=audio, image_file=image_file)
    an, actions = z.anomalies, z.recommended_actions
    vacant = vision is not None and vision.occupants == 0

    # ---------------- energy (vision + acoustic)
    energy_items = []
    if vision and vacant:
        if vision.lights_on:
            energy_items.append("ceiling lights")
        if vision.projector_on:
            energy_items.append("projector")
        if vision.monitors_on:
            energy_items.append("monitors / lab equipment")
    if energy_items:
        an.append(Anomaly(type="energy_waste", severity="high", source="vlm",
                          description=f"{', '.join(energy_items).capitalize()} left ON in an unoccupied room"))
        actions.append({"priority": "High", "category": "Energy Governance",
                        "action": f"Switch off the unattended {', '.join(energy_items)} in the vacant room."})
    ac_running = bool(audio and audio.get("label") == "ac_fan")
    comfort = None
    if env and env.get("temperature_c") is not None:
        occupied = None if vision is None else vision.occupants > 0
        comfort = classify_env(env["temperature_c"], env["humidity_pct"], env.get("aqi"), occupied=occupied)
        z.comfort_verdict = comfort
        z.gas_verdict = env.get("gas_verdict")
    if ac_running and vacant:
        sev = "high" if comfort == "OVERCOOLED_ENERGY_WASTE" else "medium"
        extra = " while the room is over-cooled" if comfort == "OVERCOOLED_ENERGY_WASTE" else (
            " without cooling the room effectively" if comfort and comfort.startswith("UNCOMFORTABLE_HOT") else "")
        an.append(Anomaly(type="energy_waste", severity=sev, source="audio",
                          description=f"Air-conditioner / fan running in an empty room{extra} ({audio.get('db')} dB)"))
        actions.append({"priority": "High" if sev == "high" else "Medium", "category": "Energy Governance",
                        "action": "Inspect / switch off the air-conditioning unit in the vacant room."})
    z.energy_status = "WASTE" if any(a.type == "energy_waste" for a in an) else ("OK" if vision else "unknown")

    # ---------------- comfort + gas (environment)
    if comfort and comfort != "COMFORTABLE":
        an.append(Anomaly(type="comfort", severity="medium", source="environment",
                          description=f"{COMFORT_PLAIN.get(comfort, comfort)}: {env['temperature_c']:.1f}°C, "
                                      f"{env['humidity_pct']:.0f}% RH (target 22-26°C, 40-60% RH)"))
        if comfort.startswith("UNCOMFORTABLE_HOT") or comfort == "UNCOMFORTABLE_HUMID":
            actions.append({"priority": "High", "category": "Comfort",
                            "action": "Check the AC unit to restore a comfortable temperature before the next session."})
        elif comfort == "OVERCOOLED_ENERGY_WASTE":
            actions.append({"priority": "Medium", "category": "Energy Governance",
                            "action": "Raise the AC set-point or switch it off - the empty room is over-cooled."})
    gas = (env or {}).get("gas_verdict")
    if gas in ("WARNING", "HAZARD"):
        an.append(Anomaly(type="air_quality", severity="critical" if gas == "HAZARD" else "high", source="environment",
                          description=f"Poor air quality: AQI {env.get('aqi')} ({env.get('aqi_label')})"
                                      + (f", MQ-135 ~{env.get('mq135_ppm')} ppm" if env.get("mq135_ppm") else "")))
        actions.append({"priority": "High", "category": "Air Quality",
                        "action": "Activate the exhaust ventilation fan / open windows to clear fumes and stale air."})

    # ---------------- safety (vision + audio)
    if vision:
        if vision.exit_visible and not vision.exit_clear:
            an.append(Anomaly(type="blocked_exit", severity="high", source="vlm",
                              description="Emergency exit pathway is obstructed"))
            actions.append({"priority": "High", "category": "Safety Compliance",
                            "action": "Remove the obstruction from the emergency exit pathway."})
        for item in vision.hazardous_items:
            an.append(Anomaly(type="lab_hazard", severity="high", source="vlm", description=f"Lab hazard: {item}"))
            actions.append({"priority": "High", "category": "Lab Safety",
                            "action": f"Make safe: {item}."})
        if vision.water_leak_or_stain:
            an.append(Anomaly(type="equipment", severity="medium", source="vlm", description="Water leak / stain visible"))
            actions.append({"priority": "Medium", "category": "Maintenance", "action": "Inspect for a water leak."})
    if audio and audio.get("label") == "alarm":
        an.append(Anomaly(type="equipment", severity="critical", source="audio",
                          description=f"Emergency alarm / water-leak acoustic signature ({audio.get('db')} dB)"))
        actions.append({"priority": "Critical", "category": "Safety", "action": "Investigate the alarm immediately."})
    z.safety_status = "HAZARD" if any(a.type in ("blocked_exit", "lab_hazard") or a.severity == "critical"
                                      for a in an) else ("COMPLIANT" if vision else "unknown")
    z.compliant = not an and vision is not None
    z.summary = zone_text(z)
    return z


def zone_text(z: ZoneInspection) -> str:
    """Plain-text summary - this is what gets embedded into the vector database."""
    ts = datetime.fromtimestamp(z.ts).strftime("%Y-%m-%d %H:%M")
    parts = [f"Inspection of zone {z.zone} on {ts}."]
    v, e, a = z.vision, z.environment, z.audio
    if v:
        on = [n for n, f in (("lights", v.lights_on), ("projector", v.projector_on), ("monitors", v.monitors_on)) if f]
        parts.append(f"Occupancy {v.occupants}. " + (f"{', '.join(on)} ON." if on else "Lights and projector OFF."))
        parts.append("Emergency exit clear." if v.exit_clear else "Emergency exit BLOCKED.")
        parts.append("Fire extinguisher present." if v.extinguisher_present else "No fire extinguisher seen.")
    if e and e.get("temperature_c") is not None:
        parts.append(f"Temperature {e['temperature_c']:.1f}C humidity {e['humidity_pct']:.0f}% comfort "
                     f"{z.comfort_verdict}. Air quality index {e.get('aqi')} {e.get('aqi_label')} gas {e.get('gas_verdict')}.")
    if a:
        parts.append(f"Audio: {a.get('title', a.get('label'))} at {a.get('db')} dB.")
    if z.anomalies:
        parts.append("Issues: " + "; ".join(x.description for x in z.anomalies) + ".")
    else:
        parts.append("No issues found; zone fully compliant.")
    return " ".join(parts)


def render_markdown(r: InspectionReport) -> str:
    lines = [f"## {r.title}", "",
             f"**Inspected zone(s):** {', '.join(z.zone for z in r.zones) or '-'}  ",
             f"**Date:** {datetime.fromtimestamp(r.created).strftime('%Y-%m-%d %H:%M')}  ",
             f"**Robot:** {r.robot_id}  ", f"**Request:** \"{r.request}\"", ""]
    all_actions = []
    for z in r.zones:
        v, e, a = z.vision, z.environment or {}, z.audio or {}
        lines.append(f"### {z.zone} — {'✅ COMPLIANT' if z.compliant else '⚠️ ISSUES FOUND'}")
        if v:
            lines.append(f"1. **Occupancy (VLM):** {v.occupants} occupant(s) detected"
                         + (" (room is currently vacant)." if v.occupants == 0 else "."))
        if e.get("temperature_c") is not None:
            climate = "BME680" if e.get("gas_resistance_ohm") else "AHT20 + BMP280"
            lines.append(f"2. **Temperature & comfort ({climate}):** {e['temperature_c']:.1f}°C, {e['humidity_pct']:.0f}% RH. "
                         f"Comfort verdict: **{COMFORT_TEXT.get(z.comfort_verdict, z.comfort_verdict)}**.")
            lines.append(f"3. **Gas & air quality ({'BME680 + ' if e.get('gas_resistance_ohm') else ''}MQ-135):** AQI {e.get('aqi')} ({e.get('aqi_label')})"
                         + (f", ~{e.get('mq135_ppm')} ppm CO₂-eq" if e.get("mq135_ppm") else "")
                         + f". Gas safety verdict: **{GAS_TEXT.get(e.get('gas_verdict'), e.get('gas_verdict'))}**.")
        if v:
            on = [n for n, f in (("ceiling lights", v.lights_on), ("projector", v.projector_on),
                                 ("monitors", v.monitors_on)) if f]
            vis = (f"{', '.join(on).capitalize()} ON" if on else "Lights/projector OFF")
            vis += "; emergency exit " + ("clear" if v.exit_clear else "**OBSTRUCTED**")
            vis += "; fire extinguisher " + ("present" if v.extinguisher_present else "not seen")
            if v.hazardous_items:
                vis += "; hazards: " + ", ".join(v.hazardous_items)
            lines.append(f"4. **Visual energy & safety audit ({v.provider}):** {vis}. _{v.description}_"
                         + (" 🔎 _Flagged for human review._" if v.needs_human_review else ""))
        if a:
            lines.append(f"5. **Acoustic audit ({a.get('method', 'audio')}):** {a.get('title', a.get('label'))} "
                         f"({a.get('db')} dB, confidence {a.get('confidence')}).")
        if z.image_file:
            lines.append(f"\n![snapshot](/images/{z.image_file})")
        lines.append("")
        all_actions += [dict(act, zone=z.zone) for act in z.recommended_actions]
    lines.append("### Recommended actions")
    if all_actions:
        order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        for act in sorted(all_actions, key=lambda x: order.get(x["priority"], 9)):
            lines.append(f"- **{act['priority']} ({act['category']}, {act['zone']}):** {act['action']}")
    else:
        lines.append("- None required. Zone(s) logged as fully compliant for this inspection cycle.")
    lines.append("")
    lines.append(f"_Archived to semantic memory (ChromaDB) at {time.strftime('%H:%M:%S')}._")
    return "\n".join(lines)


def render_html(r: InspectionReport, data_dir: str) -> str:
    """Self-contained printable report (images inlined) - used for PDF export."""
    import base64
    import html
    from pathlib import Path

    def esc(x):
        return html.escape(str(x if x is not None else "-"))

    sev_col = {"critical": "#C62828", "high": "#D6402B", "medium": "#B7791F", "low": "#2E6FA7"}
    zones_html = []
    actions = []
    for z in r.zones:
        img = ""
        if z.image_file:
            p = Path(data_dir) / "images" / z.image_file
            if p.exists():
                img = f'<img src="data:image/jpeg;base64,{base64.b64encode(p.read_bytes()).decode()}"/>'
        e, v, a = z.environment or {}, z.vision, z.audio or {}
        badge = ('<span class="badge ok">Compliant</span>' if z.compliant
                 else f'<span class="badge bad">{len(z.anomalies)} issue(s)</span>')
        facts = []
        if v:
            facts.append(("Occupancy", f"{v.occupants} people"))
        if e.get("temperature_c") is not None:
            facts += [("Temperature", f"{e['temperature_c']:.1f} °C"), ("Humidity", f"{e['humidity_pct']:.0f} %"),
                      ("Air quality", f"AQI {e.get('aqi')} ({esc(e.get('aqi_label'))})"),
                      ("Comfort", COMFORT_TEXT.get(z.comfort_verdict, z.comfort_verdict)),
                      ("Gas safety", GAS_TEXT.get(e.get("gas_verdict"), e.get("gas_verdict")))]
        if a:
            facts.append(("Sound", f"{esc(a.get('title') or a.get('label'))}, {a.get('db')} dB"))
        facts.append(("Energy", "Waste detected" if z.energy_status == "WASTE" else "OK"))
        rows = "".join(f"<tr><th>{esc(k)}</th><td>{esc(val)}</td></tr>" for k, val in facts)
        an = "".join(f'<li><b style="color:{sev_col.get(x.severity, "#333")}">{esc(x.severity.title())}</b> '
                     f'{esc(x.description)}</li>' for x in z.anomalies) or "<li>No issues found.</li>"
        desc = f'<p class="muted">{esc(v.description)}</p>' if v else ""
        zones_html.append(f"""<section class="zone"><h2>{esc(z.zone)} {badge}</h2>
          <div class="grid"><div>{img}{desc}</div><div><table>{rows}</table></div></div>
          <h3>Findings</h3><ul>{an}</ul></section>""")
        actions += [dict(act, zone=z.zone) for act in z.recommended_actions]
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    act_html = "".join(f"<tr><td><b>{esc(x['priority'])}</b></td><td>{esc(x['zone'])}</td><td>{esc(x['category'])}</td>"
                       f"<td>{esc(x['action'])}</td></tr>"
                       for x in sorted(actions, key=lambda x: order.get(x["priority"], 9)))
    when = datetime.fromtimestamp(r.created).strftime("%d %B %Y, %H:%M")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Audit report {esc(r.id)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 @page {{ size: A4; margin: 16mm; }}
 body {{ font-family: Barlow, "Segoe UI", Roboto, Arial, sans-serif; color:#14231F; margin:0; padding:24px; }}
 header {{ border-left: 6px solid #0E7C5A; padding-left: 14px; margin-bottom: 18px; }}
 h1 {{ font-size: 22px; margin: 0 0 4px; }} h2 {{ font-size: 18px; margin: 0 0 10px; }}
 h3 {{ font-size: 14px; margin: 12px 0 4px; }}
 .muted {{ color:#4F625C; font-size: 12px; }}
 .zone {{ border:1px solid #CFDAD5; border-radius: 10px; padding: 14px; margin: 0 0 14px; page-break-inside: avoid; }}
 .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap: 14px; }}
 img {{ width:100%; border-radius: 6px; }}
 table {{ border-collapse: collapse; width:100%; font-size: 12.5px; }}
 th, td {{ text-align:left; padding: 5px 6px; border-bottom: 1px solid #E3EAE7; vertical-align: top; }}
 th {{ color:#4F625C; font-weight:600; width: 38%; }}
 ul {{ margin: 4px 0 0 18px; padding:0; font-size: 13px; }} li {{ margin: 3px 0; }}
 .badge {{ font-size: 12px; padding: 2px 8px; border-radius: 99px; vertical-align: middle; }}
 .ok {{ background:#D8F0E5; color:#0B6148; }} .bad {{ background:#FCE6C5; color:#7A4A00; }}
 footer {{ margin-top: 18px; font-size: 11px; color:#4F625C; }}
 @media (max-width: 640px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style></head><body>
<header><h1>Green Campus energy, comfort &amp; lab safety audit</h1>
<div class="muted">{esc(when)} &nbsp;|&nbsp; Robot {esc(r.robot_id)} &nbsp;|&nbsp; Report {esc(r.id)}</div>
<div class="muted">Request: “{esc(r.request)}”</div></header>
{''.join(zones_html)}
<section class="zone"><h2>Recommended actions</h2>
<table><tr><th>Priority</th><th>Zone</th><th>Area</th><th>Action</th></tr>{act_html or '<tr><td colspan=4>None required.</td></tr>'}</table></section>
<footer>Generated by the AI Agent Inspection Robot (LangGraph agent, vision model, climate + MQ-135 gas sensors, acoustic classifier).</footer>
</body></html>"""


VISION_NAMES = {"sim": "Simulator", "mediapipe": "MediaPipe on the server PC", "ai": "Vision AI"}


def render_exam_html(sess: dict, data_dir: str, product: str = "Raqib", site: str = "") -> str:
    """Printable exam-monitoring report: every incident with its photos (images inlined)."""
    import base64
    import html
    from pathlib import Path

    def esc(x):
        return html.escape(str(x if x is not None else "-"))

    def img(name):
        if not name:
            return ""
        p = Path(data_dir) / "images" / Path(name).name
        return f'<img src="data:image/jpeg;base64,{base64.b64encode(p.read_bytes()).decode()}"/>' if p.exists() else ""

    incs = sess.get("incidents", [])
    counts: dict[str, int] = {}
    for i in incs:
        counts[i.get("title", i.get("type"))] = counts.get(i.get("title", i.get("type")), 0) + 1
    start = datetime.fromtimestamp(sess.get("started") or time.time())
    end = datetime.fromtimestamp(sess["ended"]) if sess.get("ended") else None
    dur = f"{((sess.get('ended') or time.time()) - (sess.get('started') or time.time())) / 60:.0f} min"
    summary_rows = "".join(f"<tr><th>{esc(k)}</th><td>{n}</td></tr>" for k, n in counts.items()) \
        or '<tr><td colspan="2">No incidents. The exam ran without problems.</td></tr>'
    cards = []
    for n, i in enumerate(incs, 1):
        when = datetime.fromtimestamp(i["ts"]).strftime("%H:%M:%S")
        cards.append(f"""<section class="inc"><h2>#{n} {esc(i.get('title'))} <span class="t">{when}</span></h2>
          <div class="grid">{img(i.get('image'))}{img(i.get('close_image'))}</div>
          <p>{esc(i.get('summary'))}</p>
          <p class="muted">{'Student was warned by the robot.' if i.get('warned') else 'No spoken warning.'}
          {(' Patrol point ' + esc(i.get('waypoint')) + '.') if i.get('waypoint') else ''}</p></section>""")
    det = sess.get("detect") or {}
    checks = ", ".join(k.replace("_", " ") for k, v in det.items() if v) or "-"
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Exam report {esc(sess.get('id'))}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 @page {{ size: A4; margin: 16mm; }}
 body {{ font-family: "Segoe UI", Roboto, Arial, sans-serif; color:#0D1530; margin:0; padding:24px; }}
 header {{ border-left: 6px solid #3D5AFE; padding-left: 14px; margin-bottom: 18px; }}
 h1 {{ font-size: 22px; margin: 0 0 4px; }} h2 {{ font-size: 16px; margin: 0 0 8px; }}
 .t {{ color:#56607F; font-weight: 500; font-size: 13px; margin-left: 6px; }}
 .muted {{ color:#56607F; font-size: 12px; }}
 .inc {{ border:1px solid #D5DBEE; border-radius: 10px; padding: 14px; margin: 0 0 14px; page-break-inside: avoid; }}
 .grid {{ display:grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
 img {{ width:100%; border-radius: 6px; }}
 table {{ border-collapse: collapse; width:100%; font-size: 13px; margin-bottom: 16px; }}
 th, td {{ text-align:left; padding: 6px; border-bottom: 1px solid #E5E9F5; }} th {{ color:#56607F; width: 45%; }}
 p {{ font-size: 13.5px; margin: 8px 0 0; }}
</style></head><body>
<header><h1>{esc(product)} exam monitoring report</h1>
<div class="muted">{esc(site)} · {esc((sess.get('zone') or 'Room').replace('_', ' '))} · {start.strftime('%d %B %Y, %H:%M')}
{('to ' + end.strftime('%H:%M')) if end else '(in progress)'} · {dur} · {'patrolling' if sess.get('mode') == 'patrol' else 'from one place'}</div></header>
<table><tr><th>Incidents</th><td><b>{len(incs)}</b></td></tr>{summary_rows}
<tr><th>Checks used</th><td>{esc(checks)}</td></tr><tr><th>Camera analysis</th><td>{esc(VISION_NAMES.get(sess.get('vision'), 'sound only'))}</td></tr>
<tr><th>Room views checked</th><td>{esc(sess.get('views'))}</td></tr><tr><th>Ended</th><td>{esc(sess.get('stop_reason'))}</td></tr></table>
{''.join(cards)}
<p class="muted">The robot does not identify students. Photos show what triggered each flag so the invigilator can decide what to do.</p>
</body></html>"""

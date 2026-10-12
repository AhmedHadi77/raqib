"""SQLite storage for reports, chat history and the audit log (who did what, when)."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

from .schemas import InspectionReport


class Store:
    def __init__(self, data_dir: str):
        self.path = Path(data_dir) / "app.db"
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, created REAL, robot_id TEXT,
                    request TEXT, zones TEXT, compliant INTEGER, json TEXT);
                CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, user TEXT,
                    action TEXT, detail TEXT);
                CREATE TABLE IF NOT EXISTS chat(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, user TEXT,
                    message TEXT, reply TEXT, report_id TEXT);
                CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, pw TEXT, role TEXT, name TEXT,
                    created REAL, disabled INTEGER DEFAULT 0, last_login REAL);
                CREATE TABLE IF NOT EXISTS schedules(id TEXT PRIMARY KEY, name TEXT, command TEXT, time TEXT,
                    days TEXT, enabled INTEGER, robot_id TEXT, created_by TEXT, created REAL, last_run REAL,
                    last_status TEXT, last_report TEXT, last_key TEXT);
                CREATE TABLE IF NOT EXISTS exam_sessions(id TEXT PRIMARY KEY, started REAL, ended REAL, zone TEXT,
                    incidents INTEGER, json TEXT);
                """
            )
            self.db.commit()

    def save_report(self, r: InspectionReport):
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO reports VALUES (?,?,?,?,?,?,?)",
                (r.id, r.created, r.robot_id, r.request, ",".join(z.zone for z in r.zones),
                 int(all(z.compliant for z in r.zones)), r.model_dump_json()),
            )
            self.db.commit()

    def list_reports(self, limit: int = 50, offset: int = 0, zone: str | None = None) -> list[dict]:
        q, args = "SELECT id, created, robot_id, request, zones, compliant FROM reports", []
        if zone:
            q += " WHERE zones LIKE ?"
            args.append(f"%{zone}%")
        q += " ORDER BY created DESC LIMIT ? OFFSET ?"
        args += [limit, offset]
        with self.lock:
            rows = self.db.execute(q, args).fetchall()
        return [{**dict(r), "zones": r["zones"].split(",") if r["zones"] else [], "compliant": bool(r["compliant"])}
                for r in rows]

    def get_report(self, report_id: str) -> InspectionReport | None:
        with self.lock:
            row = self.db.execute("SELECT json FROM reports WHERE id=?", (report_id,)).fetchone()
        return InspectionReport.model_validate_json(row["json"]) if row else None

    def zone_status(self) -> dict[str, dict]:
        """Latest inspection result for each zone (for the map colours)."""
        with self.lock:
            rows = self.db.execute("SELECT id, created, json FROM reports ORDER BY created DESC LIMIT 200").fetchall()
        out: dict[str, dict] = {}
        for r in rows:
            rep = InspectionReport.model_validate_json(r["json"])
            for z in rep.zones:
                if z.zone in out:
                    continue
                worst = "ok"
                sev = {a.severity for a in z.anomalies}
                if "critical" in sev or "high" in sev:
                    worst = "alert"
                elif sev:
                    worst = "warn"
                out[z.zone] = {"report_id": rep.id, "ts": z.ts, "compliant": z.compliant, "issues": len(z.anomalies),
                               "level": worst, "comfort": z.comfort_verdict, "gas": z.gas_verdict,
                               "energy": z.energy_status, "safety": z.safety_status}
        return out

    def audit(self, user: str | None, action: str, detail: dict | str | None = None):
        with self.lock:
            self.db.execute("INSERT INTO audit(ts,user,action,detail) VALUES (?,?,?,?)",
                            (time.time(), user, action, json.dumps(detail, default=str) if detail else None))
            self.db.commit()

    def list_audit(self, limit: int = 200) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))]

    def save_chat(self, user: str, message: str, reply: str, report_id: str | None):
        with self.lock:
            self.db.execute("INSERT INTO chat(ts,user,message,reply,report_id) VALUES (?,?,?,?,?)",
                            (time.time(), user, message, reply, report_id))
            self.db.commit()

    def list_chat(self, user: str, limit: int = 50) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT * FROM chat WHERE user=? ORDER BY id DESC LIMIT ?", (user, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]


    # ================================================================== users
    @staticmethod
    def hash_password(password: str, salt: bytes | None = None) -> str:
        salt = salt or os.urandom(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
        return f"pbkdf2${salt.hex()}${dk.hex()}"

    @staticmethod
    def check_password(password: str, stored: str) -> bool:
        try:
            _, salt, digest = stored.split("$")
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
            return hmac.compare_digest(dk.hex(), digest)
        except ValueError:
            return False

    def seed_users(self, table: dict[str, tuple[str, str]]):
        """First start only: create the accounts listed in USERS= (.env). Afterwards manage them in the app."""
        with self.lock:
            if self.db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
                return
        for name, (pw, role) in table.items():
            self.create_user(name, pw, role, name.capitalize())

    def create_user(self, username: str, password: str, role: str, name: str | None = None):
        with self.lock:
            self.db.execute("INSERT INTO users(username,pw,role,name,created) VALUES (?,?,?,?,?)",
                            (username, self.hash_password(password), role, name or username, time.time()))
            self.db.commit()

    def get_user(self, username: str) -> dict | None:
        with self.lock:
            r = self.db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return dict(r) if r else None

    def list_users(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT username, role, name, created, disabled, last_login FROM users "
                                   "ORDER BY created").fetchall()
        return [{**dict(r), "disabled": bool(r["disabled"])} for r in rows]

    def update_user(self, username: str, **fields):
        sets, args = [], []
        for k, v in fields.items():
            if v is None:
                continue
            if k == "password":
                k, v = "pw", self.hash_password(v)
            if k == "disabled":
                v = int(bool(v))
            sets.append(f"{k}=?")
            args.append(v)
        if not sets:
            return
        with self.lock:
            self.db.execute(f"UPDATE users SET {', '.join(sets)} WHERE username=?", (*args, username))  # noqa: S608
            self.db.commit()

    def delete_user(self, username: str):
        with self.lock:
            self.db.execute("DELETE FROM users WHERE username=?", (username,))
            self.db.commit()

    def count_admins(self) -> int:
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND disabled=0").fetchone()[0]

    # ================================================================== schedules
    def list_schedules(self) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT * FROM schedules ORDER BY time").fetchall()
        return [{**dict(r), "enabled": bool(r["enabled"]), "days": [int(c) for c in r["days"]]} for r in rows]

    def get_schedule(self, sid: str) -> dict | None:
        return next((s for s in self.list_schedules() if s["id"] == sid), None)

    def save_schedule(self, data: dict, user: str) -> dict:
        sid = data.get("id") or uuid.uuid4().hex[:10]
        days = "".join(str(int(d)) for d in sorted(set(data.get("days") or range(7))))
        with self.lock:
            exists = self.db.execute("SELECT 1 FROM schedules WHERE id=?", (sid,)).fetchone()
            if exists:
                self.db.execute("UPDATE schedules SET name=?, command=?, time=?, days=?, enabled=?, robot_id=? WHERE id=?",
                                (data["name"], data["command"], data["time"], days, int(data.get("enabled", True)),
                                 data.get("robot_id"), sid))
            else:
                self.db.execute("INSERT INTO schedules(id,name,command,time,days,enabled,robot_id,created_by,created) "
                                "VALUES (?,?,?,?,?,?,?,?,?)",
                                (sid, data["name"], data["command"], data["time"], days,
                                 int(data.get("enabled", True)), data.get("robot_id"), user, time.time()))
            self.db.commit()
        return self.get_schedule(sid)

    def set_schedule_enabled(self, sid: str, enabled: bool):
        with self.lock:
            self.db.execute("UPDATE schedules SET enabled=? WHERE id=?", (int(enabled), sid))
            self.db.commit()

    def delete_schedule(self, sid: str):
        with self.lock:
            self.db.execute("DELETE FROM schedules WHERE id=?", (sid,))
            self.db.commit()

    def mark_schedule(self, sid: str, key: str | None = None, status: str | None = None, report: str | None = None):
        with self.lock:
            if key is not None:
                self.db.execute("UPDATE schedules SET last_key=?, last_run=?, last_status='running' WHERE id=?",
                                (key, time.time(), sid))
            if status is not None:
                self.db.execute("UPDATE schedules SET last_status=?, last_report=? WHERE id=?", (status, report, sid))
            self.db.commit()

    # ------------------------------------------------------------------ exam monitoring sessions
    def save_exam_session(self, session: dict):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO exam_sessions VALUES (?,?,?,?,?,?)",
                            (session["id"], session.get("started"), session.get("ended"), session.get("zone"),
                             len(session.get("incidents", [])), json.dumps(session, default=str)))
            self.db.commit()

    def list_exam_sessions(self, limit: int = 30) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT json FROM exam_sessions ORDER BY started DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = json.loads(r["json"])
            d["incident_count"] = len(d.get("incidents", []))
            d.pop("incidents", None)
            out.append(d)
        return out

    def get_exam_session(self, sid: str) -> dict | None:
        with self.lock:
            r = self.db.execute("SELECT json FROM exam_sessions WHERE id=?", (sid,)).fetchone()
        return json.loads(r["json"]) if r else None

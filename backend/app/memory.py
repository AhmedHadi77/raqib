"""Semantic memory: inspection records embedded with all-MiniLM-L6-v2 and stored in ChromaDB.

Embedding backends (EMBEDDING_BACKEND):
  sentence-transformers  - the proposal's model via the sentence-transformers package (needs torch)
  chroma-default         - the SAME all-MiniLM-L6-v2 model run through ONNX by Chroma (no torch, ~80 MB download)
  hash                   - offline feature-hashing fallback (no download; lower quality, for tests)
  auto                   - first one that works, in that order
"""
from __future__ import annotations

import hashlib
import logging
import math
import random
import re
import threading
import time
from datetime import datetime

from .config import Settings
from .schemas import ZoneInspection

log = logging.getLogger(__name__)
COLLECTION = "inspections"


class HashEmbedding:
    """Deterministic bag-of-words + bigram feature hashing (384-d, L2 normalised)."""

    DIM = 384

    def __init__(self):
        pass

    @staticmethod
    def name() -> str:
        return "hash-embedding-384"

    def _vec(self, text: str) -> list[float]:
        words = re.findall(r"[a-z0-9]+", text.lower())
        feats = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
        v = [0.0] * self.DIM
        for f in feats:
            h = int(hashlib.md5(f.encode()).hexdigest(), 16)
            v[h % self.DIM] += 1.0 if (h >> 9) & 1 else -1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    def __call__(self, input):  # noqa: A002 - chroma protocol
        return [self._vec(t) for t in input]

    def embed_documents(self, texts):
        return self(texts)

    def embed_query(self, input):  # noqa: A002
        return self(input if isinstance(input, list) else [input])


def _make_embedding(s: Settings):
    wanted = s.embedding_backend.lower()
    order = ["sentence-transformers", "chroma-default", "hash"] if wanted == "auto" else [wanted]
    for b in order:
        try:
            if b == "sentence-transformers":
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(s.embedding_model)

                def ef(texts, _m=_model):
                    return [list(map(float, v)) for v in _m.encode(list(texts), normalize_embeddings=True)]
            elif b == "chroma-default":
                from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

                ef = DefaultEmbeddingFunction()
            else:
                ef = HashEmbedding()
            ef(["warm-up"])  # forces model download / import errors now
            log.info("Embedding backend: %s", b)
            return b, ef
        except Exception as e:  # noqa: BLE001
            log.warning("Embedding backend %s unavailable: %s", b, str(e)[:160])
    raise RuntimeError("no embedding backend available")


TIME_PATTERNS = [
    (r"\btoday\b", 1), (r"\byesterday\b", 2), (r"\b(last|past|this) week\b", 7),
    (r"\b(last|past|this) month\b", 31), (r"\b(this|last|past) semester\b", 140),
    (r"\b(last|past) (\d+) days?\b", None), (r"\b(this|last|past) year\b", 366),
]


def infer_filters(query: str, zones: list[str]) -> dict:
    """Natural-language query -> metadata filters (zone, time window, verdicts)."""
    q = query.lower()
    out: dict = {}
    norm = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())  # noqa: E731
    qn = norm(q)
    for z in zones:
        if norm(z) and norm(z) in qn:
            out["zone"] = z
    for pat, days in TIME_PATTERNS:
        m = re.search(pat, q)
        if m:
            out["days"] = int(m.group(2)) if days is None else days
            break
    bad = re.search(r"unhealthy|poor|bad|exceed|high|hazard|warning|fume|smell|stale", q)
    if re.search(r"air quality|gas|fume|voc|smoke|aqi", q) and bad:
        out["gas_verdict"] = ["WARNING", "HAZARD"]
    if re.search(r"humid|hot|uncomfortable|stuffy|cold|over-?cooled|temperature", q) and \
            re.search(r"humid|hot|uncomfortable|stuffy|cold|over-?cooled|too|more|often", q):
        out["uncomfortable"] = True
    if re.search(r"light|projector|energy|wast|left on|monitor", q):
        out["energy_status"] = "WASTE"
    if re.search(r"exit|block|obstruct|hazard|unsafe|safety", q) and "air" not in q:
        out["safety_status"] = "HAZARD"
    return out


def _match(meta: dict, where: dict | None) -> bool:
    """Evaluate the subset of Chroma's `where` syntax used in this project."""
    if not where:
        return True
    if "$and" in where:
        return all(_match(meta, w) for w in where["$and"])
    for key, cond in where.items():
        v = meta.get(key)
        if isinstance(cond, dict):
            for op, arg in cond.items():
                if op == "$gte" and not (v is not None and v >= arg):
                    return False
                if op == "$lte" and not (v is not None and v <= arg):
                    return False
                if op == "$in" and v not in arg:
                    return False
                if op == "$ne" and v == arg:
                    return False
        elif v != cond:
            return False
    return True


class LiteCollection:
    """Minimal ChromaDB-compatible collection (SQLite + brute-force cosine).

    Used automatically when the chromadb package is not installed, so semantic
    search still works on a slow connection; install backend/requirements-ai.txt
    to switch to ChromaDB (same API, same data model).
    """

    def __init__(self, path: str):
        import json
        import sqlite3

        self._json = json
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS docs(id TEXT PRIMARY KEY, doc TEXT, meta TEXT, emb TEXT)")
        self.db.commit()

    def upsert(self, ids, documents, metadatas, embeddings):
        for i, d, m, e in zip(ids, documents, metadatas, embeddings):
            self.db.execute("INSERT OR REPLACE INTO docs VALUES (?,?,?,?)",
                            (i, d, self._json.dumps(m), self._json.dumps([float(x) for x in e])))
        self.db.commit()

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM docs").fetchone()[0]

    def _rows(self):
        for i, d, m, e in self.db.execute("SELECT id, doc, meta, emb FROM docs"):
            yield i, d, self._json.loads(m), self._json.loads(e)

    def get(self, include=None, limit: int = 2000):
        rows = list(self._rows())[:limit]
        return {"ids": [r[0] for r in rows], "documents": [r[1] for r in rows], "metadatas": [r[2] for r in rows]}

    def query(self, query_embeddings, n_results: int = 5, where=None, include=None):
        q = query_embeddings[0]
        qn = math.sqrt(sum(x * x for x in q)) or 1.0
        scored = []
        for i, d, m, e in self._rows():
            if not _match(m, where):
                continue
            en = math.sqrt(sum(x * x for x in e)) or 1.0
            sim = sum(a * b for a, b in zip(q, e)) / (qn * en)
            scored.append((1 - sim, i, d, m))
        scored.sort(key=lambda t: t[0])
        top = scored[:n_results]
        return {"ids": [[t[1] for t in top]], "documents": [[t[2] for t in top]],
                "metadatas": [[t[3] for t in top]], "distances": [[t[0] for t in top]]}


class SemanticMemory:
    def __init__(self, s: Settings):
        self.s = s
        self.lock = threading.Lock()
        self.backend, self.ef = _make_embedding(s)
        try:
            import chromadb
        except ImportError:
            log.warning("chromadb not installed -> using the built-in lite vector store "
                        "(pip install -r requirements-ai.txt for ChromaDB)")
            self.store = "lite"
            self.col = LiteCollection(f"{s.data_dir}/memory_lite.db")
            return
        self.store = "chromadb"
        if s.chroma_mode == "http":
            self.client = chromadb.HttpClient(host=s.chroma_host, port=s.chroma_port)
        else:
            self.client = chromadb.PersistentClient(path=f"{s.data_dir}/chroma")
        name = COLLECTION if self.backend != "hash" else COLLECTION + "_hash"
        self.col = self.client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})

    # ------------------------------------------------------------------ write
    def add_inspection(self, z: ZoneInspection, report_id: str | None = None, robot_id: str = "", seeded=False):
        e = z.environment or {}
        v = z.vision
        meta = {
            "zone": z.zone,
            "ts": float(z.ts),
            "date": datetime.fromtimestamp(z.ts).strftime("%Y-%m-%d"),
            "report_id": report_id or "",
            "robot_id": robot_id,
            "temperature_c": float(e.get("temperature_c") or -1),
            "humidity_pct": float(e.get("humidity_pct") or -1),
            "aqi": float(e.get("aqi") or -1),
            "comfort_verdict": z.comfort_verdict or "unknown",
            "gas_verdict": z.gas_verdict or "unknown",
            "uncomfortable": bool(z.comfort_verdict and z.comfort_verdict != "COMFORTABLE"),
            "energy_status": z.energy_status,
            "safety_status": z.safety_status,
            "compliant": z.compliant,
            "occupants": int(v.occupants) if v else -1,
            "audio": (z.audio or {}).get("label", "unknown"),
            "image_file": z.image_file or "",
            "seeded": seeded,
        }
        with self.lock:
            self.col.upsert(ids=[z.id], documents=[z.summary], metadatas=[meta],
                            embeddings=self.ef([z.summary]))

    # ------------------------------------------------------------------ read
    def count(self) -> int:
        return self.col.count()

    def zones(self) -> list[str]:
        res = self.col.get(include=["metadatas"], limit=2000)
        return sorted({m["zone"] for m in res["metadatas"]})

    def search(self, query: str, k: int = 5, zone: str | None = None, days: int | None = None,
               smart: bool = True, extra_zones: list[str] | None = None) -> dict:
        t0 = time.perf_counter()
        filters = infer_filters(query, list(set(self.zones()) | set(extra_zones or []))) if smart else {}
        if zone:
            filters["zone"] = zone
        if days:
            filters["days"] = days
        conds = []
        if "zone" in filters:
            conds.append({"zone": filters["zone"]})
        if "days" in filters:
            conds.append({"ts": {"$gte": time.time() - filters["days"] * 86400}})
        semantic = []
        if "gas_verdict" in filters:
            semantic.append({"gas_verdict": {"$in": filters["gas_verdict"]}})
        if filters.get("uncomfortable"):
            semantic.append({"uncomfortable": True})
        if "energy_status" in filters:
            semantic.append({"energy_status": filters["energy_status"]})
        if "safety_status" in filters:
            semantic.append({"safety_status": filters["safety_status"]})

        def where_of(cs):
            return None if not cs else (cs[0] if len(cs) == 1 else {"$and": cs})

        n = max(1, self.count())
        attempts = [conds + semantic, conds] if semantic else [conds]
        hits, used = [], {}
        for cs in attempts:
            with self.lock:
                res = self.col.query(query_embeddings=self.ef([query]), n_results=min(k, n),
                                     where=where_of(cs), include=["documents", "metadatas", "distances"])
            hits = [{"id": i, "text": d, "metadata": m, "score": round(1 - dist, 3)}
                    for i, d, m, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])]
            used = cs
            if hits:
                break
        return {"query": query, "filters": filters, "where": where_of(used), "results": hits,
                "embedding": f"{self.store}/{self.backend}", "took_ms": round((time.perf_counter() - t0) * 1000, 1)}

    # ------------------------------------------------------------------ seed
    def seed(self, n: int = 60, zones: list[str] | None = None, gas: bool = True) -> int:
        """Fake history so search can be tested before real inspections exist (marked seeded=True).
        gas=False: the robot has no gas sensor, so the records carry no air-quality reading."""
        from .report import fuse
        from .schemas import VisionAnalysis

        zones = zones or ["IoT_Lab", "LectureHall_A", "LectureHall_B", "Electronics_Lab"]
        rng = random.Random(42)
        now = time.time()
        for i in range(n):
            zone = rng.choice(zones)
            t = now - rng.uniform(0, 120) * 86400
            hot = rng.random() < 0.3
            cold = not hot and rng.random() < 0.15
            fumes = "Lab" in zone and rng.random() < 0.35
            temp = rng.uniform(27, 31) if hot else rng.uniform(17, 19.5) if cold else rng.uniform(22.5, 25.5)
            rh = rng.uniform(65, 80) if hot else rng.uniform(42, 58)
            aqi = rng.uniform(155, 240) if fumes else rng.uniform(20, 90)
            verdict = "WARNING" if fumes else "NORMAL"
            occ = 0 if rng.random() < 0.7 else rng.randint(3, 40)
            v = VisionAnalysis(occupants=occ, lights_on=rng.random() < 0.5, projector_on=rng.random() < 0.25,
                               exit_clear=rng.random() > 0.15, extinguisher_present=rng.random() > 0.1,
                               hazardous_items=["soldering iron left on"] if fumes and rng.random() < 0.5 else [],
                               description="seeded record", confidence=0.9, provider="seed")
            if gas:
                env = {"temperature_c": round(temp, 1), "humidity_pct": round(rh), "aqi": round(aqi),
                       "aqi_label": "Unhealthy" if fumes else "Good", "gas_verdict": verdict}
            else:
                env = {"temperature_c": round(temp, 1), "humidity_pct": round(rh), "aqi": None,
                       "aqi_label": "Unknown", "gas_verdict": "NOT_MEASURED"}
            audio = {"label": "ac_fan" if (hot or cold) and rng.random() < 0.7 else "quiet_room",
                     "title": "", "db": round(rng.uniform(40, 70), 1)}
            z = fuse(zone, v, env, audio)
            z.ts = t
            from .report import zone_text

            z.summary = zone_text(z)
            z.id = f"seed-{i:04d}"
            self.add_inspection(z, seeded=True)
        return n

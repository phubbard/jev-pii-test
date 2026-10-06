"""Thin wrapper around the TypeSafe async SDK: concurrency cap, on-disk response cache,
usage/cost accounting and a deterministic mock mode for running without an API key."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, RetryPolicy, Score, TypeSafeError

log = logging.getLogger("jev_pii")

PRICE_USD_PER_MTOK = 0.042  # jev-1.13 input price; output tokens are free
STATE_TOKEN_BUDGET = 32_000  # state + longest question
REQUEST_TOKEN_BUDGET = 64_000  # state + all questions

Question = Noul | Choice | Score


@dataclass
class Usage:
    requests: int = 0
    cached: int = 0
    errors: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    wall_s: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)
    mock: bool = False

    @property
    def cost_usd(self) -> float:
        return self.input_tokens * PRICE_USD_PER_MTOK / 1_000_000

    def summary(self) -> dict:
        lat = sorted(self.latencies_ms)
        p = lambda q: round(lat[min(len(lat) - 1, int(q * len(lat)))], 1) if lat else None
        return {
            "mock": self.mock,
            "requests_sent": self.requests,
            "cache_hits": self.cached,
            "errors": self.errors,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 4),
            "wall_seconds": round(self.wall_s, 2),
            "latency_ms_p50": p(0.5),
            "latency_ms_p95": p(0.95),
        }


def _dump_q(q: Question) -> dict:
    return q.model_dump(exclude_none=True)


def estimate_tokens(obj: Any) -> int:
    """Rough token estimate (chars/4) used only for budget warnings and mock usage."""
    return max(1, len(json.dumps(obj, ensure_ascii=False)) // 4)


class JevClient:
    def __init__(
        self,
        *,
        model: str = "jev-latest",
        concurrency: int = 16,
        cache_path: Path | None = None,
        mock: bool = False,
        timeout: float = 60.0,
    ) -> None:
        self.model = model
        has_key = bool(os.environ.get("TYPESAFE_API_KEY"))
        self.mock = mock or not has_key
        self.mock_reason = "requested" if mock else ("no TYPESAFE_API_KEY in environment" if not has_key else None)
        self.usage = Usage(mock=self.mock)
        self._sem = asyncio.Semaphore(concurrency)
        self._db: sqlite3.Connection | None = None
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(cache_path)
            self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, response TEXT NOT NULL)")
            self._db.commit()
        self._client: AsyncTypeSafeClient | None = None
        if not self.mock:
            self._client = AsyncTypeSafeClient(
                model=model,
                timeout=timeout,
                retry=RetryPolicy(max_retries=6, backoff_initial=0.5, backoff_max=15.0, timeout=timeout),
            )

    async def __aenter__(self) -> "JevClient":
        if self._client is not None:
            await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.__aexit__(*exc)
        if self._db is not None:
            self._db.commit()
            self._db.close()

    # ---- cache ------------------------------------------------------------------
    def _key(self, payload: dict) -> str:
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def _cache_get(self, key: str) -> dict | None:
        if self._db is None:
            return None
        row = self._db.execute("SELECT response FROM cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def _cache_put(self, key: str, resp: dict) -> None:
        if self._db is None:
            return
        self._db.execute("INSERT OR REPLACE INTO cache (key, response) VALUES (?, ?)", (key, json.dumps(resp)))
        self._db.commit()

    # ---- the one call -----------------------------------------------------------
    async def ask(self, state: Any, questions: dict[str, Question]) -> dict | None:
        """Evaluate ``questions`` against ``state``. Returns a plain dict
        {"model", "answers": {id: answer-dict}, "usage": {...}, "cached": bool} or None on error."""
        payload = {"model": self.model, "state": state, "questions": {k: _dump_q(q) for k, q in questions.items()}}
        if self.mock:
            payload["mock"] = True  # keep mock answers out of the live cache
        est_state = estimate_tokens(state)
        if est_state > STATE_TOKEN_BUDGET * 0.9:
            log.warning("state is ~%d tokens, near the %d budget", est_state, STATE_TOKEN_BUDGET)
        key = self._key(payload)
        hit = self._cache_get(key)
        if hit is not None:
            self.usage.cached += 1
            hit["cached"] = True
            return hit
        async with self._sem:
            t0 = time.perf_counter()
            if self.mock:
                resp = self._mock(payload, key)
            else:
                assert self._client is not None
                try:
                    r = await self._client.system_one(state, questions)
                except TypeSafeError as e:
                    self.usage.errors += 1
                    log.error("TypeSafe error: %s", e)
                    return None
                resp = {
                    "model": r.model,
                    "answers": {k: a.model_dump() for k, a in r.answers.items()},
                    "usage": r.usage.model_dump(),
                }
            dt_ms = (time.perf_counter() - t0) * 1000
        self.usage.requests += 1
        self.usage.latencies_ms.append(dt_ms)
        self.usage.input_tokens += resp["usage"].get("input_tokens") or 0
        self.usage.output_tokens += resp["usage"].get("output_tokens") or 0
        self._cache_put(key, resp)
        resp["cached"] = False
        return resp

    def _mock(self, payload: dict, key: str) -> dict:
        """Deterministic random answers so the whole pipeline can be exercised offline.
        Numbers from a mock run are meaningless; the report flags them."""
        rng = random.Random(key)
        answers: dict[str, dict] = {}
        for qid, q in payload["questions"].items():
            if q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": round(rng.random(), 4)}
            elif q["type"] == "choice":
                opts = list(q["criteria"])
                raw = [rng.random() ** 3 for _ in opts]
                s = sum(raw)
                probs = {o: round(v / s, 4) for o, v in zip(opts, raw)}
                best = max(probs, key=probs.get)
                answers[qid] = {"type": "choice", "choice": best, "probabilities": probs, "confidence": round(probs[best], 4)}
            else:
                n = len(q["criteria"])
                raw = [rng.random() for _ in range(n)]
                s = sum(raw)
                probs = {str(i): round(v / s, 4) for i, v in enumerate(raw)}
                answers[qid] = {
                    "type": "score",
                    "score": round(sum(i * p for i, p in enumerate(raw)) / s, 4),
                    "probabilities": probs,
                    "legend": {str(i): c for i, c in enumerate(q["criteria"])},
                    "confidence": round(max(raw) / s, 4),
                }
        return {
            "model": "mock",
            "answers": answers,
            "usage": {"input_tokens": estimate_tokens(payload["state"]) + estimate_tokens(payload["questions"]), "output_tokens": 0},
        }

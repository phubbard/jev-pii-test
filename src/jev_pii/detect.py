"""Detection strategies. Each turns records or tables into Jev requests and returns
plain prediction dicts that evaluate.py scores against ground truth.

* record  — one request per record (or per batch of records), one Noul per PII category:
            "does this text contain X?". Record-level detection.
* span    — regex over-finds candidate spans, one Noul per candidate asks Jev whether the
            candidate really is that kind of PII in context. Span-level detection; Jev is
            the precision layer and the regex sets the recall ceiling.
* column  — tables: sample values per column, one Choice per column over the PII
            categories plus NONE. Column-level classification for bulk tabular data.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from typesafe_sdk import Choice, Noul, NoulCriteria

from jev_pii.candidates import Candidate, find_candidates
from jev_pii.client import JevClient
from jev_pii.taxonomy import CATEGORIES, LABELS, NONE_LABEL

log = logging.getLogger("jev_pii")

MAX_QUESTIONS_PER_REQUEST = 48


# ---- question builders -------------------------------------------------------------
def contains_noul(label: str, path: str) -> Noul:
    c = CATEGORIES[label]
    return Noul(
        instructions={
            "question": f"Does the text at `{path}` contain {c.noun}?",
            "focus": "Judge only what is literally written in that text.",
        },
        criteria=NoulCriteria(
            true={"what": f"The text includes {c.noun}. {c.definition}", "examples": list(c.examples_yes)},
            false={"what": f"No such item is present, or the only similar items are: {c.excludes}", "examples": list(c.examples_no)},
        ),
    )


def any_pii_noul(path: str) -> Noul:
    nouns = ", ".join(c.noun for c in CATEGORIES.values())
    return Noul(
        instructions={
            "question": f"Does the text at `{path}` contain personal data that identifies a specific individual?",
            "personal_data_means": nouns,
        },
        criteria=NoulCriteria(
            true="At least one item of personal data about a specific individual is present.",
            false="Only business identifiers, company details, product data, generic dates, version strings or non-personal content.",
        ),
    )


def candidate_noul(label: str, idx: int) -> Noul:
    c = CATEGORIES[label]
    return Noul(
        instructions={
            "question": f"In `text`, is the value `candidates[{idx}].value` {c.noun}?",
            "focus": "Judge this exact value in the context where it appears in `text`.",
        },
        criteria=NoulCriteria(
            true={"what": c.definition, "examples": list(c.examples_yes)},
            false={"what": c.excludes, "examples": list(c.examples_no)},
        ),
    )


def column_choice(idx: int) -> Choice:
    criteria: dict[str, dict] = {
        label: {"what": c.definition, "examples": list(c.examples_yes)} for label, c in CATEGORIES.items()
    }
    criteria[NONE_LABEL] = {
        "what": (
            "Not personal data: order, case or tracking identifiers, company or product names, "
            "statuses, amounts, timestamps, appointment or other non-birth dates, version strings, "
            "role mailboxes, business phone lines, partial card digits."
        ),
        "examples": ["ORD-4821937", "shipped", "support@acme.com", "2026-03-04T10:00:00Z", "4242"],
    }
    return Choice(
        instructions={
            "question": f"What kind of personal data, if any, do the values in `columns[{idx}].values` contain?",
            "note": f"`columns[{idx}].name` is only a hint and may be meaningless; judge the values themselves.",
        },
        criteria=criteria,
    )


def _chunks(seq: Sequence, n: int):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


# ---- strategy: record ----------------------------------------------------------------
async def run_record(client: JevClient, records: list[dict], batch: int = 1) -> list[dict]:
    """Returns one dict per record: {id, format, gold_labels, probs{label:p}, any_pii}."""
    results: dict[str, dict] = {}

    async def one_batch(group: list[dict]) -> None:
        if len(group) == 1:
            state = {"text": group[0]["text"]}
            paths = ["text"]
        else:
            state = {"records": [r["text"] for r in group]}
            paths = [f"records[{i}]" for i in range(len(group))]
        questions: dict[str, Noul] = {}
        for i, path in enumerate(paths):
            for label in LABELS:
                questions[f"r{i}_{label}"] = contains_noul(label, path)
            questions[f"r{i}_ANY"] = any_pii_noul(path)
        resp = await client.ask(state, questions)
        for i, rec in enumerate(group):
            out = {"id": rec["id"], "format": rec["format"], "gold_labels": rec["labels"], "probs": {}, "any_pii": None, "ok": resp is not None}
            if resp is not None:
                for label in LABELS:
                    out["probs"][label] = resp["answers"][f"r{i}_{label}"]["noul"]
                out["any_pii"] = resp["answers"][f"r{i}_ANY"]["noul"]
            results[rec["id"]] = out

    await _gather_with_progress([one_batch(list(g)) for g in _chunks(records, max(1, batch))], "record")
    return [results[r["id"]] for r in records]


# ---- strategy: span ------------------------------------------------------------------
async def run_span(client: JevClient, records: list[dict]) -> list[dict]:
    """Returns one dict per record: {id, format, gold: spans, candidates: [{start,end,text,kind,p}]}."""
    results: dict[str, dict] = {}

    async def one(rec: dict) -> None:
        cands = find_candidates(rec["text"])
        out = {"id": rec["id"], "format": rec["format"], "gold": rec["spans"], "candidates": [], "ok": True}
        for chunk in _chunks(cands, MAX_QUESTIONS_PER_REQUEST):
            state = {"text": rec["text"], "candidates": [{"value": c.text} for c in chunk]}
            questions = {f"c{i}": candidate_noul(c.kind, i) for i, c in enumerate(chunk)}
            resp = await client.ask(state, questions) if questions else {"answers": {}}
            if resp is None:
                out["ok"] = False
                continue
            for i, c in enumerate(chunk):
                out["candidates"].append(
                    {"start": c.start, "end": c.end, "text": c.text, "kind": c.kind, "p": resp["answers"][f"c{i}"]["noul"]}
                )
        results[rec["id"]] = out

    await _gather_with_progress([one(r) for r in records], "span")
    return [results[r["id"]] for r in records]


# ---- strategy: column ----------------------------------------------------------------
async def run_column(client: JevClient, tables: list[dict], sample_values: int = 12) -> list[dict]:
    """Returns one dict per column: {table, column, obfuscated, gold, pred, confidence, probs}."""
    results: list[dict] = []

    async def one(table: dict) -> None:
        cols = table["columns"]
        rows = table["rows"]
        state = {
            "columns": [
                {"name": c["name"], "values": [row[j] for row in rows[:sample_values]]} for j, c in enumerate(cols)
            ]
        }
        questions = {f"col{j}": column_choice(j) for j in range(len(cols))}
        resp = await client.ask(state, questions)
        for j, c in enumerate(cols):
            out = {"table": table["name"], "column": c["name"], "kind": c["kind"], "obfuscated": table["obfuscated"], "gold": c["label"], "pred": None, "confidence": None, "probs": None, "ok": resp is not None}
            if resp is not None:
                a = resp["answers"][f"col{j}"]
                out.update(pred=a["choice"], confidence=a["confidence"], probs=a["probabilities"])
            results.append(out)

    await _gather_with_progress([one(t) for t in tables], "column")
    results.sort(key=lambda r: (r["table"], r["column"]))
    return results


async def _gather_with_progress(coros: list, name: str) -> None:
    total = len(coros)
    done = 0

    async def wrap(c):
        nonlocal done
        await c
        done += 1
        if done % 50 == 0 or done == total:
            log.info("%s: %d/%d requests done", name, done, total)

    await asyncio.gather(*(wrap(c) for c in coros))

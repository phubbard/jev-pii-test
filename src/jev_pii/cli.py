"""Command line: generate a corpus, run strategies against Jev, write a report."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import logging
import sys
import time
from pathlib import Path

from jev_pii import detect, evaluate
from jev_pii.client import JevClient
from jev_pii.generate import generate_records, generate_tables, load_records, load_tables, write_corpus

log = logging.getLogger("jev_pii")


def cmd_generate(a: argparse.Namespace) -> None:
    records = generate_records(a.records, a.seed)
    tables = generate_tables(a.tables, a.seed)
    write_corpus(a.out, records, tables)
    n_pii = sum(1 for r in records if r.spans)
    spans = sum(len(r.spans) for r in records)
    print(f"wrote {len(records)} records ({n_pii} with PII, {spans} spans) and {len(tables)} tables to {a.out}/")


async def _run(a: argparse.Namespace) -> None:
    records = load_records(a.data / "records.jsonl")
    tables = load_tables(a.data / "tables")
    if a.limit:
        records = records[: a.limit]
        tables = tables[: max(1, a.limit // 10)]
    strategies = ["record", "span", "column"] if a.strategy == "all" else [a.strategy]
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + "+".join(strategies)
    predictions: dict[str, list[dict]] = {}
    t0 = time.perf_counter()
    async with JevClient(model=a.model, concurrency=a.concurrency, cache_path=a.cache, mock=a.mock) as client:
        if client.mock:
            log.warning("MOCK MODE (%s): answers are random, numbers are meaningless", client.mock_reason)
            run_id += "-MOCK"
        if "record" in strategies:
            predictions["record"] = await detect.run_record(client, records, batch=a.batch)
        if "span" in strategies:
            predictions["span"] = await detect.run_span(client, records)
        if "column" in strategies:
            predictions["column"] = await detect.run_column(client, tables, sample_values=a.sample_values)
        client.usage.wall_s = time.perf_counter() - t0
        usage = client.usage.summary()
    summary = {
        "run_id": run_id,
        "model": a.model,
        "data_dir": str(a.data),
        "strategies": strategies,
        "n_records": len(records),
        "n_tables": len(tables),
        "batch": a.batch,
        "usage": usage,
    }
    if "record" in predictions:
        summary["record"] = evaluate.eval_record(predictions["record"], a.threshold)
    if "span" in predictions:
        summary["span"] = evaluate.eval_span(predictions["span"], a.threshold)
    if "column" in predictions:
        summary["column"] = evaluate.eval_column(predictions["column"])
    out_dir = a.out / run_id
    evaluate.write_outputs(out_dir, summary, predictions)
    print(evaluate.render_report(summary))
    print(f"wrote {out_dir}/summary.json, report.md and predictions_*.jsonl")


def cmd_run(a: argparse.Namespace) -> None:
    asyncio.run(_run(a))


def cmd_report(a: argparse.Namespace) -> None:
    import json

    summary = json.loads((a.run_dir / "summary.json").read_text())
    print(evaluate.render_report(summary))


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="jev-pii", description="POC: can Jev detect PII in bulk data?")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="write a synthetic labeled corpus")
    g.add_argument("--records", type=int, default=600)
    g.add_argument("--tables", type=int, default=30)
    g.add_argument("--seed", type=int, default=1)
    g.add_argument("--out", type=Path, default=Path("data"))
    g.set_defaults(func=cmd_generate)

    r = sub.add_parser("run", help="run detection strategies and write a report")
    r.add_argument("--data", type=Path, default=Path("data"))
    r.add_argument("--out", type=Path, default=Path("results"))
    r.add_argument("--cache", type=Path, default=Path(".cache/jev_responses.sqlite"))
    r.add_argument("--strategy", choices=["all", "record", "span", "column"], default="all")
    r.add_argument("--limit", type=int, default=0, help="only the first N records (and N/10 tables)")
    r.add_argument("--batch", type=int, default=1, help="records per request for the record strategy")
    r.add_argument("--sample-values", type=int, default=12, help="values per column sent for the column strategy")
    r.add_argument("--concurrency", type=int, default=16)
    r.add_argument("--threshold", type=float, default=0.5)
    r.add_argument("--model", default="jev-latest")
    r.add_argument("--mock", action="store_true", help="do not call the API; random answers")
    r.set_defaults(func=cmd_run)

    rp = sub.add_parser("report", help="re-render report.md from a run's summary.json")
    rp.add_argument("run_dir", type=Path)
    rp.set_defaults(func=cmd_report)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stderr)
    for noisy in ("httpx2", "typesafe_sdk", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    a.func(a)


if __name__ == "__main__":
    main()

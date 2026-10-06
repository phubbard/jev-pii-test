"""Score predictions against ground truth and render summary.json + report.md."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from jev_pii.candidates import find_candidates
from jev_pii.metrics import Counts, Span, calibration, match_spans, merge_counts, micro, sweep
from jev_pii.taxonomy import LABELS, NONE_LABEL


# ---- record -------------------------------------------------------------------------
def eval_record(preds: list[dict], threshold: float = 0.5) -> dict:
    preds = [p for p in preds if p["ok"]]
    per_label = {}
    for label in LABELS:
        scored = [(p["probs"][label], label in p["gold_labels"]) for p in preds]
        c = Counts()
        for s, g in scored:
            c.add(s >= threshold, g)
        per_label[label] = {"at_threshold": c.prf(), "sweep": sweep(scored)["best"], "calibration": calibration(scored)}
    any_scored = [(p["any_pii"], bool(p["gold_labels"])) for p in preds]
    c = Counts()
    for s, g in any_scored:
        c.add(s >= threshold, g)
    by_format: dict[str, Counts] = defaultdict(Counts)
    for p in preds:
        by_format[p["format"]].add(p["any_pii"] >= threshold, bool(p["gold_labels"]))
    # record-level "all labels right": every category decision correct
    exact = sum(all((p["probs"][l] >= threshold) == (l in p["gold_labels"]) for l in LABELS) for p in preds)
    return {
        "n_records": len(preds),
        "threshold": threshold,
        "per_label": per_label,
        "micro": micro({l: _counts_from(v["at_threshold"]) for l, v in per_label.items()}),
        "any_pii": {"at_threshold": c.prf(), "sweep": sweep(any_scored)["best"], "calibration": calibration(any_scored)},
        "any_pii_by_format": {k: v.prf() for k, v in sorted(by_format.items())},
        "records_fully_correct": exact,
        "records_fully_correct_frac": round(exact / len(preds), 4) if preds else None,
    }


def _counts_from(prf: dict) -> Counts:
    return Counts(tp=prf["tp"], fp=prf["fp"], fn=prf["fn"], tn=prf["tn"])


# ---- span ---------------------------------------------------------------------------
def eval_span(preds: list[dict], threshold: float = 0.5) -> dict:
    preds = [p for p in preds if p["ok"]]
    gold_all = []
    jev_parts, base_parts = [], []
    ceiling_hit = Counter()
    ceiling_total = Counter()
    scored_by_label: dict[str, list[tuple[float, bool]]] = defaultdict(list)
    by_format: dict[str, list[dict[str, Counts]]] = defaultdict(list)

    for p in preds:
        gold = [Span(s["start"], s["end"], s["label"]) for s in p["gold"]]
        cands = [Span(c["start"], c["end"], c["kind"]) for c in p["candidates"]]
        jev = [Span(c["start"], c["end"], c["kind"]) for c in p["candidates"] if c["p"] >= threshold]
        jev_parts.append(match_spans(jev, gold))
        base_parts.append(match_spans(cands, gold))
        by_format[p["format"]].append(jev_parts[-1])
        # recall ceiling: is each gold span covered by some same-label candidate?
        for g in gold:
            ceiling_total[g.label] += 1
            if any(c.label == g.label and c.overlap(g) >= 0.5 for c in cands):
                ceiling_hit[g.label] += 1
        # per-candidate truth for sweeps/calibration: candidate is "true" if it overlaps a same-label gold span
        for c in p["candidates"]:
            cs = Span(c["start"], c["end"], c["kind"])
            truth = any(g.label == cs.label and cs.overlap(g) >= 0.5 for g in gold)
            scored_by_label[c["kind"]].append((c["p"], truth))
        gold_all.extend(gold)

    jev_counts = merge_counts(jev_parts)
    base_counts = merge_counts(base_parts)
    per_label = {}
    for label in LABELS:
        sc = scored_by_label.get(label, [])
        per_label[label] = {
            "jev": jev_counts.get(label, Counts()).prf(),
            "regex_baseline": base_counts.get(label, Counts()).prf(),
            "recall_ceiling": round(ceiling_hit[label] / ceiling_total[label], 4) if ceiling_total[label] else None,
            "n_candidates": len(sc),
            "sweep": sweep(sc)["best"] if sc else None,
            "calibration": calibration(sc) if sc else None,
        }
    all_scored = [x for v in scored_by_label.values() for x in v]
    return {
        "n_records": len(preds),
        "n_gold_spans": len(gold_all),
        "n_candidates": len(all_scored),
        "threshold": threshold,
        "per_label": per_label,
        "micro_jev": micro(jev_counts),
        "micro_regex_baseline": micro(base_counts),
        "micro_recall_ceiling": round(sum(ceiling_hit.values()) / sum(ceiling_total.values()), 4) if ceiling_total else None,
        "micro_sweep": sweep(all_scored)["best"] if all_scored else None,
        "micro_calibration": calibration(all_scored) if all_scored else None,
        "by_format": {k: micro(merge_counts(v)) for k, v in sorted(by_format.items())},
    }


# ---- column -------------------------------------------------------------------------
def eval_column(preds: list[dict]) -> dict:
    preds = [p for p in preds if p["ok"]]
    labels = list(LABELS) + [NONE_LABEL]
    counts = {l: Counts() for l in labels}
    confusion: dict[str, Counter] = defaultdict(Counter)
    correct = 0
    by_obf = {True: [0, 0], False: [0, 0]}
    for p in preds:
        confusion[p["gold"]][p["pred"]] += 1
        ok = p["pred"] == p["gold"]
        correct += ok
        by_obf[p["obfuscated"]][0] += ok
        by_obf[p["obfuscated"]][1] += 1
        for l in labels:
            counts[l].add(p["pred"] == l, p["gold"] == l)
    # confidence-gated: accuracy among high-confidence predictions and coverage
    gated = {}
    for t in (0.5, 0.7, 0.9):
        sel = [p for p in preds if (p["confidence"] or 0) >= t]
        gated[str(t)] = {
            "coverage": round(len(sel) / len(preds), 4) if preds else None,
            "accuracy": round(sum(p["pred"] == p["gold"] for p in sel) / len(sel), 4) if sel else None,
        }
    return {
        "n_columns": len(preds),
        "accuracy": round(correct / len(preds), 4) if preds else None,
        "accuracy_obfuscated_headers": round(by_obf[True][0] / by_obf[True][1], 4) if by_obf[True][1] else None,
        "accuracy_named_headers": round(by_obf[False][0] / by_obf[False][1], 4) if by_obf[False][1] else None,
        "per_label": {l: counts[l].prf() for l in labels},
        "confidence_gated": gated,
        "confusion": {g: dict(c) for g, c in sorted(confusion.items())},
        "misses": [
            {"table": p["table"], "column": p["column"], "gold": p["gold"], "pred": p["pred"], "confidence": p["confidence"]}
            for p in preds
            if p["pred"] != p["gold"]
        ][:40],
    }


# ---- report -------------------------------------------------------------------------
def _pct(x) -> str:
    return "-" if x is None else f"{100 * x:.1f}%"


def _prf_row(name: str, d: dict) -> str:
    return f"| {name} | {d['support']} | {_pct(d['precision'])} | {_pct(d['recall'])} | {_pct(d['f1'])} | {d['fp']} | {d['fn']} |"


PRF_HEADER = "| label | support | precision | recall | F1 | FP | FN |\n|---|---|---|---|---|---|---|"


def render_report(summary: dict) -> str:
    out = []
    u = summary["usage"]
    out.append(f"# jev-pii run `{summary['run_id']}`\n")
    if u["mock"]:
        out.append("> **MOCK RUN.** No API key was present (or `--mock` was passed); answers are random. "
                   "Only the pipeline mechanics and cost estimate are meaningful here.\n")
    out.append(f"Model `{summary['model']}` · data `{summary['data_dir']}` · strategies: {', '.join(summary['strategies'])}\n")
    out.append("## Usage and cost\n")
    out.append("| requests | cache hits | errors | input tokens | est. cost (USD) | wall s | p50 ms | p95 ms |\n|---|---|---|---|---|---|---|---|")
    out.append(f"| {u['requests_sent']} | {u['cache_hits']} | {u['errors']} | {u['input_tokens']:,} | ${u['cost_usd']:.4f} | {u['wall_seconds']} | {u['latency_ms_p50']} | {u['latency_ms_p95']} |\n")
    if "record" in summary:
        r = summary["record"]
        out.append(f"## Strategy: record-level Nouls ({r['n_records']} records, threshold {r['threshold']})\n")
        out.append(PRF_HEADER)
        for l in LABELS:
            out.append(_prf_row(l, r["per_label"][l]["at_threshold"]))
        out.append(_prf_row("**micro**", r["micro"]))
        out.append(_prf_row("ANY_PII", r["any_pii"]["at_threshold"]))
        out.append("")
        out.append(f"Records with every category decided correctly: {r['records_fully_correct']} / {r['n_records']} ({_pct(r['records_fully_correct_frac'])})\n")
        out.append("Best threshold per label (F1-optimal on this data) and calibration error:\n")
        out.append("| label | best threshold | F1 at best | ECE |\n|---|---|---|---|")
        for l in LABELS:
            s = r["per_label"][l]["sweep"]
            out.append(f"| {l} | {s['threshold']} | {_pct(s['f1'])} | {r['per_label'][l]['calibration']['ece']} |")
        out.append("")
        out.append("ANY_PII by record format:\n")
        out.append(PRF_HEADER)
        for fmt, d in r["any_pii_by_format"].items():
            out.append(_prf_row(fmt, d))
        out.append("")
    if "span" in summary:
        s = summary["span"]
        out.append(f"## Strategy: candidate spans + Jev ({s['n_records']} records, {s['n_gold_spans']} gold spans, {s['n_candidates']} candidates, threshold {s['threshold']})\n")
        out.append("Jev as precision layer over recall-tuned regex candidates:\n")
        out.append(PRF_HEADER)
        for l in LABELS:
            out.append(_prf_row(l, s["per_label"][l]["jev"]))
        out.append(_prf_row("**micro**", s["micro_jev"]))
        out.append("")
        out.append("Regex-only baseline (every candidate accepted):\n")
        out.append(PRF_HEADER)
        for l in LABELS:
            out.append(_prf_row(l, s["per_label"][l]["regex_baseline"]))
        out.append(_prf_row("**micro**", s["micro_regex_baseline"]))
        out.append("")
        out.append("Recall ceiling (gold spans the regex found at all), best threshold, calibration:\n")
        out.append("| label | recall ceiling | candidates | best threshold | F1 at best | ECE |\n|---|---|---|---|---|---|")
        for l in LABELS:
            d = s["per_label"][l]
            sw = d["sweep"] or {}
            cal = d["calibration"] or {}
            out.append(f"| {l} | {_pct(d['recall_ceiling'])} | {d['n_candidates']} | {sw.get('threshold', '-')} | {_pct(sw.get('f1')) if sw else '-'} | {cal.get('ece', '-')} |")
        out.append(f"| **micro** | {_pct(s['micro_recall_ceiling'])} | {s['n_candidates']} | {s['micro_sweep']['threshold'] if s['micro_sweep'] else '-'} | {_pct(s['micro_sweep']['f1']) if s['micro_sweep'] else '-'} | {s['micro_calibration']['ece'] if s['micro_calibration'] else '-'} |")
        out.append("")
        out.append("By record format (Jev, micro):\n")
        out.append(PRF_HEADER)
        for fmt, d in s["by_format"].items():
            out.append(_prf_row(fmt, d))
        out.append("")
    if "column" in summary:
        c = summary["column"]
        out.append(f"## Strategy: column classification ({c['n_columns']} columns)\n")
        out.append(f"Accuracy: **{_pct(c['accuracy'])}** · named headers {_pct(c['accuracy_named_headers'])} · obfuscated headers {_pct(c['accuracy_obfuscated_headers'])}\n")
        out.append(PRF_HEADER)
        for l in list(LABELS) + [NONE_LABEL]:
            out.append(_prf_row(l, c["per_label"][l]))
        out.append("")
        out.append("Confidence gating (act only above a confidence floor):\n")
        out.append("| confidence ≥ | coverage | accuracy |\n|---|---|---|")
        for t, g in c["confidence_gated"].items():
            out.append(f"| {t} | {_pct(g['coverage'])} | {_pct(g['accuracy'])} |")
        out.append("")
        if c["misses"]:
            out.append("Misclassified columns (first 40):\n")
            out.append("| table | column | gold | predicted | confidence |\n|---|---|---|---|---|")
            for m in c["misses"]:
                out.append(f"| {m['table']} | {m['column']} | {m['gold']} | {m['pred']} | {m['confidence']} |")
            out.append("")
    return "\n".join(out) + "\n"


def write_outputs(out_dir: Path, summary: dict, predictions: dict[str, list[dict]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    (out_dir / "report.md").write_text(render_report(summary))
    for name, preds in predictions.items():
        with (out_dir / f"predictions_{name}.jsonl").open("w") as f:
            for p in preds:
                f.write(json.dumps(p) + "\n")

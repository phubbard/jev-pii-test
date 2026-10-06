# jev-pii

**Results of the live run are in [FINDINGS.md](FINDINGS.md).** Short version: micro-F1 96.5% (record), 98.9% (span), 95.4% column accuracy at one record per request; packing records into one request halves accuracy.

Proof of concept for one question: **can TypeSafe's Jev reliably detect PII in bulk data?**

Jev ([docs](https://docs.typesafe.ai/)) is a "System One" model. It does not generate text.
You send it `state` plus typed questions (yes/no *Noul*, one-of-N *Choice*, ordered *Score*)
and get back calibrated probabilities. That shapes how PII detection has to work: Jev
cannot extract spans, so code has to propose candidates or ask record-level questions and
let Jev judge. This POC measures three framings on a synthetic corpus with exact ground
truth.

## Strategies under test

| strategy | what Jev is asked | granularity | what it tells you |
|---|---|---|---|
| `record` | one Noul per PII category: "does this text contain a person's name / an SSN / ...?" plus an overall "any personal data?" | record | can Jev flag records for review or routing |
| `span` | regex over-finds candidate spans; one Noul per candidate: "in this text, is *this value* a personal phone number?" | span | can Jev be the precision layer over cheap high-recall patterns (this is the TypeSafe-recommended pattern for extraction) |
| `column` | sample values per column; one Choice over the PII categories plus NONE | column | can Jev classify columns in bulk tabular data, with and without meaningful headers |

Every request packs many questions (fan-out), which is how TypeSafe prices and tunes the
model. `--batch N` additionally packs N records into one `record`-strategy request so you
can measure the accuracy cost of larger state.

## PII taxonomy

Eight categories, each with a definition, exclusions and examples that are used both to
build the questions and to design the generator's hard negatives: PERSON_NAME, EMAIL,
PHONE, SSN, CREDIT_CARD, STREET_ADDRESS, DATE_OF_BIRTH, IP_ADDRESS. See
`src/jev_pii/taxonomy.py`. Hard negatives include company names, role mailboxes
(`support@`), 1-800 lines, SSN-shaped case numbers, "card ending in 4242", appointment
dates in DOB formats, and four-part version strings that look like IPs.

## Data

The corpus is synthetic (Faker), so it contains no real person's data and regenerates
from a seed at any size:

* `data/records.jsonl` — support tickets (50%), log lines (25%) and flat JSON records
  (25%) with character-offset spans. ~30% of records have no PII, only hard negatives.
* `data/tables/*.csv` + `*.schema.json` — tables whose columns are labeled with a category
  or NONE; 30% have obfuscated headers (`col_1`, ...).

The ai4privacy datasets were considered and rejected: their license is academic-only and
forbids redistribution and derivative works.

## Running it

```bash
uv sync
uv run jev-pii generate --records 600 --tables 30 --seed 1
export TYPESAFE_API_KEY=...        # from https://console.typesafe.ai/keys
uv run jev-pii run --strategy all
```

Without an API key the run falls back to **mock mode** (random answers) and the report
says so loudly; use it to check the pipeline, not the model. Responses are cached in
`.cache/jev_responses.sqlite`, so re-running with the same data and questions is free.

Useful flags for `run`: `--strategy record|span|column|all`, `--limit N` (first N records),
`--batch N` (records per request), `--sample-values K` (values per column), `--threshold`
(Noul decision threshold, default 0.5), `--concurrency` (default 16), `--model`
(default `jev-latest`; pin `jev-1.13.0` to freeze thresholds).

Outputs land in `results/<run-id>/`: `summary.json`, `report.md` and
`predictions_<strategy>.jsonl` for drilling into individual misses.

## What the report measures

* Precision / recall / F1 per category and micro-averaged, at the chosen threshold.
* The F1-optimal threshold per category, and expected calibration error (ECE), because
  Jev's pitch is calibrated probabilities and that is what makes thresholds portable.
* For `span`: the regex-only baseline (what Jev adds) and the recall ceiling (gold spans
  the regex found at all; Jev cannot recover what the candidate finder misses).
* For `column`: accuracy split by named vs obfuscated headers, and coverage/accuracy
  under confidence gating.
* Breakdown by record format, and usage: requests, input tokens, estimated cost at
  $0.042 per million input tokens, wall time, latency percentiles.

## Known limits of this POC

* Names have no regex. The `span` strategy proposes capitalised 2–3 word sequences, so
  its PERSON_NAME recall ceiling is bounded by that heuristic and company names flood the
  candidates. Production would use an NER model for name candidates.
* English only. Jev's own docs say other languages are weaker.
* Jev 1.13 reads literally, is order-sensitive for Choice options and loses accuracy as
  state grows ([jaggedness notes](https://docs.typesafe.ai/model-jaggedness/jev-1.13)).
  The `--batch` knob exists to measure the last point.
* Synthetic data is cleaner than real data. Treat results as an upper bound and re-run
  on a sample of the real bulk data once the pipeline shape is settled.

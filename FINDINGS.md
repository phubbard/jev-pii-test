# Findings: can Jev detect PII in bulk data?

Live run on 2026-10-06 against `jev-latest` (= `jev-1.13.0`), 600 synthetic records
(1,048 PII spans, 8 categories, 30% records with no PII) and 30 tables (175 columns).
Full reports with per-label tables are in `docs/runs/`.

**Short answer: yes, when each request carries one record.** Micro-F1 at the default 0.5
threshold was 96.5% for record-level flagging, 98.9% for span detection over regex
candidates, and 95.4% column-classification accuracy. The entire run cost $0.09 and
10.5 seconds of wall time at concurrency 16 (p50 latency 122 ms, p95 210 ms, zero errors
or rate-limit hits).

## Headline numbers (one record per request, threshold 0.5)

| strategy | unit | precision | recall | F1 | notes |
|---|---|---|---|---|---|
| record: per-category Nouls | record × category (943 positives) | 93.5% | 99.7% | 96.5% | 535/600 records had all eight category decisions right |
| record: ANY_PII Noul | record (418 positives) | 97.4% | 99.3% | 98.3% | 11 FP, 3 FN |
| span: regex candidates + Jev Noul | span (1,048 gold) | 98.8% | 99.0% | 98.9% | 13 FP, 11 FN |
| span: regex only (baseline) | span | 46.0% | 100% | 63.0% | 1,230 FP: what Jev removes |
| column: Choice over 8 labels + NONE | column (175) | accuracy 95.4% | | | named headers 99.1%, obfuscated headers 88.1% |

Calibration is good: expected calibration error (ECE) was 0.02–0.05 for most categories
in the span strategy, and the F1-optimal thresholds sit near 0.5 for the categories that
matter, so the default threshold is usable without per-category tuning.

## What Jev got wrong, and why it matters

**Record level.** 52 of the 65 false positives were PERSON_NAME. Every one of them was a
surname-shaped token the generator did not label: 16 personal emails whose local part is a
name (`donna.smith84@yahoo.com`), 17 company names built from surnames (`Brown Group`,
`Logan-Carroll`), 10 street names that are first-name-plus-suffix (`494 Jennifer Grove`),
and 9 role mailboxes at surname domains (`support@hernandez.com`). Jev answered the literal
question ("does this text contain a person's name?") correctly; the taxonomy disagreed about
whether that counts. For a real deployment the fix is a policy decision in the criteria,
not a model change. The remaining 13 FPs were store addresses and role mailboxes
scored 0.5–0.86 as personal; the 3 FNs were a tax_id field not read as an SSN and two JSON
fields just under threshold.

**Span level.** The 12 PERSON_NAME false positives were all street names inside addresses
(`Kathryn Park`, `Scott Keys`). The 11 misses: five addresses in JSON fields scored
0.30–0.48, two `tax_id` values not treated as SSNs (0.10, 0.21), two 13- and 15-digit card
numbers (0.33, 0.45), two phones. All but one miss were between 0.3 and 0.5, so a 0.4
threshold or a review band would recover most of them at little precision cost.

**Column level.** Eight misses, all on obfuscated headers or hard negatives: SSN-shaped
case numbers called SSN (three at 0.90–0.99 confidence), four-part version strings called
IP addresses (0.70–0.87), one role-mailbox column called EMAIL (0.44). With no header and
only values to look at, Jev cannot distinguish a 3-2-4 digit case number from an SSN, and
says so confidently. Confidence gating at 0.9 still kept 88% coverage at 98% accuracy, but
it does not catch these particular errors.

## Batching destroys accuracy and barely saves money

Packing several records into one request (the `--batch` flag) is the obvious way to cut
request count for bulk data. It is the wrong trade for Jev 1.13:

| records per request | requests | input tokens | cost | per-category micro-F1 | ANY_PII F1 | records fully correct |
|---|---|---|---|---|---|---|
| 1 | 600 | 1,250,947 | $0.053 | **96.5%** | 98.3% | 89.2% |
| 10 | 60 | 1,125,787 | $0.047 | 63.7% | 83.7% | 45.8% |
| 25 | 24 | 1,119,523 | $0.047 | 49.9% | 81.2% | 23.7% |

Tokens barely move because the record text dominates and the per-question overhead is
small, so batching saves about 10% of cost and halves accuracy. This matches TypeSafe's
own warning about accuracy loss with large, mixed state. Bulk throughput should come
from concurrency, not from packing state. At 80 requests/second the published limit allows
roughly 290,000 single-record requests per hour.

## Cost and throughput for bulk data

Per record, one request with nine Nouls (record strategy) averaged about 2,100 input
tokens, or $0.00009. At the list price of $0.042 per million input tokens:

| volume | record strategy | span strategy (≈1,400 tokens/record) |
|---|---|---|
| 1 million records | ~$88 | ~$58 |
| 100 million records | ~$8,800 | ~$5,800 |

The span strategy is cheaper per record and more precise, but its recall is capped by the
candidate finder. Here the regexes covered 100% of gold spans because the generator and
regexes share assumptions; real data will not be that kind, especially for names, where
the candidate finder is a capitalised-word heuristic.

## Recommendations

1. **Use the span strategy for redaction and the record ANY_PII Noul for triage.** Both
   are production-grade on this data. Run the record strategy first as a cheap filter and
   send flagged records to the span strategy only if spans are needed.
2. **One record per request, high concurrency.** Never pack records.
3. **Decide the surname question in the criteria.** Either declare names inside emails,
   domains, company names and street names out of scope explicitly, or label them as PII
   in your ground truth. Jev will follow whichever you write.
4. **Add a review band (0.3–0.6) for span decisions**, and route column classifications
   below 0.9 confidence or with SSN/IP predictions on headerless columns to a human.
5. **Before trusting these numbers, re-run on a sample of the real bulk data** with
   hand-labeled ground truth. Synthetic data is cleaner and the regexes were tuned to it.
6. Pin `jev-1.13.0` in production so threshold tuning survives model alias moves.

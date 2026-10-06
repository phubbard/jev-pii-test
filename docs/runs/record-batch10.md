# jev-pii run `20261006-112952-record`

Model `jev-latest` · data `data` · strategies: record

## Usage and cost

| requests | cache hits | errors | input tokens | est. cost (USD) | wall s | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| 60 | 0 | 0 | 1,125,787 | $0.0473 | 2.23 | 232.8 | 438.5 |

## Strategy: record-level Nouls (600 records, threshold 0.5)

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| PERSON_NAME | 240 | 65.7% | 78.3% | 71.5% | 98 | 52 |
| EMAIL | 132 | 59.3% | 72.7% | 65.3% | 66 | 36 |
| PHONE | 112 | 55.3% | 60.7% | 57.9% | 55 | 44 |
| SSN | 97 | 55.8% | 69.1% | 61.8% | 53 | 30 |
| CREDIT_CARD | 83 | 55.7% | 71.1% | 62.4% | 47 | 24 |
| STREET_ADDRESS | 95 | 57.9% | 69.5% | 63.2% | 48 | 29 |
| DATE_OF_BIRTH | 92 | 50.9% | 62.0% | 55.9% | 55 | 35 |
| IP_ADDRESS | 92 | 52.0% | 69.6% | 59.5% | 59 | 28 |
| **micro** | 943 | 58.0% | 70.5% | 63.7% | 481 | 278 |
| ANY_PII | 418 | 81.5% | 86.1% | 83.7% | 82 | 58 |

Records with every category decided correctly: 275 / 600 (45.8%)

Best threshold per label (F1-optimal on this data) and calibration error:

| label | best threshold | F1 at best | ECE |
|---|---|---|---|
| PERSON_NAME | 0.6 | 72.2% | 0.1232 |
| EMAIL | 0.8 | 67.4% | 0.1083 |
| PHONE | 0.4 | 59.7% | 0.0919 |
| SSN | 0.65 | 65.0% | 0.1058 |
| CREDIT_CARD | 0.3 | 64.4% | 0.0996 |
| STREET_ADDRESS | 0.5 | 63.2% | 0.0914 |
| DATE_OF_BIRTH | 0.45 | 60.0% | 0.0972 |
| IP_ADDRESS | 0.35 | 61.5% | 0.1003 |

ANY_PII by record format:

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| json | 98 | 87.5% | 85.7% | 86.6% | 12 | 14 |
| log | 104 | 75.2% | 78.8% | 77.0% | 27 | 22 |
| ticket | 216 | 81.9% | 89.8% | 85.7% | 43 | 22 |


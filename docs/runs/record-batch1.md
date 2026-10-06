# jev-pii run `20261006-113038-record`

Model `jev-latest` · data `data` · strategies: record

## Usage and cost

| requests | cache hits | errors | input tokens | est. cost (USD) | wall s | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| 600 | 0 | 0 | 1,250,947 | $0.0525 | 5.45 | 126.6 | 203.6 |

## Strategy: record-level Nouls (600 records, threshold 0.5)

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| PERSON_NAME | 240 | 82.8% | 100.0% | 90.6% | 50 | 0 |
| EMAIL | 132 | 97.1% | 100.0% | 98.5% | 4 | 0 |
| PHONE | 112 | 100.0% | 99.1% | 99.6% | 0 | 1 |
| SSN | 97 | 100.0% | 99.0% | 99.5% | 0 | 1 |
| CREDIT_CARD | 83 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| STREET_ADDRESS | 95 | 94.0% | 99.0% | 96.4% | 6 | 1 |
| DATE_OF_BIRTH | 92 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| IP_ADDRESS | 92 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| **micro** | 943 | 94.0% | 99.7% | 96.8% | 60 | 3 |
| ANY_PII | 418 | 97.2% | 99.3% | 98.2% | 12 | 3 |

Records with every category decided correctly: 539 / 600 (89.8%)

Best threshold per label (F1-optimal on this data) and calibration error:

| label | best threshold | F1 at best | ECE |
|---|---|---|---|
| PERSON_NAME | 0.95 | 99.4% | 0.108 |
| EMAIL | 0.9 | 100.0% | 0.0454 |
| PHONE | 0.2 | 100.0% | 0.0418 |
| SSN | 0.3 | 99.5% | 0.0329 |
| CREDIT_CARD | 0.1 | 100.0% | 0.0332 |
| STREET_ADDRESS | 0.5 | 96.4% | 0.0385 |
| DATE_OF_BIRTH | 0.4 | 100.0% | 0.0235 |
| IP_ADDRESS | 0.1 | 100.0% | 0.0232 |

ANY_PII by record format:

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| json | 98 | 100.0% | 96.9% | 98.5% | 0 | 3 |
| log | 104 | 94.5% | 100.0% | 97.2% | 6 | 0 |
| ticket | 216 | 97.3% | 100.0% | 98.6% | 6 | 0 |


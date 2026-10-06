# jev-pii run `20261006-112955-record`

Model `jev-latest` · data `data` · strategies: record

## Usage and cost

| requests | cache hits | errors | input tokens | est. cost (USD) | wall s | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| 24 | 0 | 0 | 1,119,523 | $0.0470 | 2.16 | 479.4 | 1001.1 |

## Strategy: record-level Nouls (600 records, threshold 0.5)

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| PERSON_NAME | 240 | 52.0% | 80.0% | 63.0% | 177 | 48 |
| EMAIL | 132 | 42.1% | 66.7% | 51.6% | 121 | 44 |
| PHONE | 112 | 39.4% | 58.0% | 46.9% | 100 | 47 |
| SSN | 97 | 38.6% | 60.8% | 47.2% | 94 | 38 |
| CREDIT_CARD | 83 | 32.7% | 65.1% | 43.5% | 111 | 29 |
| STREET_ADDRESS | 95 | 36.1% | 64.2% | 46.2% | 108 | 34 |
| DATE_OF_BIRTH | 92 | 28.6% | 60.9% | 38.9% | 140 | 36 |
| IP_ADDRESS | 92 | 36.4% | 56.5% | 44.3% | 91 | 40 |
| **micro** | 943 | 40.0% | 66.5% | 49.9% | 942 | 316 |
| ANY_PII | 418 | 75.0% | 88.5% | 81.2% | 123 | 48 |

Records with every category decided correctly: 142 / 600 (23.7%)

Best threshold per label (F1-optimal on this data) and calibration error:

| label | best threshold | F1 at best | ECE |
|---|---|---|---|
| PERSON_NAME | 0.45 | 63.5% | 0.2119 |
| EMAIL | 0.7 | 54.9% | 0.1891 |
| PHONE | 0.45 | 47.4% | 0.181 |
| SSN | 0.4 | 49.3% | 0.1817 |
| CREDIT_CARD | 0.65 | 46.8% | 0.2031 |
| STREET_ADDRESS | 0.65 | 47.9% | 0.1889 |
| DATE_OF_BIRTH | 0.75 | 40.0% | 0.2273 |
| IP_ADDRESS | 0.45 | 46.1% | 0.1825 |

ANY_PII by record format:

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| json | 98 | 79.4% | 86.7% | 82.9% | 22 | 13 |
| log | 104 | 67.9% | 85.6% | 75.7% | 42 | 15 |
| ticket | 216 | 76.9% | 90.7% | 83.2% | 59 | 20 |


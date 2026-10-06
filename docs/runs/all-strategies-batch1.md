# jev-pii run `20261006-112859-record+span+column`

Model `jev-latest` · data `data` · strategies: record, span, column

## Usage and cost

| requests | cache hits | errors | input tokens | est. cost (USD) | wall s | p50 ms | p95 ms |
|---|---|---|---|---|---|---|---|
| 1185 | 5 | 0 | 2,085,432 | $0.0876 | 10.53 | 121.6 | 209.5 |

## Strategy: record-level Nouls (600 records, threshold 0.5)

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| PERSON_NAME | 240 | 82.2% | 100.0% | 90.2% | 52 | 0 |
| EMAIL | 132 | 95.0% | 100.0% | 97.4% | 7 | 0 |
| PHONE | 112 | 100.0% | 99.1% | 99.6% | 0 | 1 |
| SSN | 97 | 100.0% | 99.0% | 99.5% | 0 | 1 |
| CREDIT_CARD | 83 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| STREET_ADDRESS | 95 | 94.0% | 99.0% | 96.4% | 6 | 1 |
| DATE_OF_BIRTH | 92 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| IP_ADDRESS | 92 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| **micro** | 943 | 93.5% | 99.7% | 96.5% | 65 | 3 |
| ANY_PII | 418 | 97.4% | 99.3% | 98.3% | 11 | 3 |

Records with every category decided correctly: 535 / 600 (89.2%)

Best threshold per label (F1-optimal on this data) and calibration error:

| label | best threshold | F1 at best | ECE |
|---|---|---|---|
| PERSON_NAME | 0.95 | 99.4% | 0.1081 |
| EMAIL | 0.9 | 100.0% | 0.0453 |
| PHONE | 0.2 | 100.0% | 0.0414 |
| SSN | 0.3 | 99.5% | 0.0323 |
| CREDIT_CARD | 0.1 | 100.0% | 0.0328 |
| STREET_ADDRESS | 0.55 | 97.4% | 0.0402 |
| DATE_OF_BIRTH | 0.4 | 100.0% | 0.0235 |
| IP_ADDRESS | 0.1 | 100.0% | 0.0229 |

ANY_PII by record format:

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| json | 98 | 100.0% | 96.9% | 98.5% | 0 | 3 |
| log | 104 | 94.5% | 100.0% | 97.2% | 6 | 0 |
| ticket | 216 | 97.7% | 100.0% | 98.9% | 5 | 0 |

## Strategy: candidate spans + Jev (600 records, 1048 gold spans, 2278 candidates, threshold 0.5)

Jev as precision layer over recall-tuned regex candidates:

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| PERSON_NAME | 298 | 96.1% | 100.0% | 98.0% | 12 | 0 |
| EMAIL | 146 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| PHONE | 122 | 100.0% | 98.4% | 99.2% | 0 | 2 |
| SSN | 103 | 100.0% | 98.1% | 99.0% | 0 | 2 |
| CREDIT_CARD | 86 | 100.0% | 97.7% | 98.8% | 0 | 2 |
| STREET_ADDRESS | 100 | 99.0% | 95.0% | 96.9% | 1 | 5 |
| DATE_OF_BIRTH | 95 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| IP_ADDRESS | 98 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| **micro** | 1048 | 98.8% | 99.0% | 98.9% | 13 | 11 |

Regex-only baseline (every candidate accepted):

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| PERSON_NAME | 298 | 49.1% | 100.0% | 65.9% | 309 | 0 |
| EMAIL | 146 | 60.3% | 100.0% | 75.3% | 96 | 0 |
| PHONE | 122 | 70.9% | 100.0% | 83.0% | 50 | 0 |
| SSN | 103 | 53.9% | 100.0% | 70.1% | 88 | 0 |
| CREDIT_CARD | 86 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| STREET_ADDRESS | 100 | 69.4% | 100.0% | 82.0% | 44 | 0 |
| DATE_OF_BIRTH | 95 | 13.4% | 100.0% | 23.7% | 613 | 0 |
| IP_ADDRESS | 98 | 76.6% | 100.0% | 86.7% | 30 | 0 |
| **micro** | 1048 | 46.0% | 100.0% | 63.0% | 1230 | 0 |

Recall ceiling (gold spans the regex found at all), best threshold, calibration:

| label | recall ceiling | candidates | best threshold | F1 at best | ECE |
|---|---|---|---|---|---|
| PERSON_NAME | 100.0% | 607 | 0.85 | 99.5% | 0.0388 |
| EMAIL | 100.0% | 242 | 0.5 | 100.0% | 0.0575 |
| PHONE | 100.0% | 172 | 0.1 | 100.0% | 0.0905 |
| SSN | 100.0% | 191 | 0.3 | 99.0% | 0.0657 |
| CREDIT_CARD | 100.0% | 86 | 0.0 | 100.0% | 0.148 |
| STREET_ADDRESS | 100.0% | 144 | 0.4 | 99.0% | 0.1476 |
| DATE_OF_BIRTH | 100.0% | 708 | 0.2 | 100.0% | 0.016 |
| IP_ADDRESS | 100.0% | 128 | 0.05 | 100.0% | 0.0268 |
| **micro** | 100.0% | 2278 | 0.45 | 98.9% | 0.0415 |

By record format (Jev, micro):

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| json | 189 | 98.4% | 96.3% | 97.3% | 3 | 7 |
| log | 218 | 97.8% | 99.5% | 98.6% | 5 | 1 |
| ticket | 641 | 99.2% | 99.5% | 99.4% | 5 | 3 |

## Strategy: column classification (175 columns)

Accuracy: **95.4%** · named headers 99.1% · obfuscated headers 88.1%

| label | support | precision | recall | F1 | FP | FN |
|---|---|---|---|---|---|---|
| PERSON_NAME | 12 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| EMAIL | 14 | 93.3% | 100.0% | 96.5% | 1 | 0 |
| PHONE | 14 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| SSN | 14 | 77.8% | 100.0% | 87.5% | 4 | 0 |
| CREDIT_CARD | 17 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| STREET_ADDRESS | 10 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| DATE_OF_BIRTH | 7 | 100.0% | 100.0% | 100.0% | 0 | 0 |
| IP_ADDRESS | 7 | 70.0% | 100.0% | 82.3% | 3 | 0 |
| NONE | 80 | 100.0% | 90.0% | 94.7% | 0 | 8 |

Confidence gating (act only above a confidence floor):

| confidence ≥ | coverage | accuracy |
|---|---|---|
| 0.5 | 99.4% | 96.0% |
| 0.7 | 97.1% | 96.5% |
| 0.9 | 88.0% | 98.0% |

Misclassified columns (first 40):

| table | column | gold | predicted | confidence |
|---|---|---|---|---|
| t001 | col_2 | NONE | IP_ADDRESS | 0.83 |
| t001 | col_7 | NONE | EMAIL | 0.44 |
| t002 | case_ref | NONE | SSN | 0.62 |
| t014 | col_4 | NONE | SSN | 0.99 |
| t015 | col_3 | NONE | SSN | 0.99 |
| t018 | col_4 | NONE | SSN | 0.9 |
| t022 | col_2 | NONE | IP_ADDRESS | 0.87 |
| t028 | col_4 | NONE | IP_ADDRESS | 0.7 |


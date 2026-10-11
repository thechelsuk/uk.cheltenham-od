# Fact Check: Private Rented Homes Below EPC C (Post 2026-10-15)

Every figure, its source and whether it matched. Data from `_data/epc-scores.json` (generated 2026-10-11) unless stated.

| Figure | Source | Matched |
| --- | --- | --- |
| 8,746 privately rented homes | `by_tenure[Private rented].homes` | Yes |
| 4,571 below C (52.3%) | `by_tenure[Private rented].below_c`; 4,571 / 8,746 = 52.3% | Yes |
| 3,452 D, 1,037 E, 82 F or G (51 F + 31 G) | `by_tenure[Private rented].counts` | Yes, sums to 4,571 |
| 4,170 could reach C (91.2%) | `by_tenure[Private rented].below_c_could_reach_c(_pct)` | Yes |
| Ward counts (Lansdown 735 to Up Hatherley 92) | `private_rented_by_ward`, names from `_data/wards/index.json`; `assets/findings/cheltenham-private-rented-epc.csv` | Yes |
| Five central wards 2,598 (57%) | 735 + 575 + 444 + 427 + 417 = 2,598; / 4,571 = 56.8% | Yes |
| Central wards 57% to 64% below C | CSV `below_c_pct`: 57.2, 61.9, 63.7, 57.0, 61.0 | Yes |
| Most other wards 90 to 135 | CSV: 13 wards between 92 and 134 | Yes |
| 47.7% private rented C+, 40.9% owner-occupied, 73.5% social | `by_tenure[*].c_plus_pct` | Yes |
| Median score 68 private rented, 67 owner-occupied | `by_tenure[*].median_score` | Yes |
| 8,875 certificates without tenure | `tenure_unknown_display` | Yes |
| 12,378 privately rented households, Census 2021 | Nomis NM_2072_1 (TS054), Cheltenham E07000078, "Private rented" | Yes (primary) |
| 1 October 2030, EPC C equivalent, £10,000 cap, needs Parliament's approval, new metrics | GOV.UK consultation outcome, "Improving the energy performance of privately rented homes: 2025 update" | Yes (primary); also Elmhurst Energy and Devonshires commentary |
| Minimum E since April 2020 unless exempt | GOV.UK domestic private rented property minimum energy efficiency standard guidance | Yes (standard rule) |
| Landlords must give tenants the certificate | Energy Performance of Buildings (England and Wales) Regulations 2012 | Yes (standard rule) |

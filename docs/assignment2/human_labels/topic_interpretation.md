# Topic interpretation — Debanjan / Alfred / Dan

Read from representative Q&A (see `topic_examples.md` and Stage 2.1), **not** from BERTopic's top-word string.  
M7: every observed topic mapped to one of eight prudential categories, dual-coded, disagreements recorded.

Eight categories (Aidan M2a): `capital_adequacy` · `liquidity_funding` · `asset_quality_credit` · `profitability_earnings` · `operational_efficiency` · `market_traded_risk` · `conduct_operational` · `business_model_strategy` · plus `untagged` when the cluster has no single home.

**Protocol:** Debanjan names the cluster from the questions. Alfred and Dan independently map it to one of eight. Resolution is recorded; it is not a majority vote that erases the disagreement.

| Topic | n | BERTopic name (machine) | Debanjan — what the Q&A is actually about | Alfred 8-way | Dan 8-way | Agree? | Resolved map | Why / disagreement |
|---|---|---|---|---|---|---|---|---|
| −1 | 104 | think / thank / growth / questions | Residual. Courtesy turns, mixed double questions, and parser bleed. Examples include NII, capital distribution, USCB, rate sensitivity — no stable theme. | untagged | untagged | yes | **untagged** | Do not force a prudential law onto HDBSCAN leftovers. |
| 0 | 23 | hedge / structural / expect | Structural hedge, deposit lag, and BUK NII/margin walks. Analysts are triangulating rate-sensitivity of **earnings**, occasionally IRRBB. | profitability_earnings | market_traded_risk | **no** | **profitability_earnings** (secondary: IRRBB) | Dan files hedge-as-risk. Alfred files hedge-as-NII. Resolution: the questions are almost all “what does this do to NII/guidance this year”, so earnings. Record Dan’s IRRBB read as a known alternative — do not silently drop it. |
| 1 | 12 | cost / costs / billion | Operating-cost guidance, inflation vs saves, investment spend, FX in the cost number. | operational_efficiency | operational_efficiency | yes | **operational_efficiency** | Cleanest cluster. A few HSBC turns also mention CRE/tariffs as a *second* question; the topic still formed on the cost limb. |
| 2 | 11 | growth / banking / lending | Banking NII, UK/HK lending volumes, IB FICC/equities vs peers. | profitability_earnings | profitability_earnings | yes | **profitability_earnings** | Dan noted FICC examples could be `market_traded_risk`. Minority of the cluster; keep earnings, footnote the IB bleed. |
| 3 | 11 | wealth / growth / hsbc | HSBC wealth and non-interest income: sustainability of fees, CSM, GBM vs transaction banking, HK. | profitability_earnings | business_model_strategy | **no** | **profitability_earnings** (secondary: franchise) | Alfred reads run-rate/fee income. Dan reads Asia wealth strategy. Resolution: the asks are “is this income sustainable / how do I triangulate NII vs wealth”. Strategy is the overlay, not the filing. |
| 4 | 11 | downside / ecl / impairment | ECL, HK/China CRE, BoCom VIU, tariff/trade *plausible downside* vs ECL tests. | asset_quality_credit | asset_quality_credit | yes | **asset_quality_credit** | Some 2025-q1 turns are revenue-downside rather than Stage 3. Bleed into `profitability_earnings` is real; still an asset-quality cluster. |
| 5 | 9 | capital / months | CET1, RWA (US cards), buybacks and distribution timing. | capital_adequacy | capital_adequacy | yes | **capital_adequacy** | Clustering miss: Ed Firth 2024-q2 (US cards **NPLs**) landed here. Do not let that example redefine the topic. |

## What this does *not* mean

- BERTopic top-words (`think`, `would`, `bit`) are not labels. The human names above replace them for the pitch and for Stage 7.
- Topic −1 is 104/181 turns. Any Stage 6 chart that treats “Topic 1” as *the* cost story must quote **n** on Topic 1 (12), not the residual.
- Dual-code disagreement on Topics 0 and 3 is the M7 deliverable, not a failure. The resolved map is the law we use in Stage 6 grouping; the dissent stays in this table.

## Evidence IDs (M9)

At least three pair_ids a supervisor can open for the three clusters that matter to A2:

- Topic 1 (costs): `barclays_2024-annual_003`, `barclays_2024-q2_001`, `hsbc_2024-annual_006`
- Topic 4 (ECL/CRE): `hsbc_2025-interim_003`, `hsbc_2024-annual_009`, `hsbc_2025-q3_010`
- Topic 0 (hedge/NII): `barclays_2024-q3_001`, `barclays_2024-q3_007`, `hsbc_2024-q1_003`

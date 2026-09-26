    # Prudential Risk Taxonomy from PRA Sources

**Owner:** Aidan Cameron. **Built independently of the transcript corpus** — these
categories come from the PRA's own published supervisory framework, defined before
any transcript was read. This independence is the evidence that the M7 mapping
(bottom-up analyst topics → top-down prudential categories) is a genuine test, not a
fit constructed to succeed. See `docs/assignment2/A2_pitch_outline.md`, Slide 9,
"Why the Taxonomy Comes First."

## Prudential supervisor approach

A prudential supervisor uses financial reports and investor materials to form an
early view of a bank's solvency, liquidity, asset quality, earnings resilience, risk
concentrations, and governance. Although a bank's profitability is of some interest
here, the main focus is: **can a bank absorb plausible stress and continue critical
services without needing public support?**

The following 18 categories are the main Basel-aligned taxonomies a prudential
supervisor would be concerned with.

## The 18 Basel-aligned PRA categories

| Code | Basel-aligned PRA taxonomy | Primary official report family |
|---|---|---|
| P01 | Own funds, capital requirements and RWA | COREP / own-funds reporting; Pillar 3 |
| P02 | Leverage | UK leverage reporting; Pillar 3 |
| P03 | Financial position and performance | FINREP; PRA capital-planning forecasts |
| P04 | Credit risk and asset quality | FINREP; Pillar 3 credit risk disclosures |
| P05 | Large exposures and concentration risk | COREP large exposures |
| P06 | Counterparty credit risk | Pillar 3 CCR disclosure |
| P07 | Securitisation | Pillar 3 securitisation disclosure |
| P08 | Market risk | Pillar 3 market risk disclosure |
| P09 | Operational risk | Pillar 3 operational risk disclosure |
| P10 | Liquidity coverage and liquidity position | LCR supervisory reporting; Pillar 3 liquidity disclosure |
| P11 | Stable funding and funding profile | NSFR supervisory reporting; Pillar 3 |
| P12 | Additional liquidity monitoring and counterbalancing capacity | ALMM; counterbalancing-capacity reporting |
| P13 | Asset encumbrance | Asset encumbrance reporting; Pillar 3 disclosure |
| P14 | IRRBB | Pillar 3 IRRBB disclosure |
| P15 | Capital planning, stress and forecasts | UK PRA data items |
| P16 | Cash-flow mismatch / Pillar 2 liquidity | UK PRA data items |
| P17 | G-SII / systemic importance | COREP supplementary reporting |
| P18 | Scope, risk management and governance disclosures | Pillar 3 disclosures |

> **Note on code numbering:** the source document numbered these P01\u2013P09, then
> P010\u2013P018 (three digits from P10 onward). Standardised to two-digit P01\u2013P18
> above for consistency with the notebook's own code references \u2014 confirm this
> matches whatever convention `scripts/` and Stage 3.6 actually use before treating
> this table as canonical.

## Mapping: notebook seed category \u2192 PRA element

This maps the **four-line bottom-up seed taxonomy** (`SEED_TAXONOMY` in Stage 2.0 \u2014
`profitability`, `efficiency`, `asset_quality`, `capital`) onto the PRA elements
above. This is a different, coarser mapping than the eight-way prudential map used
in Stage 3.6 (`liquidity_funding`, `credit`, `market_risk`, `business_model`,
`governance_controls`, `operational_resilience`, `systematic_risk`, `capital`) \u2014
see the open question below.

| Notebook seed category | PRA element | PRA code |
|---|---|---|
| Capital | Own funds, capital adequacy, capital requirements and RWA | P01 |
| Capital \u2014 capital-plan/stress/distribution-specific only | Forecast capital, stress testing, management buffers, capital actions | P15 |
| Profitability | Statement of profit or loss and financial performance | P03 |
| Profitability \u2014 IRRBB-specific only | Earnings or EVE sensitivity to interest-rate shocks | P14 |
| Efficiency | Administrative expenses, staff expenses and other operating expenses | P03 |
| Asset Quality | Credit quality, impairment, provisions, NPEs and forbearance | P04 |
| Mixed | None until individual concepts are separated | \u2014 |
| Untagged | None until manually classified | \u2014 |

## Open question, worth resolving before this is treated as final

This table maps the **four-way seed taxonomy** to PRA codes. It does not cover the
**eight-way prudential category map** (Stage 3.6: `liquidity_funding`, `credit`,
`market_risk`, `business_model`, `governance_controls`, `operational_resilience`,
`systematic_risk`, `capital`) that the M7 dual-coding exercise (Aidan vs. machine
`coder1`/`coder2`) is actually scored against. Worth confirming with Aidan whether:

- this seed-to-PRA-code mapping is a separate, earlier-stage artifact (documenting
  where the four bottom-up metrics sit in the full 18-category PRA framework), and
- a second table mapping the **eight-way** categories to PRA codes exists or is
  still needed, since that's the scheme the actual dual-coding agreement numbers
  (35% machine, 50% human) are measured against.

If only one of the two taxonomies has documented PRA provenance, that's worth
stating explicitly \u2014 it changes what the "built independently, before reading a
transcript" claim actually covers.
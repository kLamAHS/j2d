# 7. Hospital and payer price transparency

**One line:** negotiated rate benchmarks built from the machine-readable files CMS
requires hospitals and payers to publish and that are technically compliant and
practically hostile.

| Axis | Score | Why |
|---|---|---|
| Derived, not published | 4 | Rate benchmarking requires normalization the files actively resist |
| Fragmentation | 2 | Federal mandate, roughly common schema intent, one regulator |
| Deadline | 1 | Disclosure deadlines already passed; nothing forces a purchase |
| Unhappy incumbent | 4 | Turquoise and Serif are real, funded, and ahead |
| **Total** | **11** | |
| Crowding | **severe** | Multiple funded entrants with meaningful head starts |

## Why it is in this repo

It scores last and it belongs here anyway, because it is the **purest example of the
pattern**: mandated disclosure, published in a form deliberately calibrated to satisfy
the letter of the rule while being unusable, with enormous derived value sitting on
top. Every other idea here is a variation on this shape. Keep it as the reference case
even though the answer is probably "not this one."

## The derived field

- **Negotiated rate by procedure, payer, and provider**, normalized across the coding
  and contract-structure variations that make raw files incomparable.
- **Rate dispersion for the same service in the same market**, which is the number
  employers and benefit consultants actually want.
- **Percentage-of-Medicare benchmarking**, the common denominator that makes rates
  comparable at all.
- **Contract structure inference** — distinguishing case rates, per diems, percent-of-
  charge, and fee schedules from files that encode them inconsistently.

## Sources

CMS hospital price transparency machine-readable files and payer transparency-in-
coverage files. Hundreds of gigabytes. Non-standard schemas despite schema guidance.
Unstable URLs that move without notice. Files that are technically present and
practically undownloadable.

## Why it is hard

The difficulty is volume and hostility rather than fragmentation:

- **Scale.** Payer files run to hundreds of GB per payer per month. The ingestion cost
  is real infrastructure spend before any analysis happens.
- **Deliberate unusability.** Compliance is measured on publication, not on
  legibility, so there is no incentive to make files parseable and some incentive not
  to.
- **URL instability.** Index files move. Historical snapshots are nobody's obligation,
  so the time series only exists if you built it, which favors whoever started first —
  and that is not you.

That last point is the real problem. In a dataset where history accrues only to
whoever was collecting, a two-year head start is not a head start, it is an asset you
cannot buy.

## Why now

Nothing. The disclosure deadlines have passed, the files exist, and the competitors
have been ingesting them for years. Scored 1 honestly.

## Buyers

Employers and benefit consultants, providers doing competitive rate analysis, health
plans, and life sciences market access teams. Large buyer set, already being sold to.

## Incumbents

Turquoise Health and Serif Health, both funded, both with years of accumulated
history. This is not an unhappy monopolist — it is a competitive market with informed
buyers.

## Wedge

Only worth entering on a narrow vertical the incumbents are structurally unwilling to
serve: **one specialty, one region, employer-side benchmarking**, sold as an answer
rather than a data feed. Not head-on, ever.

## What would kill it

Entering at all, on current scores. The historical depth advantage is unbuyable and
the deadline axis is a 1. Revisit only if a specific vertical buyer surfaces with a
question the incumbents demonstrably do not answer.

## Open questions

- Is there a specialty where rate dispersion is high enough and incumbent coverage
  poor enough to justify the ingestion cost?
- Does anyone sell historical snapshots, or is the time series genuinely unbuyable?

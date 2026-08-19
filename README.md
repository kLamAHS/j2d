# j2d — dataset opportunity notes

Working notes on mandated-disclosure datasets worth building.

## The pattern

A government mandate creates disclosure. The disclosure is public but fragmented
across jurisdictions and formats. The field people actually want is a **derived
number**, not a lookup.

That last part is the whole thesis. If the valuable field is published, someone
already scraped it and the price is zero. The margin lives in the number nobody
publishes: ask-vs-award spread, withdrawal causation, unit price by region and
quarter, rate change velocity.

## The filter

Four questions, scored 1–5 each. See [`docs/scoring-filter.md`](docs/scoring-filter.md)
for what each score means.

1. **Derived, not published** — is the valuable field computed rather than looked up?
2. **Fragmentation** — does jurisdictional spread multiply the work? Fifty states is a
   moat; one federal portal is not.
3. **Deadline** — is there a compliance date? Deadlines create budget.
4. **Unhappy incumbent** — does someone charge a lot for a mediocre version? That is
   validation, not discouragement. You want a market with an unhappy monopolist, not
   an empty one.

Crowding is tracked separately as a penalty, not a fifth axis. A well-funded
competitor does not change whether the dataset is worth building; it changes
whether *you* should build it head-on.

## Portfolio

| # | Idea | Derived | Frag | Deadline | Incumbent | Total | Crowding |
|---|------|---------|------|----------|-----------|-------|----------|
| 0 | [Transmission](ideas/00-transmission-baseline.md) *(reference project)* | — | — | — | — | — | — |
| 1 | [State rate case tracker](ideas/01-state-rate-case-tracker.md) | 5 | 5 | 2 | 5 | **17** | low |
| 2 | [Interconnection queue outcomes](ideas/02-interconnection-queue-outcomes.md) | 4 | 3 | 3 | 3 | **13** | severe |
| 3 | [Water treatment buying signal](ideas/03-water-treatment-buying-signal.md) | 5 | 5 | 5 | 2 | **17** | low |
| 4 | [DOT bid tabulation benchmark](ideas/04-dot-bid-tabulation-benchmark.md) | 5 | 5 | 2 | 3 | **15** | low |
| 5 | [Insurance rate filings (SERFF)](ideas/05-serff-insurance-rate-filings.md) | 5 | 5 | 3 | 4 | **17** | moderate |
| 6 | [Municipal disclosure (EMMA)](ideas/06-emma-municipal-disclosure.md) | 4 | 3 | 2 | 4 | **13** | moderate |
| 7 | [Hospital & payer price transparency](ideas/07-price-transparency.md) | 4 | 2 | 1 | 4 | **11** | severe |

Scores are a first pass, argued in each file. They are meant to be disagreed with.

**Reading of the table.** Three ideas tie at 17 and they tie for different reasons,
which matters more than the tie. Rate case and SERFF score on an unhappy incumbent —
demand is proven, you are displacing someone. Water scores on a deadline — demand is
about to exist, and you would be creating the category. Those are different companies
with different sales motions and different failure modes.

Idea 6 is the interesting failure: EMMA is a *single federal portal*, so it fails the
fragmentation test on the user's own terms. Its difficulty is document heterogeneity,
not jurisdictional spread. That is real work but it is not a moat in the same way —
one good document model erases it, and document models are getting better fast.

## Sequencing

Transmission first — it is the reference project and it scores well on all four axes.
These are what year two and three look like.

If year two has to be picked today: **water treatment (3)** on timing, because the
deadline is dated and near and the funding is already appropriated and named, or
**rate case (1)** on revenue certainty, because S&P's RRA has already proven what
utility regulatory teams will pay. Water is the bigger swing with the shorter fuse.
Rate case is the safer one.

## Layout

```
docs/scoring-filter.md   what the four scores mean, and how to avoid grading on a curve
ideas/_template.md       structure for adding a new idea
ideas/NN-*.md            one file per idea
portfolio.csv            the scores, machine-readable
```

# 4. National DOT bid tabulation benchmark

**One line:** a national unit-price index by pay item, region, and quarter, built from
every state DOT's historical bid tabs, joined to programmed future work so estimators
know both what things cost and what is coming.

| Axis | Score | Why |
|---|---|---|
| Derived, not published | 5 | The index requires pay-item normalization across 50 coding schemes — a genuine modeling choice |
| Fragmentation | 5 | 50 DOTs, 50 formats, scanned tables, no common item codes |
| Deadline | 2 | Letting calendars create rhythm, not deadlines |
| Unhappy incumbent | 3 | Estimating tools and cost references exist; none is a national normalized index |
| **Total** | **15** | |
| Crowding | low | Surprisingly untouched for how obvious it is |

## The derived field

Every state publishes its bid tabs. The tabs are a lookup. The index is not:

- **Normalized unit price by pay item, region, and quarter.** The normalization is the
  product: "Class A concrete, cubic yard" is a different item code in every state and
  is not quite the same item in any two of them. Deciding what is comparable is the
  modeling judgment.
- **Competitive position** — where a given contractor's bid sat in the distribution
  for that item, that quarter, that region. An estimating department will pay real
  money to learn its $/CY is in the 70th percentile.
- **Bid spread and bidder count by item and letting**, which is the actual measure of
  how competitive a market is and moves before prices do.
- **Escalation series by item class**, which is what a surety or a materials supplier
  needs and what generic construction cost indices are too coarse to give.
- **Joined to STIP/TIP programming**, so the index carries forward: here is what this
  item costs and here is $X billion of programmed work containing it.

## Sources

Fifty state DOT bid tab archives. Some publish clean CSV or Excel going back decades.
Some publish PDFs of scanned tables. Some have a query interface that emits HTML.
Plus STIP and TIP documents — statewide and MPO-level transportation improvement
programs — which are PDFs almost without exception and are the forward-looking half.

## Why it is hard

- **Pay item codes do not reconcile.** Each state maintains its own item code
  dictionary, revises it periodically, and does not publish crosswalks. Building and
  maintaining the crosswalk *is* the company. It is also why a competitor cannot
  simply re-scrape you.
- **Scanned tables.** Item-level tables in scanned PDFs, with columns that wrap and
  merge, in documents that occasionally include handwritten annotations.
- **Quantity effects.** A unit price for 50 CY and for 50,000 CY are not the same
  number and averaging them is malpractice. The index has to condition on quantity,
  which means the model needs more structure than a median.
- **STIP/TIP joining.** Programmed projects are described in prose with no item
  breakdown. Mapping programmed dollars to expected item quantities is inference.

## Why now

The weak axis. Letting calendars are seasonal and reliable but nothing forces a
purchase by a date. The nearest thing to a catalyst is federal surface transportation
reauthorization and the obligation of remaining IIJA-era funding, which moves
programmed volume around and makes forward visibility temporarily more valuable.
Treat "why now" as a sales problem here, not a gift.

## Buyers

- **Heavy civil contractors' estimating departments.** The clearest willingness to pay
  in this repo. Being 5% off on unit prices across a bid book is the difference
  between winning unprofitable work and losing profitable work, and they know it.
- **Materials suppliers** pricing regionally.
- **Sureties** underwriting contractor bid behavior.
- **DOTs themselves**, for engineer's estimates — a buyer that is also a source, which
  is a pleasant position and a licensing question.

## Incumbents

Fragmented. State-specific bid tab tools, general construction cost references, and a
lot of Excel maintained by individual estimators. No national normalized index with
programming joined to it. That is a 3, not a 5: the absence of an entrenched vendor
means less validation, though the workflow it replaces is visible and expensive.

## Wedge

One region, one work type. Highway and bridge items across a contiguous 5–8 state
region, ten years of tabs, with percentile position and quantity conditioning working.
Sell to estimating departments bidding in exactly that footprint. They will tell you
within one bid cycle whether the normalization is credible.

## What would kill it

Estimators do not trust a normalized number they did not build. This product's
adoption risk is cultural rather than technical: the buyer's expertise is precisely
the thing you are automating, and the first wrong crosswalk destroys credibility.
Ship the underlying comparables alongside every index value so the number is
auditable, or it will not be believed.

## Open questions

- Do DOTs restrict commercial redistribution of bid tabs? Assume some do; check before
  building on states that do.
- Is percentile position sellable to contractors, or does it feel like exposure?
- How much does the STIP/TIP join actually add versus the historical index alone?

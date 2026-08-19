# 1. State rate case tracker

**One line:** every investor-owned utility rate case at every state commission, with
requested vs. authorized ROE, so you can see which commissions are getting punitive
and by how much.

| Axis | Score | Why |
|---|---|---|
| Derived, not published | 5 | The spread is the product; nobody publishes ask-vs-award |
| Fragmentation | 5 | ~50 commission docket systems, no common numbering, scanned PDFs |
| Deadline | 2 | Continuous cycle, no terminal date — the weak axis |
| Unhappy incumbent | 5 | S&P RRA charges enterprise money and buyers name it |
| **Total** | **17** | |
| Crowding | low | Nobody venture-backed is attacking RRA directly |

## The derived field

Not "here is the rate case." The columns that matter:

- **Ask-vs-award spread on ROE** — requested minus authorized, in basis points, by
  commission, by year. This is the headline number.
- **Months to decision**, filing to final order. Regulatory lag priced in months is
  what a capital plan actually runs on.
- **Settled vs. litigated**, and the spread difference between the two. Settlement
  rates by commission are a proxy for how negotiable a jurisdiction is.
- **Authorized rate base and equity ratio**, so ROE is comparable across cases of
  wildly different size.
- **Trend derivatives:** rolling spread by commission over time. Which commissions
  are drifting punitive, and how fast.

The trend derivatives are the reason this is a 5 and not a 3. Any one case is a
lookup. The drift across fifty commissions over ten years is a model.

## Sources

State PUC/PSC docket systems, one per state, plus DC. Each has its own search
interface, its own docket numbering, and its own idea of what a document type is.
Filings, orders, testimony, and settlement stipulations, mostly as PDFs, frequently
scanned. Some commissions have usable APIs. Most do not. A few still expect you to
click through a session-based search form that will not survive a bookmark.

## Why it is hard

The docket systems are the moat, and they are hard in a way that does not compress:

- **No common identifier.** A case is `ER-2024-0189` in one state and
  `Docket No. 24-0451` in another, and neither tells you it is the same utility's
  general rate case. Entity resolution across utility subsidiaries, holding companies,
  and the operating-company names that appear on filings is genuinely difficult and
  never finished.
- **The number is in prose.** Authorized ROE frequently appears in an order's text or
  a settlement stipulation exhibit, not in any table. Sometimes it is not stated at
  all — a settlement authorizes a revenue requirement and a black-box return, and you
  have to decide whether to impute an ROE or mark it null. That judgment call is
  exactly the modeling choice that makes your data differ from a competitor's.
- **Portals rot.** Search interfaces change, URL schemes change, and nothing announces
  it. This is ongoing operational cost, which is the good kind of hard.
- **Coverage tail.** The top 30 utilities are tractable. The value of a national
  benchmark is in the tail — municipal-adjacent IOUs, small water and gas utilities,
  the cases nobody covers.

## Why now

The weakest axis, and worth being honest about: there is no compliance deadline. What
there is instead is filing volume. Load growth from data centers is driving a wave of
rate cases and capital plans, which raises the frequency of the underlying event and
the stakes on each one. That is a 3-grade cycle argument dressed as a 2-grade deadline.
Do not oversell it.

## Buyers

- **Utility regulatory and strategy teams.** They pay to know what to ask for. A
  utility about to file wants to know what its commission has authorized recently and
  what neighboring commissions did with similar asks.
- **Infrastructure funds and utility equity analysts.** Authorized ROE is a direct
  input to valuation, and regulatory lag drives cash flow timing.
- **Consultants and expert witnesses** in rate proceedings, who currently build this
  by hand for each engagement.

## Incumbents

S&P Global's Regulatory Research Associates (RRA) is the incumbent and charges
accordingly. That is proof of demand and it is also the competition. RRA is well
regarded — this is not a market with an obviously bad incumbent, which is the
uncomfortable part of the 5.

The attack is not "cheaper RRA." It is coverage depth on the tail, latency, and
delivering the data as data — API and warehouse-native — rather than as research
notes and PDFs. Ask actual buyers whether their complaint is price or shape before
committing. If it is price, walk away.

## Wedge

One sector, one region, full history. Electric IOUs in a set of 8–10 states with
active filing volume, ten years back, with the spread and months-to-decision series
complete. Sell to regulatory teams in exactly those states first — they will tell you
in the first meeting whether the derived fields are the right ones.

## What would kill it

RRA is good enough that buyers do not switch. The realistic failure is not that you
cannot build the data — you can — but that you build it and discover the incumbent's
customers are contractually locked and mildly satisfied. Validate switching intent
before coverage.

## Open questions

- Does a black-box settlement get an imputed ROE or a null? This single choice defines
  the methodology and should be decided before ingestion, not after.
- How far back does history need to go to be credible? Ten years is a guess.
- Are the buyers actually the utilities, or the people selling to the utilities?

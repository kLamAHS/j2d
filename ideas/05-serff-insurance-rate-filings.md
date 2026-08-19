# 5. Insurance rate filings (SERFF)

**One line:** rate change velocity by line, carrier, and geography, built from the
filings every state insurance department reviews through SERFF.

| Axis | Score | Why |
|---|---|---|
| Derived, not published | 5 | Velocity, ask-vs-approved, and cat assumption extraction are all computed |
| Fragmentation | 5 | 50 DOIs with wildly uneven access — some open, some paywalled, some FOIA-only |
| Deadline | 3 | Renewal cycles and filing seasons, no compliance cliff |
| Unhappy incumbent | 4 | Paid products exist; coverage and latency complaints are real |
| **Total** | **17** | |
| Crowding | moderate | Established vendors, no dominant modern entrant |

## The derived field

- **Rate change velocity** — approved rate change by line, carrier, and geography, as
  a time series with acceleration, not a point value. How fast is homeowners repricing
  in this county, and is the rate of change itself increasing?
- **Ask vs. approved**, by state, by line. The same spread logic as the rate case
  tracker (idea 1) and equally unpublished. Which departments are suppressing rate,
  and by how much.
- **Time to decision**, filing to disposition. In a hardening market this is the
  number that determines whether a carrier can write at all.
- **Catastrophe model assumptions extracted from actuarial memoranda** — which vendor
  model, which version, what loss cost trend, what reinsurance cost load. This is the
  hardest extraction and the most valuable field, because it reveals what carriers
  actually believe about risk in a geography before it shows up in price.
- **Withdrawal and non-renewal signal**, inferred from filing patterns — form changes,
  territory restrictions, deductible restructuring — which frequently precedes a
  public market exit.

## Sources

SERFF is the common rails, but access is per-state and wildly uneven:

- Some states publish filings openly with full attachments.
- Some run a paid access tier.
- Some treat filings as effectively FOIA-only.
- Trade secret designations remove actuarial exhibits from public versions at varying
  rates by state.

The unevenness is the fragmentation and it is unusually severe, because it is not just
format variance — it is *legal access* variance. That is a higher barrier than parsing
and a correspondingly better moat, with a matching compliance burden.

## Why it is hard

- **Access is a legal problem before it is an engineering problem.** Terms of use vary
  by state portal, and some prohibit bulk collection. This has to be worked state by
  state, in writing, before building. Do not skip this and do not let it be discovered
  later by a customer's counsel.
- **Actuarial memoranda are dense PDFs** written by actuaries for regulators. Cat model
  assumptions appear in narrative and in exhibits that are frequently redacted.
- **Filing structure is not the unit of analysis.** A single rate change may span
  several filings — rate, rule, and form — and a company group may file separately
  per subsidiary. Rolling that up to "what did this carrier do in this state" is
  entity and event resolution.
- **Redaction asymmetry.** The same carrier's filing may be public in one state and
  trade-secret-redacted in another, which means your coverage is uneven in a way that
  needs to be disclosed rather than papered over.

## Why now

Homeowners in Florida, California, and Louisiana is where the money is, and that is
where the questions are being asked with the most urgency. California's post-Sustainable
Insurance Strategy filings, Florida's post-reform market, and Louisiana's ongoing
repricing all mean the rate environment is moving fast enough that stale data is
useless — which is exactly the condition that makes a data product valuable.

No compliance deadline, so a 3. But the reinsurance renewal calendar (January 1 and
mid-year) gives a hard rhythm to when buyers need the data refreshed.

## Buyers

The largest buyer set in this repo, which is the main argument for it:

- **Carriers**, for competitive intelligence — what did the other carrier ask for and
  get in my state.
- **Reinsurers and brokers**, for portfolio and treaty pricing.
- **Cat modelers**, for calibration against what carriers actually assume.
- **Mortgage originators and servicers**, who are newly exposed to insurance cost as a
  driver of borrower default and have almost no data on its trajectory.
- **Real estate investors and REITs**, underwriting insurance cost trajectories in
  cat-exposed geographies. This buyer barely existed five years ago and has the least
  incumbent-loyalty of the set.

The mortgage and real estate buyers are the interesting ones. They need the same data
as carriers, have budget, and are not served by products built for insurance insiders.

## Incumbents

Established data vendors serve the carrier and reinsurer side, and buyers complain
about coverage gaps and staleness rather than price — the good kind of complaint. The
mortgage and real estate buyers are effectively unserved.

## Wedge

**Homeowners, three states, one derived field: approved rate change velocity by ZIP
or county, monthly.** Sell it to mortgage and real estate underwriters rather than to
carriers — same data, uncontested buyer, no incumbent relationship to displace, and a
buyer who wants a number rather than a filings archive.

## What would kill it

Access, not extraction. If enough states prohibit or price out systematic collection,
coverage becomes patchy in exactly the states that matter, and a homeowners product
missing Florida is not a product. Resolve access in the three target states in writing
before writing any parser.

Second risk: trade secret redaction hollows out the cat assumption field, leaving the
approved-rate series — still valuable, but a 4 rather than a 5.

## Open questions

- Which states permit systematic collection, and on what terms? This is the first
  research task and it gates everything.
- Is the mortgage/real-estate buyer real, or does the interest evaporate at a purchase
  order? Test before building coverage.
- How much of the cat model assumption field survives redaction across the target
  states?

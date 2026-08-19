# 2. Interconnection queue outcomes

**One line:** project-level queue positions across all seven ISOs and the non-ISO
utilities, tracked longitudinally through withdrawal, with network upgrade cost
assignment attached to each project.

| Axis | Score | Why |
|---|---|---|
| Derived, not published | 4 | Withdrawal causation and per-project cost assignment are computed; queue position is a lookup |
| Fragmentation | 3 | Seven ISOs is not fifty states — the non-ISO tail is where the work is |
| Deadline | 3 | FERC Order 2023 cluster transitions create dated milestones, not a compliance cliff |
| Unhappy incumbent | 3 | Grid Status and Cleanview exist; LBNL publishes free aggregates |
| **Total** | **13** | |
| Crowding | **severe** | The most crowded idea in this repo |

## The derived field

The queue itself is published. Do not build that. What is not published:

- **Network upgrade cost assignment at project level** — what this specific project
  was told it would owe, how that number moved between study phases, and what it
  finally settled at. This is the number a site selector needs and the aggregate
  reports do not give.
- **Withdrawal causation.** Projects leave the queue constantly. Almost nothing says
  *why*. Distinguishing "priced out by upgrade costs" from "lost the offtake" from
  "resubmitted under a new name in the next cluster" is a modeling problem and it is
  the single most valuable field here.
- **Cost per MW of deliverable capacity by point of interconnection**, which is the
  form the question actually gets asked in.
- **Survival curves by ISO, by cluster, by technology** — probability of reaching
  commercial operation conditional on having cleared each study phase.

Withdrawal causation is a 5-grade field. It is dragged to a 4 by everything around it
already being visible.

## Sources

Seven ISO/RTO queue postings, each with its own cadence, schema, and definition of a
queue phase. Cluster study reports and restudy results, often as PDFs or spreadsheets
posted to stakeholder pages. Plus the non-ISO utilities — the Southeast, much of the
West outside CAISO, large parts of the Mountain region — which post OASIS data and
study reports of wildly varying quality, and which nobody covers well.

## Why it is hard

The honest answer is that the easy part is done and published. What is left:

- **Identity across time.** A project changes name, capacity, POI, and owner over a
  five-year queue life, and may withdraw and resubmit. Without stable identity, the
  longitudinal view — the entire point — is noise.
- **Cost assignment lives in study reports**, not queue postings. Extracting a
  per-project upgrade cost from a cluster study means parsing documents that were
  written to satisfy a tariff obligation, not to be read.
- **The non-ISO tail** is where fragmentation would score higher, and it is also where
  data center load growth is landing hardest. This is the underserved half.
- **Causation requires inference.** You will never have a labeled reason for
  withdrawal. You will have features — cost jump between studies, restudy count, time
  in queue, cluster composition — and you will have to model it and defend the model.

## Why now

FERC Order 2023 forced every transmission provider onto cluster study processes with
defined transition milestones and penalties for study delay. That reshapes the data
generating process and creates a clean before/after break. Combined with data center
load growth making interconnection the binding constraint on siting, the questions
are being asked with more money behind them than at any prior point.

But it is a cycle, not a cliff. Nobody has to buy this by a date.

## Buyers

- **Data center site selectors and hyperscaler energy teams** — the buyer with the
  most urgency and the deepest pockets. They need to know, for a given POI, what
  upgrade cost and what timeline they should expect. This is the wedge.
- **Renewable and storage developers** deciding where to submit.
- **Lenders and tax equity** underwriting project timelines.

## Incumbents

Grid Status and Cleanview are venture-backed and in this space. LBNL publishes
excellent free aggregate research (the annual queue reports), which sets a public
baseline and caps what you can charge for anything aggregate-shaped.

The free LBNL work is the specific problem: it is good, it is cited, and it means the
obvious version of this product competes with free.

## Wedge

Do not build a queue tracker. Build **cost assignment and withdrawal risk for one
region's non-ISO territory**, priced and sold to data center site selection. Narrow,
underserved, and the buyer has budget that does not care about a subscription price.

## What would kill it

Entering head-on. Against two funded entrants and a free federal-lab baseline, a
general-purpose queue product loses. The idea survives only as the narrow wedge; if
the wedge does not sell, this stays a year-three idea or never.

Second risk: ISOs improve their own reporting under FERC pressure and publish cost
assignment directly, which converts the 4 into a 2 overnight.

## Open questions

- Is the site-selector wedge actually a data product, or is it a consulting engagement
  that happens to need data?
- How much of the non-ISO tail is obtainable without FOIA or membership access?

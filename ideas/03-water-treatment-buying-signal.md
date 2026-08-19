# 3. Who is about to buy treatment equipment

**One line:** the list of water systems with a known contaminant problem, a dated
compliance deadline, and identified funding — ranked by how close they are to writing
a purchase order.

| Axis | Score | Why |
|---|---|---|
| Derived, not published | 5 | A buying-intent rank fused from four sources that share no key |
| Fragmentation | 5 | 50 state SRF plans, 50 state LSL inventory formats, all different |
| Deadline | 5 | November 1, 2027 and 2029/2031, both dated and both near |
| Unhappy incumbent | 2 | Nobody sells this. The weak axis, and it cuts both ways |
| **Total** | **17** | |
| Crowding | low | Adjacent players exist; nobody has fused these sources |

## The derived field

Each input source is a lookup and each is already public. The product is the fusion:

- **A ranked buying-intent score per system**, combining measured contaminant
  occurrence, compliance jeopardy, appropriated funding, and deadline proximity.
- **Estimated treatment capacity required** — from system size, source count, and
  measured concentration, not from a survey. This is what a vendor sizes a proposal
  against.
- **Funding-to-need match:** which systems have a named SRF allocation that plausibly
  covers their problem, and — more valuably — which have the problem and no funding
  line, because those are the ones about to go looking.
- **Deadline distance in months**, per system, per obligation.
- **The ≥12 ppt segment** (see below), which is a distinct and unusually actionable cut.

No source contains any of these. There is no common key across them — PWSID gets you
partway, but SRF plans name borrowers in prose and inventories arrive in whatever
format each state chose.

## Sources

1. **UCMR 5** — nationwide PFAS occurrence monitoring, 29 PFAS plus lithium. As of the
   eleventh data release (February 12, 2026), roughly 1.9 million sample results
   covering 10,299 public water systems, about 95% of expected results, spanning Q1
   2023 through Q3 2025. **The twelfth and final release is due early fall 2026** —
   i.e. now. Federal, clean, bulk-downloadable. This is the one easy source.
2. **SDWIS / ECHO** — violations and enforcement history. Federal, structured, with
   known data quality caveats around state reporting lag.
3. **State SRF Intended Use Plans** — the annual project priority lists naming
   borrower, project, and dollar amount. Fifty states, published on fifty schedules,
   almost entirely as PDFs, with project descriptions in free prose. **This is the
   hard source and the valuable one**, because it is the only place the money appears
   before it is spent.
4. **Lead service line inventories** — every system had to file an initial inventory
   by October 2024, in whatever format its state felt like accepting. Some states
   publish a clean statewide table. Some publish a map with no export. Some publish
   nothing and you go system by system.

## Why it is hard

- **No join key.** An SRF Intended Use Plan names "City of ——— Water Treatment Plant
  Improvements, $4.2M." Tying that to a PWSID, to a UCMR 5 sampling point, and to an
  LSL inventory row is entity resolution against prose. Every one of these datasets
  identifies systems differently.
- **Fifty IUP formats, republished annually.** Not a one-time parse — an operational
  commitment with a yearly cadence and no notification when a state changes its
  template.
- **Inventory formats are worse than the IUPs**, because states were given latitude
  and used it. This is the source that makes the fragmentation score a 5 rather than a 4.
- **Occurrence is per sampling point, need is per system, purchase is per plant.**
  Rolling detections up to a treatment decision requires knowing something about system
  configuration that no dataset states directly.

## What the FRS spine actually gives you

Built and measured — see `docs/frs-pipeline.md` and `src/j2d/frs/`. EPA's Facility
Registry Service is the closest thing to the missing join key, and it is now
loaded: 47.6M rows, 5.3M facilities, a 7.6M-link cross-program crosswalk.

What it solves:

- **380,410 distinct PWSIDs**, of which **131,598** are community or
  non-transient non-community systems — the population actually subject to the
  PFAS MCLs and the LCRI. That is the denominator for the whole product, and it
  is now a table rather than an estimate.
- **235,288 water-treatment-plant records** *inside* those systems. Plant-level
  granularity is what a vendor sizes a proposal against, and it is finer than
  anything SDWIS exposes conveniently.
- A **crosswalk to every other program** at the same facility, including roughly
  forty-five state systems. This is the fragmentation asset: NJ-NJEMS,
  CA-ENVIROVIEW, MN-TEMPO, TX-TCEQ ACR and their peers are exactly the
  state-by-state surface the thesis says is a moat.

What it does **not** solve, and these matter:

- **Drinking water is `SFDW`, not `SDWIS`.** The acronym everyone searches for is
  not the one in the data. Trivial once known, silently empty until then.
- **The crosswalk is to a facility, not to a borrower.** SRF Intended Use Plans
  name a borrower in prose. FRS gets you PWSID ↔ facility ↔ other program IDs; it
  does not get you "City of ——— Water Treatment Plant Improvements, $4.2M" ↔
  PWSID. That entity resolution is still the hard, unsolved, valuable part.
- **No coordinates.** All 5,319,139 facility rows have empty latitude and
  longitude in this extract. Geospatial targeting needs a separate EPA download.

Net: FRS removes maybe a third of the entity-resolution problem — the part that
joins EPA's own systems to each other. The SRF-to-PWSID join, which is where the
money signal lives, is untouched by it.

## Why now

This is the strongest timing in the repo, and the dates are worth stating exactly
because two of them are commonly misremembered:

- **LCRI compliance date: November 1, 2027** (not October — October 2024 was the
  *initial inventory* deadline). By that date systems need a baseline inventory
  identifying lead, galvanized-requiring-replacement, and lead connectors, an approved
  replacement plan, an updated sampling plan, and a school and childcare facility list.
  Interim consumer notifications run each November in 2025, 2026, and 2027.
- **PFAS, as of the May 18, 2026 proposals** (both still proposed, comment periods
  closed July 20, 2026): EPA proposed keeping the 4 ppt PFOA/PFOS MCLs while extending
  compliance two years to **2031**, and separately proposed **rescinding** the
  regulatory determinations and standards for PFHxS, PFNA, HFPO-DA, and the Hazard
  Index mixture — on the procedural ground that EPA proposed and finalized those
  determinations simultaneously in 2024 rather than sequentially. Several states keep
  their own limits for those compounds regardless, which *increases* fragmentation
  value rather than reducing it.
- **The ≥12 ppt condition.** Under the extension proposal, systems at or above 12 ppt
  PFOA or PFOS that request the extension must implement **interim control measures**
  during the two added years. That is a dated, funded, non-deferrable obligation for a
  segment you can compute exactly from UCMR 5. It is the single most actionable cut in
  this dataset and it is a direct consequence of a rule that is still only proposed.
- **UCMR 5 completes in early fall 2026**, giving the first genuinely complete national
  occurrence picture.

**The catch, stated plainly:** the 2031 extension and the rescissions are *proposals*,
not final rules. If the rescissions finalize, the addressable contaminant list
shrinks. If the extension finalizes, the most urgent deadline moves two years further
out and some of the urgency you are selling against goes with it. Build the product so
the deadline is a data field, not an assumption baked into the pitch — and treat the
state-level patchwork that survives a federal rescission as the more durable asset.

## Buyers

- **Membrane and media vendors.** This is literally the market NALA-type suppliers
  sell into. A ranked list of systems about to buy, with sized need, is a sales
  territory plan.
- **Engineering firms' business development** — Black & Veatch, Jacobs, Carollo. They
  currently find this work through relationships and by reading IUPs by hand.
- **Water-focused private equity**, for acquisition targeting and for underwriting
  capex at portfolio companies.
- **Municipal advisors and SRF-adjacent lenders**, secondarily.

## Incumbents

Nobody sells this fused product. That is the 2, and it is the honest weak point: no
incumbent means no proof anyone will pay. Adjacent validation exists — market research
subscriptions, engineering firms' internal BD databases, list brokers selling
utility contacts without the intent signal — but none of it is the same thing.

The mitigation is that the buyer's alternative is visible and expensive: BD teams
reading fifty IUPs by hand every year. You are not asking them to believe in a new
category, you are asking them to stop doing something they already do badly.

## Wedge

**PFAS only, top 500 systems by population served, with the ≥12 ppt segment flagged.**
Skip lead entirely in v1 — the LSL inventories are the worst source and lead pulls in
a different buyer. Sell to three or four treatment vendors as a territory list, priced
per seat, and find out in eight weeks whether the intent ranking predicts anything
their reps recognize.

If the ranking is any good, their own pipeline is the validation set. Ask for it.

## What would kill it

Two things, in order of likelihood:

1. **Vendors have their own list.** The BD teams at the large firms may already know
   these systems by name — the market is more relationship-driven than the data
   suggests, and a ranked list may tell them what they already believe. Test this in
   the first sales conversation, not the tenth.
2. **The rules move.** Both PFAS proposals are unfinalized. A rescission plus a
   two-year extension takes real air out of the urgency, though the state patchwork
   and the LCRI date survive either way.

## Open questions

- Does the ≥12 ppt interim-control-measures segment survive to the final rule? Watch
  the docket; this is the highest-value single field and it is contingent.
- Which states retain their own PFHxS/PFNA/HFPO-DA limits if the federal rescission
  finalizes? That map becomes the product if it does.
- Are SRF Intended Use Plans consistently available for all states, or does the tail
  require records requests?
- Is lead a second product or a second segment of the same one?

## Sources cited

- [EPA, Proposed PFOA and PFOS Compliance Extension Rule](https://www.epa.gov/sdwa/proposed-pfoa-and-pfos-compliance-extension-rule)
- [EPA, Proposed PFAS Rescission Rule](https://www.epa.gov/sdwa/proposed-pfas-rescission-rule)
- [Federal Register, Rescission of Regulatory Determinations for Four PFAS Substances (May 20, 2026)](https://www.federalregister.gov/documents/2026/05/20/2026-10085/rescission-of-regulatory-determinations-and-removal-of-related-provisions-for-four-pfas-substances)
- [Jones Day, EPA Proposes to Rescind Certain PFAS Drinking Water Standards](https://www.jonesday.com/en/insights/2026/05/epa-proposes-to-rescind-certain-pfas-drinking-water-standards-and-extend-compliance-deadlines-for-pfoa-and-pfos)
- [ASDWA, EPA Publishes Eleventh Set of UCMR 5 Data](https://www.asdwa.org/2026/02/13/epa-publishes-eleventh-set-of-ucmr-5-data/)
- [EPA, Fifth Unregulated Contaminant Monitoring Rule Data Finder](https://epa.gov/dwucmr/fifth-unregulated-contaminant-monitoring-rule-data-finder)
- [Federal Register, National Primary Drinking Water Regulations for Lead and Copper: Improvements](https://www.federalregister.gov/documents/2024/10/30/2024-23549/national-primary-drinking-water-regulations-for-lead-and-copper-improvements-lcri)
- [EPA, Lead and Copper Rule Improvements](https://www.epa.gov/ground-water-and-drinking-water/lead-and-copper-rule-improvements)

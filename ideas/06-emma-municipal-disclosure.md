# 6. Municipal continuing disclosure (EMMA)

**One line:** comparable credit fundamentals for the tens of thousands of municipal
issuers who file annual financials and event notices to EMMA as unstructured PDFs.

| Axis | Score | Why |
|---|---|---|
| Derived, not published | 4 | Comparability across accounting presentations is genuine modeling |
| Fragmentation | 3 | **One federal portal.** Fails the fragmentation test on its own terms |
| Deadline | 2 | Filing obligations are continuous; lateness is a signal, not a deadline |
| Unhappy incumbent | 4 | Merritt and DPC Data exist; small and mid-size issuer coverage is genuinely thin |
| **Total** | **13** | |
| Crowding | moderate | Established vendors, and document AI lowers the barrier every year |

## The derived field

- **Normalized credit fundamentals** — debt service coverage, days cash on hand,
  pension funded ratio, OPEB liability, fund balance as a percentage of expenditures —
  computed consistently across issuers who present them inconsistently or not at all.
- **Comparability adjustments** across GASB presentation choices, fiscal year ends, and
  the difference between governmental and enterprise fund reporting. This is the actual
  modeling work.
- **Disclosure timeliness as a credit signal.** How late is this issuer relative to its
  own history and its peers. Lateness is well established as an early distress
  indicator and nobody sells it as a clean series.
- **Peer set construction** — who is actually comparable to this issuer, which is the
  question a muni analyst asks first and answers by hand.

## Why it scores 3 on fragmentation, and why that matters

This is the instructive one. EMMA is a **single federal portal** with a single
submission process. There is no jurisdictional fragmentation at all. The difficulty is
document heterogeneity: tens of thousands of issuers, each with its own accounting
presentation, filing as PDFs of varying quality.

That is real work, but it is a different *kind* of hard, and it is aging worse. Fifty
state portals that break in fifty ways stay hard indefinitely because the breakage is
adversarial and continuous. Ten thousand inconsistent PDFs behind one stable API get
easier every time document models improve — and they are improving fast.

If the moat is "these documents are hard to parse," the moat has a depreciation
schedule. Score it honestly.

## Sources

MSRB EMMA. Annual financial information, audited financial statements, and material
event notices, filed under continuing disclosure agreements. Mostly PDFs. Frequently
late. Occasionally not filed at all, which is itself information.

## Why it is hard

- **Presentation heterogeneity.** A small district's audited financials and a large
  city's CAFR share a standard and almost nothing else. Extracting comparable line
  items means understanding fund structure, not just table parsing.
- **The tail is enormous and thinly covered.** The existing vendors cover the issuers
  people already watch. The unserved value is in small and mid-size issuers — where
  the credit surprises come from and where no analyst has time to read the PDFs.
- **Non-filing is data.** Building the denominator — who *should* have filed and did
  not — requires reconstructing continuing disclosure obligations from official
  statements, which is a separate and harder extraction problem.

## Why now

Weak. There is no deadline. The arguments are secular: muni issuance volume, rate
volatility making credit selection matter more, and pension and OPEB liabilities
maturing into visible stress at exactly the small-issuer tail nobody covers.

## Buyers

- **Muni asset managers**, particularly high-yield and separately managed account
  shops that hold small issuers.
- **Bond insurers**, for surveillance across a portfolio too large to read by hand.
- **Municipal advisors**, for pricing comparables.

## Incumbents

Merritt Research and DPC Data. Both established, both real. Coverage of small and
mid-size issuers is genuinely thin — that is the gap and it is the whole opportunity.

## Wedge

One sector, full tail. Water and sewer revenue credits, or school districts, in a set
of states — every issuer including the small ones, with coverage and days-cash series
complete and timeliness scored. Depth on a segment the incumbents skim.

## What would kill it

The moat depreciates. If a general document model can extract a CAFR reliably in two
years, the barrier drops to zero and the incumbents — who have distribution and
issuer-obligation history you do not — win the reprice. Build this only if the
defensibility comes from the *obligation reconstruction* and peer-set modeling, which
are not document problems, rather than from parsing skill.

## Open questions

- Is the durable asset the extracted fundamentals, or the continuing-disclosure
  obligation map that tells you who did not file?
- Which sector's tail has the most credit dispersion, and therefore the most value in
  covering it?

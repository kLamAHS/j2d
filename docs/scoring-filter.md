# The filter

Four axes, 1–5. Total out of 20. The point of writing the anchors down is to stop
score inflation — every idea feels like a 5 on the day you think of it.

## 1. Derived, not published

Is the field the buyer actually wants computed rather than looked up?

| | |
|---|---|
| **1** | The valuable field is published as-is. You are a mirror with a nicer UI. |
| **3** | Valuable field is a join across two published sources. Real work, but a competent team replicates it in a quarter. |
| **5** | Valuable field requires extraction from unstructured source documents *and* a modeling judgment call (causation, normalization, comparability) that reasonable people would implement differently. |

The 5-case is where durable margin lives, because your number and a competitor's
number will differ, and buyers will develop a preference. That preference is the
product.

**Test:** if you can describe the output as "a table of X by Y," it is probably a 2.
If you have to describe a methodology to explain the output, it is a 4 or 5.

## 2. Fragmentation

Does jurisdictional spread multiply the acquisition work?

| | |
|---|---|
| **1** | One federal portal, one schema, bulk download. |
| **3** | A handful of sources (5–15) with different schemas, or one source with severe document heterogeneity. |
| **5** | 50+ independent sources, each with its own interface, numbering scheme, and format, including scanned PDFs and portals with no stable URLs. |

Fragmentation is a moat because it converts into ongoing operational cost that scales
with coverage, not a one-time engineering cost. Competitors can match your parser;
they cannot skip the two years of babysitting fifty portals that change without notice.

**Careful:** document heterogeneity is not the same thing as jurisdictional
fragmentation, and it is aging worse. Fifty portals that break in fifty ways stay
hard. Ten thousand inconsistent PDFs get easier every time document models improve.
Score those 3, not 5. (See idea 6.)

## 3. Deadline

Is there a compliance date that creates budget?

| | |
|---|---|
| **1** | No deadline. Buyer purchases out of general curiosity, i.e. does not. |
| **3** | Recurring cycle with urgency (renewal dates, letting seasons, filing seasons) but no terminal date. |
| **5** | A dated regulatory deadline within 12–36 months that forces a named set of entities to spend money. |

Deadlines matter because they answer "why now" and "out of whose budget," which are
the two questions that kill enterprise deals. A 5 here also gives you a natural
expiry — plan for what the product becomes after the deadline passes.

**Careful about the far side:** a deadline that creates the market can also end it.
Ask what the dataset is worth 18 months after the compliance date.

## 4. Unhappy incumbent

Does someone already charge a lot for a mediocre version?

| | |
|---|---|
| **1** | Nobody sells this. You are creating a category and paying to educate the market. |
| **3** | Free or cheap tools exist with real coverage; monetization is unproven. |
| **5** | An entrenched vendor charges enterprise prices, buyers complain about it by name, and the complaints are about coverage or latency rather than price. |

An empty market is the trap this axis exists to catch. Low scores here are not
disqualifying, but they change the company: no incumbent means a longer sales cycle,
more evangelism, and a real chance the willingness-to-pay you assumed is imaginary.

**Complaint quality matters more than the score.** "Too expensive" means the incumbent
is fine and you are proposing a price war. "Missing half the small issuers" or "ninety
days stale" is a product gap you can attack.

## Crowding (penalty, tracked separately)

Not an axis — it says nothing about whether the dataset should exist. It says whether
you should be the one to build it.

- **low** — no venture-backed entrant focused on this
- **moderate** — funded entrants exist, coverage or vertical gaps remain
- **severe** — multiple funded entrants with head starts; only worth entering on a
  narrow vertical wedge they are structurally unwilling to serve

## Using it

Score honestly, then read the *shape* rather than the total. A 17 built on
deadline + fragmentation is a different business from a 17 built on incumbent +
fragmentation. The first is a race. The second is a siege.

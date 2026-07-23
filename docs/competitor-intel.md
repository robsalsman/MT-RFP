# Competitor intelligence — sources & qualification

How Matt finds competitor customers, and which competitors are worth
going after. Qualification is data-driven: every candidate was probed
against both public funding datasets (2026-07).

## Data sources (implemented)

| Source | What it yields | Freshness |
|---|---|---|
| **E-Rate Form 471 FRN Status** (USAC `qdmp-ygft`) | Recurring annual spend per district, incumbent provider, contract expiration, filing contact, consultant | Current funding year |
| **ECF Form 471** (USAC `i5j4-3rvr`) | The covid hotspot program: named contacts (name/email/phone), device counts, approved $. Program ENDED → every account is a win-back | 2021–2023 vintage |
| **Public-web mentions** (DuckDuckGo HTML, no key) | Board minutes, tech plans, news naming customers | live |
| **Vendor case studies** (mobilebeacon.org via search index) | Mobile Beacon's own published customer stories | live |
| **NCES CCD** (Urban Institute API) | District enrollment + total budget enrichment | 2020–2022 |

## Qualification probe (E-Rate FY2025 + ECF funded)

| Candidate | E-Rate FY25 | ECF funded | Verdict |
|---|---|---|---|
| Kajeet | $15.6M | $110M+ | **In** — #1 direct rival |
| Verizon Wireless | $6.6M | $108M+ | **In** |
| AT&T Mobility (+FirstNet) | $28.9M | $45M+ | **In** |
| Mobile Beacon (Voqal) | $0 | $1.27M / 107 orgs | **In** — ECF-only, all win-backs |
| Mobile Citizen (Voqal) | $0 | $204k | **In** (small) |
| US Cellular | $24k | **$2.0M / 173 orgs** | **In** — added 2026-07 |
| Starlink / SpaceX | **$297k / 70 lines** | $331k | **In** — growing rural threat |
| Viasat | $4k | **$1.06M** | **In** — satellite, rural niche |
| HughesNet | $2k | **$3.07M** | **In** — satellite, rural niche |
| DISH / Boost | $0 | $0 | Out — no footprint |
| Cricket | $0 | $0 funded | Out (folded conceptually into AT&T) |
| Tracfone | $0 | $0 | Out |
| ENA / Zayo | $240M (!) | $456k | **Watch-tier, excluded** — managed *fiber*; not LTE-displaceable line-by-line; would flood the board with 1,500 dead leads |
| T-Mobile | $36.8M | **$585M** | **Excluded — partner.** Their ECF dominance is the network Mission rides on; it's a selling point, not a target |

Satellite tier rationale: Starlink/Viasat/HughesNet win the same rural
districts fixed-wireless/LTE serves; Mission beats them on latency,
per-student hotspot lending, E-Rate eligibility, and nonprofit pricing.

## Evaluated, not (yet) implemented

- **State spending-transparency portals** (TX SmartBuy, CA eProcure,
  OpenBook NY…): vendor-payment records would reveal off-E-Rate
  purchases, but each state needs a bespoke scraper — high effort,
  do per-state on demand if Kim needs a specific territory.
- **USAspending / SAM.gov**: federal vendors only; K-12 buys don't appear.
- **TechSoup**: distributes Mobile Beacon to nonprofits; no public
  customer list.
- **IMLS grant narratives**: sometimes name hotspot vendors for library
  programs; searchable via the web-mentions tool already.

## How Matt uses this

- Login greeting: offers RFPs vs. competitor raids, recommending the
  soonest-expiring big E-Rate contract and the biggest untouched ECF
  win-back.
- `competitor_accounts` — the swept board (both programs, all 9 tracked
  competitors).
- `find_competitor_mentions` — public-web soft leads with source URLs.
- `prep_outreach` — district-site contact lookup + drafted email from
  real numbers.

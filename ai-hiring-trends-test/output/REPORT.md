# AI/ML Hiring Trends — India — Last 2 Months

**Window:** 2026-04-16 → 2026-06-17  
**Generated:** 2026-06-17  
**Scope guardrail:** India · AI/ML roles only (healthcare, finance, generic SWE filtered out)

> Reliability test of Apify job-scraper actors. Governed to a hard budget; all numbers are reproducible from `output/processed.json` + `output/manifest.json`.

## 1. Headline

- **312 unique AI/ML openings** captured across **2 live sources** (India).
- Date coverage: **231 in-window**, 81 undated, 0 older.
- Salary disclosed on **30/312 (10%)** roles (most India listings hide pay).
- **Spend: $4.4043** this run · final usage **$5.0244 / $5.00 cap**.

> ⚠️ **Coverage caveat:** Only **LinkedIn + Google Jobs** completed. Google Jobs' real cost was ~**$1.05/query** (vs ~$0.04 the 10-row probe implied — non-linear per-run fee), so it consumed the budget and the governor **correctly skipped Naukri, Glassdoor, Foundit, Indeed & HackerNews**. The $5 cap is now reached (resets ~2026-07-02). These figures = **LinkedIn + Google Jobs only.**

## 2. Which AI roles have the most openings

| Rank | Normalized AI Role | Openings |
|---|---|---|
| 1 | Data Scientist | 86 |
| 2 | Machine Learning Engineer | 66 |
| 3 | AI Engineer | 50 |
| 4 | MLOps Engineer | 41 |
| 5 | GenAI / LLM Engineer | 40 |
| 6 | AI/ML Engineer | 10 |
| 7 | Data Engineer | 4 |
| 8 | ML Platform / AI Infra | 4 |
| 9 | Deep Learning Engineer | 4 |
| 10 | NLP Engineer | 4 |
| 11 | Computer Vision Engineer | 2 |
| 12 | AI / ML Architect | 1 |

## 3. By AI role family

| AI Family | Openings |
|---|---|
| Core ML/AI | 212 |
| GenAI / LLM / NLP / CV | 50 |
| MLOps / AI Infrastructure | 45 |
| AI-adjacent Data & Product | 5 |

## 4. By company tier

| Company Tier | Openings |
|---|---|
| Unclassified | 220 |
| T2 - Indian IT / GCC / Unicorn | 43 |
| T3 - Funded / Mid-size Product | 25 |
| T1 - Global Big Tech / Product | 17 |
| T4 - Staffing / Consultancy (proxy employer) | 7 |

## 5. Top hiring companies (AI roles)

| Company | Tier | Openings |
|---|---|---|
| Infosys | T2 - Indian IT / GCC / Unicorn | 9 |
| Google | T1 - Global Big Tech / Product | 6 |
| Apple | T1 - Global Big Tech / Product | 4 |
| Michael Page | Unclassified | 4 |
| PwC India | T2 - Indian IT / GCC / Unicorn | 3 |
| Citi | Unclassified | 3 |
| LTM | Unclassified | 3 |
| NielsenIQ | Unclassified | 3 |
| Quest Global | Unclassified | 3 |
| EPAM Systems | T3 - Funded / Mid-size Product | 3 |
| Cognizant | T2 - Indian IT / GCC / Unicorn | 3 |
| UPS | Unclassified | 2 |
| Tech Mahindra | T2 - Indian IT / GCC / Unicorn | 2 |
| Persistent Systems | T2 - Indian IT / GCC / Unicorn | 2 |
| eBay | Unclassified | 2 |
| Infosys Finacle | T2 - Indian IT / GCC / Unicorn | 2 |
| EXL | Unclassified | 2 |
| HCLTech | T2 - Indian IT / GCC / Unicorn | 2 |
| Colgate-Palmolive | Unclassified | 2 |
| Tiger Analytics | T2 - Indian IT / GCC / Unicorn | 2 |

## 6. Source coverage & cost (governance)

| Requested Site | Status | Raw | Kept (AI) | Cost USD |
|---|---|---|---|---|
| LinkedIn Jobs | SCRAPED | 202 | 172 | 0.1881 |
| Google Jobs | SCRAPED | 240 | 213 | 4.2162 |
| Naukri | NOT RUN (budget ceiling hit first) | 0 | 0 | 0 |
| Glassdoor | NOT RUN (budget ceiling hit first) | 0 | 0 | 0 |
| Foundit (Monster) | NOT RUN (budget ceiling hit first) | 0 | 0 | 0 |
| Indeed | NOT RUN (budget ceiling hit first) | 0 | 0 | 0 |
| HackerNews Who-is-Hiring | NOT RUN (budget ceiling hit first) | 0 | 0 | 0 |
| Kaggle Jobs | BLOCKED | — | — | Job board permanently closed (no live source / no actor). |
| Instahire | BLOCKED | — | — | No dedicated Apify actor exists; only generic multi-source aggregators. |
| LinkedIn (social/profiles) | BLOCKED | — | — | Out of scope: only LinkedIn *Jobs* scraped. Profile/people scraping omitted (ToS/compliance). |

## 7. Guardrails & governance applied

- **Budget governor** reads real account spend before/after every actor run; soft-stops new runs at $4.0, hard-aborts at $4.5, absolute abort at $4.8 (under the $5 platform cap).
- **AI-role filter**: only titles matching the AI/ML taxonomy are kept; healthcare, finance, sales, HR, civil/mech, generic SWE explicitly excluded.
- **Per-actor item caps** prevent any single scraper from draining the budget.
- **Cross-source dedup** on (title, company) so Google Jobs / LinkedIn / Indeed overlaps aren't double-counted.
- **7-day retention mitigated**: all raw + processed data exported locally on capture.

## 8. Limitations (read before presenting)

- FREE-plan $5 cap → this is a **representative sample, not a census**. Counts show *relative* demand, not absolute market size.
- Many India listings omit dates → 'undated' rows are kept (dropping them would bias the sample); treat trend as *recent-activity* signal.
- Company-tier is rubric-based; unknown employers are honestly labelled **Unclassified**, not guessed.
- HackerNews 'Who is Hiring' is **global** and parsed from free text → low-weight, flagged separately.
- Third-party actors can change output schemas; figures are reproducible from the saved raw JSON.

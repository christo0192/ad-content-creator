# Emerging AI Roles → IK India Curriculum Gap Analysis
### India market · last 2 months · Naukri + LinkedIn

**Window:** 2026-04-16 → 2026-06-17 · **Generated:** 2026-06-18
**Evidence base:** 658 AI/ML job rows (637 = 97% date-confirmed in-window) · LinkedIn 471 + Naukri 187 · **Spend $2.23 / $5 cap (no overshoot)**
**Method:** deterministic title extraction + skills mining, mapped against IK's 19-course / 67-tag curriculum (`curriculum_coverage.json`); narrative synthesis by Claude with every claim tied to scraped counts.

---

## TL;DR for managers

1. **IK's core bet is correct and market-validated.** The two largest emerging role-clusters in India right now are **GenAI/LLM Engineer (124)** and **AI Agent / Agentic AI Engineer (66)**, and the #1–2 most-demanded skills are **Agents (41% of postings)** and **RAG (31%)** — exactly IK's deepest coverage. No pivot needed; lean in.
2. **The market is mostly *renaming*, not inventing.** Of 75 "novel/unmapped" titles, the top ones — *AI Developer, AIML Engineer, AI/ML Developer* — are India naming variants of roles IK already covers. **Few genuinely net-new role *categories* exist beyond IK's catalog.** The real gaps are **depth & positioning**, not missing role types.
3. **Three concrete gaps worth acting on:** (a) **cloud diversity** — market wants Azure (23%) ≥ AWS (20%) + GCP (14%), IK is **AWS-only**; (b) **production LLMOps/MLOps** — 46 in-market roles, thin in IK outside Flagship ML; (c) **AI Evaluation** as a *named* outcome — strong skill demand (20%) + emerging "Eval Engineer" titles, currently taught but not positioned as a role.

---

## 1. Emerging roles in the market vs IK coverage (Gap Matrix)

| Emerging role (market) | Openings | In-window | IK coverage (corrected) | Verdict |
|---|---|---|---|---|
| GenAI / LLM Engineer | **124** | 118 | Deep (all EdgeUp + PwC + ML) | ✅ Covered — core strength |
| AI Agent / Agentic AI Engineer | **66** | 64 | Deep (multi-agent, MCP/A2A across 13 tracks) | ✅ Covered — core strength |
| AI / ML Architect *(seniority)* | **50** | — | Covered (AI/ML Architect outcome) | ✅ Covered — well-aligned |
| MLOps / LLMOps Engineer | **46** | 46 | Partial — concentrated in Flagship ML only | 🟠 **Strengthen** |
| Prompt Engineer | 19 | 19 | Covered as skill (not named role) | ✅ Covered |
| AI Platform / Infra / Inference | 4 | 4 | Thin — no serving/inference track | 🟠 Emerging gap (small) |
| RAG / Retrieval Engineer | 4* | 4 | Deep (Agentic RAG, GraphRAG, hybrid) | ✅ Covered |
| AI Safety / Governance | 4 | 4 | Partial (guardrails, RBAC, PII) | ⚪ Low India demand — watch |
| Applied AI / Research Scientist | 3 | 3 | Gap (IK is applied, not research) | ⚪ Low demand — likely intentional |
| Forward-Deployed AI Engineer | 1 | 1 | Not positioned | ⚪ Negligible India signal |

\*RAG/LLM-Engineer/Prompt counts understate true demand — those skills appear *inside* GenAI roles (RAG skill = 31% of all postings), not as standalone titles.

---

## 2. Skills/tools demand vs curriculum (the sharper signal)

| Skill / Tool | % of postings | In IK curriculum? | Note |
|---|---|---|---|
| **Agents / tool use** | **41%** | ✅ Yes (deep) | IK's #1 strength = market's #1 skill |
| **RAG** | **31%** | ✅ Yes (deep) | Agentic RAG, GraphRAG, hybrid |
| **Azure** | **23%** | ❌ **No (AWS-only)** | 🔴 **Top gap** |
| AWS | 20% | ✅ Yes | — |
| Fine-tuning (LoRA/PEFT) | 20% | ✅ Yes | — |
| Prompt Engineering | 20% | ✅ Yes | — |
| **LLM Eval (LangSmith/RAGAS/DeepEval)** | **20%** | ✅ Yes (taught, not branded a role) | Elevate to named outcome |
| LangChain | 20% | ✅ Yes | — |
| Vector DB (FAISS/Chroma/Qdrant) | 16% | ✅ Yes | (auto-tool flagged this wrong; IK *does* teach it) |
| TensorFlow / PyTorch | 15% / 15% | ✅ Yes (Flagship ML / DS) | — |
| **GCP / Vertex AI** | **14%** | ❌ **No** | 🔴 Cloud gap |
| LangGraph | 10% | ✅ Yes | — |

**Read:** IK matches the market on the *AI substance* (agents, RAG, fine-tuning, eval, vector DBs, LangChain/LangGraph). The clearest, highest-ROI miss is **cloud breadth** — the market increasingly asks for **Azure (23%) and GCP (14%)**, and IK teaches **AWS only**.

---

## 3. What the "novelty net" caught (light lens-2)

75 rows (40 distinct titles) mapped to *no* known role bucket. The point of this net was to catch genuinely new naming. Finding:

- **Mostly nomenclature, not new capability:** `AI Developer` (10), `AIML Engineer` (10), `AI/ML Developer` (3), `AI Specialist`, `AI Consultant` — India-market synonyms for roles IK already trains.
- **A few worth noting:** `Applied Research Scientist – AI Models & Agents` (research-leaning, not IK's applied audience); `Software Engineer, ML Systems` (ML-infra leaning); `AI Developer – Agent Specialist` (agentic, covered).
- **Takeaway:** the absence of a long tail of net-new *role types* is itself the finding — **IK's catalog spans the role space; the market is iterating on titles, not inventing categories.**

---

## 4. Prioritized recommendations (to update the Program Master Index)

| # | Action | Why (evidence) | Effort |
|---|---|---|---|
| 1 | **Stay the course on Agentic + GenAI + RAG** | #1–2 role clusters (124, 66) and #1–2 skills (Agents 41%, RAG 31%) | None — validation |
| 2 | **Add Azure AI + GCP Vertex modules** (cross-track) | Azure 23% (≥ AWS), GCP 14%; IK is AWS-only | Medium — highest ROI |
| 3 | **Stand up a dedicated LLMOps / AI-Platform module** | 46 MLOps roles in-window; thin outside Flagship ML; AI-Platform/Inference emerging | Medium |
| 4 | **Brand "AI Evaluation Engineer" as a named outcome/badge** | Eval skills 20% + emerging "Eval Engineer" titles; already taught | Low — repackage |
| 5 | **Marketing/SEO: align titles to India search terms** | "AI/ML Developer", "AIML Engineer", "AI Developer" dominate India naming | Low |
| 6 | **Watch, don't build yet:** AI Safety/Governance, Forward-Deployed, AI Research | Low India demand now (4/1/3) — revisit next quarter | Monitor |

---

## 5. Honest caveats (read before presenting)

- **2-month point-in-time sample, not a time-trend** — "emerging" = present-and-novel relative to IK's curriculum and canonical roles, not a measured rise over time (no historical baseline exists).
- **Sample, not census** — 658 rows from 2 sources under a $2.23 budget; counts show *relative* demand reliably, not absolute market size. Naukri stopped at 4/8 queries (budget ceiling), so Naukri is under-weighted vs LinkedIn.
- **Skills mined from job descriptions** by keyword match — directional, not exhaustive.
- **Coverage judgments** corrected manually against `curriculum_coverage.json` (auto-flags had false negatives, e.g. Vector DB, LLM-Eval).
- Everything is reproducible from `emerging_rows.json` + `emerging_aggregates.json` + the raw per-query JSON.

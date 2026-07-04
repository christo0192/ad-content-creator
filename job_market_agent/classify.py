"""AI-role taxonomy filter + India company-tier rubric + salary/date parsing.

GUARDRAIL: only titles matching the AI include-taxonomy survive; healthcare,
finance, sales, generic SWE, etc. are dropped. Role family + normalized bucket
assigned. Company tier classified against a curated India rubric; unknown
companies are honestly labelled 'Unclassified' (never fabricated).
"""
import re
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# 1. AI ROLE TAXONOMY  (pattern, normalized_bucket, family). First match wins.
# Families: A=Core, B=GenAI/LLM/NLP/CV, C=MLOps/Infra, D=AI-adjacent data&product
# ---------------------------------------------------------------------------
INCLUDE = [
    (r"\b(generative ai|gen[\s\-]?ai|llm|large language model|foundation model)\b", "GenAI / LLM Engineer", "B"),
    (r"\bprompt engineer", "Prompt Engineer", "B"),
    (r"\b(nlp|natural language)\b", "NLP Engineer", "B"),
    (r"\b(computer vision|cv engineer|image processing)\b", "Computer Vision Engineer", "B"),
    (r"\bdeep learning\b", "Deep Learning Engineer", "B"),
    (r"\bml[\s\-]?ops\b", "MLOps Engineer", "C"),
    (r"\b(ml|ai) (platform|infrastructure|infra|systems)\b", "ML Platform / AI Infra", "C"),
    (r"\b(ml|ai) (engineer|developer).*(platform|infra)\b", "ML Platform / AI Infra", "C"),
    (r"\bmachine learning\b", "Machine Learning Engineer", "A"),
    (r"\bml engineer\b", "Machine Learning Engineer", "A"),
    (r"\bdata scientist\b", "Data Scientist", "A"),
    (r"\b(applied scientist|research scientist|ai researcher|research engineer)\b", "AI Research / Applied Scientist", "A"),
    (r"\b(ai|a\.i\.|artificial intelligence) (engineer|developer|specialist|lead|consultant)\b", "AI Engineer", "A"),
    (r"\bai engineer\b", "AI Engineer", "A"),
    (r"\b(ai|ml) (architect)\b", "AI / ML Architect", "D"),
    (r"\bdata engineer\b", "Data Engineer", "D"),
    (r"\b(analytics engineer)\b", "Analytics Engineer", "D"),
    (r"\bdata analyst\b", "Data Analyst", "D"),
    (r"\b(ai|ml) product manager\b", "AI Product Manager", "D"),
    (r"\b(ai/ml|ml/ai|aiml)\b", "AI/ML Engineer", "A"),
]

EXCLUDE = [
    r"\b(nurse|physician|clinical|medical|pharma|healthcare|radiolog|therapist|dentist)\b",
    r"\b(accountant|auditor|investment banker|teller|underwrit|actuar|tax )\b",
    r"\b(sales|business development|account executive|telecaller|bpo|customer support|call center)\b",
    r"\b(recruiter|talent acquisition|hr executive|human resources)\b",
    r"\b(civil|mechanical|electrical|chemical) engineer\b",
    r"\b(driver|electrician|plumber|technician|welder|fitter)\b",
    r"\b(content writer|graphic designer|video editor|social media)\b",
]
AMBIGUOUS_EXCLUDE = [r"\bbusiness analyst\b"]

FAMILY_NAME = {
    "A": "Core ML/AI",
    "B": "GenAI / LLM / NLP / CV",
    "C": "MLOps / AI Infrastructure",
    "D": "AI-adjacent Data & Product",
}

_inc = [(re.compile(p, re.I), b, f) for p, b, f in INCLUDE]
_exc = [re.compile(p, re.I) for p in EXCLUDE]
_amb = [re.compile(p, re.I) for p in AMBIGUOUS_EXCLUDE]
_ai_ctx = re.compile(r"\b(ai|ml|machine learning|data scien|analytic)\b", re.I)


def classify_role(title):
    """Return (keep: bool, normalized_bucket, family_code, family_name)."""
    if not title:
        return False, None, None, None
    t = title.lower()
    for rx in _exc:
        if rx.search(t):
            return False, None, None, None
    for rx in _amb:
        if rx.search(t) and not _ai_ctx.search(t):
            return False, None, None, None
    for rx, bucket, fam in _inc:
        if rx.search(t):
            return True, bucket, fam, FAMILY_NAME[fam]
    return False, None, None, None


# ---------------------------------------------------------------------------
# 2. INDIA COMPANY TIER RUBRIC
# ---------------------------------------------------------------------------
TIER1_BIGTECH = {
    "google", "microsoft", "amazon", "meta", "facebook", "apple", "netflix",
    "nvidia", "adobe", "uber", "linkedin", "salesforce", "oracle", "ibm",
    "intel", "qualcomm", "samsung", "openai", "anthropic", "databricks",
    "atlassian", "paypal", "visa", "mastercard", "goldman sachs", "morgan stanley",
    "walmart", "walmart global tech", "deloitte ai",
}
TIER2_SERVICES_UNICORN = {
    "tcs", "tata consultancy", "infosys", "wipro", "hcl", "tech mahindra",
    "accenture", "cognizant", "capgemini", "ltimindtree", "mphasis", "persistent",
    "flipkart", "swiggy", "zomato", "razorpay", "freshworks", "paytm", "phonepe",
    "ola", "byju", "meesho", "cred", "dream11", "nykaa", "zoho", "myntra",
    "fractal", "tiger analytics", "mu sigma", "course5", "quantiphi", "genpact",
    "ey", "kpmg", "pwc", "deloitte",
}
TIER2_HINTS = ("technologies", "consultancy", "solutions", "infotech", "systems", "services")
STAFFING_HINTS = ("staffing", "recruit", "consultancy services", "manpower",
                  "hiring", "placement", "talent", "hr services")


def classify_tier(company):
    if not company:
        return "Unclassified"
    c = company.lower().strip()
    base = re.sub(r"[^a-z0-9 ]", "", c)
    for k in TIER1_BIGTECH:
        if k in base:
            return "T1 - Global Big Tech / Product"
    for k in TIER2_SERVICES_UNICORN:
        if k in base:
            return "T2 - Indian IT / GCC / Unicorn"
    if any(h in base for h in STAFFING_HINTS):
        return "T4 - Staffing / Consultancy (proxy employer)"
    if any(base.endswith(h) or (" " + h) in base for h in TIER2_HINTS):
        return "T3 - Funded / Mid-size Product"
    return "Unclassified"


# ---------------------------------------------------------------------------
# 3. SALARY normalize (best-effort) + INR LPA range parse
# ---------------------------------------------------------------------------
def normalize_salary(raw):
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s or s.lower() in ("not disclosed", "none", "n/a", "unpaid", "0"):
        return ""
    return s[:120]


_LPA = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|to|–)\s*(\d+(?:\.\d+)?)\s*(?:lpa|lakh|l\b)", re.I)
_LPA_SINGLE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lpa|lakh|l\b)", re.I)


def parse_salary_inr(raw):
    """Best-effort -> (min_inr, max_inr) absolute rupees, or (None, None).
    LinkedIn India rarely populates salary; this is opportunistic only."""
    if not raw:
        return None, None
    s = str(raw)
    m = _LPA.search(s)
    if m:
        return int(float(m.group(1)) * 100000), int(float(m.group(2)) * 100000)
    m = _LPA_SINGLE.search(s)
    if m:
        v = int(float(m.group(1)) * 100000)
        return v, v
    return None, None


# ---------------------------------------------------------------------------
# 4. DATE parse + in-window check
# ---------------------------------------------------------------------------
_REL = re.compile(r"(\d+)\s*(day|days|week|weeks|month|months|hour|hours|minute|min)", re.I)


def parse_posted(raw, report_date):
    """Return (date or None, raw_string). Handles ISO, epoch, '3 days ago', etc."""
    if raw is None:
        return None, ""
    s = str(raw).strip()
    if not s:
        return None, ""
    if re.fullmatch(r"\d{10,13}", s):
        try:
            v = int(s)
            if v > 1e12:
                v /= 1000
            return datetime.utcfromtimestamp(v).date(), s
        except Exception:
            pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(s[:len(fmt) + 4], fmt).date(), s
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date(), s
    except Exception:
        pass
    m = _REL.search(s)
    if m:
        n = int(m.group(1)); unit = m.group(2).lower()
        days = {"hour": 0, "minute": 0, "min": 0, "day": 1, "week": 7, "month": 30}
        d = days.get(unit.rstrip("s"), 1) * n
        return report_date - timedelta(days=d), s
    if re.search(r"just posted|today|new|hour|minute", s, re.I):
        return report_date, s
    return None, s


def in_window(d, window_start, report_date):
    if d is None:
        return None  # unknown
    return window_start <= d <= report_date

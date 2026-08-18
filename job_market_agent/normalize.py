"""Map a raw LinkedIn job item -> a unified, defensively-typed row.

LinkedIn `curious_coder/linkedin-jobs-scraper` schema (observed 2026-06):
  id, link, title, companyName, companyLinkedinUrl, location, postedAt,
  salary (usually ""), descriptionText, applicantsCount (str, capped "200"),
  seniorityLevel, employmentType, jobFunction, industries, companyWebsite, ...
"""
import re


def first(d, keys, default=""):
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return default


def _flatten(v):
    if isinstance(v, dict):
        for k in ("name", "text", "label", "value", "title", "localizedName"):
            if k in v and isinstance(v[k], str):
                return v[k]
        return " ".join(str(x) for x in v.values() if isinstance(x, (str, int)))[:160]
    if isinstance(v, list):
        return ", ".join(_flatten(x) if isinstance(x, (dict, list)) else str(x) for x in v)[:200]
    return "" if v is None else str(v)


def _int_or_none(v):
    if v in (None, ""):
        return None
    m = re.search(r"\d+", str(v))
    return int(m.group(0)) if m else None


def normalize_linkedin(item):
    """Return the unified LinkedIn row (raw, pre-classification)."""
    return {
        "source": "LinkedIn",
        "job_id": str(first(item, ["id", "trackingId", "refId"])),
        "title": first(item, ["title", "jobTitle"]),
        "company": _flatten(first(item, ["companyName", "company"])),
        "location": _flatten(first(item, ["location"])),
        "salary_raw": first(item, ["salary"]),
        "posted_raw": str(first(item, ["postedAt", "postedDate", "listedAt"])),
        "url": first(item, ["link", "applyUrl", "url"]),
        "seniority_level": first(item, ["seniorityLevel"]) or None,
        "employment_type": first(item, ["employmentType"]) or None,
        "job_function": _flatten(first(item, ["jobFunction"])) or None,
        "industries": _flatten(first(item, ["industries"])) or None,
        "applicants_count": _int_or_none(item.get("applicantsCount")),
        "company_website": first(item, ["companyWebsite"]) or None,
        "description": str(first(item, ["descriptionText"]))[:2000],
    }


_TAG = re.compile(r"<[^>]+>")


def _naukri_skills_flat(skills):
    """thirdwatch `skills` is a list (or a stringified list like "['a','b']").
    Return a comma-joined string so scoring.extract_skills can pick tools up."""
    if isinstance(skills, list):
        return ", ".join(str(s) for s in skills if s)
    if isinstance(skills, str) and skills.strip():
        s = skills.strip()
        if s.startswith("["):
            try:
                import ast
                parsed = ast.literal_eval(s)
                if isinstance(parsed, list):
                    return ", ".join(str(x) for x in parsed if x)
            except Exception:
                pass
        return s
    return ""


def _naukri_salary_flat(item):
    """thirdwatch exposes salary_raw + salary_disclosed. Return a parseable
    string, or 'Not Disclosed'."""
    if not item.get("salary_disclosed"):
        return "Not Disclosed"
    raw = str(item.get("salary_raw") or "").strip()
    if raw:
        return raw
    lo, hi = item.get("salary_min") or 0, item.get("salary_max") or 0
    cur = item.get("salary_currency") or "INR"
    if lo or hi:
        return f"{lo}-{hi} {cur}"
    return "Not Disclosed"


def normalize_naukri(item):
    """Map a raw Naukri item (`thirdwatch/naukri-jobs-scraper`, flat 60-field
    schema) -> the same unified row shape as normalize_linkedin.

    thirdwatch is ~10x cheaper than the muhammetakkurtt detailed actor and
    returns a FLAT payload (no jobDetails nesting), with posted_date already
    ISO, a real skills list, and broken-out salary fields."""
    if not isinstance(item, dict):
        item = {}

    desc = _TAG.sub(" ", str(item.get("description") or ""))
    skills_txt = _naukri_skills_flat(item.get("skills"))

    return {
        "source": "Naukri",
        "job_id": str(item.get("job_id") or ""),
        "title": item.get("title") or "",
        "company": item.get("company_name") or "",
        "location": item.get("location") or "",
        "salary_raw": _naukri_salary_flat(item),
        # posted_date is already 'YYYY-MM-DD'; created_at is ISO — either parses.
        "posted_raw": str(item.get("posted_date") or item.get("created_at") or ""),
        "url": item.get("apply_url") or item.get("external_apply_url") or "",
        # Naukri has no LinkedIn-style seniority; carry experience as a hint.
        "seniority_level": item.get("experience") or None,
        "employment_type": item.get("employment_type") or None,
        "job_function": item.get("functional_area") or None,
        "industries": item.get("industry") or None,
        "applicants_count": _int_or_none(item.get("applicant_count")),
        "company_website": item.get("company_website") or None,
        # fold skills into description text so extract_skills captures them
        "description": (desc + " | Skills: " + skills_txt)[:2000],
    }

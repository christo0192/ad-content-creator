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

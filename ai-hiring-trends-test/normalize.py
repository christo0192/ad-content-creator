"""Map each actor's raw output to a unified row:
  {source, title, company, location, salary, posted_raw, url}
Defensive: tries candidate keys and digs into dict-typed fields so it tolerates
schema variation across third-party actors.
"""
import re


def first(d, keys, default=""):
    for k in keys:
        if k in d and d[k] not in (None, "", [], {}):
            return d[k]
    return default


def dig(val, subkeys, default=""):
    """If val is a dict, return first present subkey; if str, return it."""
    if isinstance(val, dict):
        for k in subkeys:
            if k in val and val[k] not in (None, "", [], {}):
                v = val[k]
                return v if not isinstance(v, (dict, list)) else _flatten(v)
        return default
    if isinstance(val, list):
        return _flatten(val)
    return val if val not in (None,) else default


def _flatten(v):
    if isinstance(v, dict):
        for k in ("name", "text", "label", "value", "title", "localizedName"):
            if k in v and isinstance(v[k], str):
                return v[k]
        return " ".join(str(x) for x in v.values() if isinstance(x, (str, int)))[:120]
    if isinstance(v, list):
        return ", ".join(_flatten(x) if isinstance(x, (dict, list)) else str(x) for x in v)[:160]
    return str(v)


def _from_extensions(item):
    """Google Jobs: detected_extensions dict + extensions list of human strings."""
    salary = posted = ""
    de = item.get("detected_extensions")
    if isinstance(de, dict):
        posted = de.get("posted_at", "") or ""
        salary = de.get("salary", "") or ""
    ext = item.get("extensions")
    if isinstance(ext, list):
        for e in ext:
            es = str(e)
            if not posted and re.search(r"(day|hour|week|month|ago|posted)", es, re.I):
                posted = es
            if not salary and re.search(r"(₹|\$|lpa|per year|per month|a year|k\b|lakh)", es, re.I):
                salary = es
    return salary, posted


def normalize_row(source, item, report_date=None):
    s = source.lower()
    if "linkedin" in s:
        return {
            "source": source,
            "title": first(item, ["title", "jobTitle"]),
            "company": first(item, ["companyName", "company"]),
            "location": first(item, ["location"]),
            "salary": first(item, ["salary"]),
            "posted_raw": str(first(item, ["postedAt", "postedDate", "listedAt"])),
            "url": first(item, ["link", "applyUrl", "url"]),
        }
    if "google" in s:
        salary, posted = _from_extensions(item)
        return {
            "source": source,
            "title": first(item, ["title", "job_title"]),
            "company": first(item, ["company_name", "company"]),
            "location": first(item, ["location"]),
            "salary": salary,
            "posted_raw": posted,
            "url": first(item, ["share_link", "source_link", "url"]),
        }
    if "glassdoor" in s:
        age = item.get("ageInDays")
        posted = ""
        if age not in (None, "") and report_date is not None:
            try:
                from datetime import timedelta
                posted = str(report_date - timedelta(days=int(age)))
            except Exception:
                posted = f"{age} days ago"
        return {
            "source": source,
            "title": first(item, ["title"]),
            "company": dig(item.get("employer"), ["name", "shortName", "employerName"]) or first(item, ["employer"]),
            "location": dig(item.get("location"), ["localizedName", "name", "cityName", "text"]) or first(item, ["location"]),
            "salary": dig(item.get("pay"), ["salaryText", "payText", "text", "median", "minimum", "maximum"]),
            "posted_raw": posted,
            "url": first(item, ["url", "seoUrl"]),
        }
    if "foundit" in s:
        return {
            "source": source,
            "title": first(item, ["title"]),
            "company": dig(item.get("company"), ["name", "companyName", "text"]) or first(item, ["company"]),
            "location": _flatten(first(item, ["locations", "location"])),
            "salary": dig(item.get("salary"), ["text", "label", "value", "salaryText", "min", "max"]),
            "posted_raw": dig(item.get("postingDetails"), ["postedOn", "date", "postedDate", "text"]),
            "url": dig(item.get("urls"), ["jobUrl", "url", "detailUrl"]) or first(item, ["url"]),
        }
    if "hackernews" in s or "hacker news" in s:
        text = str(first(item, ["text"]))
        parts = [p.strip() for p in re.split(r"\s*\|\s*", text) if p.strip()]
        company = parts[0][:80] if parts else first(item, ["company"])
        title = parts[1][:120] if len(parts) > 1 else text[:120]
        loc = parts[2][:80] if len(parts) > 2 else ("Remote" if str(item.get("remote")).lower() == "true" else "")
        sal = ""
        m = re.search(r"(₹|\$)\s?[\d,.]+\s?[kK]?(\s?-\s?(₹|\$)?\s?[\d,.]+\s?[kK]?)?", text)
        if m:
            sal = m.group(0)
        return {
            "source": source,
            "title": title,
            "company": company,
            "location": loc,
            "salary": sal,
            "posted_raw": str(first(item, ["createdAt"])),
            "url": first(item, ["url"]),
        }
    if "naukri" in s:
        jd = item.get("jobDetails") if isinstance(item.get("jobDetails"), dict) else item
        comp = jd.get("staticCompanyName", "") or dig(jd.get("companyDetail"), ["name", "companyName"])
        if comp:  # 'hcltech-jobs-careers-460' -> 'Hcltech'
            comp = re.split(r"-jobs-careers", str(comp))[0].replace("-", " ").strip().title()
        sal = jd.get("salaryDetail")
        return {
            "source": source,
            "title": jd.get("title", ""),
            "company": comp,
            "location": _flatten(jd.get("locations") or jd.get("placeholders")),
            "salary": (dig(sal, ["label", "text", "salary"]) if isinstance(sal, dict) else (sal or "")),
            "posted_raw": str(jd.get("createdDate", "")),
            "url": jd.get("staticUrl", "") or jd.get("companyPageUrl", ""),
        }
    # Generic fallback (Indeed / unknown) — defensive resolver
    return {
        "source": source,
        "title": first(item, ["title", "jobTitle", "job_title", "position", "name", "designation"]),
        "company": _flatten(first(item, ["companyName", "company", "employerName", "employer", "company_name", "organization", "hiringCompany"])),
        "location": _flatten(first(item, ["location", "jobLocation", "locations", "place", "places", "city"])),
        "salary": _flatten(first(item, ["salary", "ctc", "salaryDetail", "payRange", "compensation", "salaryRange", "package"])),
        "posted_raw": str(first(item, ["postedDate", "postedAt", "createdDate", "datePosted", "postedOn", "date", "footerPlaceholderLabel", "freshness"])),
        "url": first(item, ["url", "jobUrl", "link", "jdURL", "jobLink", "detailUrl"]),
    }

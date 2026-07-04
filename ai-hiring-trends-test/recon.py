"""Recon: pull clean pay-per-event pricing + input-schema fields for candidate actors.
Token read from APIFY_TOKEN env var (never hardcoded). Read-only — spends nothing."""
import os, json, sys
import requests

TOKEN = os.environ.get("APIFY_TOKEN")
if not TOKEN:
    sys.exit("APIFY_TOKEN env var not set")

CANDIDATES = [
    "curious_coder~linkedin-jobs-scraper",
    "johnvc~Google-Jobs-Scraper",
    "muhammetakkurtt~naukri-job-scraper",
    "thirdwatch~naukri-jobs-scraper",
    "memo23~naukri-scraper",
    "cheap_scraper~glassdoor-jobs-scraper-remove-duplicate-jobs",
    "valig~glassdoor-jobs-scraper",
    "easyapi~foundit-jobs-scraper",
    "borderline~indeed-scraper",
    "agency-shift~hackernews-jobs-ask-scraper",
]

S = requests.Session()

def get(url):
    r = S.get(url, timeout=60)
    r.raise_for_status()
    return r.json()

def pricing(act):
    pis = act.get("pricingInfos") or []
    if not pis:
        cp = act.get("currentPricingInfo") or {}
        return cp.get("pricingModel", "FREE?"), []
    cur = pis[-1]
    model = cur.get("pricingModel")
    lines = []
    if model == "PAY_PER_EVENT":
        ev = (cur.get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
        for k, v in ev.items():
            price = v.get("eventPriceUsd")
            lines.append(f"{k}=${price} (primary={v.get('isPrimaryEvent')})")
    elif model == "PRICE_PER_DATASET_ITEM":
        lines.append(f"${cur.get('pricePerUnitUsd')}/{cur.get('unitName')}")
    elif model == "FLAT_PRICE_PER_MONTH":
        lines.append(f"RENTAL ${cur.get('pricePerUnitUsd')}/mo NEEDS-PAID-PLAN")
    return model, lines

def input_fields(actor_id):
    """Read input schema field names + required from the default build."""
    try:
        b = get(f"https://api.apify.com/v2/acts/{actor_id}/builds/default?token={TOKEN}")
        sch = b.get("data", {}).get("inputSchema")
        if isinstance(sch, str):
            sch = json.loads(sch)
        if not sch:
            return None, []
        props = sch.get("properties", {})
        req = sch.get("required", [])
        fields = []
        for name, spec in props.items():
            t = spec.get("type")
            ex = spec.get("prefill", spec.get("default"))
            mark = "*" if name in req else " "
            fields.append(f"{mark}{name}:{t}" + (f"={ex}" if ex not in (None, [], {}) else ""))
        return req, fields
    except Exception as e:
        return None, [f"<schema err: {e}>"]

for a in CANDIDATES:
    print("=" * 70)
    print(a)
    try:
        act = get(f"https://api.apify.com/v2/acts/{a}?token={TOKEN}")["data"]
    except Exception as e:
        print("  ACT ERR:", e); continue
    model, lines = pricing(act)
    print("  PRICING:", model)
    for l in lines:
        print("    ", l)
    req, fields = input_fields(a)
    print("  REQUIRED:", req)
    print("  INPUT FIELDS:")
    for f in fields[:40]:
        print("    ", f)

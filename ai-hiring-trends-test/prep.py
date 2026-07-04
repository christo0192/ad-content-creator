"""Smoke-test prep (read-only, $0): verify the NEW account + pull pricing for
candidate actors so we pick the cheapest viable one per site."""
import os, sys, json
import requests

TOKEN = os.environ.get("APIFY_TOKEN")
if not TOKEN:
    sys.exit("APIFY_TOKEN not set")
API = "https://api.apify.com/v2"
S = requests.Session()


def get(u):
    r = S.get(u, timeout=40); r.raise_for_status(); return r.json()


# Account
try:
    u = get(f"{API}/users/me?token={TOKEN}")["data"]
    lim = get(f"{API}/users/me/limits?token={TOKEN}")["data"]
    print("ACCOUNT:", u.get("username"), "| id:", u.get("id"), "| plan:", (u.get("plan") or {}).get("id"))
    print("  monthly cap $", lim["limits"]["maxMonthlyUsageUsd"],
          "| used $", round(lim["current"]["monthlyUsageUsd"], 4),
          "| cycle ends", lim["monthlyUsageCycle"]["endAt"][:10])
except Exception as e:
    print("ACCOUNT ERR:", e)

CANDS = [
    ("Naukri", "muhammetakkurtt~naukri-job-scraper"),
    ("Naukri-alt", "thirdwatch~naukri-jobs-scraper"),
    ("Google-PPR", "johnvc~google-jobs-scraper---pay-per-result"),
    ("Google-igview", "igview-owner~google-jobs-scraper"),
    ("Google-orgupdate", "orgupdate~google-jobs-scraper"),
    ("Indeed", "borderline~indeed-scraper"),
    ("Glassdoor-valig", "valig~glassdoor-jobs-scraper"),
    ("Glassdoor-cheap", "cheap_scraper~glassdoor-jobs-scraper-remove-duplicate-jobs"),
    ("Foundit", "easyapi~foundit-jobs-scraper"),
    ("HackerNews", "agency-shift~hackernews-jobs-ask-scraper"),
    ("LinkedIn", "curious_coder~linkedin-jobs-scraper"),
]

print("\nPRICING (per-event decomposed; $None => hidden, must measure):")
for label, aid in CANDS:
    try:
        act = get(f"{API}/acts/{aid}?token={TOKEN}")["data"]
        pis = act.get("pricingInfos") or []
        if not pis:
            print(f"  {label:<18} {aid:<55} FREE/none"); continue
        cur = pis[-1]
        model = cur.get("pricingModel")
        parts = []
        if model == "PAY_PER_EVENT":
            ev = (cur.get("pricingPerEvent") or {}).get("actorChargeEvents") or {}
            for k, v in ev.items():
                parts.append(f"{k}=${v.get('eventPriceUsd')}")
        elif model == "PRICE_PER_DATASET_ITEM":
            parts.append(f"${cur.get('pricePerUnitUsd')}/item")
        elif model == "FLAT_PRICE_PER_MONTH":
            parts.append(f"RENTAL ${cur.get('pricePerUnitUsd')}/mo")
        print(f"  {label:<18} {aid:<55} {model}: {', '.join(parts)}")
    except Exception as e:
        print(f"  {label:<18} {aid:<55} ERR {e}")

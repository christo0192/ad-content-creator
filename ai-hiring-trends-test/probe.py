"""Calibration probe: tiny run per actor to capture REAL output schema + REAL cost.
Validates the full launch->poll->fetch->bill flow within a few cents."""
import os, json, sys, time
import config as C
import harness as H

OUT_RAW = os.path.join(os.path.dirname(__file__), "raw")
os.makedirs(OUT_RAW, exist_ok=True)

gov = H.BudgetGovernor()
summary = []

for entry in C.ROSTER:
    site = entry["site"]
    actor = entry["actor"]
    q = entry["queries"][0]
    label = f"probe:{site}"
    print("\n" + "=" * 64)
    print(f"PROBE {site}  ({actor})  query='{q}'  maxItems={C.PROBE_MAX_ITEMS}")
    try:
        run_input = entry["build_input"](q, C.PROBE_MAX_ITEMS)
        items, cost, meta = H.run_actor(actor, run_input, gov, label,
                                         memory_mb=None, timeout_s=180)
    except H.BudgetExceeded as e:
        print(f"  !! BUDGET STOP: {e}")
        summary.append({"site": site, "status": "BUDGET-STOP", "n": 0, "cost": 0})
        break
    except Exception as e:
        print(f"  !! ERROR: {e}")
        summary.append({"site": site, "status": f"ERR:{e}", "n": 0, "cost": 0})
        continue

    # Save raw
    safe = site.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
    with open(os.path.join(OUT_RAW, f"probe_{safe}.json"), "w", encoding="utf-8") as f:
        json.dump({"input": run_input, "meta": meta, "items": items}, f,
                  ensure_ascii=False, indent=2)

    print(f"  status={meta.get('status')}  items={meta.get('n_items')}  "
          f"cost=${meta.get('cost_usd')}  session=${meta.get('session_spent')}  "
          f"elapsed={meta.get('elapsed_s')}s")
    if meta.get("error"):
        print("  launch-error:", meta["error"][:300])
    if items:
        keys = sorted(items[0].keys())
        print("  FIELD KEYS:", keys)
        # print a compact sample of the first item's most useful fields
        s0 = items[0]
        preview = {k: (str(s0[k])[:80] if not isinstance(s0[k], (dict, list)) else type(s0[k]).__name__)
                   for k in keys[:25]}
        print("  SAMPLE:", json.dumps(preview, ensure_ascii=False)[:1000])
    summary.append({"site": site, "status": meta.get("status"),
                    "n": meta.get("n_items"), "cost": meta.get("cost_usd")})

print("\n" + "#" * 64)
print("PROBE SUMMARY")
for s in summary:
    print(f"  {s['site']:<28} {str(s['status']):<12} items={s['n']:<5} cost=${s['cost']}")
print(f"TOTAL SESSION SPEND: ${gov.session_spent:.4f}  (baseline ${gov.baseline:.4f})")

# Deploy on Fly.io (weekly scheduled Machine)

Batch job: boots weekly, runs the 3 weekly agents + Executive Summary, writes
BigQuery, exits. The image bundles **Python + the Claude Code CLI** because all
LLM calls go through `claude -p`.

## Prereqs

- `flyctl` installed + logged in
- `market-research-bq@` service-account key (see `../job_market_agent/IAM_REQUEST.md`)
- A **Claude Code OAuth token** for headless auth on the Max plan:
  ```bash
  claude setup-token        # run locally; copies a long-lived token
  ```
- (optional) Apify acct #2 token if you want Reddit in the Social tab

## 1. Create app + image

```bash
cd market_research
fly apps create ik-market-research-weekly      # match fly.toml
fly deploy --ha=false
```

## 2. Secrets

```bash
# Claude Code Max-plan auth (so `claude -p` works headless in the container)
fly secrets set CLAUDE_CODE_OAUTH_TOKEN="<from claude setup-token>" -a ik-market-research-weekly

# BigQuery writer SA (base64 of the JSON key)
fly secrets set MARKET_RESEARCH_BQ_SA_B64="$(base64 -w0 market-research-bq.json)" -a ik-market-research-weekly

# optional: Reddit
fly secrets set APIFY_TOKEN="<acct2 token>" -a ik-market-research-weekly
```

Non-secret config (`MR_BQ_DATASET=Market_Research`, model names) is in `fly.toml [env]`.

## 3. Register the weekly run

```bash
fly machine run . --schedule weekly --restart no --region sin -a ik-market-research-weekly
```

`--schedule` ∈ `hourly|daily|weekly|monthly`. The job runs, writes BQ, exits;
`--restart no` keeps it a clean cron tick.

## 4. Verify

```bash
# manual one-off (don't wait a week):
fly machine run . --restart no --region sin -a ik-market-research-weekly \
  --command "python run_weekly.py"
fly logs -a ik-market-research-weekly

# rows landed:
#   SELECT 'social' t, COUNT(*) n FROM `ik-marketing-data.Market_Research.social_trends`     WHERE run_date=CURRENT_DATE()
#   UNION ALL SELECT 'blog',  COUNT(*) FROM `ik-marketing-data.Market_Research.blog_publications` WHERE run_date=CURRENT_DATE()
#   UNION ALL SELECT 'comp',  COUNT(*) FROM `ik-marketing-data.Market_Research.competitor_intel`  WHERE run_date=CURRENT_DATE()
#   UNION ALL SELECT 'exec',  COUNT(*) FROM `ik-marketing-data.Market_Research.executive_summary` WHERE run_date=CURRENT_DATE();
```

## Notes

- **Two scheduled Machines total** for the whole product: this one (`weekly`) +
  the job-market one (`monthly`, in `../job_market_agent`). Both write the same
  `Market_Research` dataset.
- **Image size:** installs Node + `@anthropic-ai/claude-code`. First build is a
  few minutes; cached after.
- **Rate limits:** `MR_LLM_CONCURRENCY` bounds parallel `claude -p` calls so a run
  stays within Max-plan limits. Lower it if you see throttling in logs.
- **Ephemeral FS:** `output/*.json` snapshots vanish on stop — BigQuery is the
  durable store.
- **Token rotation:** `CLAUDE_CODE_OAUTH_TOKEN` is long-lived but rotate it like
  any secret; re-run `claude setup-token` and `fly secrets set` to refresh.
```

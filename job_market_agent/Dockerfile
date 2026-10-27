# Batch job image for the monthly job-market agent (Naukri on Fly via
# JOBMKT_SOURCE). Runs once and exits -> a stopped Fly Machine that the
# Cloudflare Worker ik-intelligence-trigger starts monthly (no Fly --schedule).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only the runtime modules (no raw/output/logs, no PowerShell scripts).
COPY config.py harness.py normalize.py classify.py scoring.py \
     schema.py bigquery_writer.py run_monthly.py ./

# LIVE run by default. The Worker starts the Machine, this runs to completion,
# exits (0 OK / 2 preflight failed, nothing spent / 3 zero rows), and the
# Machine stops. Smoke without spend: --command "python run_monthly.py --preflight".
CMD ["python", "run_monthly.py"]

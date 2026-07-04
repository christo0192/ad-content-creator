# Batch job image for the monthly LinkedIn job-market agent.
# Runs once and exits -> fits a Fly.io scheduled Machine (--schedule monthly).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only the runtime modules (no raw/output/logs, no PowerShell scripts).
COPY config.py harness.py normalize.py classify.py scoring.py \
     schema.py bigquery_writer.py run_monthly.py ./

# LIVE run by default. The scheduled Machine starts the container, this runs to
# completion, exits 0, and the Machine stops.
CMD ["python", "run_monthly.py"]

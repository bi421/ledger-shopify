from prefect import flow, task
import polars as pl
import requests
from datetime import datetime, timedelta
from src.trueroas.config import get_settings
from src.trueroas.engine import engine

@task(retries=3, retry_delay_seconds=60)
def notify_slack(account_id: str, score: int):
    """Sends a Slack alert if the audit score is below threshold."""
    settings = get_settings()
    webhook_url = settings.SLACK_WEBHOOK_URL
    
    if webhook_url and score < 90:
        payload = {
            "text": (
                f"🚨 *TrueROAS Audit Alert*\n"
                f"*Account ID:* `{account_id}`\n"
                f"*Health Score:* `{score}/100`\n"
                f"Status: *Low data reliability detected. Audit required.*"
            )
        }
        requests.post(webhook_url, json=payload)

@task(retries=3, retry_delay_seconds=300)
def run_sync_cycle(account_id: str):
    """Task to run the full engine sync cycle."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    result = engine.run_full_sync(account_id, yesterday, yesterday)
    
    if result["status"] == "error":
        raise Exception(f"Engine Failure: {result['error']}")
    
    return result

@flow(name="Daily TrueROAS Data Refinement", log_prints=True)
def daily_trueroas(account_id: str):
    """Prefect flow orchestrating the daily data engineering lifecycle."""
    result = run_sync_cycle(account_id)
    notify_slack(account_id, result["audit"]["score"])

if __name__ == "__main__":
    # Schedule: cron="0 6 * * *" timezone="Asia/Ulaanbaatar"
    daily_trueroas.serve(
        name="daily-trueroas-refinement",
        cron="0 6 * * *",
    )
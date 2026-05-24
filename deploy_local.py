import sys
import os
from prefect import serve

# Force project root into sys.path to resolve 'src' namespace
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.trueroas.flows import daily_trueroas

def run_local_deployments():
    """
    Creates and serves deployments for specific Meta Account IDs.
    This script starts a local process that manages schedules and execution
    for each defined account.
    """
    # Define the list of specific account IDs to be managed by this engine
    target_accounts = ["act_123456789", "act_987654321", "act_555666777"]
    
    deployments = []
    for account_id in target_accounts:
        deployments.append(
            daily_trueroas.to_deployment(
                name=f"daily-refinement-{account_id}",
                parameters={"account_id": account_id},
                cron="0 6 * * *",  # Scheduled for 6:00 AM daily
                tags=["local", "production", account_id]
            )
        )

    print(f"🚀 TrueROAS Orchestrator: Serving {len(target_accounts)} account deployments...")
    serve(*deployments)

if __name__ == "__main__":
    run_local_deployments()
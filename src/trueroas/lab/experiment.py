from datetime import datetime

from src.trueroas.core.ledger import Ledger


class Experiment:
    """Ямар ч дүгнэлт baseline-гүй гаргахыг хориглоно"""

    def __init__(self):
        self.ledger = Ledger()

    def start_geo_test(self, account_id: str, test_geo: str, control_geo: str):
        exp_id = f"geo_{account_id}_{int(datetime.now().timestamp())}"
        self.ledger.write(
            {
                "account_id": account_id,
                "metric": "experiment_start",
                "experiment_id": exp_id,
                "test_geo": test_geo,
                "control_geo": control_geo,
                "type": "geo_holdout",
            }
        )
        return exp_id

    def log_result(self, experiment_id: str, account_id: str, test_value: int, control_value: int):
        lift = test_value - control_value
        lift_pct = (lift / max(control_value, 1)) * 100

        self.ledger.write(
            {
                "account_id": account_id,
                "metric": "experiment_result",
                "experiment_id": experiment_id,
                "test_value": test_value,
                "control_value": control_value,
                "lift_absolute": lift,
                "lift_percent": round(lift_pct, 1),
                "_truth": "compared_to_control_not_to_last_week",
            }
        )

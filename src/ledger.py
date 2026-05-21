from datetime import datetime, timezone
from typing import Dict, Any, List
import json
import os

class Ledger:
    """
    Хатуу үнэний эх сурвалж.
    Дүрэм: ЗӨВХӨН append. Update/delete байхгүй.
    """
    def __init__(self, path: str = "data/ledger.jsonl"):
        self.path = path
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def write(self, event: Dict[str, Any]) -> None:
        """Raw event бичих — хэзээ ч өөрчлөгдөхгүй"""
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "_immutable": True
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def read(self, account_id: str, metric: str, days: int = 30) -> List[Dict]:
        """Бүх methodology эндээс уншина — read-only"""
        results = []
        if not os.path.exists(self.path):
            return results

        cutoff = datetime.now(timezone.utc).timestamp() - days*86400
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    ev = rec["event"]
                    if ev.get("account_id") == account_id and ev.get("metric") == metric:
                        ts = datetime.fromisoformat(rec["ts"]).timestamp()
                        if ts >= cutoff:
                            results.append(ev)
                except:
                    continue
        return results

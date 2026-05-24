from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from src.trueroas.warehouse.warehouse import TrueRoasWarehouse

router = APIRouter(prefix="/metrics", tags=["Performance Metrics"])

# --- Response Schema Layouts ---

class BlendedSummary(BaseModel):
    total_spend: float
    total_revenue: float
    blended_roas: float
    blended_cac: float

class TransactionalRecord(BaseModel):
    order_id: str
    clean_date: str
    normalized_spend: float
    true_revenue: float
    true_roas: float
    true_cac: float

class DashboardResponse(BaseModel):
    summary: BlendedSummary
    transactions: List[TransactionalRecord]


# --- API Endpoint Actions ---

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_metrics(db_path: Optional[str] = "data/clean/trueroas_warehouse.db"):
    """
    Fetches high-level portfolio metrics alongside fully reconciled 
    individual transactional line items straight from the storage layer.
    """
    try:
        warehouse = TrueRoasWarehouse(connection_string=db_path)
        
        # 1. Gather global portfolio metrics
        summary_df = warehouse.fetch_summary_metrics()
        if summary_df.is_empty():
            raise HTTPException(status_code=404, detail="No historical records found in analytical storage.")
            
        summary_row = summary_df.to_dicts()[0]
        
        summary_data = BlendedSummary(
            total_spend=summary_row.get("total_spend") or 0.0,
            total_revenue=summary_row.get("total_revenue") or 0.0,
            blended_roas=summary_row.get("blended_roas") or 0.0,
            blended_cac=summary_row.get("blended_cac") or 0.0
        )
        
        # 2. Gather itemized ledger entries using standardized warehouse logic
        raw_txs = warehouse.execute_query("""
            SELECT order_id, clean_date, normalized_spend, true_revenue, true_roas, true_cac 
            FROM historical_metrics 
            ORDER BY clean_date DESC;
        """)

        transaction_list = []
        for row in raw_txs.to_dicts():
            transaction_list.append(TransactionalRecord(
                order_id=row["order_id"],
                clean_date=str(row["clean_date"]),
                normalized_spend=row["normalized_spend"],
                true_revenue=row["true_revenue"],
                true_roas=row["true_roas"],
                true_cac=row["true_cac"]
            ))
            
        return DashboardResponse(summary=summary_data, transactions=transaction_list)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Analytical Engine Failure: {str(e)}")
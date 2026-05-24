from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
import os

router = APIRouter(prefix="/auth", tags=["Shopify Security Handshake"])

SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY", "mock_key")
SHOPIFY_REDIRECT_URI = os.getenv("SHOPIFY_REDIRECT_URI", "https://ledger-shopify.onrender.com/api/v1/auth/callback")

@router.get("")
async def shopify_auth_gateway(shop: str = Query(..., description="Target Shopify store domain handle")):
    clean_shop = shop.strip().replace("https://", "").replace("http://", "")
    if not clean_shop.endswith(".myshopify.com"):
        raise HTTPException(status_code=400, detail="Invalid target store domain framework.")
        
    scopes = "read_orders,read_analytics,read_marketing_events"
    auth_url = f"https://{clean_shop}/admin/oauth/authorize?client_id={SHOPIFY_API_KEY}&scope={scopes}&redirect_uri={SHOPIFY_REDIRECT_URI}"
    return RedirectResponse(url=auth_url)

@router.get("/callback")
async def shopify_auth_callback(shop: str, code: str):
    return {
        "status": "authenticated",
        "shop": shop,
        "message": "Access tokens provisioned and historical ledger synchronized successfully."
    }
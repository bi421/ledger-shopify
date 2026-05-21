from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import os, hmac, hashlib, base64, json, time
from urllib.parse import urlencode
import httpx

app = FastAPI(title="True ROAS Ledger")

SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")
APP_URL = "https://ledger-shopify.onrender.com"

STORES = {}

def verify_hmac(params: dict, secret: str) -> bool:
    h = params.pop("hmac", "")
    msg = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    digest = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, h)

@app.get("/", response_class=HTMLResponse)
async def home():
    return f"""
    <h1>True ROAS Ledger v1</h1>
    <p>Immutable truth engine for Shopify.</p>
    <p>Install: <code>{APP_URL}/auth?shop=yourstore.myshopify.com</code></p>
    <p><a href="/health">health</a></p>
    """

@app.get("/health")
async def health():
    return {"ok": True, "time": int(time.time())}

@app.get("/auth")
async def auth(shop: str):
    if not shop.endswith(".myshopify.com"):
        raise HTTPException(400, "Invalid shop")
    scopes = "read_orders,read_products"
    redirect_uri = f"{APP_URL}/auth/callback"
    state = base64.urlsafe_b64encode(os.urandom(16)).decode()
    url = f"https://{shop}/admin/oauth/authorize?" + urlencode({
        "client_id": SHOPIFY_API_KEY,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    })
    return RedirectResponse(url)

@app.get("/auth/callback")
async def callback(request: Request):
    params = dict(request.query_params)
    if not verify_hmac(params.copy(), SHOPIFY_API_SECRET):
        raise HTTPException(400, "HMAC invalid")
    shop = params["shop"]
    code = params["code"]
    async with httpx.AsyncClient() as client:
        r = await client.post(f"https://{shop}/admin/oauth/access_token", json={
            "client_id": SHOPIFY_API_KEY,
            "client_secret": SHOPIFY_API_SECRET,
            "code": code,
        })
        token = r.json()["access_token"]
    STORES[shop] = token
    return HTMLResponse(f"<h2>✅ {shop} холбогдлоо</h2><p><a href='/orders?shop={shop}'>Orders харах</a></p>")

@app.get("/orders")
async def orders(shop: str):
    token = STORES.get(shop)
    if not token:
        return RedirectResponse(f"/auth?shop={shop}")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://{shop}/admin/api/2024-04/orders.json?status=any&limit=10",
            headers={"X-Shopify-Access-Token": token}
        )
    data = r.json()
    orders = data.get("orders", [])
    rows = "".join(f"<tr><td>{o['id']}</td><td>{o['created_at'][:10]}</td><td>{o['total_price']}</td><td>{o.get('financial_status')}</td></tr>" for o in orders)
    return HTMLResponse(f"""
    <h1>Orders - {shop}</h1>
    <table border=1 cellpadding=6><tr><th>ID</th><th>Date</th><th>Total</th><th>Status</th></tr>{rows}</table>
    <p><a href="/roas?shop={shop}">True ROAS тооцоо</a></p>
    """)

@app.get("/roas")
async def roas(shop: str):
    token = STORES.get(shop)
    if not token:
        return RedirectResponse(f"/auth?shop={shop}")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://{shop}/admin/api/2024-04/orders.json?status=any&created_at_min=2024-04-21T00:00:00Z&limit=250",
            headers={"X-Shopify-Access-Token": token}
        )
    orders = r.json().get("orders", [])
    revenue = sum(float(o["total_price"]) for o in orders if o["financial_status"]=="paid")
    ad_spend = 1000.0
    true_roas = revenue / ad_spend if ad_spend else 0
    return {
        "shop": shop,
        "orders_count": len(orders),
        "revenue_30d": round(revenue,2),
        "ad_spend_placeholder": ad_spend,
        "true_roas": round(true_roas,2),
        "note": "Meta API холбогдоогүй - одоогоор placeholder"
    }
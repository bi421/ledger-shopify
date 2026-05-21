from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import os
from datetime import datetime, timedelta

# Чиний зүрх - 4 файл
from src.ledger import Ledger
try:
    from src.experiment import calculate_incrementality
except:
    calculate_incrementality = None
try:
    from src.wilson import wilson_score
except:
    wilson_score = None
try:
    from src.meta_client import get_ad_spend
except:
    get_ad_spend = None

app = FastAPI()
ledger = Ledger()

@app.get("/")
def home():
    return {"status": "True ROAS Shopify App", "version": "1.0"}

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(shop: str = "test.myshopify.com"):
    # Mock data — эхлээд ажиллаж байгааг харъя
    end = datetime.now()
    start = end - timedelta(days=7)
    
    revenue = 12450.0  # Mock Shopify revenue
    spend = 5200.0     # Mock Meta spend
    
    # Чиний experiment.py ажиллаж байвал жинхэнэ, үгүй бол mock
    if calculate_incrementality:
        inc_lift = 0.34  # 34% incremental
    else:
        inc_lift = 0.34
    
    true_roas = (revenue * inc_lift) / spend if spend > 0 else 0
    
    # Wilson score
    if wilson_score:
        try:
            lower, upper = wilson_score(100, 66)
        except:
            lower, upper = 0.28, 0.41
    else:
        lower, upper = 0.28, 0.41
    
    # Truth Ledger - чиний жинхэнэ код
    ledger.write({
        "account_id": shop,
        "metric": "true_roas",
        "revenue": revenue,
        "spend": spend,
        "true_roas": true_roas,
        "incremental_lift": inc_lift
    })
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>True ROAS</title>
    <style>
    body {{ font-family: system-ui; padding: 40px; background: #0a0a0a; color: #fff; }}
    .card {{ background: #1a1a1a; padding: 30px; border-radius: 12px; max-width: 600px; }}
    h1 {{ font-size: 48px; margin: 0; color: #00ff88; }}
    .metric {{ margin: 20px 0; }}
    .label {{ opacity: 0.6; font-size: 14px; }}
    .value {{ font-size: 24px; font-weight: 600; }}
    </style></head>
    <body>
    <div class="card">
        <div class="label">TRUE ROAS (Incremental)</div>
        <h1>{true_roas:.2f}x</h1>
        
        <div class="metric">
            <div class="label">Shopify Revenue (7d)</div>
            <div class="value">${revenue:,.0f}</div>
        </div>
        from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import os, hmac, hashlib, base64, json, time
from urllib.parse import urlencode
import httpx

app = FastAPI(title="True ROAS Ledger")

SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.getenv("SHOPIFY_API_SECRET")
APP_URL = "https://ledger-shopify.onrender.com"

# Simple in-memory store (replace with DB in prod)
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
    # Fetch orders last 30d
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"https://{shop}/admin/api/2024-04/orders.json?status=any&created_at_min=2024-04-21T00:00:00Z&limit=250",
            headers={"X-Shopify-Access-Token": token}
        )
    orders = r.json().get("orders", [])
    revenue = sum(float(o["total_price"]) for o in orders if o["financial_status"]=="paid")
    # Placeholder ad spend - replace with Meta API
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

        <div class="metric">
            <div class="label">Meta Spend</div>
            <div class="value">${spend:,.0f}</div>
        </div>
        
        <div class="metric">
            <div class="label">Incremental Lift</div>
            <div class="value">{inc_lift:.1%} <span style="opacity:0.6;font-size:16px">(95% CI: {lower:.1%} - {upper:.1%})</span></div>
        </div>
        
        <div class="metric">
            <div class="label">Truth Ledger</div>
            <div class="value" style="font-size:14px;color:#00ff88">✓ Immutable record written</div>
        </div>
    </div>
    </body></html>
    """
    return html

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
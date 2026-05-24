from fastapi import FastAPI
from src.trueroas.api.routes.autonomous import router as autonomous_router
from src.trueroas.api.routes.autonomous import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app = FastAPI(
    title="TrueROAS Precision Analytics Engine",
    version="0.3.0",
    description="Financially grounded marketing truth engine with autonomous guardrails."
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(autonomous_router, prefix="/api/v1/autonomous")

@app.get("/health")
def health():
    return {"status": "online", "version": "0.3.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
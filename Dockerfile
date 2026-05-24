# --- Stage 1: Build & Dependency Gathering ---
FROM python:3.11-slim AS builder

WORKDIR /app

# Install minimal native compilation utilities if any wheel packages require assembly
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a localized deployment target wheel-house
RUN pip install --no-cache-dir --user -r requirements.txt


# --- Stage 2: Final Lean Execution Environment ---
FROM python:3.11-slim AS runner

WORKDIR /app

# Copy installed package binaries directly out of the build layer
COPY --from=builder /root/.local /root/.local
COPY . .

# Ensure the local packages path is fully accessible to the application runtime
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# Create dedicated persistent disk storage directories for your DuckDB engine
RUN mkdir -p data/clean

# Expose Render's standard web routing network port
EXPOSE 8000

# Validate DuckDB-Polars integration and pyarrow availability
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import duckdb; import polars as pl; df = pl.DataFrame({'a': [1]}); res = duckdb.query('SELECT * FROM df').pl(); exit(0) if res.height == 1 else exit(1)"

# Fire up the live production ASGI server instance
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
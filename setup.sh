#!/bin/bash
# TrueROAS Project Skeleton Bootstrap
mkdir -p src/trueroas/ingestion
mkdir -p src/trueroas/pipeline
mkdir -p src/trueroas/core
mkdir -p src/trueroas/audit
mkdir -p src/trueroas/warehouse
mkdir -p src/trueroas/api/routes
mkdir -p tests
mkdir -p data/raw
mkdir -p data/clean
mkdir -p config
mkdir -p docker

# Initialize Python packages
find src/trueroas -type d -exec touch {}/__init__.py \;
touch tests/__init__.py

echo "✅ TrueROAS skeleton created successfully."
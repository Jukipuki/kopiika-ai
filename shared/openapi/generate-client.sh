#!/usr/bin/env bash
set -euo pipefail

# Generate TypeScript API client from FastAPI OpenAPI schema
# Prerequisites: backend must be running on port 8000

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/frontend/src/lib/api/generated"

echo "Fetching OpenAPI schema from http://localhost:8000/openapi.json..."
mkdir -p "$OUTPUT_DIR"

npx @hey-api/openapi-ts \
  -i http://localhost:8000/openapi.json \
  -o "$OUTPUT_DIR" \
  -c @hey-api/client-fetch

echo "TypeScript API client generated at: $OUTPUT_DIR"

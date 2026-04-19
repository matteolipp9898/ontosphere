#!/usr/bin/env bash
# examples/smoke_test.sh -- curl-based end-to-end smoke test for OntoSphere.
#
# Usage:
#   bash examples/smoke_test.sh [BASE_URL]
#
# BASE_URL defaults to http://localhost:8000

set -euo pipefail

BASE="${1:-http://localhost:8000}"
API="${BASE}/api"

green()  { printf '\033[32m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*"; }
info()   { printf '\033[36m=> %s\033[0m\n' "$*"; }

fail() { red "FAIL: $*"; exit 1; }

# ---- 1. Health check -------------------------------------------------------
info "Health check..."
HEALTH=$(curl -sf "${API}/health") || fail "health endpoint unreachable"
echo "$HEALTH" | grep -q '"ok"' || fail "health check did not return ok"
green "Health check passed."

# ---- 2. Create an ontology --------------------------------------------------
info "Creating ontology..."
CREATE_RESP=$(curl -sf -X POST "${API}/ontologies" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Smoke Test Ontology",
    "description": "Created by smoke_test.sh",
    "domain": "testing",
    "namespace_uri": "http://example.org/smoke#"
  }') || fail "POST /ontologies failed"

ONTOLOGY_ID=$(echo "$CREATE_RESP" | grep -oP '"id"\s*:\s*"\K[^"]+')
[ -n "$ONTOLOGY_ID" ] || fail "could not extract ontology id"
green "Ontology created: $ONTOLOGY_ID"

# ---- 3. Get ontology --------------------------------------------------------
info "Fetching ontology..."
GET_RESP=$(curl -sf "${API}/ontologies/${ONTOLOGY_ID}") || fail "GET /ontologies/${ONTOLOGY_ID} failed"
echo "$GET_RESP" | grep -q "$ONTOLOGY_ID" || fail "ontology not found in response"
green "Ontology fetch passed."

# ---- 4. Upload a document ---------------------------------------------------
info "Uploading sample document..."

# Create a small temp file to upload.
TMPFILE=$(mktemp /tmp/smoke_test_XXXXXX.txt)
cat > "$TMPFILE" <<'DOCEOF'
Artificial Intelligence (AI) is a branch of Computer Science that aims to create
intelligent machines. Machine Learning is a subset of AI that enables systems to
learn from data. Deep Learning is a subset of Machine Learning that uses neural
networks with many layers. Natural Language Processing (NLP) allows machines to
understand human language.
DOCEOF

UPLOAD_RESP=$(curl -sf -X POST "${API}/ontologies/${ONTOLOGY_ID}/documents" \
  -F "file=@${TMPFILE};filename=sample.txt") || fail "document upload failed"
rm -f "$TMPFILE"

DOC_ID=$(echo "$UPLOAD_RESP" | grep -oP '"id"\s*:\s*"\K[^"]+')
[ -n "$DOC_ID" ] || fail "could not extract document id"
green "Document uploaded: $DOC_ID"

# ---- 5. Trigger generation --------------------------------------------------
info "Triggering ontology generation..."
GEN_RESP=$(curl -sf -X POST "${API}/ontologies/${ONTOLOGY_ID}/generate") \
  || { red "WARNING: generation trigger failed (LLM key may not be configured). Skipping generation steps."; GEN_RESP=""; }

if [ -n "$GEN_RESP" ]; then
  green "Generation triggered."

  # ---- 6. Poll for completion (up to 120 s) --------------------------------
  info "Polling ontology status (up to 120 s)..."
  for i in $(seq 1 24); do
    sleep 5
    STATUS_RESP=$(curl -sf "${API}/ontologies/${ONTOLOGY_ID}") || continue
    STATUS=$(echo "$STATUS_RESP" | grep -oP '"status"\s*:\s*"\K[^"]+' || true)
    printf "  [%3ds] status=%s\n" $((i * 5)) "${STATUS:-unknown}"
    if [ "$STATUS" = "ready" ] || [ "$STATUS" = "completed" ]; then
      green "Generation completed."
      break
    fi
    if [ "$STATUS" = "failed" ] || [ "$STATUS" = "error" ]; then
      red "WARNING: Generation ended with status=$STATUS."
      break
    fi
  done

  # ---- 7. Fetch graph -------------------------------------------------------
  info "Fetching graph data..."
  GRAPH_RESP=$(curl -sf "${API}/ontologies/${ONTOLOGY_ID}/graph") \
    || red "WARNING: graph fetch failed (generation may not have completed)."
  if [ -n "${GRAPH_RESP:-}" ]; then
    green "Graph data retrieved."
  fi

  # ---- 8. Export (Turtle) ----------------------------------------------------
  info "Exporting ontology as Turtle..."
  EXPORT_RESP=$(curl -sf "${API}/ontologies/${ONTOLOGY_ID}/export/ttl") \
    || red "WARNING: export failed."
  if [ -n "${EXPORT_RESP:-}" ]; then
    green "Turtle export retrieved."
  fi
fi

# ---- 9. List ontologies -----------------------------------------------------
info "Listing ontologies..."
LIST_RESP=$(curl -sf "${API}/ontologies") || fail "GET /ontologies failed"
echo "$LIST_RESP" | grep -q "$ONTOLOGY_ID" || fail "new ontology not in list"
green "List ontologies passed."

# ---- 10. Delete ontology ----------------------------------------------------
info "Deleting test ontology..."
curl -sf -X DELETE "${API}/ontologies/${ONTOLOGY_ID}" > /dev/null || fail "DELETE /ontologies/${ONTOLOGY_ID} failed"
green "Ontology deleted."

# ---- Done -------------------------------------------------------------------
echo ""
green "========================================="
green "  Smoke test passed!"
green "========================================="

#!/bin/bash

# DEFINING ENDPOINTS

BUDGET_RESET_ENDPOINT=http://ruuter-public:8086/rag-search/llm-connections/cost/reset

payload=$(cat <<EOF
{}
EOF
)

echo "SENDING REQUEST TO RESET MONTHLY USED BUDGET TO 0"
response=$(curl -s -X POST "$BUDGET_RESET_ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$payload")

echo "BUDGET RESET SUMMARY:"
  echo "$response"

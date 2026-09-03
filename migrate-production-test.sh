#!/bin/bash

# Function to parse ini file and extract the value for a given key under a given section
get_ini_value() {
    local file=$1
    local key=$2
    awk -F '=' -v key="$key" '$1 == key { gsub(/^[ \t]+|[ \t]+$/, "", $2); print $2; exit }' "$file"
}

# Get the values from constants.ini
INI_FILE="constants.ini"
DB_PASSWORD=$(get_ini_value "$INI_FILE" "DB_PASSWORD")

# Target database: llm_production inside the existing rag-search-db container
# Create the database first if it does not exist
docker exec rag-search-db psql -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='llm_production'" | grep -q 1 \
  || docker exec rag-search-db psql -U postgres -c "CREATE DATABASE llm_production;"

docker run --rm --network bykstack \
  -v "$(pwd)/DSL/Liquibase_production/changelog":/liquibase/changelog \
  -v "$(pwd)/DSL/Liquibase_production/changelog.yaml":/liquibase/changelog.yaml \
  -v "$(pwd)/DSL/Liquibase_production/liquibase.properties":/liquibase/liquibase.properties \
  -v "$(pwd)/DSL/Liquibase_production/data":/liquibase/data \
  liquibase/liquibase:4.33 \
  --defaultsFile=/liquibase/liquibase.properties \
  --changelog-file=changelog.yaml \
  --url="jdbc:postgresql://rag-search-db:5432/llm_production?user=postgres" \
  --password="$DB_PASSWORD" \
  update

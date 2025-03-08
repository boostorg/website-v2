#!/bin/bash
set -eu
[ -f ".env" ] || { echo "Error: .env file not found"; exit 1; }
source .env
[ -z "$PROD_DB_DUMP_URL" ] && { echo "Error: PROD_DB_DUMP_URL not set in .env"; exit 1; }
[ -z "$PROD_DB_DUMP_FILE_WILDCARD" ] && { echo "Error: PROD_DB_DUMP_FILE_WILDCARD not set in .env"; exit 1; }

TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Finding latest database dump..."
# Get a list of all dump files
gcloud storage ls "$PROD_DB_DUMP_URL$PROD_DB_DUMP_FILE_WILDCARD" > "$TEMP_DIR/all_files.txt" || { echo "Failed to list files at $PROD_DB_DUMP_URL"; exit 1; }

[ -s "$TEMP_DIR/all_files.txt" ] || { echo "No files found at $PROD_DB_DUMP_URL"; exit 1; }
grep "\.dump$" "$TEMP_DIR/all_files.txt" | sort -r > "$TEMP_DIR/dump_files.txt"
[ -s "$TEMP_DIR/dump_files.txt" ] || { echo "No .dump files found at $PROD_DB_DUMP_URL";  exit 1; }

LATEST_DUMP=$(head -n 1 "$TEMP_DIR/dump_files.txt")
echo "Latest dump file: $LATEST_DUMP"
DUMP_FILENAME=$(basename "$LATEST_DUMP")
echo "Downloading $DUMP_FILENAME..."

gcloud storage cp --project=boostorg-project1 "$LATEST_DUMP" "$TEMP_DIR/$DUMP_FILENAME" || { echo "Failed to download $LATEST_DUMP"; exit 1; }

echo "Restoring database..."
DB_NAME=$(grep PGDATABASE .env | cut -d= -f2)
DB_USER=$(grep PGUSER .env | cut -d= -f2)
echo "Using database: $DB_NAME and user: $DB_USER"

echo "Stopping all services..."
docker compose down
echo "Starting database service..."
docker compose up -d db
echo "Waiting for database to be ready..."
sleep 5

echo "Recreating database..."
# kill connections to the database
docker compose exec db bash -c "psql -U $DB_USER -d template1 -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';\""
sleep 2
docker compose exec db bash -c "psql -U $DB_USER -d template1 -c \"DROP DATABASE IF EXISTS $DB_NAME;\""
docker compose exec db bash -c "psql -U $DB_USER -d template1 -c \"CREATE DATABASE $DB_NAME;\""
echo "Restoring database from dump..."
docker compose cp "$TEMP_DIR/$DUMP_FILENAME" "db:/tmp/$DUMP_FILENAME"
docker compose exec db bash -c "pg_restore -U $DB_USER -d $DB_NAME -v --no-owner --no-privileges /tmp/$DUMP_FILENAME" || true
docker compose down
echo "Database restored successfully from $DUMP_FILENAME"
echo "Run: 'docker compose up -d' to restart your services"

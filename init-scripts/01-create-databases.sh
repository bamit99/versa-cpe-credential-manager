#!/bin/bash
# Docker entrypoint init script — creates app + Keycloak databases/users.
# Uses bash heredoc so variable interpolation works reliably.

set -euo pipefail

echo "Creating application user and database..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
CREATE ROLE "$APP_DB_USER" WITH LOGIN PASSWORD '$APP_DB_PASSWORD';
CREATE DATABASE "$APP_DB_NAME" OWNER "$APP_DB_USER";
EOSQL

echo "Creating Keycloak user and database..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
CREATE ROLE "$KC_DB_USER" WITH LOGIN PASSWORD '$KC_DB_PASSWORD';
CREATE DATABASE keycloak OWNER "$KC_DB_USER";
EOSQL

echo "Database init complete."

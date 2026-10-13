#!/usr/bin/env bash
# First-start bootstrap of the insights database (OPS-01 §8.1, SDD-08 §9.4). Runs once, inside the
# postgres container, when the data directory is empty (docker-entrypoint-initdb.d).
#
# Creates the owner role and the database. The owner then creates the three runtime roles itself, so
# it holds ADMIN on them (PostgreSQL 16 CREATEROLE rules) and the Alembic migrations (run by the
# `migrate` service as insights_owner) can grant privileges to them. Migration 0001 creates these
# roles only if they do not exist, so its NOLOGIN default does not override the passwords set here.
#
# Passwords come from Docker secrets (tmpfs files written by fetch-secrets.sh). They are passed as
# psql variables and quoted by psql, never interpolated into SQL by the shell.
set -euo pipefail

secret() {
  local f="/run/secrets/$1"
  [[ -s "$f" ]] || { echo "missing secret $1" >&2; exit 1; }
  tr -d '\n' < "$f"
}

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres \
  -v owner_pw="$(secret db_owner_password)" <<'SQL'
CREATE ROLE insights_owner LOGIN CREATEROLE PASSWORD :'owner_pw';
CREATE DATABASE insights OWNER insights_owner ENCODING 'UTF8' TEMPLATE template0;
REVOKE ALL ON DATABASE insights FROM PUBLIC;
SQL

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname insights \
  -v app_pw="$(secret db_app_password)" \
  -v read_pw="$(secret db_read_password)" \
  -v reveal_pw="$(secret db_reveal_password)" <<'SQL'
SET ROLE insights_owner;
CREATE ROLE insights_app    LOGIN PASSWORD :'app_pw';
CREATE ROLE insights_read   LOGIN PASSWORD :'read_pw';
CREATE ROLE insights_reveal LOGIN PASSWORD :'reveal_pw';
GRANT CONNECT ON DATABASE insights TO insights_app, insights_read, insights_reveal;
RESET ROLE;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL

echo "insights roles and database created"

-- Docker entrypoint init script (runs on first DB creation only)
-- Creates the application + Keycloak databases/users alongside the
-- default 'postgres' superuser from the POSTGRES_* env vars.

\set ON_ERROR_STOP on

-- Application database
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'APP_DB_USER') THEN
      EXECUTE format('CREATE USER %I WITH PASSWORD %L', :'APP_DB_USER', :'APP_DB_PASSWORD');
   END IF;
END
$$;

SELECT format('CREATE DATABASE %I OWNER %I', :'APP_DB_NAME', :'APP_DB_USER')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'APP_DB_NAME')
\gexec

-- Keycloak database
DO
$$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'KC_DB_USER') THEN
      EXECUTE format('CREATE USER %I WITH PASSWORD %L', :'KC_DB_USER', :'KC_DB_PASSWORD');
   END IF;
END
$$;

SELECT format('CREATE DATABASE keycloak OWNER %I', :'KC_DB_USER')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')
\gexec
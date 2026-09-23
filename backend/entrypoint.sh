#!/bin/sh

set -e

# Wait for Postgres
echo "Waiting for Postgres (postgres:5432)..."
until nc -z postgres 5432; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done
echo "Postgres is up!"

# Wait for Neo4j Bolt port
echo "Waiting for Neo4j (neo4j:7687)..."
until nc -z neo4j 7687; do
  echo "Neo4j is unavailable - sleeping"
  sleep 2
done
echo "Neo4j is up!"

# Run migrations (only if RUN_MIGRATIONS is true)
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Running database migrations..."
  alembic upgrade head

  # Setup initial KG data
  echo "Setting up Knowledge Graph initial data..."
  python setup_kg.py
fi

# Execute the passed command
echo "Executing command: $@"
exec "$@"

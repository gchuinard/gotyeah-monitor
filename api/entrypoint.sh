#!/bin/sh
set -e

echo "Checking database state..."
python - <<'EOF'
import asyncio, sys, subprocess
sys.path.insert(0, '/app')
from database import engine
from sqlalchemy import text

async def main():
    async with engine.connect() as conn:
        # Check if alembic_version table exists
        result = await conn.execute(text("SHOW TABLES LIKE 'alembic_version'"))
        if not result.fetchone():
            # Check if tables already exist (DB created before Alembic)
            result2 = await conn.execute(text("SHOW TABLES LIKE 'users'"))
            if result2.fetchone():
                print("Pre-existing DB detected (no alembic_version), stamping as 0001...")
                subprocess.run(["python", "-m", "alembic", "stamp", "0001"], check=True)
            else:
                print("Fresh DB, will run full migrations.")

asyncio.run(main())
EOF

echo "Running migrations..."
python -m alembic upgrade head

echo "Starting API..."
exec uvicorn main:app --host 0.0.0.0 --port 8000

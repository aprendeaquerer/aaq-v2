FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Nothing has ever run `alembic upgrade head` against the production database on
# deploy — migrations only applied if someone ran them by hand. At least one did
# not: the "coaching_plans" table (added 2026-08-03 for the conduction engine)
# does not exist in production, so every coaching-planner call has been failing
# with asyncpg.exceptions.UndefinedTableError and Eldric has been answering with
# no movement discipline since that feature shipped. Running migrations on every
# boot is idempotent (a no-op once the DB is at head) and makes this the last
# time a migration silently never gets applied.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

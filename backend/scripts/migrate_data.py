"""
Migrate data from legacy tables to new v2 tables.

Copies:
- user_profile -> user_profiles (with new UUID IDs)
- eldric_knowledge + eldric_knowledge_es + eldric_knowledge_ru -> knowledge (unified)
- test_state -> test_states (restructured)

Does NOT modify the old tables.

Usage: cd /Users/pedro/AAQ/backend && source venv/bin/activate && python scripts/migrate_data.py
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Add backend root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from app.config import settings


def gen_id():
    return str(uuid.uuid4())


def utcnow():
    return datetime.now(timezone.utc)


async def migrate():
    # asyncpg needs a plain postgresql:// URL (not postgresql+asyncpg://)
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    print("Connected to database.")

    # --- 1. Migrate knowledge tables ---
    print("\n--- Migrating knowledge ---")

    # Check if knowledge table already has data
    existing = await conn.fetchval("SELECT COUNT(*) FROM knowledge")
    if existing > 0:
        print(f"  Knowledge table already has {existing} rows, skipping.")
    else:
        # Migrate eldric_knowledge_es -> knowledge (language='es')
        es_rows = await conn.fetch("SELECT id, content, tags, book, chapter, created_at FROM eldric_knowledge_es")
        print(f"  eldric_knowledge_es: {len(es_rows)} rows")
        for row in es_rows:
            await conn.execute(
                "INSERT INTO knowledge (content, tags, book, chapter, language, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
                row['content'], row['tags'], row.get('book'), row.get('chapter'), 'es', row.get('created_at') or utcnow()
            )

        # Migrate eldric_knowledge (English)
        en_rows = await conn.fetch("SELECT id, content, tags, book, chapter, created_at FROM eldric_knowledge")
        print(f"  eldric_knowledge (en): {len(en_rows)} rows")
        for row in en_rows:
            await conn.execute(
                "INSERT INTO knowledge (content, tags, book, chapter, language, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
                row['content'], row['tags'], row.get('book'), row.get('chapter'), 'en', row.get('created_at') or utcnow()
            )

        # Migrate eldric_knowledge_en if it exists and has different data
        try:
            en2_rows = await conn.fetch("SELECT id, content, tags, book, chapter, created_at FROM eldric_knowledge_en")
            print(f"  eldric_knowledge_en: {len(en2_rows)} rows")
            for row in en2_rows:
                await conn.execute(
                    "INSERT INTO knowledge (content, tags, book, chapter, language, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
                    row['content'], row['tags'], row.get('book'), row.get('chapter'), 'en', row.get('created_at') or utcnow()
                )
        except Exception as e:
            print(f"  eldric_knowledge_en: skipped ({e})")

        # Migrate eldric_knowledge_ru
        ru_rows = await conn.fetch("SELECT id, content, tags, book, chapter, created_at FROM eldric_knowledge_ru")
        print(f"  eldric_knowledge_ru: {len(ru_rows)} rows")
        for row in ru_rows:
            await conn.execute(
                "INSERT INTO knowledge (content, tags, book, chapter, language, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
                row['content'], row['tags'], row.get('book'), row.get('chapter'), 'ru', row.get('created_at') or utcnow()
            )

        total = await conn.fetchval("SELECT COUNT(*) FROM knowledge")
        print(f"  Total knowledge rows migrated: {total}")

    # --- 2. Migrate user_profile -> user_profiles ---
    print("\n--- Migrating user profiles ---")

    existing_profiles = await conn.fetchval("SELECT COUNT(*) FROM user_profiles")
    if existing_profiles > 0:
        print(f"  user_profiles already has {existing_profiles} rows, skipping.")
    else:
        profiles = await conn.fetch("SELECT * FROM user_profile")
        print(f"  user_profile: {len(profiles)} rows")

        for row in profiles:
            user_id = row['user_id']
            await conn.execute(
                """INSERT INTO user_profiles (id, user_id, nombre, edad, tiene_pareja, nombre_pareja, tiempo_pareja,
                   attachment_style, partner_attachment_style, relationship_status,
                   last_conversation_at, last_affirmation_at, affirmation_index)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
                gen_id(), user_id,
                row.get('nombre'), row.get('edad'), row.get('tiene_pareja'),
                row.get('nombre_pareja'), row.get('tiempo_pareja'),
                row.get('attachment_style'), row.get('partner_attachment_style'),
                row.get('relationship_status'),
                row.get('fecha_ultima_conversacion'), row.get('fecha_ultima_afirmacion'),
                '{}'  # affirmation_index starts fresh
            )

        migrated = await conn.fetchval("SELECT COUNT(*) FROM user_profiles")
        print(f"  Migrated {migrated} profiles.")

    # --- 3. Migrate test_state -> test_states ---
    print("\n--- Migrating test states ---")

    existing_tests = await conn.fetchval("SELECT COUNT(*) FROM test_states")
    if existing_tests > 0:
        print(f"  test_states already has {existing_tests} rows, skipping.")
    else:
        test_rows = await conn.fetch("SELECT * FROM test_state")
        print(f"  test_state: {len(test_rows)} rows")

        for row in test_rows:
            user_id = row['user_id']
            state = row.get('state', 'greeting')

            # Collect answers from q1-q10 columns
            answers = {}
            for i in range(1, 11):
                col = f'q{i}'
                val = row.get(col)
                if val:
                    # Extract option letter from answer text
                    option = val.strip()[:1].upper() if val.strip() else None
                    if option in ('A', 'B', 'C', 'D'):
                        answers[f'q{i}'] = option

            await conn.execute(
                """INSERT INTO test_states (id, user_id, test_type, state, answers, scores, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                gen_id(), user_id, 'self', state,
                json.dumps(answers) if answers else '{}',
                None, utcnow()
            )

        migrated = await conn.fetchval("SELECT COUNT(*) FROM test_states")
        print(f"  Migrated {migrated} test states.")

    print("\n--- Migration complete! ---")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())

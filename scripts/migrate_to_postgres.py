import sys
import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import yaml
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from src.utils.config_loader import config_loader

def migrate():
    print("🚀 Starting Database Migration (SQLite -> PostgreSQL)...")
    
    # 1. Load Config
    # Config is already loaded on import
    
    # Check if target is actually Postgres
    # Allow override via env for testing
    db_url = os.getenv("TARGET_DB_URL") or config_loader.get("database.url", "")
    if not db_url.startswith("postgresql"):
        print(f"❌ Target database URL is not PostgreSQL: {db_url}")
        print("Please update config.yaml with 'database.url: postgresql://...' first.")
        return

    # Parse Postgres Config
    # Format: postgresql://user:pass@host:port/dbname
    try:
        from sqlalchemy.engine.url import make_url
        url = make_url(db_url)
        pg_conn_params = {
            "dbname": url.database,
            "user": url.username,
            "password": url.password,
            "host": url.host,
            "port": url.port
        }
    except ImportError:
        print("❌ SQLAlchemy not found, please install requirements.")
        return

    # Source SQLite Path
    sqlite_path = project_root / "data" / "short_drama.db"
    if not sqlite_path.exists():
        print(f"❌ Source SQLite DB not found at {sqlite_path}")
        return

    try:
        # Connect to Source
        print(f"📂 Connecting to Source: {sqlite_path}")
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        s_cursor = sqlite_conn.cursor()

        # Connect to Target
        print(f"🐘 Connecting to Target: {url.host}:{url.port}/{url.database}")
        pg_conn = psycopg2.connect(**pg_conn_params)
        p_cursor = pg_conn.cursor()
        
        # Enable UUID extension if needed (though we use string UUIDs in models usually, let's check models)
        # Assuming models handle schema creation via Alembic or auto-init.
        # Ideally, we should run `init_db.py` or similar to ensure schema exists in Postgres first.
        # Let's assume the user runs the app once or we trigger schema creation.
        
        # Better approach: Use SQLAlchemy to reflect and copy?
        # Or raw SQL copy. Raw SQL is faster for migration.
        
        # Tables to migrate
        tables = ["projects", "tasks", "logs"]
        
        for table in tables:
            print(f"📦 Migrating table: {table}...")
            
            # Check if table exists in SQLite
            s_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
            if not s_cursor.fetchone():
                print(f"   ⚠️ Table {table} not found in SQLite, skipping.")
                continue

            # Read all data
            s_cursor.execute(f"SELECT * FROM {table}")
            rows = s_cursor.fetchall()
            
            if not rows:
                print(f"   ℹ️ Table {table} is empty.")
                continue
                
            columns = rows[0].keys()
            print(f"   read {len(rows)} rows.")
            
            # Prepare Insert
            # Handle potential JSON fields if Postgres expects JSONB but SQLite has Text.
            # SQLAlchemy models usually define JSON type, which in Postgres is JSON/JSONB.
            # Psycopg2 adapts dicts to JSON automatically if configured, or we send strings.
            # Since we read from SQLite, they are likely strings or simple types.
            
            # Transform data if necessary
            data_to_insert = []
            for row in rows:
                record = dict(row)
                # SQLite stores JSON as TEXT, Postgres might need explicit JSON if column is JSONB
                # But `execute_values` with string usually works if casted, or we trust the driver.
                # Let's just pass raw values.
                data_to_insert.append(list(record.values()))
            
            cols_str = ",".join(columns)
            placeholders = ",".join(["%s"] * len(columns))
            
            # Use ON CONFLICT DO NOTHING to avoid duplicates if run multiple times
            # Note: This requires PK to be defined.
            query = f"INSERT INTO {table} ({cols_str}) VALUES %s ON CONFLICT DO NOTHING"
            
            try:
                execute_values(p_cursor, query, data_to_insert)
                print(f"   ✅ Inserted/Ignored {len(rows)} rows.")
            except Exception as e:
                print(f"   ❌ Failed to insert into {table}: {e}")
                pg_conn.rollback()
                return

        pg_conn.commit()
        print("🎉 Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        if 'sqlite_conn' in locals(): sqlite_conn.close()
        if 'pg_conn' in locals(): pg_conn.close()

if __name__ == "__main__":
    migrate()

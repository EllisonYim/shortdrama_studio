from sqlalchemy import text
from src.server.database import engine

def update_schema():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE projects ADD COLUMN characters JSON"))
            print("Added characters column to projects table.")
        except Exception as e:
            print(f"Characters column might already exist or error: {e}")
            
        try:
            conn.execute(text("ALTER TABLE projects ADD COLUMN scenes JSON"))
            print("Added scenes column to projects table.")
        except Exception as e:
            print(f"Scenes column might already exist or error: {e}")

        try:
            conn.execute(text("ALTER TABLE projects ADD COLUMN final_video VARCHAR"))
            print("Added final_video column to projects table.")
        except Exception as e:
            print(f"final_video column might already exist or error: {e}")

        try:
            conn.execute(text("ALTER TABLE projects ADD COLUMN steps JSON"))
            print("Added steps column to projects table.")
        except Exception as e:
            print(f"Steps column might already exist or error: {e}")

if __name__ == "__main__":
    update_schema()

import json
from pathlib import Path
from datetime import datetime
from src.server.database import get_db
from src.server.models import Project
from src.utils.history_manager import history_manager

def migrate():
    print("Starting migration...")
    
    # Load history using existing manager logic to get the file path correctly
    history_manager._load_history()
    projects_data = history_manager.get_all_projects()
    
    if not projects_data:
        print("No history data found.")
        return

    db = next(get_db())
    try:
        count = 0
        for p_data in projects_data:
            pid = p_data.get("project_id")
            if not pid:
                continue
                
            # Check if exists
            existing = db.query(Project).filter(Project.id == pid).first()
            if existing:
                print(f"Project {pid} already exists in DB. Skipping.")
                continue
                
            # Parse dates
            created_at = None
            if p_data.get("created_at"):
                try:
                    created_at = datetime.fromisoformat(p_data["created_at"])
                except:
                    pass
            
            updated_at = None
            if p_data.get("updated_at"):
                try:
                    updated_at = datetime.fromisoformat(p_data["updated_at"])
                except:
                    pass

            # Map fields
            project = Project(
                id=pid,
                name=p_data.get("project_name", "Untitled"),
                input_type=p_data.get("input_type", "topic"),
                input_content=p_data.get("input_content", ""),
                status=p_data.get("status", "pending"),
                current_step=p_data.get("current_step", 0),
                steps=p_data.get("steps", []),
                topic_meta=p_data.get("topic_meta", {}),
                script=p_data.get("script", []),
                storyboard=p_data.get("storyboard", {}),
                image_prompts=p_data.get("image_prompts", []),
                video_prompts=p_data.get("video_prompts", []),
                image_paths=p_data.get("image_paths", []),
                video_paths=p_data.get("video_paths", []),
                final_video=p_data.get("final_video") or p_data.get("output_path"),
                total_tokens=p_data.get("total_tokens", {}),
                created_at=created_at,
                updated_at=updated_at
            )
            
            db.add(project)
            count += 1
        
        db.commit()
        print(f"Migrated {count} projects to database.")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate()

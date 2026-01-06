from sqlalchemy.orm import Session
from sqlalchemy import desc
from .models import Project
from datetime import datetime

class ProjectService:
    def __init__(self, db: Session):
        self.db = db

    def create_project(self, project_name, input_type, input_content, meta=None):
        steps = [
            {"step_name": "剧本创作", "status": "pending" if input_type == "topic" else "skipped"},
            {"step_name": "角色设计", "status": "pending"},
            {"step_name": "场景设计", "status": "pending"},
            {"step_name": "分镜生成", "status": "pending"},
            {"step_name": "提示词生成", "status": "pending"},
            {"step_name": "分镜首图", "status": "pending"},
            {"step_name": "分镜视频", "status": "pending"},
            {"step_name": "视频拼接", "status": "pending"}
        ]
        
        project = Project(
            name=project_name,
            input_type=input_type,
            input_content=input_content,
            status="pending",
            current_step=0 if input_type == "topic" else 1,
            steps=steps,
            topic_meta=meta or {},
            total_tokens={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_project(self, project_id):
        return self.db.query(Project).filter(Project.id == project_id).first()

    def get_all_projects(self, filters=None):
        query = self.db.query(Project)
        
        if filters:
            if filters.get("name"):
                query = query.filter(Project.name.ilike(f"%{filters['name']}%"))
            if filters.get("status"):
                query = query.filter(Project.status == filters["status"])
            if filters.get("input_type"):
                query = query.filter(Project.input_type == filters["input_type"])
                
        # Fetch all results first, then filter by JSON fields in memory if needed
        # (SQLite JSON support varies, python filtering is safer for this scale)
        results = query.order_by(desc(Project.created_at)).all()
        
        if not filters:
            return results
            
        final_results = []
        for p in results:
            meta = p.topic_meta or {}
            
            if filters.get("platform"):
                if meta.get("platform") != filters["platform"]:
                    continue
                    
            if filters.get("resolution"):
                if meta.get("resolution") != filters["resolution"]:
                    continue
                    
            if filters.get("aspect_ratio"):
                if meta.get("aspect_ratio") != filters["aspect_ratio"]:
                    continue
                    
            final_results.append(p)
            
        return final_results

    def update_project(self, project_id, updates):
        project = self.get_project(project_id)
        if not project:
            return None
        
        for key, value in updates.items():
            if hasattr(project, key):
                setattr(project, key, value)
            elif key == "project_name": # map project_name to name
                 project.name = value
        
        # Manually force update of updated_at if not handled by SQLAlchmey automatically in some contexts, 
        # but onupdate=func.now() should handle it.
        # However, for JSON fields, SQLAlchemy tracks mutations if using MutableDict, otherwise we might need to flag modified.
        # Since we are re-assigning the whole dict/list usually, it should be detected.
        
        self.db.commit()
        self.db.refresh(project)
        return project

    def update_step(self, project_id, step_index, step_updates):
        project = self.get_project(project_id)
        if not project or not project.steps:
            return None
        
        # Deep copy steps to modify
        steps = list(project.steps)
        if 0 <= step_index < len(steps):
            steps[step_index].update(step_updates)
            project.steps = steps # Re-assign to trigger update
            self.db.commit()
            return True
        return False

    def add_tokens(self, project_id, prompt_tokens, completion_tokens):
        project = self.get_project(project_id)
        if not project:
            return
            
        tokens = dict(project.total_tokens or {})
        tokens["prompt_tokens"] = tokens.get("prompt_tokens", 0) + prompt_tokens
        tokens["completion_tokens"] = tokens.get("completion_tokens", 0) + completion_tokens
        tokens["total_tokens"] = tokens["prompt_tokens"] + tokens["completion_tokens"]
        
        project.total_tokens = tokens
        self.db.commit()

    def add_usage(self, project_id, images=0, videos=0, duration=0.0):
        """Accumulate usage statistics"""
        project = self.get_project(project_id)
        if not project:
            return
            
        stats = dict(project.usage_stats or {})
        stats["total_images"] = stats.get("total_images", 0) + images
        stats["total_videos"] = stats.get("total_videos", 0) + videos
        stats["total_video_duration"] = stats.get("total_video_duration", 0.0) + float(duration)
        
        project.usage_stats = stats
        self.db.commit()

    def delete_project(self, project_id):
        project = self.get_project(project_id)
        if project:
            self.db.delete(project)
            self.db.commit()
            return True
        return False

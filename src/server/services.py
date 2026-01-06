from sqlalchemy.orm import Session
from .models import Task, Log, Project
import datetime
import json
from src.utils.redis_client import redis_client

class TaskService:
    def __init__(self, db: Session):
        self.db = db

    def _cache_key(self, task_id):
        return f"task:{task_id}"

    def create_task(self, project_id, task_type):
        """Create a new task. Ensures project exists in DB."""
        # Ensure project exists
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            project = Project(id=project_id, name="Unknown Project", input_content="Auto-created")
            self.db.add(project)
            self.db.commit()

        task = Task(project_id=project_id, type=task_type, status="pending", progress=0)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        
        # Initial Cache
        self._update_cache(task)
        
        return task

    def update_task(self, task_id, progress=None, status=None, step=None, result=None, error=None):
        """Update task status and progress."""
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if task:
            if progress is not None:
                task.progress = progress
            if status:
                task.status = status
            if step:
                task.current_step = step
            if result:
                task.result = result
            if error:
                task.error = error
            self.db.commit()
            self.db.refresh(task)
            
            # Write-Through Cache
            self._update_cache(task)
            
            return task
        return None

    def get_task(self, task_id):
        # Cache-Aside: Try Redis first
        cached = redis_client.hgetall(self._cache_key(task_id))
        if cached:
            # Reconstruct basic Task object for response
            # Note: This is a partial object, but sufficient for status polling
            # result/error are stored as strings in Redis, might need parsing if complex logic uses them.
            # But for simple polling, returning dict or object with attributes is fine.
            # To be compatible with ORM usage downstream, we might need a real object, 
            # but usually API layer just serializes it.
            # Let's return a simple object wrapper or the dict if the caller handles it.
            # However, existing code expects object access like task.status.
            
            class CachedTask:
                def __init__(self, data):
                    self.id = data.get("id")
                    self.project_id = data.get("project_id")
                    self.type = data.get("type")
                    self.status = data.get("status")
                    self.progress = int(data.get("progress", 0))
                    self.current_step = int(data.get("current_step", 0)) if data.get("current_step") else None
                    self.result = json.loads(data.get("result")) if data.get("result") else None
                    self.error = data.get("error") if data.get("error") != 'None' else None
                    self.created_at = datetime.datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else None
                    self.updated_at = datetime.datetime.fromisoformat(data.get("updated_at")) if data.get("updated_at") else None

            return CachedTask(cached)

        # Fallback to DB
        task = self.db.query(Task).filter(Task.id == task_id).first()
        if task:
            self._update_cache(task)
        return task

    def get_project_tasks(self, project_id):
        # We don't cache list for now as it's less frequent and harder to invalidate
        return self.db.query(Task).filter(Task.project_id == project_id).order_by(Task.created_at.desc()).all()

    def _update_cache(self, task):
        data = {
            "id": str(task.id),
            "project_id": str(task.project_id),
            "type": str(task.type),
            "status": str(task.status),
            "progress": str(task.progress),
            "current_step": str(task.current_step) if task.current_step is not None else "",
            "result": json.dumps(task.result) if task.result else "",
            "error": str(task.error) if task.error else "None",
            "created_at": task.created_at.isoformat() if task.created_at else "",
            "updated_at": task.updated_at.isoformat() if task.updated_at else ""
        }
        redis_client.hset(self._cache_key(task.id), mapping=data)
        redis_client.expire(self._cache_key(task.id), 3600) # 1 hour TTL

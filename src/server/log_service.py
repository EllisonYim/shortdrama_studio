from sqlalchemy.orm import Session
from .models import Log

class LogService:
    def __init__(self, db: Session):
        self.db = db

    def log(self, project_id, task_id, level, message, module=None, details=None):
        """Create a new log entry."""
        log_entry = Log(
            project_id=project_id, 
            task_id=task_id, 
            level=level, 
            message=message, 
            module=module,
            details=details
        )
        self.db.add(log_entry)
        self.db.commit()
        return log_entry

    def get_logs(self, project_id=None, task_id=None, level=None, limit=100):
        query = self.db.query(Log)
        if project_id:
            query = query.filter(Log.project_id == project_id)
        if task_id:
            query = query.filter(Log.task_id == task_id)
        if level:
            query = query.filter(Log.level == level)
        
        return query.order_by(Log.timestamp.desc()).limit(limit).all()

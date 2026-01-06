import time
import threading
from loguru import logger
from sqlalchemy.orm import Session
from src.server.database import get_db
from src.server.models import VideoTask, Project
from src.models.veadk_client import veadk_client
from src.core.video_generator import VideoGenerator
from src.server.project_service import ProjectService
from src.server.log_service import LogService
from src.server.services import TaskService

class VideoScheduler:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(VideoScheduler, cls).__new__(cls)
            cls._instance.running = False
            cls._instance.video_gen = VideoGenerator()
        return cls._instance

    def start(self):
        if self.running:
            return
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()
        logger.info("Video Scheduler started")

    def _loop(self):
        while self.running:
            try:
                self._process_pending_tasks()
            except Exception as e:
                logger.error(f"Video Scheduler Error: {e}")
            time.sleep(5) # Poll every 5 seconds

    def _process_pending_tasks(self):
        # Use a new session for each cycle to ensure freshness
        db = next(get_db())
        try:
            # Limit batch size to avoid holding DB too long if many tasks
            tasks = db.query(VideoTask).filter(VideoTask.status == "submitted").limit(10).all()
            if tasks:
                logger.debug(f"Video Scheduler checking {len(tasks)} tasks...")
            
            for task in tasks:
                self._check_task(task, db)
        finally:
            db.close()

    def _check_task(self, task: VideoTask, db: Session):
        try:
            status, video_url, error = veadk_client.check_video_task_status(task.volc_task_id)
            
            if status == "RUNNING":
                return # Do nothing
            
            ps = ProjectService(db)
            ls = LogService(db)
            
            if status == "SUCCEEDED" and video_url:
                logger.info(f"Task {task.volc_task_id} (Shot {task.shot_number}) succeeded. Processing result...")
                
                # Process result (Download/Upload)
                final_url, proc_error = self.video_gen.process_completed_video(
                    video_url, 
                    task.project_id, 
                    task.shot_number
                )
                
                if final_url:
                    # Update Task
                    task.status = "completed"
                    task.video_url = final_url
                    db.commit() # Commit task update first
                    
                    # Update Project
                    project = ps.get_project(task.project_id)
                    if project:
                        video_paths = list(project.video_paths or [])
                        # Ensure size
                        while len(video_paths) < task.shot_number:
                            video_paths.append(None)
                        # Shot number is 1-based index usually
                        if task.shot_number > 0:
                            video_paths[task.shot_number - 1] = final_url
                            ps.update_project(task.project_id, {"video_paths": video_paths})
                            
                            # Update meta status
                            meta = dict(project.topic_meta or {})
                            meta[f"shot_status_video_{task.shot_number}"] = "completed"
                            ps.update_project(task.project_id, {"topic_meta": meta})
                            
                            # Log
                            ls.log(task.project_id, None, "INFO", f"Shot {task.shot_number} video completed", module="video_scheduler")
                    
                    if task.task_id:
                        self._update_parent_task(task.task_id, db)

                else:
                    # Processing failed
                    task.status = "failed"
                    task.error_msg = f"Processing failed: {proc_error}"
                    db.commit()
                    ls.log(task.project_id, None, "ERROR", f"Shot {task.shot_number} processing failed: {proc_error}", module="video_scheduler")
                    
                    # Update meta
                    project = ps.get_project(task.project_id)
                    if project:
                        meta = dict(project.topic_meta or {})
                        meta[f"shot_status_video_{task.shot_number}"] = "failed"
                        meta[f"shot_error_video_{task.shot_number}"] = proc_error
                        ps.update_project(task.project_id, {"topic_meta": meta})
                    
                    if task.task_id:
                        self._update_parent_task(task.task_id, db)

            elif status == "FAILED":
                logger.info(f"Task {task.volc_task_id} (Shot {task.shot_number}) failed: {error}")
                task.status = "failed"
                task.error_msg = error
                db.commit()
                
                ls.log(task.project_id, None, "ERROR", f"Shot {task.shot_number} generation failed: {error}", module="video_scheduler")
                
                # Update meta
                project = ps.get_project(task.project_id)
                if project:
                    meta = dict(project.topic_meta or {})
                    meta[f"shot_status_video_{task.shot_number}"] = "failed"
                    meta[f"shot_error_video_{task.shot_number}"] = error
                    ps.update_project(task.project_id, {"topic_meta": meta})
                
                if task.task_id:
                    self._update_parent_task(task.task_id, db)
            
            # If UNKNOWN, maybe retry later?
            
        except Exception as e:
            logger.error(f"Error checking task {task.id}: {e}")
            # Don't mark failed immediately unless critical?

    def _update_parent_task(self, parent_task_id, db: Session):
        # Check all sibling tasks
        siblings = db.query(VideoTask).filter(VideoTask.task_id == parent_task_id).all()
        if not siblings:
            return

        total = len(siblings)
        completed = sum(1 for t in siblings if t.status == "completed")
        failed = sum(1 for t in siblings if t.status == "failed")
        
        # Calculate progress
        progress = int((completed + failed) / total * 100) if total > 0 else 0
        
        ts = TaskService(db)
        parent_task = ts.get_task(parent_task_id)
        if not parent_task:
            return

        if completed + failed == total:
            # All done
            if failed == total:
                 ts.update_task(parent_task_id, status="failed", error="All video tasks failed")
            else:
                 # Partial success is considered success for the batch task, 
                 # as users can see individual failures.
                 ts.update_task(parent_task_id, status="completed", progress=100, result={"completed": completed, "failed": failed})
        else:
            # Still running
            ts.update_task(parent_task_id, status="running", progress=progress)


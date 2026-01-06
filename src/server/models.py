from sqlalchemy import Column, String, Integer, JSON, DateTime, ForeignKey, Text, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    input_type = Column(String) # topic, script
    input_content = Column(Text, nullable=False)
    status = Column(String, default="pending") # pending, in_progress, completed, failed
    current_step = Column(Integer, default=0)
    steps = Column(JSON, default=[])
    
    # JSON fields for flexible data storage
    topic_meta = Column(JSON, default={})
    script = Column(JSON, default=[])
    characters = Column(JSON, default=[])
    scenes = Column(JSON, default=[])
    storyboard = Column(JSON, default={})
    image_prompts = Column(JSON, default=[])
    video_prompts = Column(JSON, default=[])
    image_paths = Column(JSON, default=[])
    video_paths = Column(JSON, default=[])
    final_video = Column(String, nullable=True)
    total_tokens = Column(JSON, default={})
    usage_stats = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    logs = relationship("Log", back_populates="project", cascade="all, delete-orphan")

    def to_dict(self):
        base_dict = {
            "project_id": self.id,
            "project_name": self.name,
            "input_type": self.input_type,
            "input_content": self.input_content,
            "status": self.status,
            "current_step": self.current_step,
            "steps": self.steps,
            "topic_meta": self.topic_meta,
            "script": self.script,
            "characters": self.characters,
            "scenes": self.scenes,
            "storyboard": self.storyboard,
            "image_prompts": self.image_prompts,
            "video_prompts": self.video_prompts,
            "image_paths": self.image_paths,
            "video_paths": self.video_paths,
            "final_video": self.final_video,
            "total_tokens": self.total_tokens,
            "usage_stats": self.usage_stats,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
        # Flatten topic_meta into base_dict for backward compatibility
        if self.topic_meta:
            for k, v in self.topic_meta.items():
                base_dict[k] = v
        return base_dict


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False) # script_generation, image_generation, etc.
    status = Column(String, default="pending") # pending, running, completed, failed
    progress = Column(Integer, default=0)
    current_step = Column(String, nullable=True) # Description of current step
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    project = relationship("Project", back_populates="tasks")
    logs = relationship("Log", back_populates="task", cascade="all, delete-orphan")


class Log(Base):
    __tablename__ = "logs"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    level = Column(String, default="INFO") # DEBUG, INFO, WARN, ERROR
    message = Column(Text, nullable=False)
    module = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="logs")
    task = relationship("Task", back_populates="logs")


class VideoTask(Base):
    __tablename__ = "video_tasks"

    id = Column(String, primary_key=True, default=generate_uuid)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    shot_number = Column(Integer, nullable=False)
    volc_task_id = Column(String, nullable=False)
    status = Column(String, default="submitted") # submitted, completed, failed
    video_url = Column(String, nullable=True)
    error_msg = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    project = relationship("Project")

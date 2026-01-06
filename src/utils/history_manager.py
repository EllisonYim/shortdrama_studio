"""
历史记录管理模块
用于管理项目历史记录和Token消耗统计
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from loguru import logger
from dataclasses import dataclass, asdict
import uuid


@dataclass
class TokenUsage:
    """Token使用记录"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def add(self, prompt: int, completion: int):
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.total_tokens = self.prompt_tokens + self.completion_tokens


@dataclass
class StepRecord:
    """步骤记录"""
    step_name: str
    status: str  # pending, running, completed, failed
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    token_usage: Optional[Dict] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ProjectRecord:
    """项目记录"""
    project_id: str
    project_name: str
    input_type: str  # topic or script
    input_content: str
    created_at: str
    updated_at: str
    status: str  # pending, in_progress, completed, failed
    current_step: int
    steps: List[Dict]
    total_tokens: Dict
    output_path: Optional[str] = None


from src.utils.config_loader import config_loader

class HistoryManager:
    """历史记录管理器"""
    
    def __init__(self, history_file: str = None):
        if history_file is None:
            history_file = config_loader.get("app.history_file")
        
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._history: List[Dict] = []
        self._load_history()
    
    def _load_history(self):
        """加载历史记录"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
                logger.info(f"加载历史记录: {len(self._history)} 条")
            except Exception as e:
                logger.error(f"加载历史记录失败: {e}")
                self._history = []
        else:
            self._history = []
    
    def _save_history(self):
        """保存历史记录"""
        try:
            # Atomic write: write to temp file then rename
            temp_file = self.history_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
            temp_file.replace(self.history_file)
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
    
    def create_project(self, project_name: str, input_type: str, input_content: str) -> str:
        """创建新项目"""
        project_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        steps = [
            {"step_name": "剧本创作", "status": "pending" if input_type == "topic" else "skipped"},
            {"step_name": "分镜生成", "status": "pending"},
            {"step_name": "提示词生成", "status": "pending"},
            {"step_name": "分镜首图", "status": "pending"},
            {"step_name": "分镜视频", "status": "pending"},
            {"step_name": "视频拼接", "status": "pending"}
        ]
        
        project = {
            "project_id": project_id,
            "project_name": project_name,
            "input_type": input_type,
            "input_content": input_content,
            "created_at": now,
            "updated_at": now,
            "status": "pending",
            "current_step": 0 if input_type == "topic" else 1,
            "steps": steps,
            "total_tokens": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "output_path": None
        }
        
        self._history.insert(0, project)
        self._save_history()
        logger.info(f"创建新项目: {project_id}")
        
        return project_id
    
    def get_project(self, project_id: str) -> Optional[Dict]:
        """获取项目记录"""
        for project in self._history:
            if project["project_id"] == project_id:
                return project
        return None
    
    def update_project(self, project_id: str, updates: Dict):
        """更新项目记录"""
        for i, project in enumerate(self._history):
            if project["project_id"] == project_id:
                project.update(updates)
                project["updated_at"] = datetime.now().isoformat()
                self._history[i] = project
                self._save_history()
                return True
        return False
    
    def update_step(self, project_id: str, step_index: int, step_updates: Dict):
        """更新步骤状态"""
        project = self.get_project(project_id)
        if project and 0 <= step_index < len(project["steps"]):
            project["steps"][step_index].update(step_updates)
            project["updated_at"] = datetime.now().isoformat()
            self._save_history()
            return True
        return False
    
    def add_tokens(self, project_id: str, prompt_tokens: int, completion_tokens: int):
        """添加Token使用量"""
        project = self.get_project(project_id)
        if project:
            project["total_tokens"]["prompt_tokens"] += prompt_tokens
            project["total_tokens"]["completion_tokens"] += completion_tokens
            project["total_tokens"]["total_tokens"] = (
                project["total_tokens"]["prompt_tokens"] + 
                project["total_tokens"]["completion_tokens"]
            )
            self._save_history()
    
    def get_all_projects(self) -> List[Dict]:
        """获取所有项目"""
        return self._history
    
    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        for i, project in enumerate(self._history):
            if project["project_id"] == project_id:
                self._history.pop(i)
                self._save_history()
                logger.info(f"删除项目: {project_id}")
                return True
        return False
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total_projects = len(self._history)
        completed_projects = sum(1 for p in self._history if p["status"] == "completed")
        total_tokens = sum(p["total_tokens"]["total_tokens"] for p in self._history)
        
        return {
            "total_projects": total_projects,
            "completed_projects": completed_projects,
            "in_progress_projects": sum(1 for p in self._history if p["status"] == "in_progress"),
            "failed_projects": sum(1 for p in self._history if p["status"] == "failed"),
            "total_tokens": total_tokens,
            "avg_tokens_per_project": total_tokens / total_projects if total_projects > 0 else 0
        }


# 全局历史管理器实例
history_manager = HistoryManager()

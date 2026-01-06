"""
配置加载器模块
用于加载和管理配置文件
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


class ConfigLoader:
    """配置加载器类"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    _prompts: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Fix root_path calculation
        self.root_path = Path(__file__).resolve().parents[2]
        # If config dir doesn't exist here, try subdirectory (common in some setups)
        if not (self.root_path / "config").exists():
            potential_path = self.root_path / "short_drama_studio"
            if (potential_path / "config").exists():
                self.root_path = potential_path
        
        if not self._config:
            self.load_config()
            self.load_prompts()
    
    def load_config(self, config_path: str = None) -> Dict[str, Any]:
        """加载主配置文件"""
        if config_path is None:
            config_path = self.root_path / "config" / "config.yaml"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            
            # 执行配置结构迁移 (In-Memory Migration)
            self._migrate_config_structure()
            
            logger.info(f"配置文件加载成功: {config_path}")
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
            self._config = self._get_default_config()
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            self._config = self._get_default_config()
        
        return self._config

    def _migrate_config_structure(self):
        """将旧版配置结构迁移到新的多平台结构"""
        if not self._config: return

        # 确保 platform 存在
        if "platform" not in self._config:
            self._config["platform"] = "volcengine"
        
        if "platforms" not in self._config:
            self._config["platforms"] = {}
        
        # 迁移根节点的 volcengine 配置
        if "volcengine" in self._config:
            if "volcengine" not in self._config["platforms"]:
                self._config["platforms"]["volcengine"] = self._config["volcengine"]
            # 移除根节点以强制使用新结构（通过 get 的兼容逻辑访问）
            del self._config["volcengine"]

        # 迁移根节点的 tos 配置到 volcengine 平台下
        if "tos" in self._config:
            if "volcengine" in self._config["platforms"]:
                if "tos" not in self._config["platforms"]["volcengine"]:
                    self._config["platforms"]["volcengine"]["tos"] = self._config["tos"]
            del self._config["tos"]
    
    def load_prompts(self, prompts_path: str = None) -> Dict[str, Any]:
        """加载提示词配置文件"""
        if prompts_path is None:
            prompts_path = self.root_path / "config" / "prompts.yaml"
        
        try:
            with open(prompts_path, 'r', encoding='utf-8') as f:
                self._prompts = yaml.safe_load(f)
            logger.info(f"提示词配置加载成功: {prompts_path}")
        except FileNotFoundError:
            logger.warning(f"提示词配置不存在: {prompts_path}，使用默认提示词")
            self._prompts = self._get_default_prompts()
        except Exception as e:
            logger.error(f"提示词配置加载失败: {e}")
            self._prompts = self._get_default_prompts()
        
        return self._prompts
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "platform": "volcengine",
            "platforms": {
                "volcengine": {
                    "access_key": "",
                    "secret_key": "",
                    "endpoints": {
                        "llm": "https://ark.cn-beijing.volces.com/api/v3",
                        "image": "https://visual.volcengineapi.com",
                        "video": "https://open.volcengineapi.com"
                    },
                    "models": {
                        "llm": {
                            "model_id": "",
                            "model_name": "doubao-pro-32k",
                            "max_tokens": 4096,
                            "temperature": 0.7
                        },
                        "image": {
                            "model_id": "high_aes_general_v21",
                            "width": 1280,
                            "height": 720,
                            "steps": 30
                        },
                        "video": {
                            "model_id": "video_generation_v1",
                            "duration": 5,
                            "fps": 24
                        }
                    },
                    "tos": {
                        "enable": False,
                        "endpoint": "tos-cn-beijing.volces.com",
                        "region": "cn-beijing",
                        "bucket_name": ""
                    }
                }
            },
            "app": {
                "allow_settings_edit": False,
                "project_dir": str(self.root_path / "data" / "projects"),
                "history_file": str(self.root_path / "data" / "history.json"),
                "temp_dir": str(self.root_path / "data" / "temp"),
                "max_history": 100,
                "video_format": "mp4",
                "video_resolution": {
                    "width": 1024,
                    "height": 1024
                }
            },
            "server": {
                "host": "127.0.0.1",
                "port": 8000
            },
            "web": {
                "server": {
                    "host": "127.0.0.1",
                    "port": 8000
                }
            },
            "logging": {
                "level": "INFO",
                "file": "./logs/app.log",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
    
    def _get_default_prompts(self) -> Dict[str, Any]:
        """获取默认提示词"""
        return {
            "script_generation": {
                "system": "你是一位专业的短剧编剧。",
                "user_template": "请根据主题'{topic}'创作剧本。"
            },
            "storyboard_generation": {
                "system": "你是一位专业的分镜师。",
                "user_template": "请将剧本转化为分镜：{script}"
            }
        }
    
    @property
    def config(self) -> Dict[str, Any]:
        """获取配置"""
        return self._config
    
    @property
    def prompts(self) -> Dict[str, Any]:
        """获取提示词配置"""
        return self._prompts
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项（支持点号分隔的路径）"""
        # 尝试直接获取
        val = self._get_value_by_path(key)
        if val is not None:
            return val
            
        # 兼容性回退逻辑
        if key == "volcengine" or key.startswith("volcengine."):
            # 映射 volcengine.xxx -> platforms.volcengine.xxx
            suffix = key[10:] # remove "volcengine"
            new_key = "platforms.volcengine" + suffix
            val = self._get_value_by_path(new_key)
            if val is not None: return val
            
        if key == "tos" or key.startswith("tos."):
            # 映射 tos.xxx -> platforms.{current_platform}.tos.xxx
            current_platform = self._config.get("platform", "volcengine")
            suffix = key[3:] # remove "tos"
            new_key = f"platforms.{current_platform}.tos{suffix}"
            val = self._get_value_by_path(new_key)
            if val is not None: return val
            
            # Fallback to volcengine if not found in current platform (optional, but safer for legacy)
            if current_platform != "volcengine":
                 new_key_legacy = f"platforms.volcengine.tos{suffix}"
                 val = self._get_value_by_path(new_key_legacy)
                 if val is not None: return val
            
        return default

    def _get_value_by_path(self, key: str) -> Any:
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
            if value is None:
                return None
        return value
    
    def get_prompt(self, key: str) -> Optional[Dict[str, str]]:
        """获取提示词配置"""
        keys = key.split('.')
        value = self._prompts
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return None
        return value
    
    def save_config(self, config_path: str = None):
        """保存配置到文件"""
        if config_path is None:
            config_path = self.root_path / "config" / "config.yaml"
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
        logger.info(f"配置已保存: {config_path}")
    
    def save_prompts(self, prompts_path: str = None):
        """保存提示词到文件"""
        if prompts_path is None:
            prompts_path = self.root_path / "config" / "prompts.yaml"
        
        with open(prompts_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._prompts, f, allow_unicode=True, default_flow_style=False)
        logger.info(f"提示词已保存: {prompts_path}")
    
    def update_config(self, key: str, value: Any):
        """更新配置项"""
        # 映射旧 key 到新结构
        real_key = key
        if key.startswith("volcengine."):
            real_key = "platforms.volcengine" + key[10:]
        elif key.startswith("tos."):
            current_platform = self._config.get("platform", "volcengine")
            real_key = f"platforms.{current_platform}.tos" + key[3:]
            
        keys = real_key.split('.')
        config = self._config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value
    
    def update_prompt(self, key: str, value: Any):
        """更新提示词"""
        keys = key.split('.')
        prompts = self._prompts
        for k in keys[:-1]:
            prompts = prompts.setdefault(k, {})
        prompts[keys[-1]] = value


# 全局配置实例
config_loader = ConfigLoader()

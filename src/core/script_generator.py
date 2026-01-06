"""
剧本生成模块
"""

import json
from typing import Dict, Tuple
from loguru import logger

from ..models.veadk_client import veadk_client
from ..utils.config_loader import config_loader


class ScriptGenerator:
    """剧本生成器"""
    
    def __init__(self):
        self.prompts = config_loader.get_prompt("script_generation")
    
    def generate(
        self, 
        topic: str, 
        duration: int = 3, 
        style: str = "现代都市",
        audience: str = "年轻人"
    ) -> Tuple[str, Dict]:
        """
        根据主题生成剧本
        
        Args:
            topic: 主题
            duration: 时长（分钟）
            style: 风格
            audience: 目标受众
        
        Returns:
            (剧本内容, Token使用情况)
        """
        system_prompt = self.prompts.get("system", "")
        user_template = self.prompts.get("user_template", "")
        
        user_message = user_template.format(
            topic=topic,
            duration=duration,
            style=style,
            audience=audience
        )
        
        messages = [{"role": "user", "content": user_message}]
        
        logger.info(f"开始生成剧本: {topic}")
        script, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        return script, token_usage
    
    def optimize(self, original_script: str, feedback: str) -> Tuple[str, Dict]:
        """
        根据反馈优化剧本
        
        Args:
            original_script: 原剧本
            feedback: 用户反馈
        
        Returns:
            (优化后的剧本, Token使用情况)
        """
        opt_prompts = config_loader.get_prompt("script_optimization")
        system_prompt = opt_prompts.get("system", "")
        user_template = opt_prompts.get("user_template", "")
        
        user_message = user_template.format(
            original_script=original_script,
            feedback=feedback
        )
        
        messages = [{"role": "user", "content": user_message}]
        
        logger.info("优化剧本中...")
        optimized_script, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        return optimized_script, token_usage

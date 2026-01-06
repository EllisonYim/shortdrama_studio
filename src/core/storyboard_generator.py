"""
分镜生成模块
"""

import json
import re
from typing import Dict, List, Tuple
from loguru import logger

from ..models.veadk_client import veadk_client
from ..utils.config_loader import config_loader


class StoryboardGenerator:
    """分镜生成器"""
    
    def __init__(self):
        self.prompts = config_loader.get_prompt("storyboard_generation")
    
    def generate(self, script: str) -> Tuple[Dict, Dict]:
        """
        根据剧本生成分镜
        
        Args:
            script: 剧本内容
        
        Returns:
            (分镜数据, Token使用情况)
        """
        system_prompt = self.prompts.get("system", "")
        user_template = self.prompts.get("user_template", "")
        
        user_message = user_template.format(script=script)
        
        messages = [{"role": "user", "content": user_message}]
        
        logger.info("开始生成分镜...")
        response, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        # 解析JSON
        storyboard = self._parse_storyboard(response)
        
        return storyboard, token_usage
    
    def _parse_storyboard(self, response: str) -> Dict:
        """解析分镜JSON"""
        try:
            # 尝试提取JSON块
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response
            
            storyboard = json.loads(json_str)
            logger.info(f"分镜解析成功: {storyboard.get('total_shots', 0)} 个镜头")
            return storyboard
            
        except json.JSONDecodeError as e:
            logger.error(f"分镜JSON解析失败: {e}")
            return {
                "title": "未知",
                "total_shots": 0,
                "shots": [],
                "raw_response": response
            }
    
    def optimize(self, original_storyboard: Dict, feedback: str) -> Tuple[Dict, Dict]:
        """
        根据反馈优化分镜
        
        Args:
            original_storyboard: 原分镜
            feedback: 用户反馈
        
        Returns:
            (优化后的分镜, Token使用情况)
        """
        opt_prompts = config_loader.get_prompt("storyboard_optimization")
        system_prompt = opt_prompts.get("system", "")
        user_template = opt_prompts.get("user_template", "")
        
        user_message = user_template.format(
            original_storyboard=json.dumps(original_storyboard, ensure_ascii=False, indent=2),
            feedback=feedback
        )
        
        messages = [{"role": "user", "content": user_message}]
        
        logger.info("优化分镜中...")
        response, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        storyboard = self._parse_storyboard(response)
        
        return storyboard, token_usage

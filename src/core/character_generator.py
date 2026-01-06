"""
角色生成模块
"""

import json
from typing import Dict, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from ..models.veadk_client import veadk_client
from ..utils.config_loader import config_loader


class CharacterGenerator:
    """角色生成器"""
    
    def __init__(self):
        self.max_workers = config_loader.get("app.concurrency.prompt", 5)

    def reload_config(self):
        self.max_workers = config_loader.get("app.concurrency.prompt", 5)
    
    def generate(
        self, 
        script: str
    ) -> Tuple[List[Dict], Dict]:
        """
        根据剧本生成角色设计 (不含Prompt)
        """
        # Reload prompts
        prompts = config_loader.get_prompt("character_design")
        system_prompt = prompts.get("system", "")
        user_template = prompts.get("user_template", "")
        
        user_message = user_template.format(script=script)
        messages = [{"role": "user", "content": user_message}]
        
        logger.info("开始提取角色设计...")
        content, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        try:
            content = self._extract_json(content)
            data = json.loads(content)
            characters = data.get("characters", [])
            return characters, token_usage
        except Exception as e:
            logger.error(f"角色设计解析失败: {e}")
            return [], token_usage

    def generate_prompts(
        self,
        characters: List[Dict],
        style: str,
        visual_style: str
    ) -> Tuple[List[Dict], Dict]:
        """
        为角色生成提示词 (并发版)
        """
        updated_characters = [None] * len(characters)
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        logger.info(f"开始并发生成角色提示词 (Workers: {self.max_workers})...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Map future to index to maintain order
            future_to_index = {
                executor.submit(self.generate_single_prompt, char, style, visual_style): i 
                for i, char in enumerate(characters)
            }
            
            for future in as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    char, usage = future.result()
                    updated_characters[i] = char
                    
                    # Aggregate usage
                    if usage:
                        for k, v in usage.items():
                            if k in total_usage and isinstance(v, (int, float)):
                                total_usage[k] += v
                except Exception as e:
                    logger.error(f"角色 {characters[i].get('name')} 提示词生成失败: {e}")
                    updated_characters[i] = characters[i] # Fallback to original
        
        # Filter out any Nones (shouldn't happen with fallback logic)
        final_chars = [c for c in updated_characters if c is not None]
        return final_chars, total_usage

    def generate_single_prompt(
        self,
        character: Dict,
        style: str,
        visual_style: str
    ) -> Tuple[Dict, Dict]:
        """
        为单个角色生成提示词
        """
        prompts_conf = config_loader.get_prompt("character_prompt_generation")
        system_prompt = prompts_conf.get("system", "")
        user_template = prompts_conf.get("user_template", "")
        
        # Wrap single character in list for the template
        chars_summary = json.dumps([character], ensure_ascii=False, indent=2)
        
        user_message = user_template.format(
            characters=chars_summary,
            style=style,
            visual_style=visual_style
        )
        messages = [{"role": "user", "content": user_message}]
        
        logger.info(f"开始生成角色 {character.get('name')} 的提示词...")
        content, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        try:
            content = self._extract_json(content)
            data = json.loads(content)
            char_prompts = data.get("characters", [])
            
            if char_prompts:
                # We expect one character back, but we'll take the first one that matches or just the first one
                generated_char = char_prompts[0]
                new_prompt = generated_char.get("prompt", "")
                
                updated_char = character.copy()
                updated_char["prompt"] = new_prompt
                return updated_char, token_usage
            
            return character, token_usage
        except Exception as e:
            logger.error(f"角色提示词解析失败: {e}")
            return character, token_usage

    def _extract_json(self, content: str) -> str:
        start = content.find("```json")
        if start != -1:
            start += 7
            end = content.find("```", start)
            if end != -1:
                return content[start:end].strip()
        return content

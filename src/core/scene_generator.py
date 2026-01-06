"""
场景生成模块
"""

import json
from typing import Dict, Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from ..models.veadk_client import veadk_client
from ..utils.config_loader import config_loader


class SceneGenerator:
    """场景生成器"""
    
    def __init__(self):
        self.max_workers = config_loader.get("app.concurrency.prompt", 5)

    def reload_config(self):
        self.max_workers = config_loader.get("app.concurrency.prompt", 5)
    
    def generate(
        self, 
        script: str
    ) -> Tuple[List[Dict], Dict]:
        """
        根据剧本生成场景设计
        """
        prompts = config_loader.get_prompt("scene_design")
        system_prompt = prompts.get("system", "")
        user_template = prompts.get("user_template", "")
        
        user_message = user_template.format(script=script)
        messages = [{"role": "user", "content": user_message}]
        
        logger.info("开始提取场景设计...")
        content, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        try:
            content = self._extract_json(content)
            data = json.loads(content)
            scenes = data.get("scenes", [])
            return scenes, token_usage
        except Exception as e:
            logger.error(f"场景设计解析失败: {e}")
            return [], token_usage

    def generate_prompts(
        self,
        scenes: List[Dict],
        style: str,
        visual_style: str
    ) -> Tuple[List[Dict], Dict]:
        """
        为场景生成提示词 (并发版)
        """
        updated_scenes = [None] * len(scenes)
        total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
        logger.info(f"开始并发生成场景提示词 (Workers: {self.max_workers})...")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(self.generate_single_prompt, scene, style, visual_style): i
                for i, scene in enumerate(scenes)
            }
            
            for future in as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    scene, usage = future.result()
                    updated_scenes[i] = scene
                    
                    if usage:
                        for k, v in usage.items():
                            if k in total_usage and isinstance(v, (int, float)):
                                total_usage[k] += v
                except Exception as e:
                    logger.error(f"场景 {scenes[i].get('name')} 提示词生成失败: {e}")
                    updated_scenes[i] = scenes[i]
        
        final_scenes = [s for s in updated_scenes if s is not None]
        return final_scenes, total_usage

    def generate_single_prompt(
        self,
        scene: Dict,
        style: str,
        visual_style: str
    ) -> Tuple[Dict, Dict]:
        """
        为单个场景重新生成提示词
        """
        prompts_conf = config_loader.get_prompt("scene_prompt_generation")
        system_prompt = prompts_conf.get("system", "")
        # Construct a temporary user prompt for single item
        # We can reuse the template but need to wrap the single scene in a list structure
        # or adjust the prompt. For simplicity, we wrap it.
        user_template = prompts_conf.get("user_template", "")
        
        scenes_summary = json.dumps([scene], ensure_ascii=False, indent=2)
        
        user_message = user_template.format(
            scenes=scenes_summary,
            style=style,
            visual_style=visual_style
        )
        messages = [{"role": "user", "content": user_message}]
        
        logger.info(f"开始重新生成场景提示词: {scene.get('name')}")
        content, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        try:
            content = self._extract_json(content)
            data = json.loads(content)
            scene_prompts = data.get("scenes", [])
            
            if scene_prompts:
                # We expect one result
                new_prompt = scene_prompts[0].get("prompt")
                scene["prompt"] = new_prompt
                
            return scene, token_usage
        except Exception as e:
            logger.error(f"单场景提示词解析失败: {e}")
            return scene, token_usage

    def _extract_json(self, content: str) -> str:
        start = content.find("```json")
        if start != -1:
            start += 7
            end = content.find("```", start)
            if end != -1:
                return content[start:end].strip()
        return content

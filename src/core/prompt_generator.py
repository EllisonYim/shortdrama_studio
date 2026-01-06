"""
提示词生成模块
生成图像提示词和视频提示词
"""

import json
import re
from typing import Dict, List, Tuple, Optional
from loguru import logger
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models.veadk_client import veadk_client
from ..utils.config_loader import config_loader


class PromptGenerator:
    """提示词生成器"""
    
    def __init__(self):
        self.reload_config()

    def reload_config(self):
        """重新加载配置"""
        self.image_prompts_config = config_loader.get_prompt("image_prompt_generation")
        self.video_prompts_config = config_loader.get_prompt("video_prompt_generation")
        self.max_workers = config_loader.get("app.concurrency.prompt", 10)
        logger.info(f"PromptGenerator 配置已更新, max_workers={self.max_workers}")

    def generate_all_prompts(
        self, 
        storyboard: Dict, 
        style: str = "cinematic",
        characters: List[Dict] = None,
        scenes: List[Dict] = None
    ) -> Tuple[List[Dict], List[Dict], Dict]:
        """
        Concurrent pipeline generation for both image and video prompts.
        """
        shots = storyboard.get("shots", [])
        total_shots = len(shots)
        
        # Pre-allocate lists
        all_image_prompts = [None] * total_shots
        all_video_prompts = [None] * total_shots
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        
        # Configs
        img_sys = self.image_prompts_config.get("system", "")
        img_tpl = self.image_prompts_config.get("user_template", "")
        vid_sys = self.video_prompts_config.get("system", "")
        vid_tpl = self.video_prompts_config.get("user_template", "")
        
        def process_shot(index, shot):
            try:
                # 1. Generate Image Prompt
                img_p, img_t = self._generate_single_image_prompt(
                    shot, img_tpl, img_sys, style, characters, scenes
                )
                
                # 2. Generate Video Prompt (using image prompt result)
                img_content = img_p.get("positive_prompt", "")
                vid_p, vid_t = self._generate_single_video_prompt(shot, img_content, vid_tpl, vid_sys)
                
                return index, img_p, vid_p, img_t, vid_t
            except Exception as e:
                logger.error(f"Shot {shot.get('shot_number')} prompt generation failed: {e}")
                return index, None, None, {}, {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(process_shot, i, shot): i
                for i, shot in enumerate(shots)
            }
            
            for future in as_completed(future_to_index):
                try:
                    idx, img_res, vid_res, img_tok, vid_tok = future.result()
                    if img_res:
                        all_image_prompts[idx] = img_res
                        total_tokens["prompt_tokens"] += img_tok.get("prompt_tokens", 0)
                        total_tokens["completion_tokens"] += img_tok.get("completion_tokens", 0)
                    
                    if vid_res:
                        all_video_prompts[idx] = vid_res
                        total_tokens["prompt_tokens"] += vid_tok.get("prompt_tokens", 0)
                        total_tokens["completion_tokens"] += vid_tok.get("completion_tokens", 0)
                        
                except Exception as e:
                    logger.error(f"Concurrent prompt generation error: {e}")

        # Filter None
        return (
            [p for p in all_image_prompts if p], 
            [p for p in all_video_prompts if p], 
            total_tokens
        )

    
    def regenerate_single_image_prompt(
        self, 
        shot: Dict, 
        style: str = "cinematic",
        characters: List[Dict] = None,
        scenes: List[Dict] = None
    ) -> Tuple[Dict, Dict]:
        """重新生成单个图像提示词"""
        system_prompt = self.image_prompts_config.get("system", "")
        user_template = self.image_prompts_config.get("user_template", "")
        return self._generate_single_image_prompt(shot, user_template, system_prompt, style, characters, scenes)

    def regenerate_single_video_prompt(self, shot: Dict, image_prompt: str) -> Tuple[Dict, Dict]:
        """重新生成单个视频提示词"""
        system_prompt = self.video_prompts_config.get("system", "")
        user_template = self.video_prompts_config.get("user_template", "")
        return self._generate_single_video_prompt(shot, image_prompt, user_template, system_prompt)

    def _generate_single_image_prompt(
        self, 
        shot: Dict, 
        user_template: str, 
        system_prompt: str, 
        style: str,
        characters: List[Dict] = None,
        scenes: List[Dict] = None
    ) -> Tuple[Dict, Dict]:
        """Helper to generate single image prompt"""
        
        # 1. Extract Character Info
        char_info_str = "无特定角色"
        char_name = shot.get("character", "")
        # Find all characters mentioned in description/dialogue to be safe
        mentioned_chars = []
        if characters:
             for c in characters:
                 c_name = c.get("name")
                 if c_name and (c_name == char_name or c_name in shot.get("description", "") or c_name in shot.get("dialogue", "")):
                     mentioned_chars.append(c)
        
        if mentioned_chars:
            char_infos = []
            for char_data in mentioned_chars:
                c_name = char_data.get("name")
                info = f"角色名：{c_name}，性别：{char_data.get('gender', '')}，年龄：{char_data.get('age', '')}，外貌：{char_data.get('appearance', '')}，服装：{char_data.get('clothing', '')}"
                if char_data.get("image_path"):
                    info += " 【重要角色，已配备参考图，请确保生成的提示词中明确要求角色形象参考设定】"
                char_infos.append(info)
            char_info_str = "； ".join(char_infos)
        elif char_name:
             char_info_str = f"角色名：{char_name}"

        # 2. Extract Scene Info
        scene_info_str = "无特定场景"
        scene_name = shot.get("scene", "")
        if scene_name and scenes:
            scene_data = next((s for s in scenes if s.get("name") == scene_name), None)
            if scene_data:
                scene_info_str = f"场景名：{scene_name}，时间：{scene_data.get('time', '')}，地点：{scene_data.get('location', '')}，氛围：{scene_data.get('atmosphere', '')}"
                if scene_data.get("image_path"):
                    scene_info_str += " 【重要场景，已配备参考图，请确保生成的提示词中明确要求场景特征参考设定】"
            else:
                scene_info_str = f"场景名：{scene_name} (未找到详细档案)"
        elif scene_name:
            scene_info_str = f"场景名：{scene_name}"

        user_message = user_template.format(
            shot_number=shot.get("shot_number", 0),
            shot_type=shot.get("shot_type", ""),
            description=shot.get("description", ""),
            action=shot.get("action", ""),
            mood=shot.get("mood", ""),
            style=style,
            character_info=char_info_str,
            scene_info=scene_info_str
        )
        
        messages = [{"role": "user", "content": user_message}]
        
        logger.info(f"生成镜头 {shot.get('shot_number')} 图像提示词...")
        response, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        # Parse response
        prompt_data = self._parse_prompt(response, shot.get("shot_number", 0))
        return prompt_data, token_usage

    def generate_image_prompts(
        self, 
        storyboard: Dict, 
        style: str = "cinematic",
        characters: List[Dict] = None,
        scenes: List[Dict] = None
    ) -> Tuple[List[Dict], Dict]:
        """
        Concurrency generate image prompts for all shots
        """
        shots = storyboard.get("shots", [])
        all_prompts = [None] * len(shots)
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        
        system_prompt = self.image_prompts_config.get("system", "")
        user_template = self.image_prompts_config.get("user_template", "")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {
                executor.submit(self._generate_single_image_prompt, shot, user_template, system_prompt, style, characters, scenes): i
                for i, shot in enumerate(shots)
            }
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    prompt_data, token_usage = future.result()
                    all_prompts[index] = prompt_data
                    total_tokens["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
                    total_tokens["completion_tokens"] += token_usage.get("completion_tokens", 0)
                except Exception as e:
                    logger.error(f"镜头 {shots[index].get('shot_number')} 图像提示词生成失败: {e}")

        return [p for p in all_prompts if p], total_tokens
    
    def _generate_single_video_prompt(self, shot: Dict, image_prompt: str, user_template: str, system_prompt: str) -> Tuple[Dict, Dict]:
        """Helper to generate single video prompt"""
        user_message = user_template.format(
            shot_number=shot.get("shot_number", 0),
            shot_type=shot.get("shot_type", ""),
            description=shot.get("description", ""),
            action=shot.get("action", ""),
            camera_movement=shot.get("camera_movement", ""),
            duration=shot.get("duration", 5),
            mood=shot.get("mood", ""),
            image_prompt=image_prompt
        )
        
        messages = [{"role": "user", "content": user_message}]
        
        logger.info(f"生成镜头 {shot.get('shot_number')} 视频提示词...")
        response, token_usage = veadk_client.call_llm(messages, system_prompt)
        
        prompt_data = self._parse_video_prompt(response, shot.get("shot_number", 0))
        return prompt_data, token_usage

    def generate_video_prompts(
        self, 
        storyboard: Dict, 
        image_prompts: List[Dict]
    ) -> Tuple[List[Dict], Dict]:
        """
        Concurrency generate video prompts for all shots
        """
        shots = storyboard.get("shots", [])
        all_prompts = [None] * len(shots)
        total_tokens = {"prompt_tokens": 0, "completion_tokens": 0}
        
        system_prompt = self.video_prompts_config.get("system", "")
        user_template = self.video_prompts_config.get("user_template", "")
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {}
            for i, shot in enumerate(shots):
                image_prompt = image_prompts[i].get("positive_prompt", "") if i < len(image_prompts) else ""
                future = executor.submit(self._generate_single_video_prompt, shot, image_prompt, user_template, system_prompt)
                future_to_index[future] = i
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    prompt_data, token_usage = future.result()
                    all_prompts[index] = prompt_data
                    total_tokens["prompt_tokens"] += token_usage.get("prompt_tokens", 0)
                    total_tokens["completion_tokens"] += token_usage.get("completion_tokens", 0)
                except Exception as e:
                    logger.error(f"镜头 {shots[index].get('shot_number')} 视频提示词生成失败: {e}")
        
        return [p for p in all_prompts if p], total_tokens
    
    def _parse_prompt(self, response: str, shot_number: int) -> Dict:
        """解析图像提示词响应"""
        try:
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response
            
            data = json.loads(json_str)
            return data
            
        except json.JSONDecodeError:
            logger.warning(f"镜头 {shot_number} 提示词解析失败，使用原始响应")
            return {
                "shot_number": shot_number,
                "positive_prompt": response,
                "negative_prompt": "blurry, low quality, distorted",
                "style": "default"
            }
    
    def _parse_video_prompt(self, response: str, shot_number: int) -> Dict:
        """解析视频提示词响应"""
        try:
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response
            
            data = json.loads(json_str)
            return data
            
        except json.JSONDecodeError:
            logger.warning(f"镜头 {shot_number} 视频提示词解析失败")
            return {
                "shot_number": shot_number,
                "video_prompt": response,
                "motion_intensity": "medium",
                "camera_motion": "static"
            }

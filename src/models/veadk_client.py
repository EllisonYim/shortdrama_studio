"""
火山引擎 VEADK 客户端模块
封装火山引擎各类API调用
"""

import os
import json
import base64
import time
import requests
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from loguru import logger
import hashlib
import hmac
from datetime import datetime, timezone
from volcenginesdkarkruntime import Ark

from ..utils.config_loader import config_loader


class VEADKClient:
    """火山引擎 VEADK 客户端"""
    
    def __init__(self):
        self.reload_config()

    def reload_config(self):
        """重新加载配置"""
        # 1. 获取当前选中的平台
        self.current_platform = config_loader.config.get("platform", "volcengine")
        
        # 2. 获取该平台的配置
        # 通过 config_loader.get 获取以支持兼容性
        self.config = config_loader.get(f"platforms.{self.current_platform}", {})
        
        # 如果配置为空且是 volcengine，尝试回退（防止极端情况）
        if not self.config and self.current_platform == "volcengine":
            self.config = config_loader.get("volcengine", {})
        
        # 3. 后续逻辑保持不变，但基于 self.config 读取
        config_api_key = self.config.get("ark_api_key")
        
        # Handle placeholder or empty
        if not config_api_key or config_api_key == "${ARK_API_KEY}":
             env_api = os.getenv("ARK_API_KEY")
        else:
             env_api = config_api_key

        if not env_api:
             # Fallback
             env_api = os.getenv("VOLCENGINE_ACCESS_KEY") or os.getenv("VOLC_ACCESS_KEY") or self.config.get("access_key", "")
        
        self.api_key = str(env_api).strip()
        env_sk = os.getenv("VOLCENGINE_SECRET_KEY")
        self.secret_key = (env_sk if env_sk is not None else self.config.get("secret_key", "")).strip()
        self.endpoints = self.config.get("endpoints", {})
        self.models = self.config.get("models", {})
        
        # 验证配置
        if not self.api_key:
            logger.warning("未检测到 API Key，请在环境变量 ARK_API_KEY 或 config.volcengine.ark_api_key 配置")
            
        # 初始化 Ark 客户端
        self.ark_client = Ark(
            base_url=self.endpoints.get("image", "https://ark.cn-beijing.volces.com/api/v3"),
            api_key=self.api_key
        )
        logger.info(f"VEADKClient 配置已重载，当前平台: {self.current_platform}")
    
    def _sign_request(self, method: str, url: str, headers: Dict, body: str = "") -> Dict:
        """生成请求签名（V4签名）"""
        # 简化签名实现，实际使用时应使用SDK提供的签名方法
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        date = timestamp[:8]
        
        headers['X-Date'] = timestamp
        headers['X-Content-Sha256'] = hashlib.sha256(body.encode()).hexdigest()
        
        return headers
    
    def call_llm(self, messages: List[Dict], system_prompt: str = None) -> Tuple[str, Dict]:
        """
        调用大语言模型
        
        Args:
            messages: 消息列表
            system_prompt: 系统提示词
        
        Returns:
            (响应内容, Token使用情况)
        """
        llm_config = self.models.get("llm", {})
        endpoint = self.endpoints.get("llm", "")
        model_id = llm_config.get("model_id", "")
        
        if not endpoint or not model_id:
            logger.error("LLM配置不完整")
            return "", {"prompt_tokens": 0, "completion_tokens": 0}
        
        url = f"{endpoint}/chat/completions"
        
        # 构建消息
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)
        
        payload = {
            "model": model_id,
            "messages": all_messages,
            "max_tokens": llm_config.get("max_tokens", 4096),
            "temperature": llm_config.get("temperature", 0.7)
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            logger.info(f"调用LLM: {model_id}")
            response = requests.post(url, json=payload, headers=headers, timeout=180)
            response.raise_for_status()
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = result.get("usage", {})
            
            token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0)
            }
            
            logger.info(f"LLM响应成功，Token: {token_usage}")
            return content, token_usage
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            # 模拟响应（开发测试用）
            return self._mock_llm_response(messages), {"prompt_tokens": 100, "completion_tokens": 200}
    
    def generate_image(self, prompt: str, negative_prompt: str = "", width: int = 1280, height: int = 720, image_urls: List[str] = None) -> Tuple[Optional[bytes], Dict]:
        """
        生成图像
        
        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词
            width: 宽
            height: 高
            image_urls: 参考图URL列表
        
        Returns:
            (图像字节数据, Token/API使用情况)
        """
        image_config = self.models.get("image", {})
        
        try:
            logger.info(f"生成图像: {prompt[:50]}...")
            
            # Construct size string. 
            # Use configured size if available (e.g. "2k"), otherwise fallback to WxH
            config_size = image_config.get("size")
            if config_size:
                size_str = str(config_size)
            else:
                size_str = f"{width}x{height}"
            
            base_url = self.endpoints.get("image", "https://ark.cn-beijing.volces.com/api/v3")
            if base_url.endswith("/"):
                base_url = base_url[:-1]
                
            # Direct API call to bypass potential SDK endpoint issues
            url = f"{base_url}/images/generations"
            
            model_id = image_config.get("model_id", "doubao-seedream-4-5-251128")
            
            payload = {
                "model": model_id,
                "prompt": prompt,
                "size": size_str,
                "response_format": "url",
            }
            # Optional watermark
            watermark = image_config.get("watermark", True)
            if watermark:
                payload["need_watermark"] = watermark
                
            # Add reference images if provided
            if image_urls and len(image_urls) > 0:
                # Assuming the API supports 'image_urls' or similar for reference
                # Doubao-Seedream standard API usually takes 'image_urls' or 'ref_images'
                # Based on common Volcengine usage:
                payload["image_urls"] = image_urls
                logger.info(f"Using {len(image_urls)} reference images")
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            logger.info(f"Requesting image from {url} with model {model_id}")
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            
            if response.status_code != 200:
                logger.error(f"Image generation error {response.status_code}: {response.text}")
                try:
                    error_detail = response.json()
                except:
                    error_detail = response.text
                return None, {
                    "api_calls": 1, 
                    "error": f"HTTP {response.status_code}: {error_detail}",
                    "request_id": response.headers.get("X-Tt-Logid", "unknown")
                }
                
            response.raise_for_status()
            
            # Parse result
            # Expected: { "data": [ { "url": "..." } ] }
            result = response.json()
            data = result.get("data", [])
            
            # Check for API level errors in response body even if status is 200
            if not data and "error" in result:
                 error_msg = result["error"].get("message", str(result["error"]))
                 logger.error(f"API Error in 200 OK: {error_msg}")
                 return None, {
                     "api_calls": 1,
                     "error": error_msg,
                     "request_id": response.headers.get("X-Tt-Logid", "unknown")
                 }

            if data and len(data) > 0:
                image_url = data[0].get("url")
                if image_url:
                    # Return URL directly
                    return image_url, {
                        "api_calls": 1, 
                        "model": model_id,
                        "size": size_str,
                        "request_id": response.headers.get("X-Tt-Logid", "unknown")
                    }
            
            logger.error(f"图像生成响应数据为空 or URL missing: {result}")
            return None, {
                "api_calls": 1, 
                "error": "Empty data or missing URL in response", 
                "details": result,
                "request_id": response.headers.get("X-Tt-Logid", "unknown")
            }
            
        except Exception as e:
            logger.error(f"图像生成失败: {e}")
            req_id = "unknown"
            if isinstance(e, requests.exceptions.RequestException) and e.response is not None:
                req_id = e.response.headers.get("X-Tt-Logid", "unknown")
            return None, {"api_calls": 1, "error": str(e), "request_id": req_id}
    
    def submit_video_generation_task(self, image_path: str = None, prompt: str = "", duration: int = 5, resolution: str = None, ratio: str = None, image_url: str = None) -> Tuple[Optional[str], Dict]:
        """
        提交视频生成任务（仅提交，不等待）
        
        Args:
            image_path: 首帧图像路径 (optional if image_url provided)
            prompt: 视频提示词
            duration: 视频时长（秒）
            resolution: 分辨率 (e.g. "1080p")
            ratio: 画面比例 (e.g. "16:9")
            image_url: 首帧图像 URL (TOS URL)
        
        Returns:
            (task_id (Optional), API使用情况/错误信息)
        """
        from ..utils.tos_client import tos_client
        import uuid
        
        video_config = self.models.get("video", {})
        # Use base URL from endpoints, similar to image generation fix
        base_url = self.endpoints.get("video", "https://ark.cn-beijing.volces.com/api/v3")
        if base_url.endswith("/"):
            base_url = base_url[:-1]
            
        endpoint = f"{base_url}/contents/generations/tasks"
        
        if not base_url:
            logger.error("视频生成配置不完整")
            return None, {"error": "Configuration incomplete: base_url missing"}
            
        # Handle Image Source
        final_image_url = image_url
        
        # If we have an image_url, check if it's a TOS URL and sign it if needed
        if final_image_url:
            parsed = tos_client.parse_tos_url(final_image_url)
            if parsed:
                bucket, key = parsed
                try:
                    # Generate signed URL for 1 hour
                    signed_url = tos_client.get_signed_url(bucket, key, expires=3600)
                    if signed_url:
                        final_image_url = signed_url
                        logger.info(f"Generated signed URL for video generation: {final_image_url[:100]}...")
                except Exception as e:
                    logger.warning(f"Failed to sign TOS URL, using original: {e}")

        if not final_image_url:
            if not image_path:
                logger.error("Must provide either image_path or image_url")
                return None, {"error": "Image path and URL both missing"}
                
            # Upload image to TOS to get URL
            try:
                with open(image_path, 'rb') as f:
                    image_content = f.read()
                
                # Use TOS client to upload
                bucket = tos_client.bucket
                if not bucket:
                     logger.error("TOS bucket not configured for video generation upload")
                     return None, {"error": "TOS bucket not configured"}
                     
                # Generate unique key
                key = f"temp_gen_video/{uuid.uuid4()}.png"
                # This returns the raw public URL
                raw_url = tos_client.upload_content(bucket, key, image_content)
                logger.info(f"Uploaded image to TOS: {raw_url}")
                
                # Now sign it
                try:
                    final_image_url = tos_client.get_signed_url(bucket, key, expires=3600)
                    logger.info(f"Generated signed URL for uploaded image: {final_image_url[:100]}...")
                except Exception as e:
                    logger.warning(f"Failed to sign uploaded URL: {e}")
                    final_image_url = raw_url
                
            except Exception as e:
                logger.error(f"Failed to prepare image for video generation: {e}")
                return None, {"error": f"Image upload failed: {str(e)}"}
        
        # Construct Payload
        # Append params to prompt
        full_prompt = prompt
        if ratio:
            full_prompt += f" --ratio {ratio}"
        # Duration handling logic
        if duration:
            # doubao-seedance-1.5-pro supports 4s to 12s
            duration_val = 5  # Default
            
            try:
                # 1. Convert to int (model typically expects integer seconds)
                # Round to nearest to handle e.g. 3.9 -> 4, 4.1 -> 4
                raw_dur = int(round(float(duration)))
                
                # 2. Clamp between 4 and 12
                if raw_dur < 4:
                    duration_val = 4
                elif raw_dur > 12:
                    duration_val = 12
                else:
                    duration_val = raw_dur
            except:
                duration_val = 5
            
            full_prompt += f" --dur {duration_val}"
            
        payload = {
            "model": video_config.get("model_id", "doubao-seedance-1-5-pro-251215"),
            "content": [
                {
                    "type": "text",
                    "text": full_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": final_image_url
                    }
                }
            ],
            "generate_audio": True
        }
        
        # Add optional params to payload if supported by model (Common practice)
        # Note: ratio and resolution are primarily handled via prompt augmentation above,
        # but if the API supports them as top-level or config parameters, we add them here.
        # For doubao-seedance, 'ratio' is supported in prompt via --ratio, but let's add it if spec allows.
        # Currently we rely on prompt modification which is the standard way for this model family.
        # However, to be safe and explicit as requested:
        if ratio:
            payload["ratio"] = ratio
        # Resolution is usually implied by ratio or model capability, but adding it doesn't hurt if API ignores extra fields
        # or if future API versions support it.
        # Actually, for some endpoints, 'resolution' might be 'size' or similar.
        # We'll stick to what we know works (prompt) + payload field for clarity/future-proof.

        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            # Enhanced logging for debugging
            logger.info("="*30 + " VIDEO GEN REQUEST " + "="*30)
            logger.info(f"Endpoint: {endpoint}")
            logger.info(f"Model: {payload.get('model')}")
            logger.info(f"Final Prompt (Text): {full_prompt}")
            logger.info(f"Image URL: {final_image_url}")
            logger.info(f"Params -> Duration: {duration}, Resolution: {resolution}, Ratio: {ratio}")
            logger.info(f"Full JSON Payload: {json.dumps(payload, ensure_ascii=False)}")
            logger.info("="*80)
            
            # Submit Task
            response = requests.post(
                endpoint, 
                json=payload,
                headers=headers,
                timeout=60
            )
            
            req_id = response.headers.get("X-Tt-Logid", "unknown")
            logger.info(f"Response Status: {response.status_code}, ReqID: {req_id}")
            
            if response.status_code != 200:
                logger.error(f"视频生成 API 错误: {response.text} (ReqID: {req_id})")
                if response.status_code == 400:
                    return None, {"api_calls": 1, "error": f"API Error 400: {response.text}", "request_id": req_id}
            
            response.raise_for_status()
            
            result = response.json()
            logger.info("="*30 + " VIDEO GEN RESPONSE " + "="*30)
            logger.info(f"Response Body: {json.dumps(result, ensure_ascii=False)}")
            logger.info("="*80)
            
            task_id = result.get("id") or result.get("task_id")
            if not task_id and "data" in result:
                task_id = result["data"].get("id") or result["data"].get("task_id")
            
            if not task_id:
                logger.error(f"Failed to get task_id from response: {result}")
                return None, {"api_calls": 1, "error": "No task_id in response"}
            
            logger.info(f"Video task submitted, ID: {task_id}")
            return task_id, {"api_calls": 1, "request_id": req_id, "model": payload["model"]}
            
        except Exception as e:
            logger.error(f"视频任务提交失败: {e}")
            req_id = "unknown"
            if isinstance(e, requests.exceptions.RequestException) and e.response is not None:
                req_id = e.response.headers.get("X-Tt-Logid", "unknown")
            return None, {"api_calls": 1, "error": str(e), "request_id": req_id}

    def check_video_task_status(self, task_id: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        检查视频任务状态
        Returns: (status, video_url, error_msg)
        status: SUCCEEDED, FAILED, RUNNING, UNKNOWN
        """
        base_url = self.endpoints.get("video", "https://ark.cn-beijing.volces.com/api/v3")
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        endpoint = f"{base_url}/contents/generations/tasks/{task_id}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            response = requests.get(endpoint, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            status = result.get("status")
            if not status and "data" in result:
                status = result["data"].get("status")
            status = str(status).upper()
            
            if status in ["SUCCEEDED", "COMPLETED", "SUCCESS"]:
                content = result.get("content")
                data = result.get("data")
                video_url = None
                if content:
                    video_url = content.get("video_url") or content.get("url")
                if not video_url and data:
                    video_url = data.get("video_url") or data.get("url")
                return "SUCCEEDED", video_url, None
                
            elif status in ["FAILED", "FAILURE"]:
                reason = "Unknown failure"
                if "error" in result:
                    reason = result["error"].get("message") or str(result["error"])
                elif "data" in result and "error" in result["data"]:
                        reason = result["data"]["error"]
                return "FAILED", None, reason
            
            else:
                return "RUNNING", None, None
                
        except Exception as e:
            logger.error(f"Check task status failed: {e}")
            return "UNKNOWN", None, str(e)

    def generate_video(self, image_path: str = None, prompt: str = "", duration: int = 5, resolution: str = None, ratio: str = None, image_url: str = None) -> Tuple[Optional[str], Dict]:
        """
        生成视频 (Blocking wrapper for backward compatibility)
        """
        # 1. Submit
        task_id, usage = self.submit_video_generation_task(image_path, prompt, duration, resolution, ratio, image_url)
        if not task_id:
            return None, usage
            
        # 2. Poll using new API
        logger.info(f"Polling status for task {task_id}...")
        
        # Polling loop (Max 5 minutes)
        max_retries = 150
        for i in range(max_retries):
            try:
                status, video_url, error = self.check_video_task_status(task_id)
                
                if status == "SUCCEEDED":
                    usage["task_id"] = task_id
                    return video_url, usage
                elif status == "FAILED":
                    usage["error"] = error
                    return None, usage
                
                # RUNNING / UNKNOWN
                if i % 10 == 0:
                    logger.debug(f"Task {task_id} status: {status}")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(2)
                
        usage["error"] = "Polling timeout"
        return None, usage
    
    def _poll_video_result(self, task_id: str, headers: Dict, endpoint_base: str = None, max_retries: int = 60) -> Tuple[Optional[str], Optional[str]]:
        """轮询获取视频生成结果 (返回URL, 错误信息)"""
        if not endpoint_base:
            endpoint_base = f"{self.endpoints.get('video', '')}/cv/v1/video_result"
        
        # If endpoint_base is the tasks endpoint, append ID
        # e.g. .../contents/generations/tasks/{id}
        url = f"{endpoint_base}/{task_id}"
        
        last_error = None
        
        for i in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=30
                )
                response.raise_for_status()
                
                result = response.json()
                # Parse status.
                # Common formats:
                # 1. { "status": "SUCCEEDED", "content": { "url": ... } }
                # 2. { "data": { "status": "completed", "video_url": ... } }
                
                status = result.get("status")
                if not status and "data" in result:
                    status = result["data"].get("status")
                
                # Normalize status
                status = str(status).upper()
                
                if status in ["SUCCEEDED", "COMPLETED", "SUCCESS"]:
                    # Log full result for debugging
                    logger.info(f"Video Poll Succeeded: {json.dumps(result, ensure_ascii=False)}")
                    # Extract content
                    content = result.get("content")
                    data = result.get("data")
                    
                    video_url = None
                    if content:
                        video_url = content.get("video_url") or content.get("url")
                    if not video_url and data:
                        video_url = data.get("video_url") or data.get("url")
                        
                    if video_url:
                        return video_url, None
                    else:
                        logger.error(f"Completed but no URL found: {result}")
                        return None, f"URL missing in response: {json.dumps(result)}"
                        
                elif status in ["FAILED", "FAILURE"]:
                    logger.error(f"视频生成任务失败: {json.dumps(result, ensure_ascii=False)}")
                    # Try extract error reason
                    reason = "Unknown failure"
                    if "error" in result:
                        reason = result["error"].get("message") or str(result["error"])
                    elif "data" in result and "error" in result["data"]:
                         reason = result["data"]["error"]
                    return None, f"Task failed: {reason}"
                
                # If RUNNING / PENDING / QUEUED, continue
                time.sleep(2) # Faster polling for responsive UI
                
            except Exception as e:
                logger.error(f"轮询视频结果失败: {e}")
                last_error = str(e)
                time.sleep(2)
        
        logger.error("视频生成超时")
        return None, f"Polling timeout or error: {last_error}"
    
    def _mock_llm_response(self, messages: List[Dict]) -> str:
        """模拟LLM响应（开发测试用）"""
        last_message = messages[-1].get("content", "") if messages else ""
        
        if "剧本" in last_message or "主题" in last_message:
            return """【剧名】：城市之光
【类型】：都市爱情
【时长】：3分钟
【人物】：
- 小明：28岁，程序员，内向但善良
- 小红：26岁，设计师，开朗活泼

【场景】：咖啡馆、办公室、公园

【剧情】：
第一幕：咖啡馆
- (小明独自坐在角落，看着电脑)
- 小红：不好意思，这里有人吗？
- 小明：(抬头，有些紧张) 没...没有

第二幕：偶遇
- (两人在公司电梯相遇)
- 小红：是你！咖啡馆那个...
- 小明：(惊喜) 你也在这栋楼工作？

第三幕：公园
- (夕阳下，两人并肩走在公园小路)
- 小明：其实，那天在咖啡馆...
- 小红：(微笑) 我知道
"""
        
        elif "分镜" in last_message:
            return """```json
{
  "title": "城市之光",
  "total_shots": 6,
  "shots": [
    {
      "shot_number": 1,
      "shot_type": "全景",
      "description": "温馨的咖啡馆内景，暖色调灯光",
      "action": "小明独自坐在角落位置，专注看着笔记本电脑",
      "dialogue": "",
      "camera_movement": "缓慢推进",
      "duration": 5,
      "mood": "安静、略带孤独"
    },
    {
      "shot_number": 2,
      "shot_type": "中景",
      "description": "小红走向小明的桌子",
      "action": "小红手持咖啡杯，微笑询问",
      "dialogue": "不好意思，这里有人吗？",
      "camera_movement": "跟随",
      "duration": 4,
      "mood": "轻松、友好"
    },
    {
      "shot_number": 3,
      "shot_type": "近景",
      "description": "小明抬头看向小红",
      "action": "小明略显紧张地回应",
      "dialogue": "没...没有",
      "camera_movement": "固定",
      "duration": 3,
      "mood": "紧张、期待"
    },
    {
      "shot_number": 4,
      "shot_type": "中景",
      "description": "公司电梯内",
      "action": "两人在电梯相遇，互相认出对方",
      "dialogue": "是你！咖啡馆那个...",
      "camera_movement": "固定",
      "duration": 5,
      "mood": "惊喜"
    },
    {
      "shot_number": 5,
      "shot_type": "全景",
      "description": "夕阳下的公园小路",
      "action": "两人并肩散步",
      "dialogue": "其实，那天在咖啡馆...",
      "camera_movement": "跟随平移",
      "duration": 5,
      "mood": "浪漫、温馨"
    },
    {
      "shot_number": 6,
      "shot_type": "特写",
      "description": "小红微笑的面部特写",
      "action": "小红温柔地微笑",
      "dialogue": "我知道",
      "camera_movement": "缓慢推进",
      "duration": 4,
      "mood": "甜蜜、幸福"
    }
  ]
}
```"""
        
        elif "提示词" in last_message or "prompt" in last_message.lower():
            return """```json
{
  "shot_number": 1,
  "positive_prompt": "cozy coffee shop interior, warm ambient lighting, young man sitting alone at corner table, looking at laptop, soft bokeh background, cinematic lighting, 8k, highly detailed",
  "negative_prompt": "blurry, low quality, distorted, ugly, bad anatomy",
  "style": "cinematic"
}
```"""
        
        return "这是一个模拟响应，用于开发测试。"
    
    def _mock_image(self) -> bytes:
        """生成模拟图像（开发测试用）"""
        from PIL import Image
        import io
        
        # 创建一个简单的渐变图像
        img = Image.new('RGB', (1280, 720), color=(100, 149, 237))
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()


# 全局客户端实例
veadk_client = VEADKClient()

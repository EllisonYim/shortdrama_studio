"""
图像生成模块
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from loguru import logger

from concurrent.futures import ThreadPoolExecutor, as_completed

from ..utils.tos_client import tos_client
from ..utils.config_loader import config_loader
from ..models.veadk_client import veadk_client

class ImageGenerator:
    """图像生成器"""
    
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = config_loader.get("app.data_dir", "./data/aigc")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reload_config()

    def reload_config(self):
        """重新加载配置"""
        self.max_workers = config_loader.get("app.concurrency.image", 5)
        logger.info(f"ImageGenerator 配置已更新, max_workers={self.max_workers}")
    
    def _generate_single_image(self, prompt_data: Dict, project_dir: Path, index: int = 0, width: int = 1280, height: int = 720, project_id: str = None, style: str = "", image_urls: List[str] = None) -> Tuple[int, Optional[str], Dict]:
        """Helper to generate single image"""
        shot_number = prompt_data.get("shot_number", 0)
        positive_prompt = prompt_data.get("positive_prompt", "")
        negative_prompt = prompt_data.get("negative_prompt", "")
        
        # Combine style with prompt
        if style:
            positive_prompt = f"{positive_prompt}, {style}"
        
        # Log explicitly for debugging "hangs"
        ref_info = f" with {len(image_urls)} refs" if image_urls else " (Text-to-Image)"
        logger.info(f"[START] Shot {shot_number} Index {index} Generation{ref_info}. Prompt len: {len(positive_prompt)}")
        
        if image_urls:
            logger.info(f"Shot {shot_number} [Image-to-Image] Prompt: {positive_prompt}")
            logger.info(f"Shot {shot_number} [Image-to-Image] Ref URLs: {image_urls}")
            
        try:
            # Set timeout inside generate_image if possible, or assume client handles it.
            # We add a safety timeout here if we were using a raw request, but client wrapper handles it.
            image_data, usage = veadk_client.generate_image(positive_prompt, negative_prompt, width=width, height=height, image_urls=image_urls)
            
            if image_data and isinstance(image_data, str) and (image_data.startswith("http://") or image_data.startswith("https://")):
                logger.info(f"Shot {shot_number} Index {index} Raw Image URL: {image_data}")
            
            if not image_data and "error" in usage:
                logger.error(f"[FAILED] Shot {shot_number} Index {index}: {usage['error']}")
                return shot_number, None, usage
                
        except Exception as e:
            logger.error(f"[EXCEPTION] Shot {shot_number} Index {index} failed: {e}")
            return shot_number, None, {"error": str(e)}
        
        if image_data:
            import time
            import mimetypes
            import imghdr
            
            timestamp = int(time.time() * 1000)
            # Default fallback
            ext = ".png"
            filename = f"shot_{shot_number:03d}_{index}_{timestamp}{ext}"
            image_path = project_dir / filename
            
            try:
                if isinstance(image_data, str) and (image_data.startswith("http://") or image_data.startswith("https://")):
                    import requests
                    with requests.get(image_data, stream=True) as r:
                        r.raise_for_status()
                        
                        # Detect extension from Content-Type
                        content_type = r.headers.get("Content-Type")
                        if content_type:
                            guess = mimetypes.guess_extension(content_type)
                            if guess:
                                ext = guess
                                if ext == ".jpe": ext = ".jpg"
                        
                        # Update filename and path with correct extension
                        filename = f"shot_{shot_number:03d}_{index}_{timestamp}{ext}"
                        image_path = project_dir / filename
                        
                        with open(image_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                f.write(chunk)
                else:
                    # Bytes
                    what = imghdr.what(None, image_data)
                    if what:
                        ext = f".{what}"
                        if ext == ".jpeg": ext = ".jpg"
                    
                    filename = f"shot_{shot_number:03d}_{index}_{timestamp}{ext}"
                    image_path = project_dir / filename
                    
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                
                logger.info(f"镜头 {shot_number} 首图已保存至本地: {image_path}")
            except Exception as e:
                logger.error(f"本地保存失败: {e}")
                pass

            # Check for TOS configuration
            final_url = None
            
            # Mandatory TOS check
            bucket = config_loader.get("tos.bucket_name")
            if not bucket:
                 raise Exception("TOS bucket is not configured. Storage configuration is mandatory.")

            bucket_dir = config_loader.get("tos.bucket_directory", "")
            
            # Upload to TOS
            if bucket_dir and not bucket_dir.endswith('/'):
                bucket_dir += '/'
            
            key = f"{bucket_dir}{project_id}/images/{filename}"
            logger.info(f"Uploading image to TOS (Mandatory): {key}")
            try:
                # Prefer uploading the local file we just saved to ensure consistency
                if image_path.exists():
                        with open(image_path, 'rb') as f:
                            url = tos_client.upload_content(bucket, key, f.read())
                elif isinstance(image_data, str) and (image_data.startswith("http://") or image_data.startswith("https://")):
                    url = tos_client.upload_from_url(bucket, key, image_data)
                else:
                    url = tos_client.upload_content(bucket, key, image_data)
                    
                logger.info(f"镜头 {shot_number} 首图已上传: {url}")
                final_url = url
            except Exception as e:
                logger.error(f"TOS upload failed: {e}")
                # Since TOS is mandatory, we must propagate error
                return shot_number, None, {"error": f"TOS upload failed: {str(e)}"}
            
            return shot_number, final_url, usage
        else:
            logger.error(f"镜头 {shot_number} 首图生成失败")
            return shot_number, None, usage

    def generate_shot_images(
        self, 
        image_prompts: List[Dict], 
        project_id: str,
        image_count: int = 1,
        ratio: str = "16:9",
        resolution: str = "1080p",
        style: str = "",
        on_status_update: Optional[callable] = None,
        sub_dir: str = "images",
        reference_map: Dict[int, List[str]] = None
    ) -> Tuple[Dict[int, List[str]], Dict]:
        """
        Concurrency generate images for all shots
        
        Args:
            image_prompts: Image prompts list
            project_id: Project ID
            image_count: Number of images per shot
            ratio: Aspect Ratio (e.g. "16:9")
            resolution: Resolution (e.g. "1080p")
            on_status_update: Callback(key, value, extra_data) for status updates
            sub_dir: Sub directory name under project folder (default: "images")
            reference_map: Dict mapping shot_number to list of reference image paths/urls
        
        Returns:
            (Dict {shot_number: [paths]}, API usage)
        """
        # Calculate Width/Height
        try:
            res_val = int(resolution.replace("p", ""))
        except:
            res_val = 1080
            
        try:
            w_r, h_r = map(int, ratio.split(":"))
            r_val = w_r / h_r
        except:
            r_val = 16 / 9
            w_r, h_r = 16, 9
            
        if r_val >= 1: # Landscape or Square
            height = res_val
            width = int(height * r_val)
        else: # Portrait
            width = res_val
            height = int(width / r_val)
            
        # Align to 8 or 64 (some models require it)
        width = (width // 8) * 8
        height = (height // 8) * 8
        
        # Ensure minimum resolution for high-res models (e.g. doubao-seedream requires > 3.6M pixels)
        min_pixels = 3686400
        current_pixels = width * height
        if current_pixels < min_pixels:
            import math
            scale = math.sqrt(min_pixels / current_pixels)
            # Add a small buffer to avoid rounding errors causing it to be slightly under
            scale = scale * 1.01
            width = int(width * scale)
            height = int(height * scale)
            # Re-align
            width = (width // 8) * 8
            height = (height // 8) * 8
            logger.info(f"Resolution upscaled to {width}x{height} to meet model requirements")
        
        shot_images = {}
        total_api_calls = 0
        
        project_dir = self.output_dir / project_id / sub_dir
        project_dir.mkdir(parents=True, exist_ok=True)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_info = {}
            
            for i, prompt in enumerate(image_prompts):
                shot_number = prompt.get("shot_number", i+1)
                
                # Mark as processing
                if on_status_update:
                    on_status_update(f"shot_status_image_{shot_number}", "processing", None)
                
                # Resolve reference images
                image_urls = None
                if reference_map and shot_number in reference_map:
                    raw_paths = reference_map[shot_number]
                    image_urls = []
                    for p in raw_paths:
                        if not p: continue
                        # If http, assume accessible or already signed
                        if p.startswith("http"):
                            image_urls.append(p)
                        else:
                            # If local path, try to get TOS URL if enabled
                            # Or upload to temp
                            # Here we assume caller passed TOS paths or we can sign them
                            # Since we don't know bucket easily here without config, let's rely on tos_client
                            if config_loader.get("tos.enable"):
                                bucket = config_loader.get("tos.bucket_name")
                                # If path is relative to bucket, we need to sign it
                                # If path is local file path, we need to upload
                                # This is complex. Let's assume caller passed valid paths/keys or public URLs.
                                # If they passed paths like "project_id/characters/image.png" (TOS key), we sign it.
                                # But image_path in DB is usually "project_id/characters/image.png" or "http..."
                                
                                # Try to sign if it looks like a key (no / at start, no http)
                                if not p.startswith("/"):
                                    try:
                                        signed = tos_client.get_signed_url(bucket, p, expires=3600)
                                        image_urls.append(signed)
                                    except:
                                        image_urls.append(p)
                                else:
                                    # Local file? 
                                    pass
                
                for j in range(image_count):
                    future = executor.submit(self._generate_single_image, prompt, project_dir, j, width, height, project_id, style=style, image_urls=image_urls)
                    future_to_info[future] = shot_number


            for future in as_completed(future_to_info):
                shot_number = future_to_info[future]
                try:
                    s_num, path, usage = future.result()
                    status = "failed"
                    extra = None
                    if path:
                        status = "completed"
                        if shot_number not in shot_images:
                            shot_images[shot_number] = []
                        shot_images[shot_number].append(path)
                        extra = {"path": path, "shot_number": shot_number}
                    elif "error" in usage:
                        # Pass error message via extra
                        extra = {"error": usage["error"]}
                    
                    if on_status_update:
                        on_status_update(f"shot_status_image_{shot_number}", status, extra)
                    total_api_calls += usage.get("api_calls", 1)
                except Exception as e:
                    logger.error(f"Image generation failed for shot {shot_number}: {e}")
                    if on_status_update:
                        on_status_update(f"shot_status_image_{shot_number}", "failed", None)
        
        return shot_images, {"api_calls": total_api_calls}
    
    def regenerate_image(
        self, 
        prompt_data: Dict, 
        project_id: str,
        width: int = 1280,
        height: int = 720
    ) -> Tuple[Optional[str], Dict]:
        """
        重新生成单张图像
        
        Args:
            prompt_data: 提示词数据
            project_id: 项目ID
            width: 宽
            height: 高
        
        Returns:
            (图像路径, API使用情况)
        """
        shot_number = prompt_data.get("shot_number", 0)
        positive_prompt = prompt_data.get("positive_prompt", "")
        negative_prompt = prompt_data.get("negative_prompt", "")
        
        project_dir = self.output_dir / project_id / "images"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"重新生成镜头 {shot_number} 首图...")
        
        image_url, usage = veadk_client.generate_image(positive_prompt, negative_prompt, width=width, height=height)
        
        if image_url:
            logger.info(f"Shot {shot_number} Raw Image URL: {image_url}")
            # Check for TOS configuration
            if config_loader.get("tos.enable"):
                bucket = config_loader.get("tos.bucket_name")
                bucket_dir = config_loader.get("tos.bucket_directory", "")
                if bucket:
                    if bucket_dir and not bucket_dir.endswith('/'):
                        bucket_dir += '/'
                    filename = f"shot_{shot_number:03d}.png"
                    key = f"{bucket_dir}{project_id}/images/{filename}"
                    try:
                        final_url = tos_client.upload_from_url(bucket, key, image_url)
                        return final_url, usage
                    except Exception as e:
                        logger.error(f"TOS upload failed: {e}")

            # Local fallback
            image_path = project_dir / f"shot_{shot_number:03d}.png"
            try:
                import requests
                with requests.get(image_url, stream=True) as r:
                    r.raise_for_status()
                    with open(image_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                return str(image_path), usage
            except Exception as e:
                logger.error(f"Local save failed: {e}")
        
        return None, usage

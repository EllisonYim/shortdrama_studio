"""
视频生成模块
"""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from loguru import logger

from concurrent.futures import ThreadPoolExecutor, as_completed

from ..models.veadk_client import veadk_client
from ..utils.tos_client import tos_client
from ..utils.config_loader import config_loader

class VideoGenerator:
    """视频生成器"""
    
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = config_loader.get("app.data_dir", "./data/aigc")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.reload_config()

    def reload_config(self):
        """重新加载配置"""
        self.max_workers = config_loader.get("app.concurrency.video", 3)
        logger.info(f"VideoGenerator 配置已更新, max_workers={self.max_workers}")
    
    def submit_single_video_task(self, params: Dict, project_id: str) -> Dict:
        """
        提交单个视频生成任务到云端，返回任务信息
        """
        shot_number = params.get("shot_number")
        image_path = params.get("image_path")
        video_prompt = params.get("video_prompt")
        duration = params.get("duration")
        resolution = params.get("resolution")
        ratio = params.get("ratio")
        
        logger.info(f"提交镜头 {shot_number} 视频任务 (Project: {project_id})...")
        
        # Check if image_path is a URL or needs upload
        image_url = None
        if image_path and (image_path.startswith("http://") or image_path.startswith("https://")):
            image_url = image_path
        else:
            # If local, upload to TOS
            if image_path and Path(image_path).exists():
                bucket = config_loader.get("tos.bucket_name")
                if not bucket:
                     return {"error": "TOS not configured, cannot upload local image for video gen"}
                
                try:
                    bucket_dir = config_loader.get("tos.bucket_directory", "")
                    if bucket_dir and not bucket_dir.endswith('/'):
                        bucket_dir += '/'
                    filename = Path(image_path).name
                    key = f"{bucket_dir}{project_id}/images/{filename}"
                    with open(image_path, 'rb') as f:
                        image_url = tos_client.upload_content(bucket, key, f.read())
                    logger.info(f"Uploaded local image for task submission: {image_url}")
                except Exception as e:
                     return {"error": f"Failed to upload local image: {e}"}
            else:
                return {"error": "Invalid image path or URL"}

        if image_url:
            task_id, usage = veadk_client.submit_video_generation_task(
                image_path=None, 
                prompt=video_prompt, 
                duration=duration, 
                image_url=image_url,
                resolution=resolution,
                ratio=ratio
            )
            
            if task_id:
                return {
                    "task_id": task_id,
                    "status": "submitted",
                    "usage": usage
                }
            else:
                return {"error": usage.get("error", "Submission failed"), "usage": usage}
        else:
            return {"error": "No image URL available"}

    def process_completed_video(self, video_url: str, project_id: str, shot_number: int) -> Tuple[Optional[str], Optional[str]]:
        """
        处理已完成的视频：保存到本地，确保TOS上有
        Returns: (final_video_path_or_url, error)
        """
        project_dir = self.output_dir / project_id / "videos"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        import time
        timestamp = int(time.time() * 1000)
        filename = f"shot_{shot_number:03d}_{timestamp}.mp4"
        video_path = project_dir / filename
        
        # Save to local
        try:
            import requests
            with requests.get(video_url, stream=True) as r:
                r.raise_for_status()
                with open(video_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logger.info(f"镜头 {shot_number} 视频已下载至: {video_path}")
        except Exception as e:
            logger.error(f"视频下载失败: {e}")
            # If download fails, we might still return the URL if it's accessible?
            # But subsequent steps (merge) need local file usually.
            # But let's try to upload URL to TOS directly if local save failed?
            pass

        # TOS Upload
        final_url = None
        bucket = config_loader.get("tos.bucket_name")
        if bucket:
            bucket_dir = config_loader.get("tos.bucket_directory", "")
            if bucket_dir and not bucket_dir.endswith('/'):
                bucket_dir += '/'
            key = f"{bucket_dir}{project_id}/videos/{filename}"
            
            try:
                if video_path.exists():
                    with open(video_path, 'rb') as f:
                        final_url = tos_client.upload_content(bucket, key, f.read())
                else:
                    final_url = tos_client.upload_from_url(bucket, key, video_url)
                logger.info(f"镜头 {shot_number} 视频已同步至TOS: {final_url}")
            except Exception as e:
                logger.error(f"TOS sync failed: {e}")
                return None, f"TOS sync failed: {e}"
        
        # Return TOS URL if available, else local path
        if final_url:
            return final_url, None
        elif video_path.exists():
            return str(video_path), None
        else:
            return None, "Failed to save video locally or upload to TOS"

    def _generate_single_video(self, params: Dict, project_dir: Path) -> Tuple[int, Optional[str], Dict]:
        """Helper to generate single video"""
        shot_number = params.get("shot_number")
        image_path = params.get("image_path")
        video_prompt = params.get("video_prompt")
        duration = params.get("duration")
        try:
            project_id = project_dir.parent.name
        except:
            project_id = "unknown"

        logger.info(f"生成镜头 {shot_number} 视频...")
        
        # Check if image_path is a URL
        image_url = None
        if image_path and (image_path.startswith("http://") or image_path.startswith("https://")):
            image_url = image_path
        else:
            # If image_path is local path, we must verify if it's already mapped to a TOS URL 
            # OR we must enforce it to be a URL.
            # The user requirement says: "When generating video, the initial image address used MUST be the cloud URL."
            # So if we receive a local path, we have a problem unless we can map it.
            # However, typically the frontend or upstream logic passes the stored path.
            # If image generation was successful, the stored path is now the TOS URL.
            # So if we get a local path here, it means either:
            # 1. Image was generated before mandatory TOS policy.
            # 2. Image generation failed to upload but saved locally (which we now prevent).
            # Let's try to upload it now if it's local.
            if image_path and Path(image_path).exists():
                logger.warning(f"Received local image path {image_path}, uploading to TOS to get cloud URL...")
                bucket = config_loader.get("tos.bucket_name")
                if not bucket:
                     return shot_number, None, {"error": "TOS not configured, cannot upload local image for video gen"}
                
                try:
                    bucket_dir = config_loader.get("tos.bucket_directory", "")
                    if bucket_dir and not bucket_dir.endswith('/'):
                        bucket_dir += '/'
                    # Use existing filename
                    filename = Path(image_path).name
                    key = f"{bucket_dir}{project_id}/images/{filename}"
                    with open(image_path, 'rb') as f:
                        image_url = tos_client.upload_content(bucket, key, f.read())
                    logger.info(f"Uploaded local image to: {image_url}")
                except Exception as e:
                     return shot_number, None, {"error": f"Failed to upload local image for video gen: {e}"}
            else:
                return shot_number, None, {"error": "Invalid image path or URL"}

        if image_url:
            video_url, usage = veadk_client.generate_video(
                image_path=None, 
                prompt=video_prompt, 
                duration=duration, 
                image_url=image_url,
                resolution=params.get("resolution"),
                ratio=params.get("ratio")
            )
        else:
            # Should not happen
            return shot_number, None, {"error": "No image URL available"}
        
        if video_url:
            import time
            timestamp = int(time.time() * 1000)
            filename = f"shot_{shot_number:03d}_{timestamp}.mp4"
            
            # Always save to local first
            video_path = project_dir / filename
            try:
                import requests
                with requests.get(video_url, stream=True) as r:
                    r.raise_for_status()
                    with open(video_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                logger.info(f"镜头 {shot_number} 视频已保存至本地: {video_path}")
            except Exception as e:
                logger.error(f"本地视频保存失败: {e}")
                # Don't return failure immediately, try TOS if configured
                pass

            # Check for TOS configuration
            final_url = None
            
            # Mandatory TOS check
            bucket = config_loader.get("tos.bucket_name")
            if not bucket:
                 raise Exception("TOS bucket is not configured. Storage configuration is mandatory.")

            bucket_dir = config_loader.get("tos.bucket_directory", "")
            
            if bucket:
                # Upload to TOS
                if bucket_dir and not bucket_dir.endswith('/'):
                    bucket_dir += '/'
                
                key = f"{bucket_dir}{project_id}/videos/{filename}"
                logger.info(f"Uploading video to TOS (Mandatory): {key}")
                try:
                    # Prefer uploading local file if available
                    if video_path.exists():
                        with open(video_path, 'rb') as f:
                            url = tos_client.upload_content(bucket, key, f.read())
                    else:
                        url = tos_client.upload_from_url(bucket, key, video_url)
                        
                    logger.info(f"镜头 {shot_number} 视频已上传: {url}")
                    final_url = url
                except Exception as e:
                    logger.error(f"TOS upload failed: {e}")
                    return shot_number, None, {"error": f"TOS upload failed: {str(e)}"}
            
            return shot_number, final_url, usage
        else:
            # API call failed
            error_msg = usage.get("error", "Unknown API error")
            req_id = usage.get("request_id", "unknown")
            logger.error(f"镜头 {shot_number} 视频生成失败: {error_msg} (ReqID: {req_id})")
            return shot_number, None, usage

    def submit_batch_video_tasks(
        self,
        image_paths: List[str],
        video_prompts: List[Dict],
        storyboard: Dict,
        project_id: str,
        resolution: str = None,
        ratio: str = None
    ) -> List[Dict]:
        """
        批量提交视频任务
        Returns: List of task info dicts (including error info if failed)
        """
        shots = storyboard.get("shots", [])
        results = [None] * len(image_paths)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {}
            for i, (image_path, prompt_data) in enumerate(zip(image_paths, video_prompts)):
                if image_path is None:
                    continue
                
                shot_number = prompt_data.get("shot_number", i + 1)
                duration = shots[i].get("duration", 5) if i < len(shots) else 5
                
                params = {
                    "shot_number": shot_number,
                    "image_path": image_path,
                    "video_prompt": prompt_data.get("video_prompt", ""),
                    "duration": duration,
                    "resolution": resolution,
                    "ratio": ratio
                }
                
                future = executor.submit(self.submit_single_video_task, params, project_id)
                future_to_index[future] = i
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    res = future.result()
                    # Add shot info
                    res["index"] = index
                    # Ensure shot_number is present
                    if "shot_number" not in res:
                         # Try to recover from prompts
                         res["shot_number"] = video_prompts[index].get("shot_number", index + 1)
                    results[index] = res
                except Exception as e:
                    logger.error(f"Batch submit failed for index {index}: {e}")
                    results[index] = {"error": str(e), "index": index, "shot_number": index+1}
                    
        return results

    def generate_shot_videos(
        self, 
        image_paths: List[str],
        video_prompts: List[Dict],
        storyboard: Dict,
        project_id: str,
        on_status_update: Optional[callable] = None,
        resolution: str = None,
        ratio: str = None
    ) -> Tuple[List[str], Dict]:
        """
        Concurrency generate videos for all shots
        
        Args:
            image_paths: Image paths list
            video_prompts: Video prompts list
            storyboard: Storyboard data
            project_id: Project ID
            on_status_update: Callback(key, value, extra_data) for status updates
            resolution: Resolution
            ratio: Aspect ratio
        
        Returns:
            (List of video paths, API usage)
        """
        shots = storyboard.get("shots", [])
        video_paths = [None] * len(image_paths)
        total_api_calls = 0
        
        project_dir = self.output_dir / project_id / "videos"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_index = {}
            for i, (image_path, prompt_data) in enumerate(zip(image_paths, video_prompts)):
                if image_path is None:
                    continue
                
                shot_number = prompt_data.get("shot_number", i + 1)
                
                # Update status
                if on_status_update:
                    on_status_update(f"shot_status_video_{shot_number}", "processing", None)
                
                duration = shots[i].get("duration", 5) if i < len(shots) else 5
                
                params = {
                    "shot_number": shot_number,
                    "image_path": image_path,
                    "video_prompt": prompt_data.get("video_prompt", ""),
                    "duration": duration,
                    "resolution": resolution,
                    "ratio": ratio
                }
                
                # Add ratio/resolution from project config? 
                # Ideally we should pass them. But generate_shot_videos doesn't take them as args.
                # However, the user requirement says "take resolution... ratio... from project settings".
                # I should update generate_shot_videos signature to accept these.
                
                future = executor.submit(self._generate_single_video, params, project_dir)
                future_to_index[future] = i
            
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    shot_num, path, usage = future.result()
                    
                    status = "failed"
                    extra = None
                    if path:
                        status = "completed"
                        video_paths[index] = path
                        extra = {"path": path, "index": index, "shot_number": shot_num}
                    else:
                        # Pass error info
                        extra = {
                            "error": usage.get("error", "Generation failed"), 
                            "request_id": usage.get("request_id", "unknown"),
                            "shot_number": shot_num,
                            "index": index
                        }
                    
                    # Update status for specific shot
                    if on_status_update:
                        on_status_update(f"shot_status_video_{shot_num}", status, extra)
                    
                    total_api_calls += usage.get("api_calls", 1)
                except Exception as e:
                    logger.error(f"Video generation failed for index {index}: {e}")
                    # We can't easily get shot_num if exception happens before return, but future result raises exception
                    # so we don't know shot_num unless we store it.
                    # But we can infer from index if prompts are ordered? 
                    # shot_num usually corresponds to index+1 if strictly ordered.
                    # Let's try to get shot_num from video_prompts[index]
                    try:
                        shot_num_err = video_prompts[index].get("shot_number", index + 1)
                        if on_status_update:
                            on_status_update(f"shot_status_video_{shot_num_err}", "failed", None)
                    except:
                        pass
        
        return video_paths, {"api_calls": total_api_calls}
    
    def _create_static_video(
        self, 
        image_path: str, 
        duration: int, 
        output_dir: Path,
        shot_number: int
    ) -> str:
        """从静态图像创建视频（备用方案）"""
        temp_file = None
        try:
            # Handle TOS URL / Private URL
            final_image_path = image_path
            if image_path.startswith("http://") or image_path.startswith("https://"):
                # Try to download using tos_client if possible, or standard requests
                # Since we likely have private bucket, we should use tos_client to get content
                # But tos_client.get_object returns object, we need to save to temp file for moviepy
                
                try:
                    import tempfile
                    from ..utils.tos_client import tos_client
                    
                    parsed = tos_client.parse_tos_url(image_path)
                    if parsed:
                        bucket, key = parsed
                        obj = tos_client.get_object(bucket, key)
                        # Read content
                        content = obj.read()
                    else:
                        # Public URL fallback
                        import requests
                        resp = requests.get(image_path)
                        resp.raise_for_status()
                        content = resp.content
                        
                    # Write to temp file
                    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    temp_file.write(content)
                    temp_file.close() # Close so moviepy can open it
                    final_image_path = temp_file.name
                    logger.info(f"Downloaded image to temp file: {final_image_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to download image for static video: {e}")
                    # If download fails, we can't create video
                    return None

            try:
                from moviepy.editor import ImageClip
            except ImportError:
                # Support moviepy v2.0+
                from moviepy import ImageClip
                
            import time
            timestamp = int(time.time() * 1000)
            video_path = output_dir / f"shot_{shot_number:03d}_{timestamp}.mp4"
            
            clip = ImageClip(final_image_path, duration=duration)
            
            # Re-check v2 API. 
            # safe approach:
            if hasattr(clip, 'with_fps'):
                clip = clip.with_fps(24)
            else:
                clip = clip.set_fps(24)
                
            clip.write_videofile(
                str(video_path), 
                codec='libx264', 
                audio=False,
                ffmpeg_params=['-crf', '18', '-preset', 'slow'],
                logger=None
            )
            clip.close()
            
            logger.info(f"使用静态图像创建视频: {video_path}")
            return str(video_path)
            
        except Exception as e:
            logger.error(f"创建静态视频失败: {e}")
            return None
        finally:
            # Cleanup temp file
            if temp_file:
                try:
                    os.remove(temp_file.name)
                except:
                    pass
    
    def regenerate_video(
        self, 
        image_path: str,
        prompt_data: Dict,
        duration: int,
        project_id: str
    ) -> Tuple[Optional[str], Dict]:
        """
        重新生成单个视频
        
        Args:
            image_path: 首图路径
            prompt_data: 视频提示词数据
            duration: 视频时长
            project_id: 项目ID
        
        Returns:
            (视频路径, API使用情况)
        """
        shot_number = prompt_data.get("shot_number", 0)
        video_prompt = prompt_data.get("video_prompt", "")
        
        project_dir = self.output_dir / project_id / "videos"
        project_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"重新生成镜头 {shot_number} 视频...")
        
        # Check if image_path is URL
        image_url = None
        if image_path and (image_path.startswith("http://") or image_path.startswith("https://")):
            image_url = image_path
            
        if image_url:
            video_url, usage = veadk_client.generate_video(image_path=None, prompt=video_prompt, duration=duration, image_url=image_url)
        else:
            video_url, usage = veadk_client.generate_video(image_path, video_prompt, duration)
        
        if video_url:
            # TOS Upload logic
            if config_loader.get("tos.enable"):
                bucket = config_loader.get("tos.bucket_name")
                bucket_dir = config_loader.get("tos.bucket_directory", "")
                if bucket:
                    import time
                    timestamp = int(time.time() * 1000)
                    filename = f"shot_{shot_number:03d}_{timestamp}.mp4"
                    if bucket_dir and not bucket_dir.endswith('/'):
                        bucket_dir += '/'
                    key = f"{bucket_dir}{project_id}/videos/{filename}"
                    try:
                        final_url = tos_client.upload_from_url(bucket, key, video_url)
                        return final_url, usage
                    except Exception as e:
                        logger.error(f"TOS upload failed: {e}")

            # Local fallback
            import time
            timestamp = int(time.time() * 1000)
            video_path = project_dir / f"shot_{shot_number:03d}_{timestamp}.mp4"
            try:
                import requests
                with requests.get(video_url, stream=True) as r:
                    r.raise_for_status()
                    with open(video_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                return str(video_path), usage
            except Exception as e:
                logger.error(f"Local save failed: {e}")
        
        return None, usage

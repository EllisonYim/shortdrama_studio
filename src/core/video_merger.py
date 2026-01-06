"""
视频拼接模块
"""

import os
import tempfile
import requests
import uuid
from pathlib import Path
from typing import List, Optional, Tuple
from loguru import logger

from ..utils.config_loader import config_loader
from ..utils.tos_client import tos_client

class VideoMerger:
    """视频拼接器"""
    
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = config_loader.get("app.project_dir", "./data/projects")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def merge_videos(
        self, 
        video_paths: List[str], 
        project_id: str,
        output_name: str = "final_video"
    ) -> Optional[str]:
        """
        拼接所有分镜视频
        
        Args:
            video_paths: 视频路径列表
            project_id: 项目ID
            output_name: 输出文件名
        
        Returns:
            最终视频路径 (本地路径 或 TOS URL)
        """
        temp_files = []
        try:
            from moviepy import VideoFileClip, concatenate_videoclips
            
            # 1. 预处理视频路径 (下载远程视频)
            local_paths = []
            
            for p in video_paths:
                if not p:
                    continue
                    
                if p.startswith("http://") or p.startswith("https://"):
                    # 下载远程视频
                    try:
                        # 尝试解析是否为 TOS URL
                        parsed = tos_client.parse_tos_url(p)
                        content = None
                        
                        if parsed:
                            bucket, key = parsed
                            # 生成签名URL以防是私有桶
                            signed_url = tos_client.get_signed_url(bucket, key)
                            if signed_url:
                                p = signed_url
                        
                        logger.info(f"Downloading video part: {p[:50]}...")
                        with requests.get(p, stream=True) as r:
                            r.raise_for_status()
                            tf = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                            for chunk in r.iter_content(chunk_size=8192):
                                tf.write(chunk)
                            tf.close()
                            local_paths.append(tf.name)
                            temp_files.append(tf.name)
                            
                    except Exception as e:
                        logger.error(f"Failed to download video part {p}: {e}")
                elif os.path.exists(p):
                    local_paths.append(p)
                else:
                    logger.warning(f"Video path not found: {p}")
            
            if not local_paths:
                logger.error("没有有效的视频文件可供拼接")
                return None
            
            logger.info(f"开始拼接 {len(local_paths)} 个视频片段...")
            
            # 2. 加载所有视频
            clips = []
            for path in local_paths:
                try:
                    clip = VideoFileClip(path)
                    # 确保所有片段尺寸一致或进行resize? 
                    # 目前假设一致，或者moviepy会自动处理(compose method)
                    clips.append(clip)
                except Exception as e:
                    logger.warning(f"无法加载视频 {path}: {e}")
            
            if not clips:
                logger.error("没有成功加载任何视频")
                return None
            
            # 3. 拼接视频
            final_clip = concatenate_videoclips(clips, method="compose")
            
            # 输出路径 (本地临时)
            # Align with VideoGenerator: save to 'videos' subdirectory
            output_dir = self.output_dir / project_id / "videos"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{output_name}.mp4"
            
            # 4. 写入文件
            logger.info(f"Writing video file to {output_path}")
            final_clip.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                fps=24,
                ffmpeg_params=['-crf', '18', '-preset', 'ultrafast'],
                logger='bar'
            )
            logger.info("Video file written successfully")

            
            # 清理 Clip 资源
            for clip in clips:
                clip.close()
            final_clip.close()
            
            final_path_str = str(output_path)
            
            # 5. 上传到 TOS (如果配置了)
            bucket = tos_client.bucket
            if bucket:
                try:
                    logger.info("Uploading final video to TOS...")
                    
                    # Align with VideoGenerator TOS path structure
                    bucket_dir = config_loader.get("tos.bucket_directory", "")
                    if bucket_dir and not bucket_dir.endswith('/'):
                        bucket_dir += '/'
                        
                    # Use 'videos' directory in TOS as well
                    key = f"{bucket_dir}{project_id}/videos/{output_name}_{uuid.uuid4().hex[:8]}.mp4"
                    
                    with open(final_path_str, 'rb') as f:
                        content = f.read()
                    
                    # 使用 public-read ACL 上传
                    tos_url = tos_client.upload_content(bucket, key, content, acl='public-read')
                    logger.info(f"Merged video uploaded to TOS: {tos_url}")
                    return tos_url
                except Exception as e:
                    logger.error(f"Failed to upload merged video to TOS: {e}")
                    # Fallback to local path if upload fails
                    return final_path_str
            
            logger.info(f"视频拼接完成 (Local): {final_path_str}")
            return final_path_str
            
        except ImportError as e:
            logger.error(f"moviepy 导入失败: {e}")
            return None
        except Exception as e:
            logger.error(f"视频拼接失败: {e}")
            return None
        finally:
            # 清理下载的临时文件
            for tf in temp_files:
                try:
                    os.remove(tf)
                except:
                    pass
    
    def add_transitions(
        self, 
        video_paths: List[str],
        transition_type: str = "fade",
        transition_duration: float = 0.5
    ) -> List[str]:
        """
        为视频添加转场效果
        
        Args:
            video_paths: 视频路径列表
            transition_type: 转场类型
            transition_duration: 转场时长
        
        Returns:
            处理后的视频路径列表
        """
        # 简化实现，实际可以添加更复杂的转场效果
        return video_paths
    
    def add_audio(
        self, 
        video_path: str, 
        audio_path: str, 
        output_path: str = None
    ) -> Optional[str]:
        """
        为视频添加音频
        
        Args:
            video_path: 视频路径
            audio_path: 音频路径
            output_path: 输出路径
        
        Returns:
            添加音频后的视频路径
        """
        try:
            from moviepy import VideoFileClip, AudioFileClip
            
            if output_path is None:
                base = Path(video_path)
                output_path = str(base.parent / f"{base.stem}_with_audio{base.suffix}")
            
            video = VideoFileClip(video_path)
            audio = AudioFileClip(audio_path)
            
            # 调整音频长度以匹配视频
            if audio.duration > video.duration:
                audio = audio.subclip(0, video.duration)
            
            video_with_audio = video.set_audio(audio)
            video_with_audio.write_videofile(
                output_path,
                codec='libx264',
                audio_codec='aac',
                ffmpeg_params=['-crf', '18', '-preset', 'slow'],
                logger=None
            )
            
            video.close()
            audio.close()
            video_with_audio.close()
            
            return output_path
            
        except Exception as e:
            logger.error(f"添加音频失败: {e}")
            return None

import asyncio
import threading
import math
import copy
from pathlib import Path
from aiohttp import web
from loguru import logger
from src.utils.config_loader import config_loader
from src.core.script_generator import ScriptGenerator
from src.core.character_generator import CharacterGenerator
from src.core.scene_generator import SceneGenerator
from src.core.storyboard_generator import StoryboardGenerator
from src.core.prompt_generator import PromptGenerator
from src.core.image_generator import ImageGenerator
from src.core.video_generator import VideoGenerator
from src.core.video_merger import VideoMerger
from src.utils.tos_client import tos_client
from src.server.database import get_db
from src.server.services import TaskService
from src.server.log_service import LogService
from src.server.project_service import ProjectService
from src.server.video_scheduler import VideoScheduler
from src.server.models import VideoTask, generate_uuid

project_root = Path(__file__).resolve().parents[2]
web_dir = project_root / "web"

# Get data_dir from config
config_data_path = config_loader.get("app.data_dir", "./data/aigc/")
if Path(config_data_path).is_absolute():
    data_dir = Path(config_data_path)
else:
    data_dir = project_root / config_data_path

# Ensure directory exists
data_dir.mkdir(parents=True, exist_ok=True)

script_gen = ScriptGenerator()
char_gen = CharacterGenerator()
scene_gen = SceneGenerator()
storyboard_gen = StoryboardGenerator()
prompt_gen = PromptGenerator()
image_gen = ImageGenerator(output_dir=str(data_dir))
video_gen = VideoGenerator(output_dir=str(data_dir))
merger = VideoMerger(output_dir=str(data_dir))


async def _health(request):
    return web.json_response({"status": "ok", "app": "short_drama_studio", "version": "1.0"})


async def _index(request):
    index_path = web_dir / "index.html"
    if index_path.exists():
        return web.FileResponse(path=str(index_path))
    return web.Response(text="Short Drama Studio", content_type="text/plain")


async def _run_blocking(func, *args):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, func, *args)

async def _start_background_task(project_id, task_type, func, *args):
    db = next(get_db())
    task_service = TaskService(db)
    log_service = LogService(db)
    
    task = task_service.create_task(project_id, task_type)
    task_id = task.id
    
    # Log start
    log_service.log(project_id, task_id, "INFO", f"Task {task_type} started", module="http_server")
    db.close() # Close main thread session

    async def wrapper():
        # Create new session for the background task
        db_gen = get_db()
        db_session = next(db_gen)
        ts = TaskService(db_session)
        ls = LogService(db_session)
        
        try:
            ts.update_task(task_id, status="running", progress=0)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, func, *args)
            
            res = result
            usage = {}
            if isinstance(result, tuple) and len(result) == 2:
                res, usage = result
                
            ts.update_task(task_id, status="completed", progress=100, result=res)
            ls.log(project_id, task_id, "INFO", f"Task {task_type} completed", module="http_server", details=usage)
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            ts.update_task(task_id, status="failed", error=str(e))
            ls.log(project_id, task_id, "ERROR", f"Task failed: {str(e)}", module="http_server", details={"error": str(e)})
        finally:
            db_session.close()
            
    asyncio.create_task(wrapper())
    return task_id

# Task & Log APIs

async def _get_task_status(request):
    task_id = request.match_info["task_id"]
    db = next(get_db())
    ts = TaskService(db)
    task = ts.get_task(task_id)
    if not task:
        db.close()
        return web.json_response({"error": "not found"}, status=404)
    
    data = {
        "task_id": task.id,
        "project_id": task.project_id,
        "type": task.type,
        "status": task.status,
        "progress": task.progress,
        "current_step": task.current_step,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None
    }
    db.close()
    return web.json_response(data)

async def _get_project_tasks(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ts = TaskService(db)
    tasks = ts.get_project_tasks(pid)
    data = []
    for t in tasks:
        data.append({
            "task_id": t.id,
            "type": t.type,
            "status": t.status,
            "progress": t.progress,
            "created_at": t.created_at.isoformat() if t.created_at else None
        })
    db.close()
    return web.json_response({"tasks": data})

async def _get_logs_api(request):
    try:
        pid = request.query.get("project_id")
        if not pid:
            pid = None
        tid = request.query.get("task_id")
        if not tid:
            tid = None
        level = request.query.get("level")
        if not level:
            level = None
        limit = int(request.query.get("limit", 100))
        
        db = next(get_db())
        try:
            ls = LogService(db)
            logs = ls.get_logs(project_id=pid, task_id=tid, level=level, limit=limit)
            
            data = []
            for l in logs:
                details = l.details
                # Sanitize details for NaN values which break JSON
                if isinstance(details, dict):
                    for k, v in details.items():
                        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                            details[k] = str(v)
                            
                data.append({
                    "id": l.id,
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                    "level": l.level,
                    "message": l.message,
                    "module": l.module,
                    "details": details,
                    "task_id": l.task_id
                })
            return web.json_response({"logs": data})
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Get logs failed: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def _create_project(request):
    data = await request.json()
    input_type = (data.get("input_type") or "topic").strip()
    input_content = (data.get("input_content") or "").strip()
    if input_type not in ("topic", "script"):
        return web.json_response({"error": "invalid input_type"}, status=400)
    if not input_content:
        return web.json_response({"error": "input_content required"}, status=400)
    
    project_name = data.get("project_name") or ("短剧-" + input_content[:10])
    
    meta = {
        "aspect_ratio": data.get("aspect_ratio") or "16:9",
        "resolution": data.get("resolution") or "1080p",
        "style": data.get("style") or "现代都市",
        "visual_style": data.get("visual_style") or "真人",
        "platform": config_loader.get("platform", "volcengine"),
    }
    if input_type == "topic":
        meta["duration"] = int(data.get("duration") or 3)
        meta["audience"] = data.get("audience") or "年轻人"

    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.create_project(project_name, input_type, input_content, meta)
        project_id = project.id
    finally:
        db.close()
        
    return web.json_response({"project_id": project_id})


async def _get_project(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response(project.to_dict())
    finally:
        db.close()


async def _generate_script(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        
        project_dict = project.to_dict() # Get data before closing session or use obj
        input_type = project.input_type
        topic = project.input_content
        meta = project.topic_meta or {}
    finally:
        db.close()

    if input_type == "script":
        # Skipped
        # Need to update step status
        db = next(get_db())
        ps = ProjectService(db)
        ps.update_step(pid, 0, {"status": "skipped"})
        db.close()
        return web.json_response({"message": "skipped"})
    
    def worker():
        # Worker DB session
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            script, tokens = script_gen.generate(
                topic,
                int(meta.get("duration", 3)),
                meta.get("style", "现代都市"),
                meta.get("audience", "年轻人"),
            )
            ps_w.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
            ps_w.update_project(pid, {"script": script, "current_step": 1, "status": "in_progress"})
            ps_w.update_step(pid, 0, {"status": "completed", "token_usage": tokens})
            return {"script": script, "tokens": tokens}, tokens
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "script_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _optimize_script(request):
    pid = request.match_info["pid"]
    data = await request.json()
    feedback = data.get("feedback")
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        original_script = data.get("script") or project.script or project.input_content
    finally:
        db.close()
    
    if not feedback:
        return web.json_response({"error": "feedback required"}, status=400)
    if not original_script:
        return web.json_response({"error": "script required"}, status=400)
        
    script, tokens = await _run_blocking(script_gen.optimize, original_script, feedback)
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        ps.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
        ps.update_project(pid, {"script": script})
    finally:
        db.close()
    
    return web.json_response({"script": script, "tokens": tokens})


async def _update_script(request):
    pid = request.match_info["pid"]
    data = await request.json()
    script = data.get("script")
    if not script:
        return web.json_response({"error": "script required"}, status=400)
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        ps.update_project(pid, {"script": script})
    finally:
        db.close()
        
    return web.json_response({"status": "ok", "script": script})


async def _generate_characters(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        script = project.script or project.input_content
        meta = project.topic_meta or {}
    finally:
        db.close()

    if not script:
        return web.json_response({"error": "script missing"}, status=400)

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            characters, tokens = char_gen.generate(script)
            ps_w.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
            ps_w.update_project(pid, {"characters": characters, "current_step": 2})
            ps_w.update_step(pid, 1, {"status": "completed", "token_usage": tokens})
            return {"characters": characters, "tokens": tokens}, tokens
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "character_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _generate_character_prompts(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        characters = project.characters or []
        meta = project.topic_meta or {}
    finally:
        db.close()

    if not characters:
        return web.json_response({"error": "characters missing"}, status=400)

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            updated_chars, tokens = char_gen.generate_prompts(
                characters,
                meta.get("style", "现代都市"),
                meta.get("visual_style", "真人")
            )
            ps_w.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
            ps_w.update_project(pid, {"characters": updated_chars})
            return {"characters": updated_chars, "tokens": tokens}, tokens
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "character_prompt_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _generate_character_images(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        characters = project.characters or []
        meta = project.topic_meta or {}
    finally:
        db.close()

    if not characters:
        return web.json_response({"error": "characters missing"}, status=400)

    ratio = meta.get("aspect_ratio", "16:9") # Actually characters usually portrait? Let's use 1:1 or 3:4 or stick to project ratio
    # Maybe use 3:4 for characters by default or user choice? Let's stick to project ratio for consistency or 1:1
    # For now, use project ratio.
    resolution = meta.get("resolution", "1080p")
    visual_style = meta.get("visual_style", "真人")

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        
        # We need to map characters to prompts for ImageGenerator
        # ImageGenerator expects list of dicts with 'positive_prompt' and 'shot_number' (or index)
        # We can use character index as shot_number or introduce new logic
        # But ImageGenerator.generate_shot_images relies on 'shot_number' key in prompts and returns dict {shot_number: [paths]}
        
        char_prompts = []
        for i, char in enumerate(characters):
            if char.get("prompt"):
                char_prompts.append({
                    "shot_number": i + 1, # Use 1-based index
                    "positive_prompt": char["prompt"]
                })
        
        if not char_prompts:
            return {"error": "no prompts"}, {}

        def status_callback(key, value, extra=None):
            # This callback updates project.topic_meta
            # We want to store character images in project.characters or separate field?
            # Existing image_gen updates 'shot_images' in topic_meta.
            # We should probably use a different key for characters, e.g. 'character_images'
            pass 

        # We can't easily reuse image_gen.generate_shot_images AS IS because it updates specific meta keys
        # But we can instantiate a fresh ImageGenerator or use its lower level methods?
        # Actually generate_shot_images calls model and returns paths.
        # The callback is optional.
        # We can handle result mapping here.
        
        try:
            # We reuse image_gen but we need to handle the result carefully
            # shot_images dict: {shot_number: [path1, path2]}
            shot_images, usage = image_gen.generate_shot_images(
                char_prompts,
                pid,
                1, # 1 image per char
                ratio=ratio,
                resolution=resolution,
                style=visual_style,
                sub_dir="characters"
            )
            
            # Update characters with image paths
            updated_chars = list(characters)
            for i, char in enumerate(updated_chars):
                idx = i + 1
                if idx in shot_images and shot_images[idx]:
                    char["image_path"] = shot_images[idx][-1]
            
            ps_w.update_project(pid, {"characters": updated_chars})
            ps_w.add_usage(pid, images=len(char_prompts))
            
            return {"characters": updated_chars}, usage
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "character_image_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _update_characters(request):
    pid = request.match_info["pid"]
    data = await request.json()
    characters = data.get("characters")
    if not characters:
        return web.json_response({"error": "characters required"}, status=400)
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        if not ps.get_project(pid):
            return web.json_response({"error": "not found"}, status=404)
        ps.update_project(pid, {"characters": characters})
    finally:
        db.close()
        
    return web.json_response({"status": "ok", "characters": characters})


async def _update_single_character_prompt(request):
    pid = request.match_info["pid"]
    index = int(request.match_info["index"])
    data = await request.json()
    prompt = data.get("prompt")
    
    if prompt is None:
        return web.json_response({"error": "prompt required"}, status=400)
        
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        
        characters = copy.deepcopy(project.characters or [])
        if index < 0 or index >= len(characters):
             return web.json_response({"error": "character not found"}, status=404)
             
        characters[index]["prompt"] = prompt
        ps.update_project(pid, {"characters": characters})
        
        return web.json_response({"status": "ok", "character": characters[index]})
    finally:
        db.close()


async def _regenerate_single_character_prompt(request):
    pid = request.match_info["pid"]
    index = int(request.match_info["index"])
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        characters = project.characters or []
        if index < 0 or index >= len(characters):
             return web.json_response({"error": "character not found"}, status=404)
        
        target_char = characters[index]
        meta = project.topic_meta or {}
        style = meta.get("style", "现代都市")
        visual_style = meta.get("visual_style", "真人")
    finally:
        db.close()
        
    updated_char, tokens = await _run_blocking(
        char_gen.generate_single_prompt,
        target_char,
        style,
        visual_style
    )
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        # Re-fetch to avoid conflicts
        project = ps.get_project(pid)
        characters = copy.deepcopy(project.characters or [])
        if index < len(characters):
            # Preserve image path if exists
            if "image_path" in characters[index]:
                updated_char["image_path"] = characters[index]["image_path"]
            characters[index] = updated_char
            ps.update_project(pid, {"characters": characters})
            ps.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
    finally:
        db.close()
        
    return web.json_response({"character": updated_char, "tokens": tokens})


async def _update_single_character(request):
    pid = request.match_info["pid"]
    index = int(request.match_info["index"])
    data = await request.json()
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        characters = copy.deepcopy(project.characters or [])
        if index < 0 or index >= len(characters):
             return web.json_response({"error": "character not found"}, status=404)
             
        # Update fields
        char = characters[index]
        for key in ["name", "gender", "age", "personality", "clothing", "appearance"]:
            if key in data:
                char[key] = data[key]
                
        ps.update_project(pid, {"characters": characters})
        
        return web.json_response({"status": "ok", "character": char})
    finally:
        db.close()


async def _regenerate_single_character_image(request):
    pid = request.match_info["pid"]
    index = int(request.match_info["index"])
    try:
        data = await request.json()
        new_prompt = data.get("prompt")
    except:
        new_prompt = None
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        characters = copy.deepcopy(project.characters or [])
        if index < 0 or index >= len(characters):
             return web.json_response({"error": "character not found"}, status=404)
             
        char = characters[index]
        
        if new_prompt is not None:
            char["prompt"] = new_prompt
            characters[index] = char
            ps.update_project(pid, {"characters": characters})
            prompt = new_prompt
        else:
            prompt = char.get("prompt")

        if not prompt:
             return web.json_response({"error": "prompt required"}, status=400)
             
        meta = project.topic_meta or {}
        ratio = meta.get("aspect_ratio", "16:9")
        resolution = meta.get("resolution", "1080p")
        visual_style = meta.get("visual_style", "真人")
    finally:
        db.close()
        
    # Reuse ImageGenerator
    # We construct a single item list for generate_shot_images
    # Shot number is arbitrary here, let's use index+1
    char_prompts = [{
        "shot_number": index + 1,
        "positive_prompt": prompt
    }]
    
    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            shot_images, usage = image_gen.generate_shot_images(
                char_prompts,
                pid,
                1, # 1 image
                ratio=ratio,
                resolution=resolution,
                style=visual_style,
                sub_dir="characters"
            )
            
            # Update character image path
            project = ps_w.get_project(pid)
            updated_chars = list(project.characters or [])
            if index < len(updated_chars):
                idx = index + 1
                if idx in shot_images and shot_images[idx]:
                    updated_chars[index]["image_path"] = shot_images[idx][-1]
                    ps_w.update_project(pid, {"characters": updated_chars})
                    ps_w.add_usage(pid, images=1)
                    
            return {"image_path": updated_chars[index].get("image_path")}, usage
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "character_image_regeneration", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _generate_scenes(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        script = project.script or project.input_content
        meta = project.topic_meta or {}
    finally:
        db.close()

    if not script:
        return web.json_response({"error": "script missing"}, status=400)

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            scenes, tokens = scene_gen.generate(script)
            ps_w.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
            ps_w.update_project(pid, {"scenes": scenes, "current_step": 3})
            ps_w.update_step(pid, 2, {"status": "completed", "token_usage": tokens})
            return {"scenes": scenes, "tokens": tokens}, tokens
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "scene_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _generate_scene_prompts(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        scenes = project.scenes or []
        meta = project.topic_meta or {}
    finally:
        db.close()

    if not scenes:
        return web.json_response({"error": "scenes missing"}, status=400)

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            updated_scenes, tokens = scene_gen.generate_prompts(
                scenes,
                meta.get("style", "现代都市"),
                meta.get("visual_style", "真人")
            )
            ps_w.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
            ps_w.update_project(pid, {"scenes": updated_scenes})
            return {"scenes": updated_scenes, "tokens": tokens}, tokens
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "scene_prompt_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _generate_scene_images(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        scenes = project.scenes or []
        meta = project.topic_meta or {}
    finally:
        db.close()

    if not scenes:
        return web.json_response({"error": "scenes missing"}, status=400)

    ratio = meta.get("aspect_ratio", "16:9")
    resolution = meta.get("resolution", "1080p")
    visual_style = meta.get("visual_style", "真人")

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        
        scene_prompts = []
        for i, scene in enumerate(scenes):
            if scene.get("prompt"):
                scene_prompts.append({
                    "shot_number": i + 1,
                    "positive_prompt": scene["prompt"]
                })
        
        if not scene_prompts:
            return {"error": "no prompts"}, {}

        try:
            shot_images, usage = image_gen.generate_shot_images(
                scene_prompts,
                pid,
                1,
                ratio=ratio,
                resolution=resolution,
                style=visual_style,
                sub_dir="scenes"
            )
            
            updated_scenes = list(scenes)
            for i, scene in enumerate(updated_scenes):
                idx = i + 1
                if idx in shot_images and shot_images[idx]:
                    scene["image_path"] = shot_images[idx][-1]
            
            ps_w.update_project(pid, {"scenes": updated_scenes})
            ps_w.add_usage(pid, images=len(scene_prompts))
            
            return {"scenes": updated_scenes}, usage
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "scene_image_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _update_scenes(request):
    pid = request.match_info["pid"]
    data = await request.json()
    scenes = data.get("scenes")
    if not scenes:
        return web.json_response({"error": "scenes required"}, status=400)
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        if not ps.get_project(pid):
            return web.json_response({"error": "not found"}, status=404)
        ps.update_project(pid, {"scenes": scenes})
    finally:
        db.close()
        
    return web.json_response({"status": "ok", "scenes": scenes})


async def _update_single_scene(request):
    pid = request.match_info["pid"]
    index = int(request.match_info["index"])
    data = await request.json()
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        scenes = copy.deepcopy(project.scenes or [])
        if index < 0 or index >= len(scenes):
             return web.json_response({"error": "scene not found"}, status=404)
             
        # Update fields
        scene = scenes[index]
        # Allow updating description fields
        for key in ["name", "time", "location", "atmosphere", "elements"]:
            if key in data:
                scene[key] = data[key]
                
        ps.update_project(pid, {"scenes": scenes})
        
        return web.json_response({"status": "ok", "scene": scene})
    finally:
        db.close()


async def _update_single_scene_prompt(request):
    pid = request.match_info["pid"]
    index = int(request.match_info["index"])
    data = await request.json()
    prompt = data.get("prompt")
    
    if prompt is None:
        return web.json_response({"error": "prompt required"}, status=400)
        
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        
        scenes = copy.deepcopy(project.scenes or [])
        if index < 0 or index >= len(scenes):
             return web.json_response({"error": "scene not found"}, status=404)
             
        scenes[index]["prompt"] = prompt
        ps.update_project(pid, {"scenes": scenes})
        
        return web.json_response({"status": "ok", "scene": scenes[index]})
    finally:
        db.close()


async def _regenerate_single_scene_prompt(request):
    pid = request.match_info["pid"]
    index = int(request.match_info["index"])
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        scenes = project.scenes or []
        if index < 0 or index >= len(scenes):
             return web.json_response({"error": "scene not found"}, status=404)
        
        target_scene = scenes[index]
        meta = project.topic_meta or {}
        style = meta.get("style", "现代都市")
        visual_style = meta.get("visual_style", "真人")
    finally:
        db.close()
        
    updated_scene, tokens = await _run_blocking(
        scene_gen.generate_single_prompt,
        target_scene,
        style,
        visual_style
    )
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        # Re-fetch to avoid conflicts
        project = ps.get_project(pid)
        scenes = copy.deepcopy(project.scenes or [])
        if index < len(scenes):
            # Preserve image path if exists
            if "image_path" in scenes[index]:
                updated_scene["image_path"] = scenes[index]["image_path"]
            scenes[index] = updated_scene
            ps.update_project(pid, {"scenes": scenes})
            ps.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
    finally:
        db.close()
        
    return web.json_response({"scene": updated_scene, "tokens": tokens})


async def _regenerate_single_scene_image(request):
    pid = request.match_info["pid"]
    index = int(request.match_info["index"])
    try:
        data = await request.json()
        new_prompt = data.get("prompt")
    except:
        new_prompt = None
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        scenes = copy.deepcopy(project.scenes or [])
        if index < 0 or index >= len(scenes):
             return web.json_response({"error": "scene not found"}, status=404)
             
        scene = scenes[index]
        
        # If new prompt provided, update it
        if new_prompt is not None:
            scene["prompt"] = new_prompt
            scenes[index] = scene
            ps.update_project(pid, {"scenes": scenes})
            prompt = new_prompt
        else:
            prompt = scene.get("prompt")

        if not prompt:
             return web.json_response({"error": "prompt required"}, status=400)
             
        meta = project.topic_meta or {}
        ratio = meta.get("aspect_ratio", "16:9")
        resolution = meta.get("resolution", "1080p")
        visual_style = meta.get("visual_style", "真人")
    finally:
        db.close()
        
    # Reuse ImageGenerator
    # We construct a single item list for generate_shot_images
    scene_prompts = [{
        "shot_number": index + 1,
        "positive_prompt": prompt
    }]
    
    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            shot_images, usage = image_gen.generate_shot_images(
                scene_prompts,
                pid,
                1, # 1 image
                ratio=ratio,
                resolution=resolution,
                style=visual_style,
                sub_dir="scenes"
            )
            
            # Update scene image path
            project = ps_w.get_project(pid)
            updated_scenes = list(project.scenes or [])
            if index < len(updated_scenes):
                idx = index + 1
                if idx in shot_images and shot_images[idx]:
                    updated_scenes[index]["image_path"] = shot_images[idx][-1]
                    ps_w.update_project(pid, {"scenes": updated_scenes})
                    ps_w.add_usage(pid, images=1)
                    
            return {"image_path": updated_scenes[index].get("image_path")}, usage
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "scene_image_regeneration", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _generate_storyboard(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        script = project.script or project.input_content
    finally:
        db.close()

    if not script:
        return web.json_response({"error": "script missing"}, status=400)
        
    storyboard, tokens = await _run_blocking(storyboard_gen.generate, script)
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        ps.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
        ps.update_project(pid, {"storyboard": storyboard, "current_step": 4})
        ps.update_step(pid, 3, {"status": "completed", "token_usage": tokens})
    finally:
        db.close()
        
    return web.json_response({"storyboard": storyboard, "tokens": tokens})


async def _update_storyboard(request):
    pid = request.match_info["pid"]
    data = await request.json()
    storyboard = data.get("storyboard")
    if not storyboard:
        return web.json_response({"error": "storyboard required"}, status=400)
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        if not ps.get_project(pid):
            return web.json_response({"error": "not found"}, status=404)
        ps.update_project(pid, {"storyboard": storyboard})
    finally:
        db.close()
        
    return web.json_response({"status": "ok", "storyboard": storyboard})


async def _generate_prompts(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        storyboard = project.storyboard or {}
    finally:
        db.close()

    if not storyboard or not storyboard.get("shots"):
        return web.json_response({"error": "storyboard missing"}, status=400)

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            # Fetch full project data for context
            project_data = ps_w.get_project(pid)
            characters = project_data.characters or []
            scenes = project_data.scenes or []
            
            # Use concurrent pipeline generation for better performance
            image_prompts, video_prompts, tokens = prompt_gen.generate_all_prompts(
                storyboard, 
                characters=characters,
                scenes=scenes
            )
            
            ps_w.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
            ps_w.update_project(pid, {
                "image_prompts": image_prompts,
                "video_prompts": video_prompts,
                "current_step": 5
            })
            ps_w.update_step(pid, 4, {"status": "completed", "token_usage": tokens})
            return {"image_prompts": image_prompts, "video_prompts": video_prompts}, tokens
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "prompt_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _update_prompts_data(request):
    pid = request.match_info["pid"]
    data = await request.json()
    image_prompts = data.get("image_prompts")
    video_prompts = data.get("video_prompts")
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        if not ps.get_project(pid):
            return web.json_response({"error": "not found"}, status=404)
        
        updates = {}
        if image_prompts is not None:
            updates["image_prompts"] = image_prompts
        if video_prompts is not None:
            updates["video_prompts"] = video_prompts
            
        if updates:
            ps.update_project(pid, updates)
    finally:
        db.close()
        
    return web.json_response({"status": "ok"})


async def _update_single_prompt(request):
    pid = request.match_info["pid"]
    shot_number = int(request.match_info["shot_number"])
    data = await request.json()
    p_type = data.get("type")
    prompt_text = data.get("prompt")
    
    if not p_type or not prompt_text:
        return web.json_response({"error": "type and prompt required"}, status=400)

    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        if p_type == "image":
            prompts = copy.deepcopy(project.image_prompts or [])
            target = next((p for p in prompts if p.get("shot_number") == shot_number), None)
            if target:
                target["positive_prompt"] = prompt_text
            else:
                prompts.append({"shot_number": shot_number, "positive_prompt": prompt_text})
                prompts.sort(key=lambda x: x.get("shot_number", 0))
            
            ps.update_project(pid, {"image_prompts": prompts})
            
        elif p_type == "video":
            prompts = copy.deepcopy(project.video_prompts or [])
            target = next((p for p in prompts if p.get("shot_number") == shot_number), None)
            if target:
                target["video_prompt"] = prompt_text
            else:
                prompts.append({"shot_number": shot_number, "video_prompt": prompt_text})
                prompts.sort(key=lambda x: x.get("shot_number", 0))
                
            ps.update_project(pid, {"video_prompts": prompts})
            
        else:
            return web.json_response({"error": "invalid type"}, status=400)
            
        return web.json_response({"status": "ok"})
    finally:
        db.close()


async def _regenerate_single_prompt(request):
    pid = request.match_info["pid"]
    shot_number = int(request.match_info["shot_number"])
    data = await request.json()
    p_type = data.get("type")
    
    if not p_type:
        return web.json_response({"error": "type required"}, status=400)

    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        storyboard = project.storyboard or {}
        shots = storyboard.get("shots", [])
        
        # Find shot data
        target_shot = next((s for s in shots if s.get("shot_number") == shot_number), None)
        if not target_shot:
            # Fallback by index
            if 0 < shot_number <= len(shots):
                target_shot = shots[shot_number-1]
        
        if not target_shot:
            return web.json_response({"error": "shot not found"}, status=404)
            
        meta = project.topic_meta or {}
        style = meta.get("visual_style", "cinematic")
            
        if p_type == "image":
            prompt_data, tokens = await _run_blocking(prompt_gen.regenerate_single_image_prompt, target_shot, style)
            
            # Update prompts list
            prompts = copy.deepcopy(project.image_prompts or [])
            # Find existing and replace or append
            existing_idx = next((i for i, p in enumerate(prompts) if p.get("shot_number") == shot_number), -1)
            if existing_idx >= 0:
                prompts[existing_idx] = prompt_data
            else:
                prompts.append(prompt_data)
                prompts.sort(key=lambda x: x.get("shot_number", 0))
                
            ps.update_project(pid, {"image_prompts": prompts})
            ps.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
            
            return web.json_response({"prompt": prompt_data, "tokens": tokens})
            
        elif p_type == "video":
            # Need image prompt for context
            image_prompts = project.image_prompts or []
            img_p_data = next((p for p in image_prompts if p.get("shot_number") == shot_number), None)
            if not img_p_data and 0 < shot_number <= len(image_prompts):
                 img_p_data = image_prompts[shot_number-1]
                 
            img_prompt_text = img_p_data.get("positive_prompt", "") if img_p_data else ""
            
            prompt_data, tokens = await _run_blocking(prompt_gen.regenerate_single_video_prompt, target_shot, img_prompt_text)
            
            prompts = list(project.video_prompts or [])
            existing_idx = next((i for i, p in enumerate(prompts) if p.get("shot_number") == shot_number), -1)
            if existing_idx >= 0:
                prompts[existing_idx] = prompt_data
            else:
                prompts.append(prompt_data)
                prompts.sort(key=lambda x: x.get("shot_number", 0))
                
            ps.update_project(pid, {"video_prompts": prompts})
            ps.add_tokens(pid, tokens.get("prompt_tokens", 0), tokens.get("completion_tokens", 0))
            
            return web.json_response({"prompt": prompt_data, "tokens": tokens})
            
        else:
            return web.json_response({"error": "invalid type"}, status=400)
            
    finally:
        db.close()


async def _generate_images(request):
    pid = request.match_info["pid"]
    data = await request.json()
    image_count = int(data.get("image_count", 1))

    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        image_prompts = project.image_prompts or []
        meta = project.topic_meta or {}
    finally:
        db.close()

    if not image_prompts:
        return web.json_response({"error": "image_prompts missing"}, status=400)
        
    ratio = meta.get("aspect_ratio", "16:9")
    resolution = meta.get("resolution", "1080p")
    visual_style = meta.get("visual_style", "真人")

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        
        def status_callback(key, value, extra=None):
            try:
                # Create a new session for thread safety as this runs in thread pool
                db_cb = next(get_db())
                ps_cb = ProjectService(db_cb)
                try:
                    project = ps_cb.get_project(pid)
                    if project:
                        meta = dict(project.topic_meta or {})
                        meta[key] = value
                        
                        updates = {"topic_meta": meta}
                        
                        if extra and "path" in extra and "shot_number" in extra:
                            shot_images = dict(meta.get("shot_images") or {})
                            shot_num = str(extra["shot_number"])
                            if shot_num not in shot_images:
                                shot_images[shot_num] = []
                            # Append if not exists (simple check)
                            if extra["path"] not in shot_images[shot_num]:
                                shot_images[shot_num].append(extra["path"])
                            meta["shot_images"] = shot_images
                            updates["topic_meta"] = meta
                        
                        # Handle error detail
                        if extra and "error" in extra:
                            # Extract shot number if available
                            shot_num = str(extra.get("shot_number", "unknown"))
                            meta[f"shot_error_image_{shot_num}"] = extra["error"]
                            updates["topic_meta"] = meta
                            
                            # Log to DB
                            ls_cb = LogService(db_cb)
                            req_id = extra.get("request_id", "unknown")
                            ls_cb.log(
                                pid, 
                                None, 
                                "ERROR", 
                                f"Shot {shot_num} failed: {extra['error']} (ReqID: {req_id})", 
                                module="image_generator", 
                                details=extra
                            )
                            
                        ps_cb.update_project(pid, updates)
                finally:
                    db_cb.close()
            except Exception as e:
                logger.error(f"Status callback failed: {e}")

        try:
            # Build Reference Map
            # Map shot_number -> [list of image paths]
            project_data = ps_w.get_project(pid)
            characters = project_data.characters or []
            scenes = project_data.scenes or []
            storyboard = project_data.storyboard or {}
            shots = storyboard.get("shots", [])
            
            # Map name to image path
            char_map = {c.get("name"): c.get("image_path") for c in characters if c.get("name") and c.get("image_path")}
            
            # Enhanced scene map: name -> path AND location -> path
            scene_map = {}
            for s in scenes:
                path = s.get("image_path")
                if not path: continue
                if s.get("name"): scene_map[s.get("name")] = path
                # Also map location if present, to catch cases where prompt mentions location instead of name
                if s.get("location"): scene_map[s.get("location")] = path
            
            reference_map = {}
            for shot in shots:
                s_num = shot.get("shot_number")
                if not s_num: continue
                
                # Get prompt text for scanning
                shot_prompt_text = ""
                # Try to find corresponding prompt
                # image_prompts is available in this scope
                p_obj = next((p for p in image_prompts if p.get("shot_number") == s_num), None)
                if p_obj:
                    shot_prompt_text = p_obj.get("positive_prompt", "")

                refs = []
                # 1. Check all characters
                for c_name, c_path in char_map.items():
                    # Check exact match in 'character' field
                    if shot.get("character") == c_name:
                        if c_path not in refs: refs.append(c_path)
                    # Check mention in prompt (priority), description or dialogue
                    elif (c_name in shot_prompt_text) or (c_name in shot.get("description", "")) or (c_name in shot.get("dialogue", "")):
                        if c_path not in refs: refs.append(c_path)
                
                # 2. Check scene
                s_name = shot.get("scene")
                
                # If s_name is empty, try to scan
                if not s_name:
                     for sc_name in scene_map.keys():
                         if (sc_name in shot_prompt_text) or (sc_name in shot.get("description", "")) or (sc_name in shot.get("dialogue", "")):
                             s_name = sc_name
                             break

                if s_name and s_name in scene_map:
                    if scene_map[s_name] not in refs: refs.append(scene_map[s_name])
                
                if refs:
                    reference_map[s_num] = refs
                    logger.info(f"Shot {s_num} will use {len(refs)} reference images: {refs}")
            
            shot_images, usage = image_gen.generate_shot_images(
                image_prompts, 
                pid, 
                image_count,
                ratio=ratio,
                resolution=resolution,
                style=visual_style,
                on_status_update=status_callback,
                reference_map=reference_map
            )
            
            # Fetch latest project state to preserve history from callbacks or previous runs
            project = ps_w.get_project(pid)
            meta = dict(project.topic_meta or {})
            current_shot_images = dict(meta.get("shot_images") or {})
            current_image_paths = list(project.image_paths or [])
            
            # Ensure current_image_paths matches prompts length
            while len(current_image_paths) < len(image_prompts):
                current_image_paths.append(None)

            # Merge new results
            for s_num, paths in shot_images.items():
                s_key = str(s_num)
                if s_key not in current_shot_images:
                    current_shot_images[s_key] = []
                for p in paths:
                    if p not in current_shot_images[s_key]:
                        current_shot_images[s_key].append(p)
                
                # Update current selection to the latest generated image
                # Assuming prompts are ordered by shot_number or index corresponds
                # Find index for this shot_number
                for idx, prompt in enumerate(image_prompts):
                    if prompt.get("shot_number", idx+1) == s_num:
                        if paths:
                            current_image_paths[idx] = paths[-1]
                        break
            
            ps_w.update_project(pid, {
                "image_paths": current_image_paths,
                "topic_meta": {**meta, "shot_images": current_shot_images},
                "current_step": 6
            })
            
            # Update usage stats
            total_gen_images = sum(len(paths) for paths in shot_images.values())
            ps_w.add_usage(pid, images=total_gen_images)
            
            ps_w.update_step(pid, 5, {"status": "completed", "token_usage": usage})
            return {"image_paths": current_image_paths, "shot_images": shot_images}, usage
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "image_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _upload_shot_image(request):
    pid = request.match_info["pid"]
    shot_number = int(request.match_info["shot_number"])
    
    # Check if multipart
    if not request.content_type.startswith("multipart/"):
        return web.json_response({"error": "multipart/form-data required"}, status=400)
        
    reader = await request.multipart()
    field = await reader.next()
    
    if not field or field.name != "file":
        return web.json_response({"error": "file field required"}, status=400)
        
    filename = field.filename
    if not filename:
        import time
        filename = f"upload_{int(time.time())}.png"
        
    # Generate standardized filename
    import time
    import os
    timestamp = int(time.time() * 1000)
    # Determine extension
    ext = os.path.splitext(filename)[1]
    if not ext:
        ext = ".png" # Default
    
    std_filename = f"shot_{shot_number:03d}_upload_{timestamp}{ext}"
    
    # Save path
    project_root = Path(__file__).parent.parent.parent
    data_dir = config_loader.get("app.data_dir", "./data/aigc")
    if data_dir.startswith("./"):
        data_dir = project_root / data_dir[2:]
    else:
        data_dir = Path(data_dir)
        
    project_dir = data_dir / pid / "images"
    project_dir.mkdir(parents=True, exist_ok=True)
    
    image_path = project_dir / std_filename
    
    try:
        with open(image_path, "wb") as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                f.write(chunk)
        logger.info(f"Uploaded image saved to {image_path}")
        
        # Upload to TOS
        final_url = None
        if config_loader.get("tos.enable"):
            bucket = config_loader.get("tos.bucket_name")
            bucket_dir = config_loader.get("tos.bucket_directory", "")
            if bucket:
                if bucket_dir and not bucket_dir.endswith('/'):
                    bucket_dir += '/'
                
                key = f"{bucket_dir}{pid}/images/{std_filename}"
                try:
                    with open(image_path, 'rb') as f:
                        final_url = tos_client.upload_content(bucket, key, f.read())
                    logger.info(f"Uploaded to TOS: {final_url}")
                except Exception as e:
                    logger.error(f"TOS upload failed: {e}")
                    # If TOS mandatory, maybe fail? But let's allow local for now or fail if strict.
                    # Current logic in generation is mandatory.
                    if not final_url:
                         return web.json_response({"error": f"TOS upload failed: {str(e)}"}, status=500)

        # Update Project
        db = next(get_db())
        ps = ProjectService(db)
        try:
            project = ps.get_project(pid)
            if not project:
                return web.json_response({"error": "project not found"}, status=404)
                
            meta = dict(project.topic_meta or {})
            shot_images = dict(meta.get("shot_images") or {})
            shot_num_str = str(shot_number)
            
            if shot_num_str not in shot_images:
                shot_images[shot_num_str] = []
            
            # Use TOS URL if available, else local path (but usually TOS is required for frontend access if not proxied)
            # Frontend uses normalizePath which handles both.
            # But standard is TOS url if uploaded.
            stored_path = final_url if final_url else str(image_path)
            
            shot_images[shot_num_str].append(stored_path)
            
            # Update current image path
            current_image_paths = list(project.image_paths or [])
            # Ensure size
            image_prompts = project.image_prompts or []
            while len(current_image_paths) < len(image_prompts):
                current_image_paths.append(None)
                
            if 0 < shot_number <= len(current_image_paths):
                current_image_paths[shot_number-1] = stored_path
                
            meta["shot_images"] = shot_images
            # Mark as completed manually since we have an image
            meta[f"shot_status_image_{shot_number}"] = "completed"
            
            ps.update_project(pid, {
                "topic_meta": meta,
                "image_paths": current_image_paths
            })
            
            return web.json_response({"status": "ok", "path": stored_path})
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return web.json_response({"error": str(e)}, status=500)


async def _select_shot_image(request):
    pid = request.match_info["pid"]
    shot_number = int(request.match_info["shot_number"])
    data = await request.json()
    path = data.get("path")
    
    if not path:
        return web.json_response({"error": "path required"}, status=400)
        
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        current_image_paths = list(project.image_paths or [])
        # Ensure size
        image_prompts = project.image_prompts or []
        while len(current_image_paths) < len(image_prompts):
            current_image_paths.append(None)
            
        if 0 < shot_number <= len(current_image_paths):
            current_image_paths[shot_number-1] = path
            ps.update_project(pid, {"image_paths": current_image_paths})
            return web.json_response({"status": "ok"})
        else:
             return web.json_response({"error": "shot number out of range"}, status=400)
    finally:
        db.close()

async def _generate_single_shot_image(request):
    pid = request.match_info["pid"]
    shot_number = int(request.match_info["shot_number"])
    data = await request.json()
    image_count = int(data.get("image_count", 1))
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        
        image_prompts = copy.deepcopy(project.image_prompts or [])
        target_prompt = next((p for p in image_prompts if p.get("shot_number") == shot_number), None)
        if not target_prompt:
            if 0 < shot_number <= len(image_prompts):
                target_prompt = image_prompts[shot_number-1]
        
        if not target_prompt:
            return web.json_response({"error": "prompt not found"}, status=404)
            
        new_prompt_text = data.get("prompt")
        if new_prompt_text:
            target_prompt["positive_prompt"] = new_prompt_text
            ps.update_project(pid, {"image_prompts": image_prompts})
            
        meta = project.topic_meta or {}
        ratio = meta.get("aspect_ratio", "16:9")
        resolution = meta.get("resolution", "1080p")
        visual_style = meta.get("visual_style", "真人")
    finally:
        db.close()
        
    def status_callback(key, value, extra=None):
        try:
            # Create a new session for thread safety
            db_cb = next(get_db())
            ps_cb = ProjectService(db_cb)
            try:
                project = ps_cb.get_project(pid)
                if project:
                    meta = dict(project.topic_meta or {})
                    meta[key] = value
                    
                    updates = {"topic_meta": meta}
                    
                    if extra and "path" in extra and "shot_number" in extra:
                        shot_images = dict(meta.get("shot_images") or {})
                        shot_num = str(extra["shot_number"])
                        if shot_num not in shot_images:
                            shot_images[shot_num] = []
                        # Append if not exists
                        if extra["path"] not in shot_images[shot_num]:
                            shot_images[shot_num].append(extra["path"])
                        meta["shot_images"] = shot_images
                        updates["topic_meta"] = meta
                    
                    # Handle error detail
                    if extra and "error" in extra:
                        # Extract shot number if available
                        shot_num = str(extra.get("shot_number", "unknown"))
                        meta[f"shot_error_image_{shot_num}"] = extra["error"]
                        updates["topic_meta"] = meta
                        
                        # Log to DB
                        ls_cb = LogService(db_cb)
                        ls_cb.log(pid, None, "ERROR", f"Shot {shot_num} failed: {extra['error']}", module="image_generator", details=extra)
                        
                    ps_cb.update_project(pid, updates)
            finally:
                db_cb.close()
        except Exception as e:
            logger.error(f"Status callback failed: {e}")

    # Explicitly set status to processing before starting (optional but good for immediate feedback)
    # Actually callback inside generate_shot_images does this, but it runs in thread.
    # To be instant, we can do it here, but let's rely on callback for now to avoid complexity.

    # Build Reference Map for Single Shot
    db = next(get_db())
    ps = ProjectService(db)
    reference_map = {}
    try:
        project_data = ps.get_project(pid)
        characters = project_data.characters or []
        scenes = project_data.scenes or []
        storyboard = project_data.storyboard or {}
        shots = storyboard.get("shots", [])
        
        target_shot = next((s for s in shots if s.get("shot_number") == shot_number), None)
        
        if target_shot:
            char_map = {c.get("name"): c.get("image_path") for c in characters if c.get("name") and c.get("image_path")}
            
            # Enhanced scene map: name -> path AND location -> path
            scene_map = {}
            for s in scenes:
                path = s.get("image_path")
                if not path: continue
                if s.get("name"): scene_map[s.get("name")] = path
                if s.get("location"): scene_map[s.get("location")] = path
            
            # Get prompt text
            shot_prompt_text = ""
            if target_prompt:
                shot_prompt_text = target_prompt.get("positive_prompt", "")

            refs = []
            # 1. Check all characters
            for c_name, c_path in char_map.items():
                if target_shot.get("character") == c_name:
                    if c_path not in refs: refs.append(c_path)
                elif (c_name in shot_prompt_text) or (c_name in target_shot.get("description", "")) or (c_name in target_shot.get("dialogue", "")):
                    if c_path not in refs: refs.append(c_path)
            
            # 2. Check scene
            s_name = target_shot.get("scene")
            if not s_name:
                 for sc_name in scene_map.keys():
                     if (sc_name in shot_prompt_text) or (sc_name in target_shot.get("description", "")) or (sc_name in target_shot.get("dialogue", "")):
                         s_name = sc_name
                         break

            if s_name and s_name in scene_map:
                if scene_map[s_name] not in refs: refs.append(scene_map[s_name])
            
            # Additional safety: if multiple scenes matched by location/alias, add them too?
            # Current logic: `scene_map` keys are name OR location.
            # If s_name matched "青云观后山" (location), `scene_map["青云观后山"]` returns path.
            # If s_name matched "青云观" (name), `scene_map["青云观"]` returns path.
            # If s_name is None, we scan.
            # The issue might be that `scene_map` overwrites keys if multiple scenes share location? 
            # Or maybe we need to be more aggressive scanning all keys in scene_map?
            
            # Let's scan ALL scene keys in prompt/desc/dialogue regardless of s_name
            # Because sometimes s_name is "Scene 1" (generic) but prompt mentions specific location.
            for sc_key, sc_path in scene_map.items():
                if (sc_key in shot_prompt_text) or (sc_key in target_shot.get("description", "")) or (sc_key in target_shot.get("dialogue", "")):
                    if sc_path not in refs: 
                        refs.append(sc_path)
                        logger.info(f"Matched scene/location '{sc_key}' in text")
            
            if refs:
                reference_map[shot_number] = refs
                logger.info(f"Shot {shot_number} will use {len(refs)} reference images: {refs}")
    finally:
        db.close()

    new_shot_images, usage = await _run_blocking(
        image_gen.generate_shot_images, 
        [target_prompt], 
        pid, 
        image_count,
        ratio,
        resolution,
        visual_style,
        status_callback,
        "images",
        reference_map
    )
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        # Refresh meta
        meta = project.topic_meta or {}
        current_shot_images = dict(meta.get("shot_images") or {})
        current_image_paths = list(project.image_paths or [])
        
        while len(current_image_paths) < len(image_prompts):
            current_image_paths.append(None)

        # Ensure new images are in shot_images (in case callback missed or we want to double check)
        # Also update current_image_paths
        success = False
        if shot_number in new_shot_images:
            shot_num_str = str(shot_number)
            if shot_num_str not in current_shot_images:
                current_shot_images[shot_num_str] = []
            
            # Merge new images
            if new_shot_images[shot_number]:
                success = True
                for path in new_shot_images[shot_number]:
                    if path not in current_shot_images[shot_num_str]:
                        current_shot_images[shot_num_str].append(path)
            
                # Update current path to the latest one
                if 0 < shot_number <= len(current_image_paths):
                    current_image_paths[shot_number-1] = new_shot_images[shot_number][-1] # Use last generated
                
        # Update status explicitly based on success
        if success:
            meta[f"shot_status_image_{shot_number}"] = "completed"
        else:
            meta[f"shot_status_image_{shot_number}"] = "failed"
                
        ps.update_project(pid, {
            "image_paths": current_image_paths,
            "topic_meta": {**meta, "shot_images": current_shot_images}
        })
        
        # Update usage stats
        generated_count = len(new_shot_images.get(shot_number, []))
        ps.add_usage(pid, images=generated_count)
    finally:
        db.close()
    
    if success:
        return web.json_response({"status": "ok", "shot_images": new_shot_images.get(shot_number, []), "usage": usage})
    else:
        return web.json_response({"error": "generation failed", "usage": usage}, status=500)


async def _update_image_selection(request):
    pid = request.match_info["pid"]
    data = await request.json()
    shot_number = int(data.get("shot_number"))
    image_path = data.get("image_path")

    if not shot_number or not image_path:
        return web.json_response({"error": "shot_number and image_path required"}, status=400)

    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        image_paths = list(project.image_paths or [])
        while len(image_paths) < shot_number:
            image_paths.append(None)
            
        image_paths[shot_number-1] = image_path
        ps.update_project(pid, {"image_paths": image_paths})
        
        return web.json_response({"status": "ok"})
    finally:
        db.close()


async def _generate_videos(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
        image_paths = project.image_paths or []
        video_prompts = project.video_prompts or []
        storyboard = project.storyboard or {}
    finally:
        db.close()
    
    if not image_paths or not video_prompts:
        return web.json_response({"error": "resources missing"}, status=400)
        
    # Extract resolution and ratio from project meta
    meta = project.topic_meta or {}
    ratio = meta.get("aspect_ratio", "16:9")
    resolution = meta.get("resolution", "1080p")

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        
        def status_callback(key, value, extra=None):
            try:
                db_cb = next(get_db())
                ps_cb = ProjectService(db_cb)
                try:
                    project = ps_cb.get_project(pid)
                    if project:
                        meta = dict(project.topic_meta or {})
                        meta[key] = value
                        updates = {"topic_meta": meta}
                        
                        if extra and "path" in extra and "index" in extra:
                            current_paths = list(project.video_paths or [])
                            idx = extra["index"]
                            while len(current_paths) <= idx:
                                current_paths.append(None)
                            current_paths[idx] = extra["path"]
                            updates["video_paths"] = current_paths
                            
                        # Handle error logging
                        if extra and "error" in extra:
                            shot_num = extra.get("shot_number", "unknown")
                            err_msg = extra.get("error", "Unknown error")
                            req_id = extra.get("request_id", "unknown")
                            
                            ls_cb = LogService(db_cb)
                            ls_cb.log(
                                pid, 
                                None, 
                                "ERROR", 
                                f"Shot {shot_num} video failed: {err_msg} (ReqID: {req_id})", 
                                module="video_generator", 
                                details=extra
                            )
                            
                        ps_cb.update_project(pid, updates)
                finally:
                    db_cb.close()
            except Exception as e:
                logger.error(f"Status callback failed: {e}")

        try:
            video_paths, usage = video_gen.generate_shot_videos(
                image_paths, 
                video_prompts, 
                storyboard, 
                pid,
                on_status_update=status_callback,
                resolution=resolution,
                ratio=ratio
            )
            # Fixed indentation
            ps_w.update_project(pid, {"video_paths": video_paths, "current_step": 5})
            
            # Update usage stats
            total_videos = 0
            total_duration = 0.0
            shots = storyboard.get("shots", [])
            for i, path in enumerate(video_paths):
                if path:
                    total_videos += 1
                    if i < len(shots):
                        total_duration += float(shots[i].get("duration", 5))
                    else:
                        total_duration += 5.0
            ps_w.add_usage(pid, videos=total_videos, duration=total_duration)
            
            ps_w.update_step(pid, 4, {"status": "completed", "token_usage": usage})
            return {"video_paths": video_paths}, usage
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "video_generation", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _generate_single_shot_video(request):
    pid = request.match_info["pid"]
    shot_number = int(request.match_info["shot_number"])
    data = await request.json()
    new_prompt_text = data.get("video_prompt")
    new_image_path = data.get("image_path")
    
    db = next(get_db())
    ps = ProjectService(db)
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        video_prompts = copy.deepcopy(project.video_prompts or [])
        target_prompt = next((p for p in video_prompts if p.get("shot_number") == shot_number), None)
        
        if not target_prompt:
            if 0 < shot_number <= len(video_prompts):
                target_prompt = video_prompts[shot_number-1]
                
        if target_prompt and new_prompt_text is not None:
            target_prompt["video_prompt"] = new_prompt_text
            ps.update_project(pid, {"video_prompts": video_prompts})
            
        image_paths = project.image_paths or []
        while len(image_paths) < shot_number:
            image_paths.append(None)
            
        if new_image_path:
            image_paths[shot_number-1] = new_image_path
            ps.update_project(pid, {"image_paths": image_paths})
            
        image_path = image_paths[shot_number-1] if 0 < shot_number <= len(image_paths) else None
        
        storyboard = project.storyboard or {}
        shots = storyboard.get("shots", [])
        duration = 5
        if 0 < shot_number <= len(shots):
            duration = float(shots[shot_number-1].get("duration", 5))
            
        # Extract meta
        meta = dict(project.topic_meta or {})
        ratio = meta.get("aspect_ratio", "16:9")
        resolution = meta.get("resolution", "1080p")
        
        # Mark as processing
        meta[f"shot_status_video_{shot_number}"] = "processing"
        ps.update_project(pid, {"topic_meta": meta})
        
    finally:
        db.close()

    if not image_path:
        return web.json_response({"error": "image path missing"}, status=400)

    params = {
        "shot_number": shot_number,
        "image_path": image_path,
        "video_prompt": target_prompt.get("video_prompt", "") if target_prompt else "",
        "duration": duration,
        "resolution": resolution,
        "ratio": ratio
    }
    
    # Create parent task
    db = next(get_db())
    ts = TaskService(db)
    task = ts.create_task(pid, "video_regeneration")
    task_id = task.id
    db.close()
    
    def submission_worker():
        db_w = next(get_db())
        ts_w = TaskService(db_w)
        try:
            ts_w.update_task(task_id, status="running", progress=0)
            
            # Submit single task
            submission_result = video_gen.submit_single_video_task(
                params,
                pid
            )
            
            if "error" in submission_result:
                raise Exception(submission_result["error"])
                
            volc_task_id = submission_result["task_id"]
            
            # Create VideoTask record
            vt = VideoTask(
                id=generate_uuid(),
                project_id=pid,
                task_id=task_id,
                shot_number=shot_number,
                volc_task_id=volc_task_id,
                status="submitted"
            )
            db_w.add(vt)
            db_w.commit()
            
        except Exception as e:
            logger.error(f"Single video submission failed: {e}")
            ts_w.update_task(task_id, status="failed", error=str(e))
            # Also update meta to failed
            ps_w = ProjectService(db_w)
            project = ps_w.get_project(pid)
            if project:
                meta = dict(project.topic_meta or {})
                meta[f"shot_status_video_{shot_number}"] = "failed"
                meta[f"shot_error_video_{shot_number}"] = str(e)
                ps_w.update_project(pid, {"topic_meta": meta})
        finally:
            db_w.close()

    threading.Thread(target=submission_worker).start()
    return web.json_response({"status": "processing", "task_id": task_id})


async def _merge_videos(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    from sqlalchemy import desc
    try:
        project = ps.get_project(pid)
        if not project:
            return web.json_response({"error": "not found"}, status=404)
            
        # Re-sync video_paths from latest VideoTasks to ensure we use the latest generation
        storyboard = project.storyboard or {}
        shots = storyboard.get("shots", [])
        num_shots = len(shots)
        
        current_video_paths = list(project.video_paths or [])
        # Ensure list size matches shots
        while len(current_video_paths) < num_shots:
            current_video_paths.append(None)
            
        updated = False
        for i in range(num_shots):
            shot_number = i + 1
            # Find latest completed task for this shot
            latest_task = db.query(VideoTask).filter(
                VideoTask.project_id == pid,
                VideoTask.shot_number == shot_number,
                VideoTask.status == "completed"
            ).order_by(desc(VideoTask.created_at)).first()
            
            if latest_task and latest_task.video_url:
                if current_video_paths[i] != latest_task.video_url:
                    logger.info(f"Syncing video path for shot {shot_number}: {current_video_paths[i]} -> {latest_task.video_url}")
                    current_video_paths[i] = latest_task.video_url
                    updated = True
        
        if updated:
            ps.update_project(pid, {"video_paths": current_video_paths})
            # Update local var
            video_paths = current_video_paths
        else:
            video_paths = project.video_paths or []
            
    finally:
        db.close()
        
    if not video_paths:
        return web.json_response({"error": "no videos"}, status=400)

    def worker():
        db_w = next(get_db())
        ps_w = ProjectService(db_w)
        try:
            # Log start
            logger.info(f"Starting video merge for project {pid} with {len(video_paths)} clips")
            
            final_video = merger.merge_videos(video_paths, pid)
            
            if not final_video:
                raise Exception("Merge returned no result")
                
            ps_w.update_project(pid, {"final_video": final_video, "status": "completed"})
            ps_w.update_step(pid, 7, {"status": "completed"})
            
            logger.info(f"Video merge completed for project {pid}: {final_video}")
            return {"final_video": final_video}
        except Exception as e:
            logger.error(f"Video merge failed for project {pid}: {e}")
            raise e
        finally:
            db_w.close()

    task_id = await _start_background_task(pid, "video_merge", worker)
    return web.json_response({"status": "processing", "task_id": task_id})


async def _list_projects(request):
    db = next(get_db())
    ps = ProjectService(db)
    try:
        # Parse query params
        filters = {}
        for key in ["name", "status", "input_type", "platform", "resolution", "aspect_ratio"]:
            val = request.query.get(key)
            if val:
                filters[key] = val
                
        projects = ps.get_all_projects(filters)
        simple_list = []
        for p in projects:
            simple_list.append({
                "project_id": p.id,
                "project_name": p.name,
                "status": p.status,
                "created_at": p.created_at.isoformat() if p.created_at else None
            })
        return web.json_response({"projects": simple_list})
    finally:
        db.close()


async def _delete_project(request):
    pid = request.match_info["pid"]
    db = next(get_db())
    ps = ProjectService(db)
    try:
        success = ps.delete_project(pid)
        if not success:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response({"status": "ok"})
    finally:
        db.close()


async def _get_config(request):
    import copy
    conf = copy.deepcopy(config_loader.config)
    
    # 递归脱敏或针对 platforms 下的所有平台脱敏
    if "platforms" in conf:
        for platform_name, p_conf in conf["platforms"].items():
            if isinstance(p_conf, dict):
                if "ark_api_key" in p_conf: p_conf["ark_api_key"] = "******"
                if "access_key" in p_conf: p_conf["access_key"] = "******"
                if "secret_key" in p_conf: p_conf["secret_key"] = "******"
    
    # 兼容旧版脱敏 (如果 _migrate_config 没有删除根节点，或者为了保险)
    if conf.get("volcengine"):
        if conf["volcengine"].get("ark_api_key"):
            conf["volcengine"]["ark_api_key"] = "******"
        if conf["volcengine"].get("access_key"):
            conf["volcengine"]["access_key"] = "******"
        if conf["volcengine"].get("secret_key"):
            conf["volcengine"]["secret_key"] = "******"
            
    return web.json_response(conf)


async def _update_config(request):
    data = await request.json()
    tos_updated = False
    for key, value in data.items():
        # Skip masked values
        if value == "******":
            continue
            
        # 检测 TOS 更新 (支持新旧 Key)
        if key.startswith("tos.") or ".tos." in key:
            tos_updated = True
            
        config_loader.update_config(key, value)
    config_loader.save_config()
    
    if tos_updated:
        # Re-init client and configure policy in background
        def configure_tos():
            try:
                # Re-initialize TOS client with new config
                tos_client.__init__()
                if config_loader.get("tos.enable"):
                    bucket = config_loader.get("tos.bucket_name")
                    directory = config_loader.get("tos.bucket_directory", "")
                    if bucket:
                        logger.info("Configuring TOS public access policy...")
                        tos_client.configure_directory_public_access(bucket, directory)
            except Exception as e:
                logger.error(f"Failed to configure TOS: {e}")
                
        threading.Thread(target=configure_tos, daemon=True).start()
        
    return web.json_response({"status": "ok"})


async def _get_prompts(request):
    return web.json_response(config_loader.prompts)


async def _update_prompts(request):
    data = await request.json()
    for key, value in data.items():
        config_loader.update_prompt(key, value)
    config_loader.save_prompts()
    return web.json_response({"status": "ok"})


async def _reload_config_api(request):
    """API to manually reload configuration from disk"""
    try:
        logger.info("Manual config reload triggered via API")
        
        # 1. Reload ConfigLoader (from file)
        config_loader.load_config()
        config_loader.load_prompts()
        
        # 2. Reload VEADKClient
        from src.models.veadk_client import veadk_client
        veadk_client.reload_config()
        
        # 3. Reload Generators
        # Using global instances defined in this module
        image_gen.reload_config()
        video_gen.reload_config()
        prompt_gen.reload_config()
        
        # 4. Check TOS update logic (re-init client)
        def configure_tos():
            try:
                # Re-initialize TOS client with new config
                # Re-calling __init__ on existing instance
                tos_client.__init__()
                if config_loader.get("tos.enable"):
                    bucket = config_loader.get("tos.bucket_name")
                    directory = config_loader.get("tos.bucket_directory", "")
                    if bucket:
                        logger.info("Configuring TOS public access policy...")
                        tos_client.configure_directory_public_access(bucket, directory)
            except Exception as e:
                logger.error(f"Failed to configure TOS: {e}")
                
        threading.Thread(target=configure_tos, daemon=True).start()

        return web.json_response({"status": "ok", "message": "Configuration reloaded successfully"})
    except Exception as e:
        logger.error(f"Reload config failed: {e}")
        return web.json_response({"error": str(e)}, status=500)



async def _list_buckets(request):
    """List available TOS buckets"""
    # Support explicit credentials via POST
    ak = None
    sk = None
    endpoint = None
    region = None
    platform = None
    
    if request.method == 'POST':
        try:
            data = await request.json()
            ak = data.get("access_key")
            sk = data.get("secret_key")
            endpoint = data.get("endpoint")
            region = data.get("region")
            platform = data.get("platform")
        except:
            pass
            
    # Resolve masked or missing keys if platform is provided
    if platform:
        from src.utils.config_loader import config_loader
        base = f"platforms.{platform}"
        
        if not ak or ak == "******":
            ak = config_loader.get(f"{base}.access_key")
            # Also check legacy/volcengine specific if not found? 
            # No, config_loader handles structure.
            
        if not sk or sk == "******":
            sk = config_loader.get(f"{base}.secret_key")
            
        # If endpoint/region not provided, try load from config
        if not endpoint:
            endpoint = config_loader.get(f"{base}.tos.endpoint")
        if not region:
            region = config_loader.get(f"{base}.tos.region")

    # If using masked values (and no platform resolution worked), fallback to None
    if ak == "******": ak = None
    if sk == "******": sk = None
            
    buckets = await _run_blocking(tos_client.list_buckets, ak, sk, endpoint, region)
    return web.json_response({"buckets": buckets})


async def _list_directories(request):
    """List directories in a bucket"""
    bucket_name = request.match_info["bucket"]
    dirs = await _run_blocking(tos_client.list_directories, bucket_name)
    return web.json_response({"directories": dirs})


async def _create_directory(request):
    """Create directory in a bucket"""
    bucket_name = request.match_info["bucket"]
    data = await request.json()
    dir_name = data.get("directory")
    if not dir_name:
        return web.json_response({"error": "directory name required"}, status=400)
        
    success = await _run_blocking(tos_client.create_directory, bucket_name, dir_name)
    if success:
        return web.json_response({"status": "ok"})
    else:
        return web.json_response({"error": "create failed"}, status=500)


async def _tos_proxy(request):
    """Proxy TOS requests to handle private buckets/CORS"""
    url = request.query.get("url")
    if not url:
        return web.json_response({"error": "url required"}, status=400)
    
    # Parse URL
    parsed = tos_client.parse_tos_url(url)
    if not parsed:
        return web.json_response({"error": "invalid tos url"}, status=400)
    
    bucket, key = parsed
    
    try:
        def fetch_object():
            return tos_client.get_object(bucket, key)
            
        obj = await _run_blocking(fetch_object)
        
        # Prepare response
        response = web.StreamResponse()
        
        # Set content type if available
        if getattr(obj, 'content_type', None):
                response.content_type = obj.content_type
        else:
                response.content_type = 'application/octet-stream'
                
        if getattr(obj, 'content_length', None):
            response.content_length = int(obj.content_length)
            
        await response.prepare(request)
        
        # Stream content
        # To avoid "Cannot write to closing transport" error, check if connection is active
        # However, aiohttp handles this mostly. The error usually means client disconnected.
        # We can just ignore the error if write fails.
        
        try:
            while True:
                chunk = obj.read(8192)
                if not chunk:
                    break
                await response.write(chunk)
            await response.write_eof()
        except (ConnectionResetError, web.HTTPException, Exception):
            # Client disconnected or other stream error
            pass
            
        return response
        
    except Exception as e:
        # Only log if it's not a proxy/connection closed error which is common for video seeking
        if "Cannot write to closing transport" not in str(e):
            logger.error(f"Proxy failed: {e}")
        return web.json_response({"error": "proxy failed"}, status=500)


async def _create_app():
    # Validate Mandatory Config at Startup
    tos_bucket = config_loader.get("tos.bucket_name")
    if not tos_bucket:
        logger.error("CRITICAL: TOS Bucket Name is not configured!")
        logger.error("Storage configuration is mandatory. Please configure 'tos.bucket_name' in config.yaml.")
        # We should ideally stop here, but since this is async create_app, raising exception will crash the runner loop.
        # It's better to crash fast so user knows they must config it.
        raise ValueError("TOS Bucket Name (tos.bucket_name) is mandatory but missing.")

    # Increase client_max_size to 100MB (default 1MB)
    app = web.Application(client_max_size=1024*1024*100)
    
    # Add simple logging middleware to debug requests
    @web.middleware
    async def request_logger(request, handler):
        import time
        start_time = time.time()
        # Log request start
        cl = request.headers.get("Content-Length", "unknown")
        logger.info(f"Incoming Request: {request.method} {request.path} | Size: {cl}")
        
        try:
            response = await handler(request)
            duration = (time.time() - start_time) * 1000
            logger.info(f"Request Completed: {request.method} {request.path} | Status: {response.status} | Time: {duration:.2f}ms")
            return response
        except web.HTTPException as ex:
            duration = (time.time() - start_time) * 1000
            logger.info(f"Request Failed (HTTPException): {request.method} {request.path} | Status: {ex.status} | Time: {duration:.2f}ms")
            raise
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"Request Error (Unhandled): {request.method} {request.path} | Error: {e} | Time: {duration:.2f}ms")
            raise

    app.middlewares.append(request_logger)

    app.router.add_get("/", _index)
    app.router.add_get("/health", _health)
    
    # Project APIs
    app.router.add_get("/api/projects", _list_projects)
    app.router.add_post("/api/projects", _create_project)
    app.router.add_get("/api/projects/{pid}", _get_project)
    app.router.add_delete("/api/projects/{pid}", _delete_project)
    
    # Task & Log APIs
    app.router.add_get("/api/tasks/{task_id}", _get_task_status)
    app.router.add_get("/api/projects/{pid}/tasks", _get_project_tasks)
    app.router.add_get("/api/logs", _get_logs_api)

    # Config APIs
    app.router.add_get("/api/config", _get_config)
    app.router.add_post("/api/config", _update_config)
    app.router.add_post("/api/system/reload", _reload_config_api) # Add reload API
    app.router.add_get("/api/buckets", _list_buckets)  # List Buckets
    app.router.add_post("/api/buckets", _list_buckets) # List Buckets (with creds)
    app.router.add_get("/api/buckets/{bucket}/directories", _list_directories) # List Directories
    app.router.add_post("/api/buckets/{bucket}/directories", _create_directory) # Create Directory
    app.router.add_get("/api/proxy/tos", _tos_proxy) # TOS Proxy
    app.router.add_get("/api/prompts", _get_prompts)
    app.router.add_post("/api/prompts", _update_prompts)
    
    # Generation APIs
    app.router.add_post("/api/projects/{pid}/script", _generate_script)
    app.router.add_put("/api/projects/{pid}/script", _update_script)  # Update Script
    app.router.add_post("/api/projects/{pid}/script/optimize", _optimize_script)

    # Character APIs
    app.router.add_post("/api/projects/{pid}/characters", _generate_characters)
    app.router.add_put("/api/projects/{pid}/characters", _update_characters)
    app.router.add_post("/api/projects/{pid}/characters/prompts", _generate_character_prompts)
    app.router.add_put("/api/projects/{pid}/characters/{index}/prompt", _update_single_character_prompt)
    app.router.add_post("/api/projects/{pid}/characters/{index}/prompt/regenerate", _regenerate_single_character_prompt)
    app.router.add_put("/api/projects/{pid}/characters/{index}", _update_single_character)
    app.router.add_post("/api/projects/{pid}/characters/{index}/image/regenerate", _regenerate_single_character_image)
    app.router.add_post("/api/projects/{pid}/characters/images", _generate_character_images)

    # Scene APIs
    app.router.add_post("/api/projects/{pid}/scenes", _generate_scenes)
    app.router.add_put("/api/projects/{pid}/scenes", _update_scenes)
    app.router.add_post("/api/projects/{pid}/scenes/prompts", _generate_scene_prompts)
    app.router.add_put("/api/projects/{pid}/scenes/{index}/prompt", _update_single_scene_prompt)
    app.router.add_post("/api/projects/{pid}/scenes/{index}/prompt/regenerate", _regenerate_single_scene_prompt)
    app.router.add_put("/api/projects/{pid}/scenes/{index}", _update_single_scene)
    app.router.add_post("/api/projects/{pid}/scenes/{index}/image/regenerate", _regenerate_single_scene_image)
    app.router.add_post("/api/projects/{pid}/scenes/images", _generate_scene_images)

    app.router.add_post("/api/projects/{pid}/storyboard", _generate_storyboard)
    app.router.add_put("/api/projects/{pid}/storyboard", _update_storyboard)  # Update Storyboard
    app.router.add_post("/api/projects/{pid}/prompts", _generate_prompts)
    app.router.add_put("/api/projects/{pid}/prompts", _update_prompts_data)  # Update Prompts Data
    app.router.add_put("/api/projects/{pid}/prompts/{shot_number}", _update_single_prompt) # Update Single Prompt
    app.router.add_post("/api/projects/{pid}/prompts/{shot_number}/regenerate", _regenerate_single_prompt) # Regenerate Single Prompt
    app.router.add_post("/api/projects/{pid}/images", _generate_images)
    app.router.add_post("/api/projects/{pid}/images/{shot_number}", _generate_single_shot_image) # Single shot regen
    app.router.add_post("/api/projects/{pid}/images/{shot_number}/upload", _upload_shot_image) # Single shot upload
    app.router.add_post("/api/projects/{pid}/images/{shot_number}/select", _select_shot_image) # Select shot image
    app.router.add_put("/api/projects/{pid}/images/selection", _update_image_selection) # Update image selection
    app.router.add_post("/api/projects/{pid}/videos", _generate_videos)
    app.router.add_post("/api/projects/{pid}/videos/{shot_number}", _generate_single_shot_video) # Single shot video regen
    app.router.add_post("/api/projects/{pid}/merge", _merge_videos)
    
    # Static Files
    if web_dir.exists():
        app.router.add_static("/static", str(web_dir), show_index=True)
    data_dir = project_root / "data"
    if data_dir.exists():
        app.router.add_static("/data", str(data_dir), show_index=False)
    return app


def start_server_in_thread(host: str, port: int):
    def _runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app = loop.run_until_complete(_create_app())
        runner = web.AppRunner(app)
        loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, host, port)
        loop.run_until_complete(site.start())
        logger.info(f"HTTP服务已启动: http://{host}:{port}/")
        try:
            # Log system startup
            db = next(get_db())
            ls = LogService(db)
            ls.log(None, None, "INFO", f"System started at http://{host}:{port}/", module="system")
            db.close()
        except Exception as e:
            logger.error(f"Failed to write startup log: {e}")

        try:
            loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            loop.run_until_complete(runner.cleanup())

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    
    # Start Video Scheduler
    VideoScheduler().start()
    
    return t

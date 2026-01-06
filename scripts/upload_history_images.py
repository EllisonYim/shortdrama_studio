import os
import sys
import asyncio
from pathlib import Path
from loguru import logger

# Add project root to path to allow imports
current_file = Path(__file__).resolve()
project_root = current_file.parents[2]  # short_drama_studio/scripts/xxx.py -> short_drama_studio
sys.path.append(str(project_root))

from short_drama_studio.src.utils.config_loader import config_loader
from short_drama_studio.src.utils.tos_client import tos_client

def upload_history_images():
    """
    Scan local data directory for images and upload them to TOS.
    Maintains the project structure: {bucket_dir}{project_id}/images/{filename}
    """
    # 1. Get Data Directory
    config_data_path = config_loader.get("app.data_dir", "./data/aigc/")
    if Path(config_data_path).is_absolute():
        data_dir = Path(config_data_path)
    else:
        # If relative, it's relative to project root
        data_dir = project_root / "short_drama_studio" / config_data_path
        # Note: In http_server.py, project_root was short_drama_studio (parents[2] of src/server/http.py)
        # Here project_root is 'trae' based on parents[2] of short_drama_studio/scripts/script.py?
        # Let's double check path logic.
        # file: /Users/bytedance/trae/trae/short_drama_studio/scripts/upload_history_images.py
        # parent: .../scripts
        # parent[1]: .../short_drama_studio
        # parent[2]: .../trae
        
        # In http_server: .../short_drama_studio/src/server/http_server.py
        # parents[2]: .../short_drama_studio
        
        # So if we want to match http_server logic:
        # We need the root to be short_drama_studio.
        pass

    # Re-calculate root correctly
    script_dir = Path(__file__).parent
    module_root = script_dir.parent # short_drama_studio
    
    # Adjust sys.path to include the parent of short_drama_studio so we can import as 'short_drama_studio.src...'
    # OR if we run as module.
    # But usually we want to import 'src...' directly if we are inside the package? 
    # The existing code uses relative imports '..utils' or absolute 'src.utils'.
    # If I look at http_server.py: `from src.utils.config_loader import config_loader`
    # This implies `short_drama_studio` is in PYTHONPATH or we are running from `short_drama_studio` dir.
    
    # Let's assume we run this script from `trae` root using `python3 short_drama_studio/scripts/upload_history_images.py`
    # Then `short_drama_studio` is a package.
    
    # Let's fix imports above to match running from root.
    # But for safety, let's just find the data dir relative to this script.
    
    real_data_dir = module_root / "data" / "aigc"
    if not real_data_dir.exists():
        logger.warning(f"Data directory not found at: {real_data_dir}")
        # Try checking config
        if Path(config_data_path).is_absolute():
            real_data_dir = Path(config_data_path)
        else:
            real_data_dir = module_root / config_data_path
            
    logger.info(f"Scanning data directory: {real_data_dir}")
    
    if not real_data_dir.exists():
        logger.error("Data directory does not exist.")
        return

    # 2. Check TOS Config
    if not config_loader.get("tos.enable"):
        logger.error("TOS is not enabled in config.")
        return
        
    bucket = config_loader.get("tos.bucket_name")
    bucket_dir = config_loader.get("tos.bucket_directory", "")
    if bucket_dir and not bucket_dir.endswith('/'):
        bucket_dir += '/'
        
    if not bucket:
        logger.error("Bucket name not configured.")
        return
        
    logger.info(f"Target Bucket: {bucket}")
    logger.info(f"Target Prefix: {bucket_dir}")

    # 3. Configure Public Access for the directory (Project requirement)
    # The requirement said: "Once storage config saved, immediately configure...". 
    # Here we should also ensure it's configured for the history upload.
    logger.info("Configuring directory public access...")
    tos_client.configure_directory_public_access(bucket, bucket_dir)

    # 4. Walk and Upload
    success_count = 0
    fail_count = 0
    skip_count = 0
    
    # Structure: data_dir / {project_id} / images / {filename}
    for project_dir in real_data_dir.iterdir():
        if not project_dir.is_dir():
            continue
            
        project_id = project_dir.name
        images_dir = project_dir / "images"
        
        if not images_dir.exists():
            continue
            
        logger.info(f"Processing project: {project_id}")
        
        for image_file in images_dir.glob("*.png"):
            filename = image_file.name
            key = f"{bucket_dir}{project_id}/images/{filename}"
            
            try:
                # Read content
                with open(image_file, 'rb') as f:
                    content = f.read()
                
                # Check if exists? (TOS doesn't have cheap exists check without HEAD)
                # Just upload.
                
                logger.info(f"Uploading {filename} -> {key}")
                url = tos_client.upload_content(bucket, key, content)
                logger.success(f"Uploaded: {url}")
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to upload {filename}: {e}")
                fail_count += 1

    logger.info(f"Upload completed. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    upload_history_images()

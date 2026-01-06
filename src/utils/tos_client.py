
import tos
from typing import List, Dict, Optional, Tuple
from loguru import logger
from ..utils.config_loader import config_loader

class TosClient:
    def __init__(self):
        # 1. 获取当前平台
        self.platform = config_loader.get("platform", "volcengine")
        
        # 2. 构造配置路径
        base_path = f"platforms.{self.platform}"
        tos_path = f"{base_path}.tos"
        
        # 3. 读取配置
        self.access_key = config_loader.get(f"{base_path}.access_key")
        self.secret_key = config_loader.get(f"{base_path}.secret_key")
        
        self.endpoint = config_loader.get(f"{tos_path}.endpoint", "tos-cn-beijing.volces.com")
        self.region = config_loader.get(f"{tos_path}.region", "cn-beijing")
        self.bucket = config_loader.get(f"{tos_path}.bucket_name")
        self.client = None
        
        if self.access_key and self.secret_key:
            try:
                self.client = tos.TosClientV2(
                    self.access_key,
                    self.secret_key,
                    self.endpoint,
                    self.region
                )
            except Exception as e:
                logger.error(f"Failed to initialize TOS client: {e}")

    def list_buckets(self, ak: str = None, sk: str = None, endpoint: str = None, region: str = None) -> List[Dict[str, str]]:
        """List all available buckets"""
        client_to_use = self.client
        
        # If credentials provided, create temporary client
        if ak and sk and endpoint and region:
            try:
                client_to_use = tos.TosClientV2(ak, sk, endpoint, region)
            except Exception as e:
                logger.error(f"Failed to create temp TOS client: {e}")
                return []

        if not client_to_use:
            return []
        
        try:
            output = client_to_use.list_buckets()
            buckets = []
            for b in output.buckets:
                buckets.append({
                    "name": b.name,
                    "location": b.location,
                    "creation_date": b.creation_date
                })
            return buckets
        except Exception as e:
            logger.error(f"Failed to list buckets: {e}")
            return []

    def check_bucket_access(self, bucket_name: str) -> bool:
        """Check if we can access the bucket (head bucket)"""
        if not self.client:
            return False
        try:
            self.client.head_bucket(bucket_name)
            return True
        except Exception as e:
            logger.error(f"Bucket access check failed: {e}")
            return False

    def list_directories(self, bucket_name: str, prefix: str = "") -> List[str]:
        """List directories (common prefixes) in a bucket"""
        if not self.client:
            return []
        
        try:
            # List objects with delimiter '/' to emulate directories
            output = self.client.list_objects(bucket_name, prefix=prefix, delimiter='/')
            dirs = []
            if output.common_prefixes:
                for p in output.common_prefixes:
                    dirs.append(p.prefix)
            return dirs
        except Exception as e:
            logger.error(f"Failed to list directories: {e}")
            return []

    def create_directory(self, bucket_name: str, directory_name: str) -> bool:
        """Create a directory (empty object ending with /)"""
        if not self.client:
            return False
            
        if not directory_name.endswith('/'):
            directory_name += '/'
            
        try:
            self.client.put_object(bucket_name, directory_name, content=b'')
            return True
        except Exception as e:
            logger.error(f"Failed to create directory: {e}")
            return False

    def upload_content(self, bucket_name: str, key: str, content: bytes, acl: str = 'public-read') -> str:
        """Upload content bytes and return public URL"""
        if not self.client:
            raise Exception("TOS Client not initialized")
            
        try:
            try:
                # Try upload with ACL
                self.client.put_object(bucket_name, key, content=content, acl=acl)
            except Exception as e:
                # If ACL fails, fallback to default (private)
                if "invalid acl type" in str(e).lower() or "not support" in str(e).lower() or "400" in str(e):
                    logger.warning(f"Upload with ACL '{acl}' failed, falling back to default: {e}")
                    self.client.put_object(bucket_name, key, content=content)
                else:
                    raise e
            
            return f"https://{bucket_name}.{self.endpoint}/{key}"
        except Exception as e:
            logger.error(f"Failed to upload content: {e}")
            raise e

    def upload_from_url(self, bucket_name: str, key: str, url: str, acl: str = 'public-read') -> str:
        """Fetch content from URL and upload to TOS (streaming)"""
        if not self.client:
            raise Exception("TOS Client not initialized")
            
        import requests
        try:
            # Attempt 1: With ACL
            try:
                with requests.get(url, stream=True) as r:
                    r.raise_for_status()
                    self.client.put_object(bucket_name, key, content=r.raw, acl=acl)
            except Exception as e:
                # If ACL fails, retry without ACL
                if "invalid acl type" in str(e).lower() or "not support" in str(e).lower() or "400" in str(e):
                    logger.warning(f"Upload from URL with ACL '{acl}' failed, retrying without ACL: {e}")
                    with requests.get(url, stream=True) as r:
                        r.raise_for_status()
                        self.client.put_object(bucket_name, key, content=r.raw)
                else:
                    raise e
            
            return f"https://{bucket_name}.{self.endpoint}/{key}"
        except Exception as e:
            logger.error(f"Failed to upload from URL: {e}")
            raise e

    def get_object(self, bucket_name: str, key: str):
        """Get object from TOS"""
        if not self.client:
            raise Exception("TOS Client not initialized")
        return self.client.get_object(bucket_name, key)

    def parse_tos_url(self, url: str) -> Optional[Tuple[str, str]]:
        """Parse bucket and key from TOS URL"""
        import re
        # Pattern 1: https://{bucket}.{endpoint}/{key}
        pattern1 = r"https?://([^.]+)\.([^/]+)/(.*)"
        match = re.match(pattern1, url)
        if match:
            # Check if group 2 matches our endpoint structure (partially)
            # Actually group 2 is endpoint.
            return match.group(1), match.group(3)
            
        # Pattern 2: https://{endpoint}/{bucket}/{key} (Path style, less common for public URLs but possible)
        # We assume virtual host style as that's what we generate.
        return None

    def get_signed_url(self, bucket_name: str, key: str, expires: int = 3600) -> str:
        """Generate a pre-signed URL for temporary access"""
        if not self.client:
            raise Exception("TOS Client not initialized")
        
        try:
            from tos.enum import HttpMethodType
            out = self.client.pre_signed_url(
                HttpMethodType.Http_Method_Get,
                bucket_name,
                key,
                expires=expires
            )
            return out.signed_url
        except Exception as e:
            logger.error(f"Failed to generate signed URL: {e}")
            raise e

    def configure_directory_public_access(self, bucket_name: str, directory: str) -> bool:
        """Configure public read access for a directory using Bucket Policy"""
        if not self.client:
            return False
            
        try:
            # Ensure directory format
            if directory and not directory.endswith('/'):
                directory += '/'
                
            # Resource path: trn:tos:::bucket/directory/*
            resource = f"trn:tos:::{bucket_name}/{directory}*"
            
            # Policy structure
            policy = {
                "Statement": [
                    {
                        "Sid": "PublicReadForDirectory",
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": ["tos:GetObject"],
                        "Resource": [resource]
                    }
                ]
            }
            
            import json
            policy_json = json.dumps(policy)
            
            logger.info(f"Setting bucket policy for {bucket_name}: {policy_json}")
            self.client.put_bucket_policy(bucket_name, policy=policy_json)
            return True
        except Exception as e:
            logger.error(f"Failed to configure bucket policy: {e}")
            return False

tos_client = TosClient()

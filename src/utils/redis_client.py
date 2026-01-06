import redis
import json
from loguru import logger
from src.utils.config_loader import config_loader

class RedisClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance.client = None
            cls._instance.enabled = False
            cls._instance._init_client()
        return cls._instance
    
    def _init_client(self):
        conf = config_loader.config.get("redis", {})
        self.enabled = conf.get("enable", False)
        
        if self.enabled:
            try:
                self.client = redis.Redis(
                    host=conf.get("host", "localhost"),
                    port=conf.get("port", 6379),
                    db=conf.get("db", 0),
                    password=conf.get("password") or None,
                    decode_responses=True, # Auto decode to utf-8 string
                    socket_timeout=1
                )
                self.client.ping()
                logger.info("Redis connected successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                self.enabled = False
                self.client = None

    def get(self, key):
        if not self.enabled or not self.client:
            return None
        try:
            return self.client.get(key)
        except Exception as e:
            logger.warning(f"Redis get failed: {e}")
            return None

    def set(self, key, value, ex=None):
        if not self.enabled or not self.client:
            return False
        try:
            return self.client.set(key, value, ex=ex)
        except Exception as e:
            logger.warning(f"Redis set failed: {e}")
            return False

    def delete(self, key):
        if not self.enabled or not self.client:
            return False
        try:
            return self.client.delete(key)
        except Exception as e:
            logger.warning(f"Redis delete failed: {e}")
            return False

    def hset(self, name, mapping=None, **kwargs):
        if not self.enabled or not self.client:
            return False
        try:
            return self.client.hset(name, mapping=mapping, **kwargs)
        except Exception as e:
            logger.warning(f"Redis hset failed: {e}")
            return False
            
    def hgetall(self, name):
        if not self.enabled or not self.client:
            return {}
        try:
            return self.client.hgetall(name)
        except Exception as e:
            logger.warning(f"Redis hgetall failed: {e}")
            return {}
            
    def expire(self, name, time):
        if not self.enabled or not self.client:
            return False
        try:
            return self.client.expire(name, time)
        except Exception as e:
            logger.warning(f"Redis expire failed: {e}")
            return False

redis_client = RedisClient()

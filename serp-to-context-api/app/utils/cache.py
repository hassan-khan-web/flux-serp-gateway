import os
import hashlib
import json
from typing import Optional
import redis
from app.utils.logger import logger

class CacheService:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.client = redis.from_url(self.redis_url, decode_responses=True)
            self.ttl = 6 * 60 * 60  # 6 hours
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def _generate_key(self, query: str, region: Optional[str] = None, language: Optional[str] = None) -> str:
        key_content = f"{query}:{region}:{language}"
        return hashlib.sha256(key_content.encode()).hexdigest()

    def get(self, query: str, region: Optional[str] = None, language: Optional[str] = None) -> Optional[dict]:
        if not self.client:
            return None
        
        try:
            key = self._generate_key(query, region, language)
            cached_data = self.client.get(key)
            if cached_data:
                logger.info(f"Cache hit for query: {query}")
                return json.loads(cached_data)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set(self, query: str, data: dict, region: Optional[str] = None, language: Optional[str] = None):
        if not self.client:
            return

        try:
            key = self._generate_key(query, region, language)
            self.client.setex(key, self.ttl, json.dumps(data))
            logger.info(f"Cache set for query: {query}")
        except Exception as e:
            logger.error(f"Cache set error: {e}")

cache = CacheService()

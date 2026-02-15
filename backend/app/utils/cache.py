import os
import hashlib
import json
from typing import Optional, Dict, Any
import redis
from app.utils.logger import logger

class CacheService:
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.client: Optional[redis.Redis] = redis.from_url(self.redis_url, decode_responses=True)
            self.ttl = 6 * 60 * 60
            logger.info("Connected to Redis at %s", self.redis_url)
        except Exception as e:
            logger.error("Failed to connect to Redis: %s", e)
            self.client = None

    def _generate_key(self, query: str, region: Optional[str] = None, language: Optional[str] = None, limit: Optional[int] = 10) -> str:
        key_content = f"{query}:{region}:{language}:{limit}"
        return hashlib.sha256(key_content.encode()).hexdigest()

    def get(self, query: str, region: Optional[str] = None, language: Optional[str] = None, limit: Optional[int] = 10) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        try:
            key = self._generate_key(query, region, language, limit)
            cached_data = self.client.get(key)
            if cached_data and isinstance(cached_data, str):
                logger.info("Cache hit for query: %s", query)
                data = json.loads(cached_data)
                if isinstance(data, dict):
                    return data
            return None
        except Exception as e:
            logger.error("Cache get error: %s", e)
            return None

    def set(self, query: str, data: dict, region: Optional[str] = None, language: Optional[str] = None, limit: Optional[int] = 10):
        if not self.client:
            return

        try:
            key = self._generate_key(query, region, language, limit)
            self.client.setex(key, self.ttl, json.dumps(data))
            logger.info("Cache set for query: %s", query)
        except Exception as e:
            logger.error("Cache set error: %s", e)

cache = CacheService()

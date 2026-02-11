from typing import List, Optional
from app.utils.logger import logger

class EmbeddingsService:
    def __init__(self):
        self.model = None
        self.model_name = "all-MiniLM-L6-v2"
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}...")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully.")
        except ImportError:
            logger.warning("sentence-transformers not installed. Vector output will be disabled.")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")

    def generate(self, texts: List[str]) -> List[List[float]]:
        if not self.model:
            logger.error("Embedding model is not loaded.")
            return []
        
        try:
            embeddings = self.model.encode(texts)
            if hasattr(embeddings, "tolist"):
                result = embeddings.tolist()
                if isinstance(result, list):
                    return result
            return []
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

embeddings_service = EmbeddingsService()

from typing import List, Optional
from app.utils.logger import logger

class EmbeddingsService:
    def __init__(self):
        self.model = None
        self.model_name = "all-MiniLM-L6-v2"

    def _load_model(self):
        if self.model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: %s...", self.model_name)
            self.model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully.")
        except ImportError:
            logger.warning("sentence-transformers not installed. Vector output will be disabled.")
            self.model = False # Mark as failed/missing so we don't retry indefinitely
        except Exception as e:
            logger.error("Failed to load embedding model: %s", e)
            self.model = False

    def generate(self, texts: List[str]) -> List[List[float]]:
        if self.model is None:
            self._load_model()

        if not self.model: # Handle case where model failed to load or is missing
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
            logger.error("Error generating embeddings: %s", e)
            return []

embeddings_service = EmbeddingsService()

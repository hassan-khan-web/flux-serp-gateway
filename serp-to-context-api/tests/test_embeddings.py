import pytest
from unittest.mock import MagicMock, patch
from app.services.embeddings import EmbeddingsService
import numpy as np


class TestEmbeddingsService:
    """Test EmbeddingsService for vector generation"""

    def test_initialization(self):
        """Test EmbeddingsService initialization"""
        service = EmbeddingsService()
        assert service is not None
        assert service.model_name == "all-MiniLM-L6-v2"

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_single_text(self, mock_transformer):
        """Test generating embedding for single text"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([[0.1, 0.2, 0.3, 0.4, 0.5]])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        result = service.generate(["Test query"])

        assert result is not None
        assert len(result) == 1

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_multiple_texts(self, mock_transformer):
        """Test generating embeddings for multiple texts"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
            [0.7, 0.8, 0.9]
        ])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        result = service.generate(["Text 1", "Text 2", "Text 3"])

        assert result is not None
        assert len(result) == 3

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_error_handling(self, mock_transformer):
        """Test error handling in generate"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        mock_model.encode.side_effect = Exception("Model error")

        service = EmbeddingsService()
        result = service.generate(["test"])

        assert result == []

    def test_model_not_loaded_returns_empty(self):
        """Test that missing model returns empty list"""
        service = EmbeddingsService()
        # Simulate model load failure (lazy loading sets it to False on failure)
        service.model = False
        
        result = service.generate(["test"])
        
        assert result == []

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_batch_processing(self, mock_transformer):
        """Test batch processing of embeddings"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        batch_embeddings = np.array([[0.1 * i, 0.2 * i] for i in range(10)])
        mock_model.encode.return_value = batch_embeddings

        service = EmbeddingsService()
        texts = [f"Text {i}" for i in range(10)]
        result = service.generate(texts)

        assert len(result) == 10

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_returns_list_of_lists(self, mock_transformer):
        """Test that generate returns list of lists format"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([[0.1, 0.2], [0.3, 0.4]])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        result = service.generate(["text1", "text2"])

        assert isinstance(result, list)
        assert isinstance(result[0], list)

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_long_text(self, mock_transformer):
        """Test generating embedding for very long text"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([[0.1] * 384])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        result = service.generate(["word " * 10000])

        assert result is not None

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_special_characters(self, mock_transformer):
        """Test generating embedding with special characters"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([[0.2] * 384])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        result = service.generate(["Text with @"])

        assert result is not None

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_unicode_text(self, mock_transformer):
        """Test generating embedding with unicode characters"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([[0.3] * 384])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        unicode_text = "你好世界 مرحبا العالم"
        result = service.generate([unicode_text])

        assert result is not None

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_whitespace_handling(self, mock_transformer):
        """Test handling of whitespace in text"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([[0.1] * 384])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        whitespace_text = "   text   with   spaces   \n\t\n  "
        result = service.generate([whitespace_text])

        assert result is not None

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_numeric_text(self, mock_transformer):
        """Test generating embeddings from numeric strings"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([[0.5] * 384])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        numeric_text = "123 456 789 0.123 -45.67"
        result = service.generate([numeric_text])

        assert result is not None

    @patch("sentence_transformers.SentenceTransformer")
    def test_generate_mixed_language_text(self, mock_transformer):
        """Test generating embeddings from multilingual text"""
        mock_model = MagicMock()
        mock_transformer.return_value = mock_model
        
        embedding_array = np.array([[0.4] * 384])
        mock_model.encode.return_value = embedding_array

        service = EmbeddingsService()
        mixed_text = "English مع عربي и русский 日本語"
        result = service.generate([mixed_text])

        assert result is not None



"""
Embedding model wrapper for multilingual-e5.

Usage:
    from embedding import EmbeddingModel
    model = EmbeddingModel()
    vectors = model.embed_documents(["some text", "another text"])
    query_vec = model.embed_query("find me a dish with beef")
"""

import os
from typing import List

PASSAGE_PREFIX = "passage: "
QUERY_PREFIX = "query: "


class EmbeddingModel:
    def __init__(
        self,
        model_name: str = None,
        device: str = None,
        batch_size: int = None,
    ):
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-large"
        )
        self.device = device or os.getenv("DEVICE", "cpu")
        self.batch_size = int(batch_size or os.getenv("BATCH_SIZE", "32"))

        print(f"Loading embedding model '{self.model_name}' on device '{self.device}'...")
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name, device=self.device)
        except Exception as e:
            fallback = "intfloat/multilingual-e5-small"
            print(f"Failed to load '{self.model_name}': {e}\nFalling back to '{fallback}'")
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(fallback, device=self.device)
            self.model_name = fallback

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of document strings with the 'passage:' prefix."""
        prefixed = [PASSAGE_PREFIX + t for t in texts]
        embeddings = self._model.encode(
            prefixed,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string with the 'query:' prefix."""
        prefixed = QUERY_PREFIX + text
        embedding = self._model.encode(
            [prefixed],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return embedding[0].tolist()

    def get_dimension(self) -> int:
        return self._model.get_sentence_embedding_dimension()

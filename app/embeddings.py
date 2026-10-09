import logging
import os
import threading

from sentence_transformers import SentenceTransformer


MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768
BATCH_SIZE = 4

DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

_model = None
_model_lock = threading.Lock()


class EmbeddingError(Exception):
    """Raised when text embedding fails."""


def get_model() -> SentenceTransformer:
    """Load the Nomic model once and reuse it."""

    global _model

    if _model is None:
        with _model_lock:
            if _model is None:

                model = SentenceTransformer(
                    MODEL_NAME
                    
                )

                model.max_seq_length = 512

                _model = model

    return _model


def _embed(
    texts: list[str],
    prefix: str
) -> list[list[float]]:

    if not texts:
        return []

    try:
        model = get_model()

        embeddings = model.encode(
            [prefix + text for text in texts],
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return [
            [round(float(value), 6) for value in vector]
            for vector in embeddings
        ]

    except Exception as exc:
        raise EmbeddingError(
            "Could not generate embeddings."
        ) from exc


def embed_documents(
    texts: list[str]
) -> list[list[float]]:

    """Generate embeddings for document chunks."""

    return _embed(texts, DOC_PREFIX)


def embed_query(text: str) -> list[float]:

    """Generate an embedding for a search query."""

    return _embed([text], QUERY_PREFIX)[0]
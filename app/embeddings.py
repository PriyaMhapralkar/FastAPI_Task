import threading

from sentence_transformers import SentenceTransformer


MODEL_NAME = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
BATCH_SIZE = 8

_model = None
_model_lock = threading.Lock()


class EmbeddingError(Exception):
    """Raised when text embedding fails."""


def get_model() -> SentenceTransformer:
    """Load BGE-M3 once and reuse it."""

    global _model

    if _model is None:
        with _model_lock:
            if _model is None:
                _model = SentenceTransformer(MODEL_NAME)

    return _model

def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate normalized BGE-M3 embeddings for a list of texts."""

    if not texts:
        return []

    try:
        model = get_model()

        embeddings = model.encode(
            texts,
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
            "Could not generate document embeddings."
        ) from exc
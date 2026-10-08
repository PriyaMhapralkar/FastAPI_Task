"""FAISS vector index over document chunks.

The index is a rebuildable cache: PostgreSQL (document_chunks.embedding) is the
source of truth. FAISS ids are the document_chunks.id values.
"""

import logging
import threading
from pathlib import Path

import faiss
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embeddings import EMBEDDING_DIM
from app.models import DocumentChunk


logger = logging.getLogger(__name__)


INDEX_DIR = Path(__file__).resolve().parent.parent / "faiss_index"
INDEX_PATH = INDEX_DIR / "chunks.index"


_index = None
_dirty = False
_lock = threading.RLock()


def _new_index():
    return faiss.IndexIDMap2(
        faiss.IndexFlatIP(EMBEDDING_DIM)
    )


def _matrix(vectors) -> np.ndarray:
    return np.asarray(vectors, dtype="float32")


def _ids(values) -> np.ndarray:
    return np.asarray(values, dtype="int64")


def _save(index) -> None:
    INDEX_DIR.mkdir(exist_ok=True)

    tmp = INDEX_PATH.with_suffix(".tmp")

    faiss.write_index(index, str(tmp))
    tmp.replace(INDEX_PATH)


def rebuild(db: Session) -> int:
    global _index, _dirty

    rows = db.execute(
        select(
            DocumentChunk.id,
            DocumentChunk.embedding
        ).where(
            DocumentChunk.embedding.is_not(None)
        )
    ).all()

    rows = [
        r
        for r in rows
        if r.embedding and len(r.embedding) == EMBEDDING_DIM
    ]

    index = _new_index()

    if rows:
        index.add_with_ids(
            _matrix([r.embedding for r in rows]),
            _ids([r.id for r in rows])
        )

    with _lock:
        _index = index
        _dirty = False
        _save(index)

    logger.info(
        "FAISS index rebuilt with %d vectors",
        index.ntotal
    )

    return index.ntotal


def _ensure_ready(db: Session):
    global _index

    with _lock:
        if _dirty:
            rebuild(db)

        elif _index is None:

            if INDEX_PATH.exists():
                try:
                    _index = faiss.read_index(
                        str(INDEX_PATH)
                    )

                    logger.info(
                        "Loaded FAISS index from disk (%d vectors)",
                        _index.ntotal
                    )

                    return _index

                except Exception:
                    logger.exception(
                        "Could not read the FAISS index file; rebuilding"
                    )

            rebuild(db)

        return _index


def update_document(
    db: Session,
    old_ids: list[int],
    new_ids: list[int],
    vectors
) -> None:

    global _dirty

    with _lock:
        try:
            index = _ensure_ready(db)

            to_remove = _ids(
                list(old_ids) + list(new_ids)
            )

            if len(to_remove):
                index.remove_ids(to_remove)

            if new_ids:
                index.add_with_ids(
                    _matrix(vectors),
                    _ids(new_ids)
                )

            _save(index)

        except Exception:
            logger.exception(
                "FAISS update failed; the index will be rebuilt on the next search"
            )

            _dirty = True


def search(
    db: Session,
    query_vector: list[float],
    top_k: int = 5
) -> list[tuple[int, float]]:

    with _lock:
        index = _ensure_ready(db)

        if index.ntotal == 0:
            return []

        scores, ids = index.search(
            _matrix([query_vector]),
            top_k
        )

    return [
        (int(i), float(s))
        for i, s in zip(ids[0], scores[0])
        if i != -1
    ]
"""Embedding providers for generating vector representations of highlights.

Supports two backends:
- **Local**: sentence-transformers (all-MiniLM-L6-v2) -- no API key needed
- **OpenAI**: text-embedding-3-small -- requires OPENAI_API_KEY
"""
from __future__ import annotations

import logging
import os
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Generator

import numpy as np

# Suppress noisy warnings from transitive dependencies before any imports
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

logger = logging.getLogger(__name__)


@contextmanager
def _quiet_model_load() -> Generator[None, None, None]:
    """Suppress noisy stderr output (torch LOAD REPORT) and logging during model init."""
    _loggers = {
        name: logging.getLogger(name)
        for name in ("sentence_transformers", "torch", "huggingface_hub")
    }
    prev = {name: lg.level for name, lg in _loggers.items()}
    for lg in _loggers.values():
        lg.setLevel(logging.ERROR)
    # Redirect fd-level stderr to /dev/null to capture C-level output
    old_fd = os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_fd, 2)
        os.close(old_fd)
        for name, lg in _loggers.items():
            lg.setLevel(prev[name])


class EmbeddingProvider(ABC):
    """Abstract embedding provider interface."""

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """Return an (N, D) array of embeddings for the given texts."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local embeddings via sentence-transformers (all-MiniLM-L6-v2)."""

    _MODEL_NAME = "all-MiniLM-L6-v2"

    def __init__(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-not-found]
        except ImportError as exc:
            msg = str(exc).lower()
            if "torchvision" in msg or "torch" in msg:
                raise ImportError(
                    "A PyTorch dependency issue was detected. "
                    "KoNotes does not require torchvision. Try:\n"
                    "  pip install sentence-transformers --no-deps && "
                    "pip install torch transformers tokenizers huggingface-hub tqdm"
                ) from exc
            raise ImportError(
                "sentence-transformers is required for local embeddings. "
                "Install with: pip install 'konotes[ai]'"
            ) from exc
        try:
            with _quiet_model_load():
                self._model = SentenceTransformer(self._MODEL_NAME)
        except Exception as exc:
            msg = str(exc).lower()
            if "torchvision" in msg:
                logger.warning(
                    "torchvision error detected during model load; "
                    "this dependency is not required by KoNotes."
                )
                raise ImportError(
                    "torchvision caused an error during model loading. "
                    "Uninstall it with: pip uninstall torchvision"
                ) from exc
            raise

    def embed(self, texts: list[str]) -> np.ndarray:
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return np.asarray(embeddings, dtype=np.float32)

    def name(self) -> str:
        return f"local ({self._MODEL_NAME})"


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI API embeddings via text-embedding-3-small."""

    _MODEL = "text-embedding-3-small"
    _BATCH_SIZE = 512

    def __init__(self, api_key: str) -> None:
        try:
            from openai import OpenAI  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "openai is required for API embeddings. "
                "Install with: pip install 'konotes[openai]'"
            ) from exc
        self._client = OpenAI(api_key=api_key)

    def embed(self, texts: list[str]) -> np.ndarray:
        all_embeddings: list[list[float]] = []
        for i in range(0, len(texts), self._BATCH_SIZE):
            batch = texts[i : i + self._BATCH_SIZE]
            response = self._client.embeddings.create(model=self._MODEL, input=batch)
            all_embeddings.extend([d.embedding for d in response.data])
        return np.asarray(all_embeddings, dtype=np.float32)

    def name(self) -> str:
        return f"openai ({self._MODEL})"


def get_provider(provider_name: str = "local", api_key: str | None = None) -> EmbeddingProvider:
    """Factory: return the requested embedding provider.

    Args:
        provider_name: ``"local"`` or ``"openai"``
        api_key: Required when *provider_name* is ``"openai"``.
    """
    if provider_name == "openai":
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI embedding provider.")
        return OpenAIEmbeddingProvider(api_key=api_key)
    return LocalEmbeddingProvider()

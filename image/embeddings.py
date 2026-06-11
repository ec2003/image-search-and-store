from __future__ import annotations

import hashlib
from functools import lru_cache
from io import BytesIO
from importlib import import_module
from typing import Protocol

from django.conf import settings


class EmbeddingProvider(Protocol):
    model_id: str
    dimensions: int

    def embed_image_bytes(self, content: bytes) -> list[float]:
        ...


class HashEmbeddingProvider:
    """Deterministic image provider for lightweight tests and local fallback."""

    def __init__(self, *, model_id: str | None = None, dimensions: int | None = None):
        self.model_id = model_id or settings.EMBEDDING_MODEL_ID
        self.dimensions = dimensions or settings.EMBEDDING_DIMENSIONS

    def embed_image_bytes(self, content: bytes) -> list[float]:
        return self._hash_to_vector(b"image:" + content)

    def _hash_to_vector(self, seed: bytes) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dimensions:
            digest = hashlib.sha256(seed + counter.to_bytes(4, "big")).digest()
            for byte in digest:
                values.append((byte / 127.5) - 1.0)
                if len(values) == self.dimensions:
                    break
            counter += 1
        return values


class EfficientNetV2EmbeddingProvider:
    def __init__(
        self,
        *,
        model_id: str | None = None,
        dimensions: int | None = None,
        device: str | None = None,
        torch_threads: int | None = None,
    ):
        self.model_id = model_id or settings.EMBEDDING_MODEL_ID
        self.dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        self.device = device or settings.EMBEDDING_DEVICE
        self.torch_threads = torch_threads if torch_threads is not None else settings.EMBEDDING_TORCH_THREADS
        self._model = None
        self._transforms = None

    def embed_image_bytes(self, content: bytes) -> list[float]:
        from PIL import Image, UnidentifiedImageError
        import torch
        import torch.nn.functional as functional

        try:
            with Image.open(BytesIO(content)) as image:
                rgb_image = image.convert("RGB")
                tensor = self.transforms(rgb_image).unsqueeze(0).to(self.device)
        except UnidentifiedImageError as exc:
            raise ValueError("Image content is not readable by EfficientNetV2.") from exc

        with torch.inference_mode():
            output = self.model(tensor).flatten()
            if output.numel() != self.dimensions:
                raise RuntimeError(
                    f"{self.model_id} produced {output.numel()} dimensions; "
                    f"expected {self.dimensions}."
                )
            output = functional.normalize(output, p=2, dim=0)
            return output.cpu().tolist()

    @property
    def model(self):
        if self._model is None:
            self._load_model()
        return self._model

    @property
    def transforms(self):
        if self._transforms is None:
            self._load_model()
        return self._transforms

    def _load_model(self) -> None:
        import torch
        from torchvision.models import EfficientNet_V2_S_Weights, efficientnet_v2_s

        if self.torch_threads > 0:
            torch.set_num_threads(self.torch_threads)

        weights = EfficientNet_V2_S_Weights.DEFAULT
        model = efficientnet_v2_s(weights=weights)
        model.classifier = torch.nn.Identity()
        model.eval()
        model.to(self.device)

        self._model = model
        self._transforms = weights.transforms()


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    module_path, class_name = settings.EMBEDDING_PROVIDER.rsplit(".", 1)
    module = import_module(module_path)
    provider_class = getattr(module, class_name)
    return provider_class()


def clear_embedding_provider_cache() -> None:
    get_embedding_provider.cache_clear()

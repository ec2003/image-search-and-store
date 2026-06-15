import io
import torch
import torchvision
import torchvision.transforms as T
import numpy as np

from torchvision.models.feature_extraction import create_feature_extractor
from functools import lru_cache
from PIL import Image

from django.conf import settings

from typing import Callable


class EmbeddingModel:
    def __init__(self):
        self.model = _get_model()
        self.model.eval()
        self.return_nodes = ["flatten"]
        self.output_dimension = settings.EMBEDDING_DIMENSIONS

        # ImageNet-standard transforms
        self.transform = T.Compose([
            T.Resize(256),
            T.CenterCrop(224),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

    def encode(self, image: torch.Tensor) -> np.ndarray:
        """Run the model on a preprocessed image tensor and return a 2048-dim vector."""
        with torch.no_grad():
            features = self._extract(image.unsqueeze(0))  # add batch dim
        return features.squeeze().cpu().numpy().astype(np.float32)

    def encode_from_bytes(self, image_bytes: bytes) -> np.ndarray:
        """Load raw image bytes (JPEG/PNG), preprocess, and encode."""
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self.transform(pil_image)
        return self.encode(tensor)

    def _extract(self, input_tensor: torch.Tensor):
        extractor = create_feature_extractor(
            self.model, return_nodes=self.return_nodes,
        )
        features = extractor(input_tensor)
        return features["flatten"]


@lru_cache(maxsize=1)
def _get_model():
    return torchvision.models.resnet50(weights=torchvision.models.ResNet50_Weights.DEFAULT)
import torch
import torchvision
from torchvision.models.feature_extraction import create_feature_extractor, get_graph_node_names
from functools import lru_cache

from django.conf import settings

from typing import Callable

class EmbeddingModel():
    def __init__(self):
        self.model = __get_model()
        self.return_nodes = ["flatten"]
        self.output_dimension = settings.EMBEDDING_DIMENSIONS


    @property
    def get_model(self):
        return self.model

    def feature_extract(self, input: torch.Tensor):
        feature_extractor = create_feature_extractor(self.model, return_nodes=self.return_nodes, )
        features = feature_extractor(input)
        return features

def feature_extract(model: torch.nn.Module, 
                    input: torch.Tensor,
                    return_nodes: list[str] = ["flatten"]):
    feature_extractor = create_feature_extractor(model, return_nodes=return_nodes, )
    features = feature_extractor(input)
    return features

@lru_cache
def __get_model():
    return torchvision.models.resnet50(weights=torchvision.models.ResNet50_Weights.DEFAULT)

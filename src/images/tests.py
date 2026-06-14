from django.core.management import call_command
from django.test import TestCase

from unittest.mock import Mock, patch

from io import BytesIO, StringIO

from embeddings import EmbeddingModel
# Create your tests here.

class ManagementCommandTests(TestCase):
    @patch("embedding.embed_model.EmbeddingModel.feature_extract")
    def test_warm_embedding_model_command_embeds_probe_image(self, mock_feature_extract):
        mock_feature_extract.return_value = Mock()

        output = StringIO()

        call_command("warm_embedding_model", stdout=output)

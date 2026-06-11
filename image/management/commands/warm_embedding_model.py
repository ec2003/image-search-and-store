from io import BytesIO

from django.core.management.base import BaseCommand

from image.embeddings import get_embedding_provider


class Command(BaseCommand):
    help = "Load and verify the configured image embedding model."

    def handle(self, *args, **options):
        from PIL import Image

        image = Image.new("RGB", (64, 64), color=(128, 128, 128))
        output = BytesIO()
        image.save(output, format="JPEG")

        provider = get_embedding_provider()
        vector = provider.embed_image_bytes(output.getvalue())
        self.stdout.write(
            self.style.SUCCESS(
                f"Warmed {provider.model_id}: generated {len(vector)} dimensions."
            )
        )

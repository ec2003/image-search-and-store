from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from image.models import ImageAsset, ImageStatus
from image.tasks import index_image_asset


class Command(BaseCommand):
    help = "Queue uploaded images for reindexing with the active embedding model."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Queue every uploaded, non-deleted image instead of only stale embeddings.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print how many images would be queued without sending Celery tasks.",
        )

    def handle(self, *args, **options):
        queryset = ImageAsset.objects.exclude(
            status__in=[ImageStatus.DELETED, ImageStatus.UPLOAD_REQUESTED]
        )
        if not options["all"]:
            queryset = queryset.filter(
                Q(embedding_model__isnull=True)
                | Q(embedding_model="")
                | ~Q(embedding_model=settings.EMBEDDING_MODEL_ID)
                | ~Q(embedding_dimensions=settings.EMBEDDING_DIMENSIONS)
            )

        image_ids = list(queryset.values_list("id", flat=True))
        if options["dry_run"]:
            self.stdout.write(f"Would queue {len(image_ids)} image(s) for reindexing.")
            return

        for image_id in image_ids:
            index_image_asset.delay(str(image_id))

        self.stdout.write(
            self.style.SUCCESS(f"Queued {len(image_ids)} image(s) for reindexing.")
        )

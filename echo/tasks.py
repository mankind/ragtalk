import logging
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from .models import Document, ProcessingStatus
from .services import DocumentIngestionService  # existing sync service

logger = logging.getLogger(__name__)


async def ingest_document_background(document_id, embeddings):
    """
    Async wrapper around the synchronous ingestion service.

    Uses sync_to_async to prevent blocking the event loop.
    Sends WebSocket notification when processing completes.

    NOTE:
    This is intentionally a lightweight async approach.
    In production, this should move to Celery / SQS.
    """

    channel_layer = get_channel_layer()

    try:
        # Fetch document safely in async context
        document = await sync_to_async(Document.objects.get)(id=document_id)
        
        ingestion_service = DocumentIngestionService(embeddings)

        # Run CPU-bound ingestion in thread
        await sync_to_async(ingestion_service.ingest)(document)

        # Refresh document state
        document = await sync_to_async(Document.objects.get)(id=document_id)

        if document.processing_status == ProcessingStatus.INDEXED:
            await channel_layer.group_send(
                "documents",
                {
                    "type": "document_indexed",
                    "document_id": str(document.id),
                    "message": "Document indexing completed successfully.",
                },
            )

    except Exception as exc:
        logger.exception("Background ingestion failed")

        try:
            document = await sync_to_async(Document.objects.get)(id=document_id)
            document.processing_status = ProcessingStatus.FAILED
            document.error_message = str(exc)
            await sync_to_async(document.save)(
                update_fields=["processing_status", "error_message"]
            )
        except Exception:
            logger.exception("Failed updating document failure state")

        await channel_layer.group_send(
            "documents",
            {
                "type": "document_failed",
                "document_id": str(document_id),
                "message": "Document indexing failed.",
            },
        )

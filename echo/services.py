import logging
from .models import Document, ProcessingStatus
from .loaders import DocumentLoader
from .parsers import DocumentParser
from .vectorstore import VectorStoreService 

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
# from .services import DocumentIngestionService  # existing sync service

logger = logging.getLogger(__name__)

class DocumentIngestionService:
    """
    Orchestrates:
    - Deduplication
    - Loading
    - Chunking
    - Vector storage
    """

    def __init__(self, embeddings):
        self.vector_service = VectorStoreService(embeddings)

    def ingest(self, document: Document):
        """
        Synchronous ingestion logic.
        Async wrapper will call this in next phase.
        """
        try:
            existing = Document.objects.filter(
                file_hash=document.file_hash,
                processing_status=ProcessingStatus.INDEXED,
            ).exclude(id=document.id).first()

            if existing:
                logger.info("Duplicate file detected. Skipping re-index.")
                document.processing_status = ProcessingStatus.INDEXED
                document.save(update_fields=["processing_status"])
                return

            raw_docs = DocumentLoader.load_pdf(document.file.path)
            chunks = DocumentParser.chunk_documents(raw_docs)

            # Inject document_id into metadata (minimal change)
            for chunk in chunks:
                if not chunk.metadata:
                    chunk.metadata = {}
                chunk.metadata["document_id"] = str(document.id)

            self.vector_service.add_documents(chunks)

            document.processing_status = ProcessingStatus.INDEXED
            document.save(update_fields=["processing_status"])

        except Exception as exc:
            logger.exception("Document ingestion failed.")
            document.processing_status = ProcessingStatus.FAILED
            document.error_message = str(exc)
            document.save(update_fields=["processing_status", "error_message"])
            raise

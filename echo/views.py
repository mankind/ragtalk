from django.shortcuts import render

# Create your views here.
import asyncio, uuid, json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import StreamingHttpResponse

from asgiref.sync import sync_to_async
from echo.models import Document
from .tasks import ingest_document_background
# inject your embeddings instance
from .embeddings import embeddings
from .rag_engine import rag_graph

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
async def upload_document(request):
    try:
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return JsonResponse({"error": "No file provided"}, status=400)

        # 1. Calculate Hash
        file_hash = Document.calculate_file_hash(uploaded_file)
        print(f'Processing file: {uploaded_file.name}, Hash: {file_hash}')

        # 2. CHECK FOR EXISTING (Deduplication Logic)
        def get_existing():
            return Document.objects.filter(file_hash=file_hash).first()
        
        existing_doc = await sync_to_async(get_existing, thread_sensitive=True)()

        if existing_doc:
            print(f'Document already exists: {existing_doc.id}')
            return JsonResponse(
                {
                    "document_id": str(existing_doc.id),
                    "status": existing_doc.processing_status,
                    "info": "Document already exists. Skipping processing."
                },
                status=200,
            )

        # 3. Create new document with File persistence fix
        # We wrap this in a sync function to ensure Django's FileField
        # correctly moves the file from memory/temp-dir to your MEDIA_ROOT.
        def create_document_sync():
            return Document.objects.create(
                title=uploaded_file.name,
                file=uploaded_file,
                file_hash=file_hash,
            )

        document = await sync_to_async(create_document_sync, thread_sensitive=True)()
        print(f'New document created: {document.id}, Path: {document.file.path}')

        # 4. Fire background task only for NEW documents
        asyncio.create_task(
            ingest_document_background(document.id, embeddings)
        )

        return JsonResponse(
            {
                "document_id": str(document.id),
                "status": document.processing_status,
            },
            status=202,
        )

    except Exception as exc:
        logger.exception("Upload failed")
        return JsonResponse(
            {"error": "Upload failed", "details": str(exc)},
            status=500,
        )

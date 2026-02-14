import time
import shutil
import os
from unittest.mock import patch
from django.test import TransactionTestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.conf import settings
from echo.models import Document

# Use a specific directory for test files
TEST_MEDIA_ROOT = os.path.join(settings.BASE_DIR, 'test_media')

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class AsyncUploadTest(TransactionTestCase):
    reset_sequences = True 

    def setUp(self):
        # Create a dummy file for reuse
        self.pdf_content = b"dummy content"

    def tearDown(self):
        """
        Deletes the test_media directory after each test case 
        to ensure no files remain on disk.
        """
        if os.path.exists(TEST_MEDIA_ROOT):
            shutil.rmtree(TEST_MEDIA_ROOT)

    @patch('echo.views.ingest_document_background')
    def test_upload_returns_202(self, mock_ingest):
        file = SimpleUploadedFile("test.pdf", self.pdf_content, content_type="application/pdf")
        
        response = self.client.post(reverse('echo:upload_document'), {"file": file})
        
        self.assertEqual(response.status_code, 202)
        self.assertIn("document_id", response.json())
        
        # Verify the background task was triggered
        self.assertTrue(mock_ingest.called)

    @patch('echo.views.ingest_document_background')
    def test_upload_creates_document_record(self, mock_ingest):
        file = SimpleUploadedFile("create_test.pdf", b"unique content", content_type="application/pdf")
        
        self.client.post(reverse('echo:upload_document'), {"file": file})
        
        # Check if record exists in DB
        self.assertTrue(Document.objects.filter(title="create_test.pdf").exists())

    @patch('echo.views.ingest_document_background')
    def test_upload_is_non_blocking(self, mock_ingest):
        file = SimpleUploadedFile("speed_test.pdf", b"fast content", content_type="application/pdf")
        
        start = time.time()
        self.client.post(reverse('echo:upload_document'), {"file": file})
        duration = time.time() - start
        
        # Should be very fast because ingestion is mocked/backgrounded
        self.assertLess(duration, 0.5)

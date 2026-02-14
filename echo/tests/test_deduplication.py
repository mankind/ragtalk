
# echo/tests/test_deduplication.py
from django.test import TransactionTestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from unittest.mock import patch
from echo.models import Document

# Use a temp directory for file uploads during tests
@override_settings(MEDIA_ROOT='/tmp/django_test_media')
class DeduplicationTest(TransactionTestCase):
    
    def setUp(self):
        self.pdf_content = b"identical content for deduplication"

    @patch('echo.views.ingest_document_background')
    def test_duplicate_document_skips_processing(self, mock_ingest):
        """
        Uploading the same file twice should return the same ID 
        and NOT trigger the background task the second time.
        """
        file1 = SimpleUploadedFile("doc1.pdf", self.pdf_content, content_type="application/pdf")
        
        # 1. First Upload (Should create and process)
        response1 = self.client.post(reverse('echo:upload_document'), {"file": file1})
        self.assertEqual(response1.status_code, 202)
        doc_id_1 = response1.json()['document_id']
        
        # Assert background task was called once
        self.assertEqual(mock_ingest.call_count, 1)

        # 2. Second Upload (Same content, different filename potentially)
        # We must create a new file object because the first one is "closed/read"
        file2 = SimpleUploadedFile("doc1_copy.pdf", self.pdf_content, content_type="application/pdf")
        
        response2 = self.client.post(reverse('echo:upload_document'), {"file": file2})
        
        # 3. Assertions
        # Should be 200 OK (found existing) not 202 (accepted new)
        self.assertEqual(response2.status_code, 200) 
        
        doc_id_2 = response2.json()['document_id']
        self.assertEqual(doc_id_1, doc_id_2) # IDs should match
        
        # Crucial: Background task count should STILL be 1 (not 2)
        self.assertEqual(mock_ingest.call_count, 1)


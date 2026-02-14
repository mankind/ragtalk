from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings

from echo.models import Document
from django.conf import settings
import os, shutil, time

# Use a specific directory for test files
TEST_MEDIA_ROOT = os.path.join(settings.BASE_DIR, 'test_media')

@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class DocumentModelTest(TestCase):

    # reset_sequences = True 

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

    def test_file_hash_is_generated(self):
        file = SimpleUploadedFile(
            "test.pdf",
            b"dummy content",
            content_type="application/pdf",
        )

        hash_value = Document.calculate_file_hash(file)
        self.assertEqual(len(hash_value), 64)

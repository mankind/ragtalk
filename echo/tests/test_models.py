from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from echo.models import Document


class DocumentModelTest(TestCase):

    def test_file_hash_is_generated(self):
        file = SimpleUploadedFile(
            "test.pdf",
            b"dummy content",
            content_type="application/pdf",
        )

        hash_value = Document.calculate_file_hash(file)
        self.assertEqual(len(hash_value), 64)

from django.db import models
import hashlib
import uuid
import os
from django.db.models.signals import post_delete
from django.dispatch import receiver

class ProcessingStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    INDEXED = "INDEXED", "Indexed"
    FAILED = "FAILED", "Failed"

class Document(models.Model):
    # Using UUID is better for external RAG references
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/")
    
    # Harmonized: Lead touch with unique constraint (no manual Index needed in Meta)
    file_hash = models.CharField(max_length=64, unique=True, null=True)
    
    # State tracking
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING,
    )
    is_indexed = models.BooleanField(default=False)
    
    # Essential for interview: shows you handle "Generative AI" failures (like OOM or Parsing errors)
    error_message = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.processing_status})"

    @staticmethod
    def calculate_file_hash(file_obj) -> str:
        sha256 = hashlib.sha256()
        for chunk in file_obj.chunks():
            sha256.update(chunk)
        file_obj.seek(0)
        return sha256.hexdigest()

@receiver(post_delete, sender=Document)
def delete_file_on_document_delete(sender, instance, **kwargs):
    """
    Deletes the physical file from the filesystem when the 
    corresponding Document object is deleted from the database.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            try:
                os.remove(instance.file.path)
                print(f"Successfully deleted file: {instance.file.path}")
            except Exception as e:
                print(f"Error deleting file: {e}")
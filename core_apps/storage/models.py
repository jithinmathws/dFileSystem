import uuid
import os
from django.db import models, transaction
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.core.files.storage import default_storage

class StorageNode(models.Model):
    """Represents a storage node where file chunks are stored."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    host = models.GenericIPAddressField()
    port = models.PositiveIntegerField(default=8001)
    capacity = models.BigIntegerField(help_text="Total capacity in bytes")
    available = models.BigIntegerField(help_text="Available space in bytes")
    is_active = models.BooleanField(default=True, db_index=True)
    last_heartbeat = models.DateTimeField(auto_now=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Storage Node'
        verbose_name_plural = 'Storage Nodes'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.host}:{self.port})"

    def update_heartbeat(self):
        """Update the last_heartbeat field to current time."""
        self.last_heartbeat = timezone.now()
        self.save(update_fields=['last_heartbeat'])

    def update_storage_metrics(self, used_space):
        """Update available space and set active status."""
        self.available = max(0, self.capacity - used_space)
        self.is_active = self.available > 0
        self.save(update_fields=['available', 'is_active'])


class FileManager(models.Manager):
    """Custom manager for File model with common queries."""
    
    def active(self):
        """Return non-deleted files."""
        return self.filter(is_deleted=False)
    
    def by_user(self, user):
        """Return files uploaded by a specific user."""
        return self.filter(user=user)
    
    def large_files(self, size_mb=100):
        """Return files larger than specified size in MB."""
        return self.filter(size__gt=size_mb * 1024 * 1024)


class File(models.Model):
    """Represents a file that has been uploaded to the system."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, db_index=True)
    size = models.BigIntegerField(help_text="File size in bytes", db_index=True)
    checksum = models.CharField(
        max_length=64, 
        help_text="SHA-256 checksum of the file",
        db_index=True
    )
    content_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="MIME type of the file"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='files',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_deleted = models.BooleanField(default=False, db_index=True)

    objects = FileManager()

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'File'
        verbose_name_plural = 'Files'
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'checksum', 'user'],
                name='unique_file_name_checksum_user'
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_human_readable_size()})"

    def get_absolute_url(self):
        """Get URL for file detail view."""
        return reverse('storage:file-detail', args=[str(self.id)])

    def soft_delete(self):
        """Mark the file as deleted instead of removing it."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        """Restore a soft-deleted file."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])

    @property
    def is_available(self):
        """Check if the file is available (not deleted and has chunks)."""
        return not self.is_deleted and self.chunks.exists()

    @property
    def is_image(self):
        """Check if the file is an image."""
        return self.content_type and self.content_type.startswith('image/')

    @property
    def is_document(self):
        """Check if the file is a document."""
        return (self.content_type and 
                any(t in self.content_type for t in ['text/', 'application/pdf', 
                    'application/msword', 'application/vnd.openxmlformats-']))

    @property
    def is_archive(self):
        """Check if the file is an archive."""
        return (self.content_type and 
                any(t in self.content_type for t in ['zip', 'rar', 'tar', '7z', 'gz']))

    def get_human_readable_size(self):
        """Convert size in bytes to human readable format."""
        size = self.size
        if size is None:
            return "0.00 B"

        try:
            size = float(size)
        except (TypeError, ValueError):
            return "0.00 B"

        if size < 0:
            return "0.00 B"

        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def get_file_type(self):
        """Categorize file into types like image, document, etc."""
        if self.is_image:
            return 'image'
        elif self.is_document:
            return 'document'
        elif self.is_archive:
            return 'archive'
        return 'other'


class Chunk(models.Model):
    """Represents a chunk of a file stored on a storage node."""
    class ChunkStatus(models.TextChoices):
        UPLOADING = 'uploading', 'Uploading'
        COMPLETED = 'completed', 'Completed'
        CORRUPTED = 'corrupted', 'Corrupted'
        DELETED = 'deleted', 'Deleted'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(
        File, 
        related_name='chunks', 
        on_delete=models.CASCADE,
        db_index=True
    )
    storage_node = models.ForeignKey(
        StorageNode, 
        related_name='chunks', 
        on_delete=models.CASCADE,
        db_index=True
    )
    object_key = models.CharField(
        max_length=512,
        default='',
        blank=True,
        db_index=True,
        help_text="Node-local identifier/path to the stored chunk bytes"
    )
    chunk_number = models.PositiveIntegerField(db_index=True)
    size = models.PositiveIntegerField(help_text="Chunk size in bytes")
    checksum = models.CharField(
        null=True,
        blank=True,
        max_length=64, 
        help_text="SHA-256 checksum of the chunk"
    )
    is_primary = models.BooleanField(
        default=False, 
        help_text="Whether this is the primary copy",
        db_index=True
    )
    status = models.CharField(
        max_length=10,
        choices=ChunkStatus.choices,
        default=ChunkStatus.UPLOADING,
        db_index=True
    )
    stored_checksum = models.CharField(
        null=True,
        blank=True,
        max_length=64, 
        help_text="SHA-256 checksum of the stored chunk"
    )
    last_verified_at = models.DateTimeField(null=True, blank=True, auto_now_add=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('file', 'chunk_number', 'storage_node')
        ordering = ['chunk_number']
        verbose_name = 'File Chunk'
        verbose_name_plural = 'File Chunks'

    def __str__(self):
        return (f"Chunk {self.chunk_number} of {self.file.name} "
                f"on {self.storage_node.name} ({self.status})")

    def get_absolute_url(self):
        """Get URL for chunk detail view."""
        return reverse('storage:chunk-detail', args=[str(self.id)])

    def mark_as_primary(self):
        """Mark this chunk as the primary copy."""
        # Primary should be per (file, chunk_number) across replicas (storage nodes)
        with transaction.atomic():
            Chunk.objects.select_for_update().filter(
                file=self.file,
                chunk_number=self.chunk_number,
                is_primary=True,
            ).exclude(pk=self.pk).update(is_primary=False)

            if not self.is_primary:
                self.is_primary = True
                self.save(update_fields=['is_primary'])

    def verify_checksum(self, calculated_checksum):
        """Verify if the chunk's checksum matches the calculated one."""
        is_valid = self.checksum == calculated_checksum
        if not is_valid:
            self.status = self.ChunkStatus.CORRUPTED
            self.save(update_fields=['status'])
        return is_valid

    @property
    def is_corrupted(self):
        """Check if the chunk is marked as corrupted."""
        return self.status == self.ChunkStatus.CORRUPTED

    def delete(self, *args, **kwargs):
        """Override delete to handle storage node space."""
        storage_node = self.storage_node
        super().delete(*args, **kwargs)
        # Update storage node's available space
        if storage_node:
            used_space = sum(
                chunk.size for chunk in 
                Chunk.objects.filter(storage_node=storage_node)
            )
            storage_node.update_storage_metrics(used_space)
    

class FileVersion(models.Model):
    """Tracks different versions of a file."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ForeignKey(
        File,
        related_name='versions',
        on_delete=models.CASCADE,
        db_index=True
    )
    version_number = models.PositiveIntegerField()
    size = models.BigIntegerField(help_text="File size in bytes")
    checksum = models.CharField(max_length=64, help_text="SHA-256 checksum")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = ('file', 'version_number')
        verbose_name = 'File Version'
        verbose_name_plural = 'File Versions'

    def __str__(self):
        return f"v{self.version_number} of {self.file.name}"

    def get_absolute_url(self):
        """Get URL for file version detail view."""
        return reverse('storage:file-version-detail', args=[str(self.id)])

    def restore(self):
        """Restore this version of the file."""
        self.file.size = self.size
        self.file.checksum = self.checksum
        self.file.save(update_fields=['size', 'checksum'])
        return self.file
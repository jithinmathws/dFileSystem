import hashlib
import os
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from config.exceptions import ValidationError, NotFound
from .models import StorageNode, File, Chunk, FileVersion
from .serializers import (
    StorageNodeSerializer, 
    FileSerializer, 
    ChunkSerializer,
    FileUploadSerializer,
    FileVersionSerializer
)

class StorageNodeViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing storage nodes.
    """
    queryset = StorageNode.objects.filter(is_active=True)
    serializer_class = StorageNodeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Optionally filter by active status."""
        queryset = super().get_queryset()
        if self.request.query_params.get('include_inactive') == 'true':
            return StorageNode.objects.all()
        return queryset

    @action(detail=True, methods=['post'])
    def heartbeat(self, request, pk=None):
        """Update the last_heartbeat timestamp for a storage node."""
        node = self.get_object()
        node.update_heartbeat()
        return Response({'status': 'heartbeat received'})

    @action(detail=True, methods=['get'])
    def chunks(self, request, pk=None):
        """Get all chunks stored on this node."""
        node = self.get_object()
        chunks = Chunk.objects.filter(storage_node=node)
        serializer = ChunkSerializer(chunks, many=True)
        return Response(serializer.data)

class FileViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing files and their chunks.
    """
    queryset = File.objects.filter(is_deleted=False)
    serializer_class = FileSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter files by the current user."""
        return self.queryset.filter(user=self.request.user)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        file_obj = request.FILES['file']
        chunk_size = serializer.validated_data['chunk_size']
        replication_factor = serializer.validated_data['replication_factor']

        # Calculate file checksum
        sha256_hash = hashlib.sha256()
        for chunk in file_obj.chunks(chunk_size=8192):
            sha256_hash.update(chunk)
        file_checksum = sha256_hash.hexdigest()

        # Check if file already exists
        existing_file = File.objects.filter(
            checksum=file_checksum,
            user=request.user
        ).first()
        
        if existing_file:
            return Response(
                {'error': 'File already exists', 'file_id': str(existing_file.id)},
                status=status.HTTP_409_CONFLICT
            )

        # Create file record
        file_record = File.objects.create(
            name=file_obj.name,
            size=file_obj.size,
            checksum=file_checksum,
            content_type=file_obj.content_type,
            user=request.user
        )

        # TODO: Implement chunking and distribution logic
        # 1. Split file into chunks
        # 2. Find available storage nodes
        # 3. Store chunks with replication
        # 4. Create chunk records

        return Response(
            FileSerializer(file_record).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download the file by combining its chunks."""
        file_obj = self.get_object()
        # TODO: Implement file reconstruction from chunks
        raise NotImplementedError("File download not implemented yet")

    @action(detail=True, methods=['post'])
    def create_version(self, request, pk=None):
        """Create a new version of the file."""
        file_obj = self.get_object()
        version = FileVersion.objects.create(
            file=file_obj,
            version_number=file_obj.versions.count() + 1,
            size=file_obj.size,
            checksum=file_obj.checksum,
            created_by=request.user,
            notes=request.data.get('notes', '')
        )
        return Response(
            FileVersionSerializer(version).data,
            status=status.HTTP_201_CREATED
        )

class ChunkViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing chunks.
    """
    serializer_class = ChunkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter chunks by the current user's files."""
        return Chunk.objects.filter(file__user=self.request.user)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify the integrity of a chunk."""
        chunk = self.get_object()
        calculated_checksum = self._calculate_checksum(chunk)
        chunk.stored_checksum = calculated_checksum
        chunk.last_verified_at = timezone.now()
        chunk.save(update_fields=['stored_checksum', 'last_verified_at'])

        is_valid = chunk.verify_checksum(calculated_checksum)
        return Response({'valid': is_valid})

    def _calculate_checksum(self, chunk):
        """Calculate checksum for a chunk's content."""
        # TODO: Implement actual chunk content checksum calculation
        return chunk.checksum

class FileVersionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing file versions.
    """
    serializer_class = FileVersionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter versions by the current user's files."""
        return FileVersion.objects.filter(file__user=self.request.user)

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restore a specific version of a file."""
        version = self.get_object()
        file_obj = version.restore()
        return Response(FileSerializer(file_obj).data)
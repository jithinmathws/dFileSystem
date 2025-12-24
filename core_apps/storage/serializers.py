from rest_framework import serializers
from .models import StorageNode, File, Chunk, FileVersion

class StorageNodeSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()
    available_gb = serializers.SerializerMethodField()
    capacity_gb = serializers.SerializerMethodField()

    class Meta:
        model = StorageNode
        fields = [
            'id', 'name', 'host', 'port', 
            'capacity', 'capacity_gb', 'available', 'available_gb',
            'is_active', 'status', 'last_heartbeat', 'created_at'
        ]
        read_only_fields = ['id', 'last_heartbeat', 'available', 'created_at']

    def get_status(self, obj):
        return 'active' if obj.is_active else 'inactive'

    def get_available_gb(self, obj):
        return obj.available / (1024 ** 3)

    def get_capacity_gb(self, obj):
        return obj.capacity / (1024 ** 3)

class FileSerializer(serializers.ModelSerializer):
    file_type = serializers.SerializerMethodField()
    size_mb = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(read_only=True)

    class Meta:
        model = File
        fields = [
            'id', 'name', 'size', 'size_mb', 'checksum', 'content_type',
            'file_type', 'user', 'is_available', 'is_deleted', 'deleted_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'is_available',
            'file_type', 'size_mb'
        ]
        extra_kwargs = {
            'user': {'required': False}  # Will be set in the view
        }

    def get_file_type(self, obj):
        return obj.get_file_type()

    def get_size_mb(self, obj):
        return obj.size / (1024 * 1024) if obj.size else 0

class ChunkSerializer(serializers.ModelSerializer):
    file_name = serializers.CharField(source='file.name', read_only=True)
    storage_node_name = serializers.CharField(source='storage_node.name', read_only=True)
    is_corrupted = serializers.BooleanField(read_only=True)
    object_key = serializers.CharField(source='object_key', read_only=True)
    stored_checksum = serializers.CharField(source='stored_checksum', read_only=True)
    last_verified_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Chunk
        fields = [
            'id', 'file', 'file_name', 'storage_node', 'storage_node_name',
            'object_key', 'chunk_number', 'size', 'checksum', 'is_primary', 'status',
            'is_corrupted', 'stored_checksum', 'last_verified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'file_name', 'storage_node_name', 'is_corrupted',
            'created_at', 'updated_at', 'object_key', 'stored_checksum', 'last_verified_at'
        ]

class FileVersionSerializer(serializers.ModelSerializer):
    size_mb = serializers.SerializerMethodField()
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = FileVersion
        fields = [
            'id', 'file', 'version_number', 'size', 'size_mb', 'checksum',
            'created_by', 'created_by_username', 'created_at', 'notes'
        ]
        read_only_fields = ['id', 'created_at', 'created_by', 'created_by_username']

    def get_size_mb(self, obj):
        return obj.size / (1024 * 1024) if obj.size else 0

class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    replication_factor = serializers.IntegerField(min_value=1, max_value=3, default=2)
    chunk_size = serializers.IntegerField(
        min_value=1024, 
        default=1024*1024,  # Default 1MB chunks
        help_text="Chunk size in bytes"
    )

    def validate_chunk_size(self, value):
        """Ensure chunk size is a multiple of 4KB for alignment."""
        if value % 4096 != 0:
            raise serializers.ValidationError("Chunk size must be a multiple of 4KB (4096 bytes)")
        return value
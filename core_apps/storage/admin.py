from django.contrib import admin
from django.utils.html import format_html
from .models import StorageNode, File, Chunk, FileVersion

@admin.register(StorageNode)
class StorageNodeAdmin(admin.ModelAdmin):
    list_display = ('name', 'host', 'port', 'available_gb', 'capacity_gb', 'status', 'last_heartbeat')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'host')
    readonly_fields = ('created_at', 'last_heartbeat')
    fieldsets = (
        ('Node Information', {
            'fields': ('name', 'host', 'port', 'is_active')
        }),
        ('Storage Information', {
            'fields': ('capacity', 'available', 'created_at', 'last_heartbeat')
        }),
    )

    def status(self, obj):
        return '🟢 Active' if obj.is_active else '🔴 Inactive'
    status.short_description = 'Status'

    def available_gb(self, obj):
        return f"{obj.available / (1024**3):.2f} GB"
    available_gb.short_description = 'Available'

    def capacity_gb(self, obj):
        return f"{obj.capacity / (1024**3):.2f} GB"
    capacity_gb.short_description = 'Capacity'

@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ('name', 'file_type', 'size_mb', 'user', 'created_at', 'is_deleted')
    list_filter = ('is_deleted', 'content_type', 'created_at')
    search_fields = ('name', 'checksum', 'user__username')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at', 'file_preview')
    fieldsets = (
        ('File Information', {
            'fields': ('name', 'user', 'size', 'checksum', 'content_type')
        }),
        ('Status', {
            'fields': ('is_deleted', 'deleted_at', 'created_at', 'updated_at')
        }),
        ('Preview', {
            'fields': ('file_preview',),
            'classes': ('collapse',)
        }),
    )

    def file_type(self, obj):
        return obj.get_file_type().title()
    file_type.short_description = 'Type'

    def size_mb(self, obj):
        return f"{obj.size / (1024 * 1024):.2f} MB"
    size_mb.short_description = 'Size'

    def file_preview(self, obj):
        if obj.is_image:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;" />',
                obj.get_absolute_url()
            )
        return "Preview not available"
    file_preview.short_description = 'Preview'

class ChunkInline(admin.TabularInline):
    model = Chunk
    extra = 0
    readonly_fields = ('size', 'checksum', 'status', 'created_at')
    fields = ('chunk_number', 'storage_node', 'object_key', 'size', 'checksum', 'is_primary', 'status', 'created_at')
    show_change_link = True

@admin.register(Chunk)
class ChunkAdmin(admin.ModelAdmin):
    list_display = ('id', 'file_name', 'chunk_number', 'storage_node', 'object_key', 'size_mb', 'status', 'is_primary')
    list_filter = ('status', 'is_primary', 'storage_node')
    search_fields = ('file__name', 'checksum')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Chunk Information', {
            'fields': ('file', 'chunk_number', 'storage_node', 'object_key', 'size', 'checksum')
        }),
        ('Status', {
            'fields': ('is_primary', 'status', 'created_at', 'updated_at')
        }),
    )

    def file_name(self, obj):
        return obj.file.name
    file_name.short_description = 'File'

    def size_mb(self, obj):
        return f"{obj.size / (1024 * 1024):.2f} MB"
    size_mb.short_description = 'Size'

class FileVersionInline(admin.TabularInline):
    model = FileVersion
    extra = 0
    readonly_fields = ('version_number', 'size', 'checksum', 'created_at', 'created_by')
    fields = ('version_number', 'size', 'checksum', 'created_at', 'created_by', 'notes')
    show_change_link = True

@admin.register(FileVersion)
class FileVersionAdmin(admin.ModelAdmin):
    list_display = ('version_number', 'file_name', 'size_mb', 'created_at', 'created_by')
    list_filter = ('created_at', 'created_by')
    search_fields = ('file__name', 'checksum')
    readonly_fields = ('created_at', 'version_number')
    fieldsets = (
        ('Version Information', {
            'fields': ('file', 'version_number', 'size', 'checksum')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'notes')
        }),
    )

    def file_name(self, obj):
        return obj.file.name
    file_name.short_description = 'File'

    def size_mb(self, obj):
        return f"{obj.size / (1024 * 1024):.2f} MB"
    size_mb.short_description = 'Size'

    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only on create
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

# Add inlines to FileAdmin
FileAdmin.inlines = [ChunkInline, FileVersionInline]
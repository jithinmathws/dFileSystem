from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

class StorageConfig(AppConfig):
    name = "core_apps.storage"
    verbose_name = _("Storage")

# ============================================================
# plugin/service_delete_system/__init__.py
#
# Exposes a single registration entry point used by
# handlers/__init__.py  →  register_all_handlers()
# ============================================================

from .handler import register_service_delete_plugin   # noqa: F401

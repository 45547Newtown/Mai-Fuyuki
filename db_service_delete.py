# ============================================================
# db_service_delete.py
# MongoDB layer for service-message auto-delete feature.
# Separate collection: service_delete  →  { chat_id, enabled }
# ============================================================

import motor

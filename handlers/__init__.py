from handlers.start import register_handlers
from plugin.lock_system import *
from plugin.welcome_system import *
from plugin.group_guard import *


def register_all_handlers(app):

    # Start Handler
    register_handlers(app)

    # Plugins auto loaded
    print("✅ All handlers loaded successfully")

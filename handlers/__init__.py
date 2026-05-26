from handlers.start import register_handlers
from plugin.lock_system import register_all_lock_plugins


def register_all_handlers(app):

    # Start commands
    register_handlers(app)

    # Lock system
    register_all_lock_plugins(app)

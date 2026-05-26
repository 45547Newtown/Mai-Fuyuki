from handlers.start import register_handlers

from plugin.lock_system import register_all_lock_plugins
from plugin.welcome_system import register_welcome_system


def register_all_handlers(app):

    # Start system
    register_handlers(app)

    # Lock system
    register_all_lock_plugins(app)

    # Welcome system
    register_welcome_system(app)

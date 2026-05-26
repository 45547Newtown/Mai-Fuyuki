from handlers.start import register_handlers
from handlers.group_commands import register_group_commands

from plugin.lock_system import register_all_lock_plugins
from plugin.welcome_system import register_welcome_system
from plugin.group_guard import register_group_guard


def register_all_handlers(app):
    register_handlers(app)
    register_group_commands(app)
    register_all_lock_plugins(app)
    register_welcome_system(app)
    register_group_guard(app)
    print("✅ All handlers loaded successfully")
    

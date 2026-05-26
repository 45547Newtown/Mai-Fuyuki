from handlers.start import register_handlers
from plugin.group_guard import register_group_guard


def register_all_handlers(app):

    register_handlers(app)

    register_group_guard(app)

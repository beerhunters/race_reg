from aiogram import Dispatcher, Bot
from handlers.simple_registration import register_simple_registration_handlers
from handlers.admin_participant_handlers import register_admin_participant_handlers
from handlers.notification_handlers import register_notification_handlers
from handlers.info_media_handlers import register_info_media_handlers
from handlers.settings_handlers import register_settings_handlers
from handlers.misc_handlers import register_misc_handlers
from handlers.profile_edit_handlers import register_profile_edit_handlers
from handlers.waitlist_handlers import register_waitlist_handlers
from handlers.archive_handlers import register_archive_handlers
from handlers.cluster_handlers import register_cluster_handlers
from handlers.backup_handlers import register_backup_handlers
from handlers.team_handlers import register_team_handlers
from logging_config import get_logger, log

logger = get_logger(__name__)


def register_all_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    log.system_event("Handler registration started")
    register_simple_registration_handlers(dp, bot, admin_id)
    register_admin_participant_handlers(dp, bot, admin_id)
    register_notification_handlers(dp, bot, admin_id)
    register_info_media_handlers(dp, bot, admin_id)
    register_settings_handlers(dp, bot, admin_id)
    register_profile_edit_handlers(dp, bot, admin_id)
    register_waitlist_handlers(dp, bot, admin_id)
    register_archive_handlers(dp, bot, admin_id)
    register_cluster_handlers(dp, bot, admin_id)
    register_backup_handlers(dp, bot, admin_id)
    register_team_handlers(dp, bot, admin_id)
    register_misc_handlers(dp, bot, admin_id)
    log.system_event("All handlers registered successfully")

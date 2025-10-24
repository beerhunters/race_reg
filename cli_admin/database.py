"""
Обертка для работы с базой данных
Использует функции из database.py корневой директории
"""

import sys
import os
from pathlib import Path

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

# Переопределяем DB_PATH перед импортом database.py
from cli_admin.config import DB_PATH as CLI_DB_PATH

# Устанавливаем правильный путь к БД в переменной окружения
# чтобы database.py мог его использовать
os.environ['DB_PATH'] = CLI_DB_PATH

# ВАЖНО: Переопределяем DB_PATH в модуле database перед импортом функций
import database as db_module
db_module.DB_PATH = CLI_DB_PATH

# Импортируем все функции из основного database.py
from database import (
    # Инициализация
    init_db,

    # Участники
    get_all_participants,
    get_participant_by_user_id,
    get_participant_count,
    get_participant_count_by_role,
    add_participant,
    add_participant_with_team,
    update_participant_field,
    delete_participant,
    update_payment_status,
    set_bib_number,
    set_result,
    set_participant_category,
    set_participant_cluster,
    clear_all_categories,
    clear_all_clusters,
    get_participants_by_role,
    get_participants_with_categories,
    get_participants_for_excel_export,

    # Pending регистрации
    add_pending_registration,
    get_pending_registrations,
    delete_pending_registration,

    # Настройки
    get_setting,
    set_setting,

    # Лист ожидания
    add_to_waitlist,
    get_waitlist_by_role,
    get_waitlist_position,
    remove_from_waitlist,
    notify_waitlist_users,
    confirm_waitlist_participation,
    decline_waitlist_participation,
    get_expired_waitlist_notifications,
    expire_waitlist_notifications,
    is_user_in_waitlist,
    get_waitlist_by_user_id,
    promote_waitlist_user_by_id,
    demote_participant_to_waitlist,

    # Запросы на редактирование
    create_edit_request,
    get_pending_edit_requests,
    approve_edit_request,
    reject_edit_request,

    # Команды
    create_team,
    get_all_teams,
    get_team_by_id,
    get_team_by_member,
    set_team_result,
    delete_team,
    clear_all_teams,
    count_team_members,
    count_complete_teams,
    get_teams_from_participants,
    get_team_member_in_waitlist,

    # Результаты и архивы
    save_race_to_db,
    clear_participants,
    get_past_races,
    get_race_data,
    archive_race_data,
    get_user_race_history,
    get_latest_user_result,
    list_race_archives,
    is_current_event_active,

    # Трансферы слотов
    create_slot_transfer_request,
    get_slot_transfer_by_code,
    register_new_user_for_transfer,
    approve_slot_transfer,
    reject_slot_transfer,
    get_pending_slot_transfers,
    cancel_slot_transfer_request,

    # Пользователи бота
    add_or_update_bot_user,
    get_all_bot_users,
    get_historical_participants,

    # Номера
    add_bib_number_info,
    get_bib_number_description,
    get_all_bib_numbers_info,
    clear_bib_numbers_info,

    # Утилиты
    cancel_user_participation,
    cleanup_blocked_user,
    get_participant_by_team_invite_code,
)

__all__ = [
    # Экспортируем все импортированные функции
    'init_db',
    'get_all_participants',
    'get_participant_by_user_id',
    'get_participant_count',
    'get_participant_count_by_role',
    'add_participant',
    'add_participant_with_team',
    'update_participant_field',
    'delete_participant',
    'update_payment_status',
    'set_bib_number',
    'set_result',
    'set_participant_category',
    'set_participant_cluster',
    'clear_all_categories',
    'clear_all_clusters',
    'get_participants_by_role',
    'get_participants_with_categories',
    'get_participants_for_excel_export',
    'add_pending_registration',
    'get_pending_registrations',
    'delete_pending_registration',
    'get_setting',
    'set_setting',
    'add_to_waitlist',
    'get_waitlist_by_role',
    'get_waitlist_position',
    'remove_from_waitlist',
    'notify_waitlist_users',
    'confirm_waitlist_participation',
    'decline_waitlist_participation',
    'get_expired_waitlist_notifications',
    'expire_waitlist_notifications',
    'is_user_in_waitlist',
    'get_waitlist_by_user_id',
    'promote_waitlist_user_by_id',
    'demote_participant_to_waitlist',
    'create_edit_request',
    'get_pending_edit_requests',
    'approve_edit_request',
    'reject_edit_request',
    'create_team',
    'get_all_teams',
    'get_team_by_id',
    'get_team_by_member',
    'set_team_result',
    'delete_team',
    'clear_all_teams',
    'count_team_members',
    'count_complete_teams',
    'get_teams_from_participants',
    'get_team_member_in_waitlist',
    'save_race_to_db',
    'clear_participants',
    'get_past_races',
    'get_race_data',
    'archive_race_data',
    'get_user_race_history',
    'get_latest_user_result',
    'list_race_archives',
    'is_current_event_active',
    'create_slot_transfer_request',
    'get_slot_transfer_by_code',
    'register_new_user_for_transfer',
    'approve_slot_transfer',
    'reject_slot_transfer',
    'get_pending_slot_transfers',
    'cancel_slot_transfer_request',
    'add_or_update_bot_user',
    'get_all_bot_users',
    'get_historical_participants',
    'add_bib_number_info',
    'get_bib_number_description',
    'get_all_bib_numbers_info',
    'clear_bib_numbers_info',
    'cancel_user_participation',
    'cleanup_blocked_user',
    'get_participant_by_team_invite_code',
]

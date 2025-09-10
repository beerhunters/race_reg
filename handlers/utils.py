import json
import logging.handlers
import os
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class CustomRotatingFileHandler(logging.handlers.BaseRotatingHandler):
    def __init__(self, filename, maxBytes, encoding=None):
        super().__init__(filename, mode="a", encoding=encoding)
        self.maxBytes = maxBytes
        self.backup_file = f"{filename}.1"

    def shouldRollover(self, record):
        if (
            os.path.exists(self.baseFilename)
            and os.path.getsize(self.baseFilename) > self.maxBytes
        ):
            return True
        return False

    def doRollover(self):
        if self.stream:
            self.stream.close()
            self.stream = None
        if os.path.exists(self.baseFilename):
            if os.path.exists(self.backup_file):
                os.remove(self.backup_file)
            os.rename(self.baseFilename, self.backup_file)
        self.stream = self._open()


os.makedirs("/app/logs", exist_ok=True)
log_level = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        CustomRotatingFileHandler("/app/logs/bot.log", maxBytes=10 * 1024 * 1024),
    ],
)
logger = logging.getLogger(__name__)

try:
    with open("messages.json", "r", encoding="utf-8") as f:
        messages = json.load(f)
    logger.info("Файл messages.json успешно загружен")
except FileNotFoundError:
    logger.error("Файл messages.json не найден")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Ошибка при разборе messages.json: {e}")
    raise

try:
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    logger.info("Файл config.json успешно загружен")
except FileNotFoundError:
    logger.error("Файл config.json не найден")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Ошибка при разборе config.json: {e}")
    raise

if config.get("log_level") not in log_level:
    logger.error(
        f"Недопустимое значение log_level: {config.get('log_level')}. Используется ERROR."
    )
    logging.getLogger().setLevel(logging.ERROR)
else:
    logging.getLogger().setLevel(log_level[config["log_level"]])
    logger.info(f"Установлен уровень логирования: {config['log_level']}")


class RegistrationForm(StatesGroup):
    waiting_for_name = State()
    waiting_for_role = State()
    waiting_for_target_time = State()
    waiting_for_gender = State()
    waiting_for_info_message = State()
    waiting_for_afisha_image = State()
    waiting_for_sponsor_image = State()
    waiting_for_notify_unpaid_message = State()
    waiting_for_reg_end_date = State()
    waiting_for_price = State()
    waiting_for_paid_id = State()
    waiting_for_bib = State()
    waiting_for_remove_id = State()
    waiting_for_runners = State()
    waiting_for_result = State()
    waiting_for_race_date = State()
    waiting_for_protocol_type = State()
    waiting_for_gender_protocol = State()
    waiting_for_notify_all_interacted_message = State()
    waiting_for_notify_all_interacted_photo = State()
    
    # Participant notification states
    waiting_for_notify_participants_message = State()
    
    # Advanced notification states
    waiting_for_notify_audience_selection = State()
    waiting_for_notify_advanced_message = State()
    waiting_for_notify_advanced_photo = State()
    
    # Results recording states
    waiting_for_results_start = State()
    waiting_for_participant_result = State()
    waiting_for_results_send_confirmation = State()
    
    # Profile editing states
    waiting_for_edit_field_selection = State()
    waiting_for_new_name = State()
    waiting_for_new_target_time = State()
    waiting_for_new_gender = State()
    waiting_for_edit_confirmation = State()
    
    # Archive states
    waiting_for_archive_date = State()
    
    # Cluster and category states
    waiting_for_category_assignment = State()
    waiting_for_cluster_assignment = State()
    
    # Sequential bib assignment states
    waiting_for_bib_assignment = State()
    
    processed = State()


def create_role_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=messages["role_runner"], callback_data="role_runner"
                )
            ],
            [
                InlineKeyboardButton(
                    text=messages["role_volunteer"], callback_data="role_volunteer"
                )
            ],
        ]
    )
    return keyboard


def create_register_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=messages["register_button"], callback_data="start_registration"
                )
            ]
        ]
    )
    return keyboard


def create_confirmation_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=messages["confirm_button"],
                    callback_data="confirm_participation",
                ),
                InlineKeyboardButton(
                    text=messages["decline_button"],
                    callback_data="decline_participation",
                ),
            ]
        ]
    )
    return keyboard


def create_gender_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=messages["gender_male"], callback_data="male"
                ),
                InlineKeyboardButton(
                    text=messages["gender_female"], callback_data="female"
                ),
            ],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
        ]
    )
    return keyboard


def create_protocol_keyboard():
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=messages["protocol_all_button"], callback_data="protocol_all"
                ),
                InlineKeyboardButton(
                    text=messages["protocol_by_gender_button"],
                    callback_data="protocol_by_gender",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🏆 По категориям", callback_data="protocol_by_category"
                ),
                InlineKeyboardButton(
                    text="🎯 По кластерам", callback_data="protocol_by_cluster"
                ),
            ],
        ]
    )
    return keyboard


def create_edit_profile_keyboard():
    """Create keyboard for profile editing field selection"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Имя", callback_data="edit_name"),
                InlineKeyboardButton(text="⏰ Целевое время", callback_data="edit_target_time"),
            ],
            [
                InlineKeyboardButton(text="👤 Пол", callback_data="edit_gender"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit"),
            ],
        ]
    )
    return keyboard


def create_admin_edit_approval_keyboard(request_id: int):
    """Create keyboard for admin to approve/reject edit requests"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_edit_{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_edit_{request_id}"),
            ],
        ]
    )
    return keyboard


def create_edit_confirmation_keyboard():
    """Create keyboard for user to confirm their edit request"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_edit"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit"),
            ],
        ]
    )
    return keyboard


def create_admin_commands_keyboard():
    """Create admin commands keyboard"""
    commands = [
        InlineKeyboardButton(
            text="👥 Участники", callback_data="category_participants"
        ),
        InlineKeyboardButton(
            text="🏁 Управление гонкой", callback_data="category_race"
        ),
        InlineKeyboardButton(
            text="📢 Уведомления", callback_data="category_notifications"
        ),
        InlineKeyboardButton(
            text="⚙️ Настройки", callback_data="category_settings"
        ),
        InlineKeyboardButton(
            text="🎨 Медиа", callback_data="category_media"
        ),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])


def create_participants_category_keyboard():
    """Create participants category keyboard"""
    commands = [
        InlineKeyboardButton(
            text="📋 Список участников", callback_data="admin_participants"
        ),
        InlineKeyboardButton(
            text="⏳ Незавершённые регистрации", callback_data="admin_pending"
        ),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
        InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data="admin_paid"),
        InlineKeyboardButton(text="🔢 Присвоить номер", callback_data="admin_set_bib"),
        InlineKeyboardButton(text="📢 Уведомить о номерах", callback_data="admin_notify_bibs"),
        InlineKeyboardButton(text="🏃 Записать результаты", callback_data="admin_results"),
        InlineKeyboardButton(
            text="🗑 Удалить участника", callback_data="admin_remove"
        ),
        InlineKeyboardButton(text="📄 Экспорт в CSV", callback_data="admin_export"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])


def create_race_category_keyboard():
    """Create race category keyboard"""
    commands = [
        InlineKeyboardButton(text="🏆 Протокол", callback_data="admin_protocol"),
        InlineKeyboardButton(text="📂 Архивировать гонку", callback_data="admin_archive_race"),
        InlineKeyboardButton(text="📈 Прошлые гонки", callback_data="admin_past_races"),
        InlineKeyboardButton(text="📋 Очередь ожидания", callback_data="admin_waitlist"),
        InlineKeyboardButton(text="🎯 Кластеры", callback_data="admin_clusters"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])


def create_notifications_category_keyboard():
    """Create notifications category keyboard"""
    commands = [
        InlineKeyboardButton(text="📢 Уведомить участников", callback_data="admin_notify_participants"),
        InlineKeyboardButton(text="✏️ Уведомить с текстом/фото", callback_data="admin_notify_with_text"),
        InlineKeyboardButton(text="💰 Напомнить об оплате", callback_data="admin_notify_unpaid"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])


def create_notify_audience_keyboard():
    """Create keyboard for selecting notification audience"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Участники", callback_data="audience_participants"),
                InlineKeyboardButton(text="⏳ Pending", callback_data="audience_pending"),
            ],
            [
                InlineKeyboardButton(text="📋 Очередь ожидания", callback_data="audience_waitlist"),
                InlineKeyboardButton(text="📂 Из архивов", callback_data="audience_archives"),
            ],
            [
                InlineKeyboardButton(text="🌍 Все группы", callback_data="audience_all"),
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_notify"),
            ],
        ]
    )
    return keyboard


def create_settings_category_keyboard():
    """Create settings category keyboard"""
    commands = [
        InlineKeyboardButton(text="🔢 Изменить лимит участников", callback_data="admin_edit_runners"),
        InlineKeyboardButton(text="📅 Установить дату окончания регистрации", callback_data="admin_set_reg_end_date"),
        InlineKeyboardButton(text="💰 Изменить цену участия", callback_data="admin_set_price"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])


def create_media_category_keyboard():
    """Create media category keyboard"""
    commands = [
        InlineKeyboardButton(text="ℹ️ Обновить информационное сообщение", callback_data="admin_info"),
        InlineKeyboardButton(text="🖼 Создать афишу", callback_data="admin_create_afisha"),
        InlineKeyboardButton(text="🤝 Обновить спонсорское изображение", callback_data="admin_update_sponsor"),
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
    ]
    return InlineKeyboardMarkup(inline_keyboard=[[cmd] for cmd in commands])


def get_participation_fee_text():
    """Get formatted participation fee text from database"""
    try:
        from database import get_setting
        fee = get_setting("participation_price")
        
        if fee is None:
            # Fallback to config if not set in database
            fee = config.get("participation_fee", 500)
        
        if fee == 0:
            return "(бесплатно)"
        else:
            return f"({fee} руб.)"
    except Exception as e:
        logger.warning(f"Ошибка получения цены из БД: {e}")
        # Fallback to config
        fee = config.get("participation_fee", 500)
        currency = config.get("participation_fee_currency", "р")
        return f"({fee}{currency})"


def create_clusters_category_keyboard():
    """Create clusters category keyboard"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Добавить категории", callback_data="admin_add_categories"),
                InlineKeyboardButton(text="🎯 Распределить кластеры", callback_data="admin_assign_clusters"),
            ],
            [
                InlineKeyboardButton(text="📋 Посмотреть распределение", callback_data="admin_view_distribution"),
            ],
            [
                InlineKeyboardButton(text="📢 Уведомить о распределении", callback_data="admin_notify_distribution"),
            ],
            [
                InlineKeyboardButton(text="📄 Создать документ", callback_data="admin_create_document"),
                InlineKeyboardButton(text="💾 Скачать CSV", callback_data="admin_download_csv"),
            ],
            [
                InlineKeyboardButton(text="🔄 Сбросить категории", callback_data="admin_clear_categories"),
                InlineKeyboardButton(text="🔄 Сбросить кластеры", callback_data="admin_clear_clusters"),
            ],
            [
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"),
            ],
        ]
    )
    return keyboard


def create_category_selection_keyboard():
    """Create keyboard for category selection"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🥇 Элита", callback_data="category_elite"),
                InlineKeyboardButton(text="🏃 Классика", callback_data="category_classic"),
            ],
            [
                InlineKeyboardButton(text="👩 Женский", callback_data="category_women"),
                InlineKeyboardButton(text="👥 Команда", callback_data="category_team"),
            ],
            [
                InlineKeyboardButton(text="⏭️ Пропустить", callback_data="category_skip"),
            ],
        ]
    )
    return keyboard


def create_cluster_selection_keyboard():
    """Create keyboard for cluster selection"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🅰️ Кластер A", callback_data="cluster_A"),
                InlineKeyboardButton(text="🅱️ Кластер B", callback_data="cluster_B"),
                InlineKeyboardButton(text="🅲 Кластер C", callback_data="cluster_C"),
            ],
            [
                InlineKeyboardButton(text="🅳 Кластер D", callback_data="cluster_D"),
                InlineKeyboardButton(text="🅴 Кластер E", callback_data="cluster_E"),
            ],
            [
                InlineKeyboardButton(text="⏭️ Пропустить", callback_data="cluster_skip"),
            ],
        ]
    )
    return keyboard


def create_bib_assignment_keyboard():
    """Create keyboard for bib number assignment"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏭️ Пропустить", callback_data="bib_skip"),
            ],
        ]
    )
    return keyboard


def create_bib_notification_confirmation_keyboard():
    """Create keyboard for bib notification confirmation"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, отправить", callback_data="confirm_bib_notify"),
                InlineKeyboardButton(text="❌ Нет, позже", callback_data="cancel_bib_notify"),
            ],
        ]
    )
    return keyboard

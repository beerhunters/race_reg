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
    waiting_for_notify_with_text_message = State()
    waiting_for_notify_with_text_photo = State()
    waiting_for_notify_unpaid_message = State()
    waiting_for_reg_end_date = State()
    waiting_for_paid_id = State()
    waiting_for_bib = State()
    waiting_for_remove_id = State()
    waiting_for_runners = State()
    waiting_for_result = State()
    waiting_for_race_date = State()
    waiting_for_protocol_type = State()
    waiting_for_gender_protocol = State()
    waiting_for_top_n = State()
    waiting_for_notify_all_interacted_message = State()
    waiting_for_notify_all_interacted_photo = State()
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
                    text=messages["protocol_top_n_button"],
                    callback_data="protocol_top_n",
                ),
            ],
        ]
    )
    return keyboard

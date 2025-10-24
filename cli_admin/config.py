"""
Конфигурация CLI приложения
"""

import os
from pathlib import Path

# Пути
PROJECT_ROOT = Path(__file__).parent.parent

# Определить дефолтные пути в зависимости от окружения
if os.path.exists("/app/data"):
    # Production окружение (Docker)
    DEFAULT_DB_PATH = "/app/data/race_participants.db"
    DEFAULT_BACKUP_DIR = "/app/backups"
    DEFAULT_EXPORT_DIR = "/app/exports"
else:
    # Локальное окружение
    # Проверить сначала в директории data/
    if os.path.exists(str(PROJECT_ROOT / "data" / "race_participants.db")):
        DEFAULT_DB_PATH = str(PROJECT_ROOT / "data" / "race_participants.db")
    else:
        DEFAULT_DB_PATH = str(PROJECT_ROOT / "race_participants.db")

    DEFAULT_BACKUP_DIR = str(PROJECT_ROOT / "backups")
    DEFAULT_EXPORT_DIR = str(PROJECT_ROOT / "exports")

DB_PATH = os.environ.get("BEERMILE_DB_PATH", DEFAULT_DB_PATH)
BACKUP_DIR = os.environ.get("BEERMILE_BACKUP_DIR", DEFAULT_BACKUP_DIR)
EXPORT_DIR = os.environ.get("BEERMILE_EXPORT_DIR", DEFAULT_EXPORT_DIR)

# Создание директорий если не существуют
try:
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    Path(EXPORT_DIR).mkdir(parents=True, exist_ok=True)
except (OSError, PermissionError):
    # Если не можем создать, используем текущую директорию
    if not os.path.exists(BACKUP_DIR):
        BACKUP_DIR = str(PROJECT_ROOT / "backups")
        Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    if not os.path.exists(EXPORT_DIR):
        EXPORT_DIR = str(PROJECT_ROOT / "exports")
        Path(EXPORT_DIR).mkdir(parents=True, exist_ok=True)

# Настройки отображения
MAX_TABLE_ROWS = 100
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT_SHORT = "%Y-%m-%d"

# Настройки пагинации
DEFAULT_PAGE_SIZE = 20

# Настройки бэкапов
BACKUP_RETENTION_DAYS = 30
AUTO_BACKUP_ENABLED = True

# Цвета (для rich)
COLOR_SUCCESS = "green"
COLOR_ERROR = "red"
COLOR_WARNING = "yellow"
COLOR_INFO = "cyan"
COLOR_PRIMARY = "blue"

# Эмодзи
EMOJI_SUCCESS = "✅"
EMOJI_ERROR = "❌"
EMOJI_WARNING = "⚠️"
EMOJI_INFO = "ℹ️"
EMOJI_RUNNER = "🏃"
EMOJI_VOLUNTEER = "🤝"
EMOJI_TEAM = "🏆"
EMOJI_BACKUP = "💾"
EMOJI_EXPORT = "📤"
EMOJI_STATS = "📊"

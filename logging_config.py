"""
Централизованная конфигурация логирования для проекта beermile_reg.
Настройка уровня логирования из config.json.
"""

import json
import logging.handlers
import os
import sys
import asyncio
from typing import Dict, Any, Optional
import traceback
import threading


class ColorCodes:
    """ANSI цветовые коды для терминала."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Основные цвета
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Яркие цвета
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'


class ColoredFormatter(logging.Formatter):
    """Цветной форматтер для консольного вывода с эмодзи."""
    
    # Эмодзи и цвета для уровней логирования
    LEVEL_CONFIGS = {
        'DEBUG': {
            'emoji': '🔍',
            'color': ColorCodes.CYAN,
            'name_color': ColorCodes.BRIGHT_CYAN
        },
        'INFO': {
            'emoji': '💡',
            'color': ColorCodes.GREEN,
            'name_color': ColorCodes.BRIGHT_GREEN
        },
        'WARNING': {
            'emoji': '⚠️',
            'color': ColorCodes.YELLOW,
            'name_color': ColorCodes.BRIGHT_YELLOW
        },
        'ERROR': {
            'emoji': '❌',
            'color': ColorCodes.RED,
            'name_color': ColorCodes.BRIGHT_RED
        },
        'CRITICAL': {
            'emoji': '🚨',
            'color': ColorCodes.BRIGHT_RED + ColorCodes.BOLD,
            'name_color': ColorCodes.BRIGHT_RED + ColorCodes.BOLD
        }
    }
    
    def __init__(self):
        # Определяем, поддерживает ли терминал цвета
        self.use_colors = self._supports_color()
        
        # Базовый формат
        if self.use_colors:
            format_str = (
                f"{ColorCodes.BRIGHT_BLUE}%(asctime)s{ColorCodes.RESET} "
                f"%(level_emoji)s %(colored_levelname)s "
                f"{ColorCodes.BRIGHT_MAGENTA}%(name)s{ColorCodes.RESET} "
                f"%(colored_message)s"
            )
        else:
            format_str = "%(asctime)s %(level_emoji)s %(levelname)s %(name)s %(message)s"
            
        super().__init__(format_str, datefmt='%H:%M:%S')
    
    def _supports_color(self) -> bool:
        """Проверяет, поддерживает ли терминал цвета."""
        # Проверяем переменные окружения
        if os.getenv('NO_COLOR') or os.getenv('ANSI_COLORS_DISABLED'):
            return False
        
        # Проверяем, является ли stdout терминалом
        if not hasattr(sys.stdout, 'isatty') or not sys.stdout.isatty():
            return False
            
        # Проверяем TERM переменную
        term = os.getenv('TERM', '').lower()
        return 'color' in term or 'xterm' in term or term in ['screen', 'tmux']
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись лога с цветами и эмодзи."""
        level_config = self.LEVEL_CONFIGS.get(record.levelname, self.LEVEL_CONFIGS['INFO'])
        
        # Добавляем эмодзи уровня
        record.level_emoji = level_config['emoji']
        
        if self.use_colors:
            # Цветное имя уровня
            record.colored_levelname = (
                f"{level_config['name_color']}{record.levelname:8}{ColorCodes.RESET}"
            )
            
            # Цветное сообщение
            message_color = level_config['color']
            record.colored_message = f"{message_color}{record.getMessage()}{ColorCodes.RESET}"
        else:
            record.colored_levelname = f"{record.levelname:8}"
            record.colored_message = record.getMessage()
        
        return super().format(record)


class PlainFormatter(logging.Formatter):
    """Простой форматтер для файлового вывода с эмодзи но без цветов."""
    
    LEVEL_EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '💡', 
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def __init__(self):
        format_str = "%(asctime)s %(level_emoji)s %(levelname)-8s %(name)s %(message)s"
        super().__init__(format_str, datefmt='%Y-%m-%d %H:%M:%S')
    
    def format(self, record: logging.LogRecord) -> str:
        """Форматирует запись лога с эмодзи для файла."""
        record.level_emoji = self.LEVEL_EMOJIS.get(record.levelname, '💡')
        return super().format(record)


class CustomRotatingFileHandler(logging.handlers.BaseRotatingHandler):
    """Кастомный ротирующий обработчик файлов для логирования."""
    
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


class TelegramHandler(logging.Handler):
    """Обработчик для отправки ERROR и CRITICAL логов в Telegram группу."""
    
    def __init__(self, bot_instance=None, chat_id: Optional[str] = None):
        super().__init__()
        self.bot = bot_instance
        self.chat_id = chat_id or os.getenv('FOR_LOGS')
        self.setLevel(logging.ERROR)  # Отправляем только ERROR и CRITICAL
        self._message_queue = []
        self._queue_lock = threading.Lock()
        
        # Запускаем фоновую задачу для отправки сообщений
        self._sender_task = None
        
        # Счетчики ошибок для статистики
        self._error_counts = {}
        self._total_errors = 0
        
        # Анти-спам для сетевых ошибок
        self._network_error_timestamps = {}
        self._network_error_threshold = 60  # Не отправлять одинаковые сетевые ошибки чаще раз в минуту
    
    def set_bot(self, bot_instance):
        """Установка экземпляра бота после инициализации."""
        self.bot = bot_instance
        if bot_instance and self._sender_task is None:
            # Запускаем задачу отправки сообщений в фоне
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    self._sender_task = asyncio.create_task(self._message_sender())
                else:
                    # Планируем запуск задачи когда цикл станет активным
                    def start_sender():
                        if self.bot and self._sender_task is None:
                            self._sender_task = asyncio.create_task(self._message_sender())
                    
                    # Запускаем через call_soon_threadsafe когда цикл будет готов
                    try:
                        loop.call_soon_threadsafe(start_sender)
                    except RuntimeError:
                        pass
            except RuntimeError:
                # Цикл событий ещё не создан, задача будет запущена при первом сообщении
                pass
    
    def emit(self, record):
        """Обработка записи лога для отправки в Telegram."""
        if not self.chat_id or not self.bot:
            return
            
        try:
            # Фильтруем типичные сетевые ошибки Telegram API
            if self._should_skip_telegram_error(record):
                return
            
            # Обновляем статистику ошибок
            self._total_errors += 1
            error_key = f"{record.name}:{record.levelname}"
            self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
            
            # Форматируем сообщение
            message = self.format_telegram_message(record)
            
            # Добавляем сообщение в очередь
            with self._queue_lock:
                self._message_queue.append(message)
                
            # Запускаем отправку если бот доступен
            self._ensure_sender_task_running()
                    
        except Exception:
            # Не логируем ошибки отправки в Telegram, чтобы избежать рекурсии
            pass
    
    def _should_skip_telegram_error(self, record) -> bool:
        """Определяет, нужно ли пропустить отправку сетевых ошибок Telegram."""
        import time
        
        message_lower = record.getMessage().lower()
        
        # Список типичных сетевых ошибок Telegram, которые не нужно отправлять
        telegram_network_errors = [
            'failed to fetch updates',
            'request timeout error',
            'bad gateway',
            'internal server error',
            'service unavailable',
            'telegram server says - bad gateway',
            'telegram server says - internal server error', 
            'telegram server says - service unavailable',
            'telegram server says - gateway timeout',
            'telegram server says - request timeout',
            'telegramnetworkerror',
            'telegramservererror',
            'connection timeout',
            'read timeout',
            'connect timeout',
            'network is unreachable',
            'connection reset by peer',
            'ssl handshake failed'
        ]
        
        # Проверяем aiogram dispatcher ошибки
        if 'aiogram.dispatcher' in record.name or 'aiogram.client' in record.name:
            matched_error = None
            for error in telegram_network_errors:
                if error in message_lower:
                    matched_error = error
                    break
            
            if matched_error:
                # Проверяем анти-спам для конкретного типа ошибки
                current_time = time.time()
                last_time = self._network_error_timestamps.get(matched_error, 0)
                
                if current_time - last_time < self._network_error_threshold:
                    # Ошибка была недавно, пропускаем
                    return True
                else:
                    # Обновляем время последней отправки
                    self._network_error_timestamps[matched_error] = current_time
                    return False  # Отправляем первую за интервал
            
        return False
    
    def format_telegram_message(self, record) -> str:
        """Форматирование сообщения для Telegram."""
        from datetime import datetime
        import pytz
        
        level_emoji = {
            'ERROR': '❌',
            'CRITICAL': '🔥'
        }.get(record.levelname, '⚠️')
        
        # Время в московском часовом поясе
        moscow_tz = pytz.timezone("Europe/Moscow")
        error_time = datetime.fromtimestamp(record.created, moscow_tz)
        
        message = f"{level_emoji} <b>{record.levelname} ОШИБКА</b>\n\n"
        message += f"🕐 <b>Время:</b> {error_time.strftime('%d.%m.%Y %H:%M:%S')} МСК\n"
        message += f"📂 <b>Модуль:</b> <code>{record.name}</code>\n"
        message += f"📁 <b>Функция:</b> <code>{record.funcName}:{record.lineno}</code>\n"
        message += f"📝 <b>Сообщение:</b> {record.getMessage()}\n"
        
        # Добавляем информацию о типе ошибки, если есть
        if record.exc_info and record.exc_info[1]:
            exc_type = record.exc_info[0].__name__
            exc_value = str(record.exc_info[1])
            message += f"⚡ <b>Тип ошибки:</b> <code>{exc_type}</code>\n"
            if exc_value and exc_value != record.getMessage():
                # Ограничиваем длину значения ошибки
                if len(exc_value) > 200:
                    exc_value = exc_value[:200] + "... (truncated)"
                message += f"💬 <b>Детали:</b> <code>{exc_value}</code>\n"
        
        # Добавляем контекстную информацию из aiogram, если доступна
        if 'aiogram' in record.name and 'update id=' in record.getMessage():
            import re
            update_match = re.search(r'update id=(\d+)', record.getMessage())
            bot_match = re.search(r'bot id=(\d+)', record.getMessage())
            if update_match:
                message += f"🤖 <b>Update ID:</b> <code>{update_match.group(1)}</code>\n"
            if bot_match:
                message += f"📡 <b>Bot ID:</b> <code>{bot_match.group(1)}</code>\n"
        
        # Добавляем информацию об окружении и статистику
        message += f"🖥 <b>Окружение:</b> {'🐳 Docker' if os.path.exists('/app') else '💻 Local'}\n"
        message += f"📊 <b>Всего ошибок:</b> {self._total_errors}\n"
        
        # Показываем частоту этого типа ошибок
        error_key = f"{record.name}:{record.levelname}"
        error_count = self._error_counts.get(error_key, 1)
        if error_count > 1:
            message += f"🔄 <b>Этот тип ошибки:</b> {error_count} раз\n"
        
        # Добавляем рекомендации по исправлению частых ошибок
        error_message_lower = record.getMessage().lower()
        
        # Специальная обработка для сетевых ошибок Telegram
        telegram_network_errors = ['failed to fetch updates', 'request timeout', 'bad gateway', 'internal server error']
        is_network_error = any(err in error_message_lower for err in telegram_network_errors)
        
        if is_network_error and ('aiogram.dispatcher' in record.name or 'aiogram.client' in record.name):
            message += f"🌐 <b>Сетевая ошибка Telegram API</b>\n"
            message += f"⏰ <b>Анти-спам:</b> Аналогичные ошибки игнорируются {self._network_error_threshold} сек\n"
            message += f"💡 <b>Совет:</b> Обычно исчезает сама - проблемы с серверами Telegram\n"
        elif 'zerodivisionerror' in error_message_lower:
            message += f"💡 <b>Совет:</b> Проверьте деление на ноль\n"
        elif 'keyerror' in error_message_lower:
            message += f"💡 <b>Совет:</b> Проверьте наличие ключа в словаре\n"
        elif 'attributeerror' in error_message_lower:
            message += f"💡 <b>Совет:</b> Проверьте существование атрибута объекта\n"
        elif 'connection' in error_message_lower or 'database' in error_message_lower:
            message += f"💡 <b>Совет:</b> Проверьте подключение к базе данных\n"
        elif 'telegram' in error_message_lower and ('bad request' in error_message_lower or 'forbidden' in error_message_lower):
            message += f"💡 <b>Совет:</b> Проверьте права бота или корректность запроса к Telegram API\n"
        
        # Добавляем трейсбек, если есть
        if record.exc_info:
            exc_text = ''.join(traceback.format_exception(*record.exc_info))
            
            # Извлекаем наиболее релевантные строки трейсбека
            lines = exc_text.split('\n')
            relevant_lines = []
            
            # Ищем строки из нашего кода (не из библиотек)
            for line in lines:
                if any(keyword in line.lower() for keyword in ['/app/', 'handlers/', 'database.py', 'main.py']):
                    relevant_lines.append(line)
            
            # Если найдены релевантные строки, показываем их
            if relevant_lines:
                relevant_trace = '\n'.join(relevant_lines[:5])  # Показываем до 5 строк
                if len(relevant_trace) > 500:
                    relevant_trace = relevant_trace[:500] + "\n... (truncated)"
                message += f"\n📍 <b>Наш код:</b>\n<code>{relevant_trace}</code>\n"
            
            # Ограничиваем размер полного трейсбека
            if len(exc_text) > 800:
                exc_text = exc_text[:800] + "\n... (truncated)"
            message += f"\n🔍 <b>Полный трейсбек:</b>\n<code>{exc_text}</code>"
        
        # Telegram ограничивает сообщения 4096 символами
        if len(message) > 4000:
            message = message[:4000] + "\n... (message truncated)"
            
        return message
    
    def _ensure_sender_task_running(self):
        """Убеждаемся, что задача отправки сообщений запущена."""
        if not self.bot or self._sender_task is not None:
            return
            
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self._sender_task = asyncio.create_task(self._message_sender())
        except RuntimeError:
            # Цикл событий не запущен, попробуем позже
            pass
    
    async def _message_sender(self):
        """Фоновая задача для отправки сообщений в Telegram."""
        while True:
            try:
                # Проверяем наличие сообщений в очереди
                messages_to_send = []
                with self._queue_lock:
                    if self._message_queue:
                        messages_to_send = self._message_queue.copy()
                        self._message_queue.clear()
                
                # Отправляем сообщения
                for message in messages_to_send:
                    try:
                        await self.bot.send_message(
                            chat_id=self.chat_id,
                            text=message,
                            parse_mode='HTML',
                            disable_notification=True
                        )
                        # Небольшая задержка между сообщениями
                        await asyncio.sleep(0.5)
                    except Exception:
                        # Игнорируем ошибки отправки
                        pass
                
                # Ждём перед следующей проверкой
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception:
                # Продолжаем работу даже при ошибках
                await asyncio.sleep(10)
    
    def close(self):
        """Закрытие обработчика."""
        if self._sender_task and not self._sender_task.done():
            self._sender_task.cancel()
        super().close()


class LoggingConfig:
    """Класс для управления конфигурацией логирования."""
    
    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.telegram_handler = None  # Для хранения Telegram обработчика
        self._setup_logging()
    
    def _load_config(self) -> Dict[str, Any]:
        """Загрузка конфигурации из config.json."""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config
        except FileNotFoundError:
            print(f"Файл {self.config_path} не найден, используем настройки по умолчанию")
            return {"log_level": "INFO"}
        except json.JSONDecodeError as e:
            print(f"Ошибка при разборе {self.config_path}: {e}, используем настройки по умолчанию")
            return {"log_level": "INFO"}
    
    def _setup_logging(self):
        """Настройка системы логирования."""
        # Создаем папку для логов (для Docker контейнера - /app/logs, для локальной разработки - ./logs)
        log_dir = "/app/logs" if os.path.exists("/app") else "./logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # Получаем уровень логирования из конфигурации
        log_level_str = self.config.get("log_level", "INFO")
        
        if log_level_str not in self.LOG_LEVELS:
            print(f"Недопустимое значение log_level: {log_level_str}. Используется INFO.")
            log_level = logging.INFO
        else:
            log_level = self.LOG_LEVELS[log_level_str]
        
        # Создаем форматтеры
        console_formatter = ColoredFormatter()
        file_formatter = PlainFormatter()
        
        # Создаем обработчики
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        
        log_file = os.path.join(log_dir, "bot.log")
        file_handler = CustomRotatingFileHandler(
            log_file, 
            maxBytes=10 * 1024 * 1024
        )
        file_handler.setFormatter(file_formatter)
        
        # Настраиваем root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Очищаем существующие обработчики
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Создаем Telegram обработчик
        self.telegram_handler = TelegramHandler()
        
        # Добавляем новые обработчики
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(self.telegram_handler)
        
        # Логируем успешную настройку
        logger = logging.getLogger(__name__)
        logger.info(f"Система логирования настроена. Уровень: {log_level_str}")
        
        # Проверяем доступность FOR_LOGS группы
        if self.telegram_handler.chat_id:
            logger.info(f"Telegram обработчик настроен для группы: {self.telegram_handler.chat_id}")
        else:
            logger.warning("FOR_LOGS не найден в переменных окружения - уведомления об ошибках не будут отправляться в Telegram")
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """Получение логгера с заданным именем."""
        return logging.getLogger(name)
    
    def get_log_level(self) -> str:
        """Получение текущего уровня логирования."""
        return self.config.get("log_level", "INFO")
    
    def set_bot_instance(self, bot_instance):
        """Установка экземпляра бота для Telegram обработчика."""
        if self.telegram_handler:
            self.telegram_handler.set_bot(bot_instance)
            logger = logging.getLogger(__name__)
            logger.info("🤖 Bot instance подключен к Telegram обработчику")


# Глобальный экземпляр для инициализации системы логирования
_logging_config = LoggingConfig()

# Функция для получения логгера (удобная обертка)
def get_logger(name: str = None) -> logging.Logger:
    """Получение логгера для модуля."""
    return _logging_config.get_logger(name)

# Функция для подключения бота к Telegram обработчику
def setup_telegram_logging(bot_instance):
    """Подключение экземпляра бота к Telegram обработчику логов."""
    _logging_config.set_bot_instance(bot_instance)

# Экспортируем уровни логирования для обратной совместимости
log_level = LoggingConfig.LOG_LEVELS


class LogHelper:
    """Вспомогательный класс для стандартизированного логирования."""

    def __init__(self, logger_name: str = None):
        self.logger = get_logger(logger_name)

    def command_received(self, command: str, user_id: int, username: str = None):
        """Логирование получения команды."""
        user_info = f"@{username}" if username else f"ID:{user_id}"
        self.logger.info(f"🎯 Command '{command}' received from user {user_info}")

    def admin_action(self, action: str, admin_id: int, details: str = None):
        """Логирование действий администратора."""
        msg = f"👑 Admin action: {action} (admin_id={admin_id})"
        if details:
            msg += f" - {details}"
        self.logger.info(msg)

    def database_operation(
        self,
        operation: str,
        table: str,
        user_id: int = None,
        success: bool = True,
        details: str = None,
    ):
        """Логирование операций с базой данных."""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        msg = f"🗃️  DB {operation} on {table}: {status}"
        if user_id:
            msg += f" (user_id={user_id})"
        if details:
            msg += f" - {details}"

        if success:
            self.logger.info(msg)
        else:
            self.logger.error(msg)

    def user_registration(
        self, user_id: int, username: str, name: str, role: str, success: bool = True
    ):
        """Логирование попыток регистрации пользователей."""
        user_info = f"{name} (@{username}, ID:{user_id})"
        if success:
            self.logger.info(f"🎉 User registration SUCCESS: {user_info} as {role}")
        else:
            self.logger.error(f"💔 User registration FAILED: {user_info} as {role}")

    def notification_sent(
        self, notification_type: str, user_id: int, success: bool = True, error: str = None
    ):
        """Логирование отправки уведомлений."""
        if success:
            self.logger.info(f"📤 Notification sent: {notification_type} to user_id={user_id}")
        else:
            self.logger.error(
                f"📵 Notification failed: {notification_type} to user_id={user_id} - {error}"
            )

    def system_event(self, event: str, details: str = None):
        """Логирование системных событий."""
        msg = f"🚀 System event: {event}"
        if details:
            msg += f" - {details}"
        self.logger.info(msg)

    def validation_error(self, field: str, value: str, error: str, user_id: int = None):
        """Логирование ошибок валидации."""
        msg = f"🔍 Validation error for {field}='{value}': {error}"
        if user_id:
            msg += f" (user_id={user_id})"
        self.logger.warning(msg)

    def handler_registration(self, handler_name: str):
        """Логирование регистрации обработчиков."""
        self.logger.info(f"⚙️  Handler registered: {handler_name}")


# Дополнительные функции для специфичных операций бота
class BotLogHelper(LogHelper):
    """Расширенный помощник логирования для специфичных операций бота."""
    
    def bot_startup(self, details: str = None):
        """Логирование запуска бота."""
        msg = f"🤖 Bot startup"
        if details:
            msg += f" - {details}"
        self.logger.info(msg)
    
    def user_blocked_cleanup(self, user_id: int, username: str, name: str):
        """Логирование очистки заблокированного пользователя."""
        self.logger.warning(f"🚫 User blocked cleanup: {name} (@{username}, ID:{user_id})")
    
    def registration_limit_reached(self, role: str, current: int, limit: int):
        """Логирование достижения лимита регистраций."""
        self.logger.warning(f"🔒 Registration limit reached for {role}: {current}/{limit}")
    
    def waitlist_notification(self, user_id: int, position: int):
        """Логирование уведомления из очереди ожидания."""
        self.logger.info(f"⏰ Waitlist notification sent to user_id={user_id} (position: {position})")
    
    def payment_status_change(self, user_id: int, old_status: str, new_status: str):
        """Логирование изменения статуса оплаты."""
        status_emoji = "💰" if new_status == "paid" else "⏳"
        self.logger.info(f"{status_emoji} Payment status changed for user_id={user_id}: {old_status} → {new_status}")
    
    def race_archived(self, date: str, participants: int):
        """Логирование архивирования гонки."""
        self.logger.info(f"📦 Race archived for date {date} with {participants} participants")
    
    def backup_created(self, backup_type: str, size: str = None):
        """Логирование создания резервной копии."""
        msg = f"💾 Backup created: {backup_type}"
        if size:
            msg += f" (size: {size})"
        self.logger.info(msg)
    
    def test_telegram_error_notification(self):
        """Тестирование отправки ошибок в Telegram группу."""
        self.logger.error("🧪 Тестовое ERROR сообщение для проверки Telegram уведомлений")
        
    def critical_system_error(self, error_msg: str, details: str = None):
        """Логирование критических системных ошибок."""
        msg = f"🔥 CRITICAL SYSTEM ERROR: {error_msg}"
        if details:
            msg += f" - {details}"
        self.logger.critical(msg)
    
    def get_error_statistics(self) -> str:
        """Получение статистики ошибок от Telegram обработчика."""
        if hasattr(_logging_config, 'telegram_handler') and _logging_config.telegram_handler:
            handler = _logging_config.telegram_handler
            
            stats = f"📊 <b>Статистика ошибок:</b>\n\n"
            stats += f"📈 <b>Всего ошибок:</b> {handler._total_errors}\n\n"
            
            if handler._error_counts:
                stats += f"🔍 <b>По типам:</b>\n"
                # Сортируем по количеству (убывание)
                sorted_errors = sorted(handler._error_counts.items(), key=lambda x: x[1], reverse=True)
                for error_type, count in sorted_errors[:10]:  # Показываем топ-10
                    module_name = error_type.split(':')[0].split('.')[-1]  # Берем последнюю часть модуля
                    level = error_type.split(':')[1]
                    stats += f"• <code>{module_name}</code> ({level}): {count} раз\n"
                
                if len(sorted_errors) > 10:
                    stats += f"• ... и ещё {len(sorted_errors) - 10} типов\n"
            else:
                stats += f"✅ <b>Ошибок пока не зарегистрировано</b>\n"
            
            return stats
        else:
            return "❌ Telegram обработчик недоступен"


# Глобальные экземпляры для удобства использования
log = BotLogHelper(__name__)
bot_log = BotLogHelper(__name__)
# Beer Mile Registration Bot

Телеграм-бот для автоматизации регистрации участников и волонтёров на гонку Beer Mile 2025, управления данными и уведомлениями. Поддерживает ограничения по времени регистрации (в часовом поясе MSK), лимиты участников, экспорт данных и работу с медиа.

## Основные возможности
- **Регистрация**: Пользователи могут зарегистрироваться как бегуны или волонтёры через команду `/start`.
- **Ограничение времени**: Регистрация закрывается по указанной дате и времени в MSK (настраивается через `/set_reg_end_date`).
- **Лимиты участников**: Ограничение числа бегунов и волонтёров (настраивается через `/edit_runners`).
- **Админ-команды**: Управление участниками, экспорт данных в CSV, настройка сообщений и медиа.
- **Уведомления**: Массовые уведомления для всех или неоплативших участников.
- **Логирование**: Ротация логов с настраиваемым уровнем логирования.
- **База данных**: SQLite для хранения данных участников и настроек.

## Требования
- Python 3.8+
- Docker и Docker Compose (для контейнеризации)
- Зависимости (см. `requirements.txt`):
  - `aiogram==3.4.1`
  - `python-dotenv`
  - `jq`
  - `pytz`
- SQLite (встроен в Python, но требуется `sqlite3` для CLI в Docker)

## Быстрый старт

### Запуск через Docker
1. Установите [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/).
2. Создайте файл `.env` в корне проекта:
   ```env
   BOT_TOKEN=ваш_токен
   ADMIN_ID=123456789
   ```
3. Создайте директории `data`, `logs`, `images`:
   ```bash
   mkdir data logs images
   ```
4. (Опционально) Поместите изображение спонсоров (`sponsor_image.jpeg`) в `images`.
5. Проверьте конфигурацию:
   ```bash
   chmod +x check_config.sh
   ./check_config.sh
   ```
6. Запустите бот:
   ```bash
   docker-compose up -d
   ```

### Запуск без Docker
1. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
2. Задайте переменные окружения:
   ```bash
   export BOT_TOKEN=ваш_токен
   export ADMIN_ID=123456789
   ```
3. Создайте директории `data`, `logs`, `images`:
   ```bash
   mkdir data logs images
   ```
4. (Опционально) Поместите изображение спонсоров (`sponsor_image.jpeg`) в `images`.
5. Проверьте конфигурацию:
   ```bash
   chmod +x check_config.sh
   ./check_config.sh
   ```
6. Запустите бот:
   ```bash
   python main.py
   ```

## Конфигурация
- **`config.json`**:
  ```json
  {
    "csv_delimiter": ";",
    "log_level": "ERROR",
    "sponsor_image_path": "/app/images/sponsor_image.jpeg"
  }
  ```
  - `csv_delimiter`: Разделитель для CSV (по умолчанию `;` для совместимости с русскоязычными системами).
  - `log_level`: Уровень логирования (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - `sponsor_image_path`: Путь к изображению спонсоров.

- **`messages.json`**: Тексты сообщений бота. Поддерживает HTML-разметку (теги `<b>`, `<i>`, `<code>` и др.). Экранируйте `<` и `>` как `&lt;` и `&gt;`, если они не являются частью тегов.
- **Переменные окружения**:
  - `BOT_TOKEN`: Токен Telegram-бота.
  - `ADMIN_ID`: Telegram ID администратора (целое число).

## Структура проекта
- `main.py`: Точка входа, инициализация бота и диспетчера.
- `handler_register.py`: Регистрация всех обработчиков.
- `handlers/`:
  - `registration_handlers.py`: Обработка регистрации (`/start`, ввод имени, роли, целевого времени).
  - `settings_handlers.py`: Настройка лимитов (`/edit_runners`) и даты окончания регистрации (`/set_reg_end_date`).
  - `admin_participant_handlers.py`: Управление участниками (`/participants`, `/stats`, `/paid`, `/set_bib`, `/remove`, `/export`).
  - `info_media_handlers.py`: Работа с информацией и медиа (`/info`, `/info_create`, `/create_afisha`, `/update_sponsor`, `/delete_afisha`).
  - `notification_handlers.py`: Уведомления (`/notify_all`, `/notify_with_text`, `/notify_unpaid`).
  - `misc_handlers.py`: Обработка неизвестных команд.
  - `utils.py`: Утилиты (логирование, клавиатуры, состояния FSM).
- `database.py`: Функции для работы с SQLite (`participants`, `pending_registrations`, `settings`).
- `messages.json`: Тексты сообщений.
- `config.json`: Настройки бота.
- `data/race_participants.db`: SQLite база данных.
- `logs/bot.log`: Лог-файл с ротацией (10 МБ, 1 бэкап).
- `images/`: Хранилище изображений (`sponsor_image.jpeg`, `afisha.jpeg`).
- `requirements.txt`: Зависимости.
- `.dockerignore`: Игнорируемые файлы для Docker.
- `docker-compose.yml`, `Dockerfile`: Контейнеризация.

## Команды бота
### Для всех пользователей
- `/start`: Начать регистрацию (с афишей, если доступна).
- `/info`: Показать информацию о забеге.

### Для администратора
- `/participants`: Список участников (бегуны и волонтёры).
- `/pending`: Незавершённые регистрации.
- `/stats`: Статистика (оплачено, бегуны, волонтёры, незавершённые).
- `/paid <user_id>`: Подтвердить оплату для участника.
- `/set_bib <user_id> <number>`: Присвоить беговой номер.
- `/remove <user_id>`: Удалить участника.
- `/export`: Экспортировать данные участников в CSV (UTF-8 с BOM, разделитель `;`).
- `/info_create`: Обновить текст команды `/info`.
- `/create_afisha`: Загрузить афишу для `/start` и `/info`.
- `/update_sponsor`: Обновить изображение спонсоров.
- `/delete_afisha`: Удалить афишу.
- `/edit_runners <number>`: Изменить лимит бегунов.
- `/set_reg_end_date`: Установить дату и время окончания регистрации (формат: `ЧЧ:ММ ДД.ММ.ГГГГ`, MSK).
- `/notify_all`: Отправить стандартное уведомление всем участникам.
- `/notify_with_text`: Отправить кастомное уведомление (с текстом и опциональным изображением).
- `/notify_unpaid`: Отправить уведомление неоплатившим участникам.

## Работа с часовыми поясами
- Время окончания регистрации (`/set_reg_end_date`) и проверки выполняются в MSK (UTC+3) с использованием `pytz`.
- Даты регистрации в базе хранятся в UTC, но отображаются в MSK (`%d.%m.%Y %H:%M`).

## Отладка
### Логи
- Логи сохраняются в `logs/bot.log` (в контейнере: `/app/logs/bot.log`).
- Ротация логов: 10 МБ, 1 бэкап.
- Установите `log_level: DEBUG` в `config.json` для детальной диагностики.
- Просмотр логов в Docker:
  ```bash
  docker logs beermile_reg-bot-1
  ```

### Проблемы с базой данных
- Проверьте наличие и права директории `data`:
  ```bash
  ls -l data/
  chmod -R 777 data
  ```
- Проверьте права базы данных:
  ```bash
  ls -l data/race_participants.db
  chmod 666 data/race_participants.db
  ```
- Пересоздание базы:
  ```bash
  rm data/race_participants.db
  docker-compose down
  docker volume rm beermile_reg_data
  ./check_config.sh
  docker-compose up -d
  ```
- Проверка ошибок SQLite:
  ```bash
  docker logs beermile_reg-bot-1 | grep ERROR
  ```

### Проблемы с HTML
- Ошибка `TelegramBadRequest: can't parse entities` указывает на некорректную HTML-разметку в `messages.json`.
- Проверьте теги:
  ```bash
  cat messages.json | grep -E "<|>"
  ```
- Экранируйте `<` и `>` как `&lt;` и `&gt;`, если они не в тегах `<b>`, `<i>`, `<code>` и т.д.
- Для диагностики включите `DEBUG` в `config.json` и проверьте сообщения:
  ```bash
  docker logs beermile_reg-bot-1 | grep "Отправка"
  ```

### Проверка обработчиков
- Убедитесь, что обработчики зарегистрированы:
  ```bash
  docker logs beermile_reg-bot-1 | grep "Обработчики успешно зарегистрированы"
  ```
- Тестирование `/start`:
  - Ожидается афиша (если есть `images/afisha.jpeg`) и текст из `start_message`.
  - Пользователь добавляется в `pending_registrations`.
- Тестирование `/set_reg_end_date`:
  - Введите дату в формате `ЧЧ:ММ ДД.ММ.ГГГГ` (например, `23:59 10.07.2025`).
  - Проверьте базу:
    ```bash
    docker exec -it beermile_reg-bot-1 sqlite3 /app/data/race_participants.db "SELECT value FROM settings WHERE key='reg_end_date';"
    ```
- Если команды не работают, проверьте `BOT_TOKEN` и сетевые настройки.

### Экспорт CSV
- Команда `/export` создаёт CSV с кодировкой UTF-8 с BOM.
- Разделитель задаётся в `config.json` (`csv_delimiter`).
- Для открытия в Excel:
  - Используйте **Данные -> Из текста/CSV**, выберите UTF-8 и разделитель `;`.
  - Или сохраните CSV в текстовом редакторе с BOM.

## Примечания
- Убедитесь, что файлы `config.json`, `messages.json`, директории `data`, `logs`, `images` существуют.
- Изображение спонсоров (`sponsor_image.jpeg`) должно быть в `images/`.
- Для проверки конфигурации используйте `check_config.sh`.
- Если регистрация закрыта (по `reg_end_date`), пользователи получают сообщение `registration_closed`.
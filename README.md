# Beer Mile Registration Bot

Телеграм-бот для регистрации участников и волонтеров на гонку.

## Быстрый старт

### Запуск через Docker
1. Установите [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/).
2. Создайте файл `.env` в корне проекта с переменными окружения:
   ```env
   BOT_TOKEN=ваш_токен
   ADMIN_ID=123456789
   ```
3. Создайте директории `data`, `logs` и `images` в корне проекта:
   ```bash
   mkdir data logs images
   ```
4. Поместите изображение спонсоров (`sponsor_image.jpeg`) в директорию `images`.
5. Выполните проверку конфигурации:
   ```bash
   chmod +x check_config.sh
   ./check_config.sh
   ```
6. Запустите бота:
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
3. Создайте директории `data`, `logs` и `images` в корне проекта:
   ```bash
   mkdir data logs images
   ```
4. Поместите изображение спонсоров (`sponsor_image.jpeg`) в директорию `images`.
5. Выполните проверку конфигурации:
   ```bash
   chmod +x check_config.sh
   ./check_config.sh
   ```
6. Запустите бота:
   ```bash
   python main.py
   ```

## Отладка
- Логи приложения сохраняются в `/app/logs/bot.log` (в контейнере) или `logs/bot.log` (локально). При превышении размера 10 МБ текущий файл переименовывается в `bot.log.1`, а старый `bot.log.1` удаляется.
- Уровень логирования задается в `config.json` (`log_level`): `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. Для диагностики HTML-ошибок установите `log_level: DEBUG` в `config.json`.
- Для просмотра логов Docker выполните:
  ```bash
  docker logs beermile_reg-bot-1
  ```
- Проверьте наличие файлов `config.json`, `messages.json`, директорий `data`, `logs` и `images` перед запуском.
- Убедитесь, что файл, указанный в `config.json` (`sponsor_image_path`), находится в `/app/images/sponsor_image.jpeg` (в контейнере) или `./images/sponsor_image.jpeg` (при локальном запуске).
- Убедитесь, что переменные `BOT_TOKEN` и `ADMIN_ID` заданы корректно.
- **Проблемы с базой данных**:
  - Если возникает ошибка при создании таблицы `participants` или `pending_registrations`, проверьте:
    ```bash
    ls -l data/
    ```
    Убедитесь, что директория `data` существует и имеет права `777`:
    ```bash
    chmod -R 777 data
    ```
  - Если файл `data/race_participants.db` существует, проверьте его права:
    ```bash
    ls -l data/race_participants.db
    chmod 666 data/race_participants.db
    ```
  - Для удаления и пересоздания базы данных:
    ```bash
    rm data/race_participants.db
    docker-compose down
    docker volume rm beermile_reg_data
    ./check_config.sh
    docker-compose up -d
    ```
  - Проверьте логи на наличие ошибок SQLite:
    ```bash
    docker logs beermile_reg-bot-1 | grep ERROR
    ```
- **Проблемы с HTML-разметкой**:
  - Если возникает ошибка `TelegramBadRequest: can't parse entities`, проверьте `messages.json` на наличие некорректных HTML-тегов (например, `<id>` вместо `<id>`).
  - Просмотрите содержимое `messages.json`:
    ```bash
    cat messages.json | grep -E "<|>"
    ```
    Убедитесь, что символы `<` и `>` экранированы как `<` и `>`, если не используются в допустимых HTML-тегах (например, `<b>`, `<i>`, `<code>`).
  - Для диагностики включите `DEBUG` в `config.json` и проверьте содержимое отправляемых сообщений в логах:
    ```bash
    docker logs beermile_reg-bot-1 | grep "Отправка admin_commands"
    ```
  - Если ошибка сохраняется, временно замените проблемное сообщение в `messages.json` (например, `admin_commands`) на текст без HTML и перезапустите бот.
- Для проверки работы обработчиков:
  - Отправьте команду `/start` в Telegram-бот для начала регистрации. Если файл `afisha.jpeg` существует, бот отправит афишу с текстом `start_message`. Если файла нет, отправится только текст. Пользователь будет добавлен в таблицу `pending_registrations` до завершения регистрации.
  - Отправьте команду `/info` для получения информации о забеге. Если файл `afisha.jpeg` существует, бот отправит афишу с текстом `info_message`. Если файла нет, отправится только текст.
  - Для администратора (`ADMIN_ID`):
    - Используйте `/participants`, `/stats`, `/paid <ID пользователя>`, `/remove <ID пользователя>`, `/export`, `/info`, `/info_create`, `/create_afisha`, `/update_sponsor`, `/delete_afisha`, `/edit_runners <число>`.
    - Команда `/info_create` позволяет обновить текст, отображаемый по `/info`. После ввода команды бот запросит новый текст (поддерживается HTML-разметка).
    - Команда `/create_afisha` позволяет загрузить изображение афиши, которое будет отправляться при выполнении `/start` и `/info`.
    - Команда `/update_sponsor` позволяет обновить изображение спонсоров, отправляемое после регистрации.
    - Команда `/delete_afisha` позволяет удалить изображение афиши, после чего `/start` и `/info` будут отправлять только текст.
    - Команда `/edit_runners <число>` позволяет изменить максимальное количество бегунов. Если лимит увеличивается, пользователи из `pending_registrations` получат уведомление о новых слотах.
  - Проверьте в `logs/bot.log`, зарегистрированы ли обработчики (сообщение "Обработчики успешно зарегистрированы").
  - Если команды не работают, убедитесь, что `BOT_TOKEN` действителен, и проверьте сетевые настройки контейнера.
- Для экспорта данных в CSV (команда `/export`):
  - Убедитесь, что используется `BufferedInputFile` для отправки файлов в `aiogram` 3.x.
  - CSV-файл формируется с кодировкой UTF-8 с BOM для корректного отображения кириллицы в приложениях, таких как Excel.
  - Данные разделяются с использованием разделителя, указанного в `config.json` (по умолчанию `;` для совместимости с русскоязычными системами).
  - Проверьте логи на наличие сообщения "CSV-файл успешно отправлен".
  - Для открытия CSV в Excel:
    - Используйте **Данные -> Из текста/CSV**, выберите кодировку **UTF-8** и разделитель (например, `;`).
    - Или откройте файл в текстовом редакторе, проверьте разделитель и сохраните с кодировкой UTF-8 с BOM.

## Переменные окружения
- `BOT_TOKEN` — токен вашего Telegram-бота.
- `ADMIN_ID` — Telegram ID администратора (целое число).

## Конфигурация
- **messages.json**: Содержит все текстовые сообщения бота. Редактируйте для изменения текстов. Ключ `info_message` задает текст для команды `/info` и обновляется через `/info_create`. Убедитесь, что символы `<` и `>` экранированы (`<`, `>`), если не используются в HTML-тегах.
- **config.json**: Настройки:
  - `max_runners`: Максимальное количество бегунов, обновляется через `/edit_runners`.
  - `max_volunteers`: Максимальное количество волонтеров.
  - `csv_delimiter`: Разделитель для CSV-файлов (по умолчанию `;`).
  - `log_level`: Уровень логирования (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - `sponsor_image_path`: Путь к изображению спонсоров (`/app/images/sponsor_image.jpeg`).
- **sponsor_image.jpeg**: Изображение спонсоров, отправляемое после регистрации. Обновляется через `/update_sponsor`.
- **afisha.jpeg**: Изображение афиши, отправляемое при выполнении `/start` и `/info`. Загружается через `/create_afisha`, удаляется через `/delete_afisha`.

## Структура проекта
- `main.py`: Точка входа для запуска бота.
- `handlers.py`: Обработчики команд и сообщений.
- `database.py`: Функции для работы с SQLite базой данных.
- `messages.json`: Тексты сообщений.
- `config.json`: Настройки лимитов, разделителя CSV, уровня логирования и пути к изображению.
- `data/race_participants.db`: SQLite база данных, содержащая таблицы `participants` и `pending_registrations`.
- `logs/bot.log`: Лог-файл приложения с ротацией.
- `images/sponsor_image.jpeg`: Изображение спонсоров.
- `images/afisha.jpeg`: Изображение афиши.

## Требования
- Python 3.8+
- aiogram 3.4.1
- python-dotenv
- jq (для `check_config.sh`)
- Docker (для запуска через контейнер)
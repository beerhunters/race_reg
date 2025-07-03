##!/bin/bash
#
## Проверяем, что скрипт запущен из правильной директории
#if [ ! -f "docker-compose.yml" ]; then
#  echo "Ошибка: Файл docker-compose.yml не найден. Убедитесь, что вы находитесь в корневой директории проекта."
#  exit 1
#fi
#
## Логирование
#LOG_FILE="/app/logs/update_and_restart.log"
#mkdir -p "$(dirname "$LOG_FILE")"
#echo "[$(date '+%Y-%m-%d %H:%M:%S')] Начало выполнения скрипта update_and_restart.sh" >> "$LOG_FILE"
#
## Выполняем git pull
#echo "Выполняется git pull..."
#if ! git pull >> "$LOG_FILE" 2>&1; then
#  echo "Ошибка: Не удалось выполнить git pull. Проверьте подключение к репозиторию или права доступа."
#  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении git pull" >> "$LOG_FILE"
#  exit 1
#fi
#echo "[$(date '+%Y-%m-%d %H:%M:%S')] git pull успешно выполнен" >> "$LOG_FILE"
#
## Проверка конфигурации
#echo "Проверка конфигурации..."
#if [ ! -f "check_config.sh" ]; then
#  echo "Ошибка: Файл check_config.sh не найден."
#  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка: check_config.sh не найден" >> "$LOG_FILE"
#  exit 1
#fi
#
#chmod +x check_config.sh
#if ! ./check_config.sh >> "$LOG_FILE" 2>&1; then
#  echo "Ошибка: Проверка конфигурации не прошла. Проверьте логи в $LOG_FILE."
#  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении check_config.sh" >> "$LOG_FILE"
#  exit 1
#fi
#echo "[$(date '+%Y-%m-%d %H:%M:%S')] Проверка конфигурации успешно пройдена" >> "$LOG_FILE"
#
## Пересборка образа
#echo "Пересборка Docker-образа..."
#if ! docker-compose build >> "$LOG_FILE" 2>&1; then
#  echo "Ошибка: Не удалось пересобрать образ. Проверьте логи в $LOG_FILE."
#  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении docker-compose build" >> "$LOG_FILE"
#  exit 1
#fi
#echo "[$(date '+%Y-%m-%d %H:%M:%S')] Docker-образ успешно пересобран" >> "$LOG_FILE"
#
## Перезапуск контейнера
#echo "Перезапуск контейнера..."
#if ! docker-compose down >> "$LOG_FILE" 2>&1; then
#  echo "Ошибка: Не удалось остановить контейнер. Проверьте логи в $LOG_FILE."
#  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении docker-compose down" >> "$LOG_FILE"
#  exit 1
#fi
#
#if ! docker-compose up -d >> "$LOG_FILE" 2>&1; then
#  echo "Ошибка: Не удалось запустить контейнер. Проверьте логи в $LOG_FILE."
#  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении docker-compose up -d" >> "$LOG_FILE"
#  exit 1
#fi
#echo "[$(date '+%Y-%m-%d %H:%M:%S')] Контейнер успешно перезапущен" >> "$LOG_FILE"
#
#echo "Обновление и перезапуск успешно завершены. Логи сохранены в $LOG_FILE."
echo "Проверка конфигурации..."
if [ ! -f ".env" ]; then
    echo "Ошибка: Файл .env не найден. Создайте его с BOT_TOKEN и ADMIN_ID."
    exit 1
fi
source .env
if [ -z "$BOT_TOKEN" ]; then
    echo "Ошибка: Переменная BOT_TOKEN не задана в .env."
    exit 1
fi
if [ -z "$ADMIN_ID" ]; then
    echo "Ошибка: Переменная ADMIN_ID не задана в .env."
    exit 1
fi
if [ ! -f "config.json" ]; then
    echo "Ошибка: Файл config.json не найден."
    exit 1
fi
if [ ! -f "messages.json" ]; then
    echo "Ошибка: Файл messages.json не найден."
    exit 1
fi
if ! jq -e '.max_runners' config.json >/dev/null; then
    echo "Ошибка: Параметр max_runners отсутствует в config.json."
    exit 1
fi
if ! jq -e '.max_volunteers' config.json >/dev/null; then
    echo "Ошибка: Параметр max_volunteers отсутствует в config.json."
    exit 1
fi
if ! jq -e '.csv_delimiter' config.json >/dev/null; then
    echo "Ошибка: Параметр csv_delimiter отсутствует в config.json."
    exit 1
fi
if ! jq -e '.log_level' config.json >/dev/null; then
    echo "Ошибка: Параметр log_level отсутствует в config.json."
    exit 1
fi
if ! jq -e '.sponsor_image_path' config.json >/dev/null; then
    echo "Ошибка: Параметр sponsor_image_path отсутствует в config.json."
    exit 1
fi
valid_log_levels=("DEBUG" "INFO" "WARNING" "ERROR" "CRITICAL")
log_level=$(jq -r '.log_level' config.json)
if [[ ! " ${valid_log_levels[@]} " =~ " ${log_level} " ]]; then
    echo "Ошибка: Неверное значение log_level в config.json. Допустимые значения: ${valid_log_levels[*]}."
    exit 1
fi
sponsor_image_path=$(jq -r '.sponsor_image_path' config.json)
if [ ! -f "${sponsor_image_path#"/app/"}" ]; then
    echo "Предупреждение: Файл ${sponsor_image_path#"/app/"} не найден. Поместите изображение спонсоров в директорию images."
fi
if [ ! -d "data" ]; then
    echo "Создание директории data..."
    mkdir data
fi
if [ ! -d "logs" ]; then
    echo "Создание директории logs..."
    mkdir logs
fi
if [ ! -d "images" ]; then
    echo "Создание директории images..."
    mkdir images
fi
chmod -R 777 data logs images
if [ -f "data/race_participants.db" ]; then
    chmod 666 data/race_participants.db
    echo "Права доступа для data/race_participants.db установлены (666)."
    # Verify participants table schema
    columns=$(docker exec race_reg-bot-1 sqlite3 /app/data/race_participants.db "PRAGMA table_info(participants)" | grep bib_number)
    if [ -z "$columns" ]; then
        echo "Предупреждение: Столбец bib_number отсутствует в таблице participants. Убедитесь, что база данных обновлена."
    else
        echo "Столбец bib_number присутствует в таблице participants."
    fi
else
    echo "Файл data/race_participants.db не существует, будет создан при запуске."
fi
echo "Права доступа для директорий data, logs и images установлены."
echo "Конфигурация проверена успешно!"
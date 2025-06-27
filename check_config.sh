#!/bin/bash
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
echo "Права доступа для директорий data, logs и images установлены."
echo "Конфигурация проверена успешно!"
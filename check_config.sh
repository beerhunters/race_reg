#!/bin/bash

echo "Проверка конфигурации..."

# Проверка наличия .env
if [ ! -f ".env" ]; then
    echo "Ошибка: Файл .env не найден. Создайте его с BOT_TOKEN и ADMIN_ID."
    exit 1
fi

# Проверка переменных окружения
source .env
if [ -z "$BOT_TOKEN" ]; then
    echo "Ошибка: Переменная BOT_TOKEN не задана в .env."
    exit 1
fi
if [ -z "$ADMIN_ID" ]; then
    echo "Ошибка: Переменная ADMIN_ID не задана в .env."
    exit 1
fi

# Проверка наличия config.json
if [ ! -f "config.json" ]; then
    echo "Ошибка: Файл config.json не найден."
    exit 1
fi

# Проверка наличия messages.json
if [ ! -f "messages.json" ]; then
    echo "Ошибка: Файл messages.json не найден."
    exit 1
fi

# Проверка директории data
if [ ! -d "data" ]; then
    echo "Создание директории data..."
    mkdir data
fi

# Проверка директории logs
if [ ! -d "logs" ]; then
    echo "Создание директории logs..."
    mkdir logs
fi

# Проверка прав доступа для директорий
chmod -R 777 data logs
echo "Права доступа для директорий data и logs установлены."

echo "Конфигурация проверена успешно!"
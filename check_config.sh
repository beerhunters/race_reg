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
if [ ! -f "images/sponsor_image.jpeg" ]; then
    echo "Предупреждение: Файл images/sponsor_image.jpg не найден. Поместите изображение спонсоров в директорию images."
fi
chmod -R 777 data logs images
echo "Права доступа для директорий data, logs и images установлены."
echo "Конфигурация проверена успешно!"
#!/bin/bash

# Проверяем, что скрипт запущен из правильной директории
if [ ! -f "docker-compose.yml" ]; then
  echo "Ошибка: Файл docker-compose.yml не найден. Убедитесь, что вы находитесь в корневой директории проекта."
  exit 1
fi

# Логирование
LOG_FILE="/app/logs/update_and_restart.log"
mkdir -p "$(dirname "$LOG_FILE")"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Начало выполнения скрипта update_and_restart.sh" >> "$LOG_FILE"

# Выполняем git pull
echo "Выполняется git pull..."
if ! git pull >> "$LOG_FILE" 2>&1; then
  echo "Ошибка: Не удалось выполнить git pull. Проверьте подключение к репозиторию или права доступа."
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении git pull" >> "$LOG_FILE"
  exit 1
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')] git pull успешно выполнен" >> "$LOG_FILE"

# Проверяем конфигурацию
echo "Проверка конфигурации..."
if [ ! -f "check_config.sh" ]; then
  echo "Ошибка: Файл check_config.sh не найден."
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка: check_config.sh не найден" >> "$LOG_FILE"
  exit 1
fi

chmod +x check_config.sh
if ! ./check_config.sh >> "$LOG_FILE" 2>&1; then
  echo "Ошибка: Проверка конфигурации не прошла. Проверьте логи в $LOG_FILE."
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении check_config.sh" >> "$LOG_FILE"
  exit 1
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Проверка конфигурации успешно пройдена" >> "$LOG_FILE"

# Перезапускаем контейнер
echo "Перезапуск контейнера..."
if ! docker-compose down >> "$LOG_FILE" 2>&1; then
  echo "Ошибка: Не удалось остановить контейнер. Проверьте логи в $LOG_FILE."
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении docker-compose down" >> "$LOG_FILE"
  exit 1
fi

if ! docker-compose up -d >> "$LOG_FILE" 2>&1; then
  echo "Ошибка: Не удалось запустить контейнер. Проверьте логи в $LOG_FILE."
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ошибка при выполнении docker-compose up -d" >> "$LOG_FILE"
  exit 1
fi
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Контейнер успешно перезапущен" >> "$LOG_FILE"

echo "Обновление и перезапуск успешно завершены. Логи сохранены в $LOG_FILE."
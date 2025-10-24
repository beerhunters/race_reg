#!/bin/bash
# Скрипт установки Beer Mile Admin CLI

set -e

echo "🍺 Beer Mile Admin CLI - Установка"
echo "=================================="
echo

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 не найден. Пожалуйста, установите Python 3.11 или выше."
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d" " -f2 | cut -d"." -f1-2)
echo "✅ Python версия: $PYTHON_VERSION"

# Проверка директории
if [ ! -d "cli_admin" ]; then
    echo "❌ Директория cli_admin не найдена. Запустите скрипт из корня проекта."
    exit 1
fi

# Установка зависимостей
echo
echo "📦 Установка зависимостей..."
pip3 install -r requirements_cli.txt

# Сделать main.py исполняемым
echo
echo "🔧 Настройка прав доступа..."
chmod +x cli_admin/main.py

# Создать алиас
echo
echo "🔗 Создание алиаса 'beermile'..."

ALIAS_CMD="alias beermile='python3 $(pwd)/cli_admin/main.py'"

# Определить shell
if [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
elif [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
else
    SHELL_RC="$HOME/.profile"
fi

# Добавить алиас если еще не добавлен
if ! grep -q "alias beermile=" "$SHELL_RC" 2>/dev/null; then
    echo "$ALIAS_CMD" >> "$SHELL_RC"
    echo "✅ Алиас добавлен в $SHELL_RC"
else
    echo "ℹ️  Алиас уже существует в $SHELL_RC"
fi

echo
echo "✅ Установка завершена!"
echo
echo "Для применения изменений выполните:"
echo "  source $SHELL_RC"
echo
echo "Или перезапустите терминал."
echo
echo "Использование:"
echo "  beermile interactive    # Интерактивный режим"
echo "  beermile status         # Показать статус"
echo "  beermile --help         # Помощь"
echo
echo "🎉 Готово! Приятного использования!"

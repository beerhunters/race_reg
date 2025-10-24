# 🚀 Быстрый старт Beer Mile Admin CLI

## 📦 Установка (5 минут)

### Шаг 1: Установить зависимости

```bash
cd /Users/olfrygt/PycharmProjects/beermile_reg
pip3 install -r requirements_cli.txt
```

### Шаг 2: Запустить скрипт установки

```bash
./install_cli.sh
```

### Шаг 3: Применить изменения

```bash
source ~/.bashrc  # или ~/.zshrc
```

## ✅ Проверка установки

```bash
# Проверить версию
beermile version

# Показать помощь
beermile --help
```

## 🎮 Первый запуск

### Вариант 1: Интерактивный режим (рекомендуется для начинающих)

```bash
beermile interactive
```

Вы увидите главное меню:
```
╔══════════════════════════════════════════════════════════════╗
║        🍺 Beer Mile - Текущая статистика                     ║
╠══════════════════════════════════════════════════════════════╣
║  🏃 Участников (бегунов):        45/100                      ║
║  🤝 Волонтеров:                  12/20                       ║
║  💳 Оплатили:                    38/45                       ║
║  📋 В листе ожидания:            8                           ║
║  🏆 Команд:                      15 (12 полных)              ║
╚══════════════════════════════════════════════════════════════╝

🍺 Beer Mile Admin - Главное меню
► 👥 Управление участниками
  ⚙️ Настройки мероприятия
  📋 Лист ожидания
  🏆 Управление командами
  📊 Статистика и аналитика
  ───────────────────────────
  ❌ Выход
```

Используйте стрелки ↑↓ для навигации, Enter для выбора.

### Вариант 2: Прямые команды (для опытных пользователей)

```bash
# Показать текущий статус
beermile status

# Список участников
beermile participants list

# Статистика
beermile stats overview
```

## 📋 Основные команды для ежедневной работы

### Просмотр данных

```bash
# Общий статус
beermile status

# Все участники
beermile participants list

# Только бегуны
beermile participants list --role runner

# Только неоплаченные
beermile participants list --paid false

# Лист ожидания
beermile waitlist list

# Команды
beermile teams list

# Статистика
beermile stats overview
beermile stats payment
```

### Работа с участниками

```bash
# Найти участника
beermile participants get 123456789

# Поиск по имени
beermile participants search "Иван"

# Отметить оплату
beermile participants mark-paid 123456789

# Присвоить номер
beermile participants set-bib 123456789 101
```

### Настройки

```bash
# Посмотреть все настройки
beermile settings list

# Изменить лимит бегунов
beermile settings set max_runners 150

# Переключить командный режим
beermile settings toggle team_mode_enabled
```

## 🎯 Типичные сценарии использования

### Сценарий 1: Проверка новых регистраций

```bash
# 1. Посмотреть статус
beermile status

# 2. Посмотреть последних участников
beermile participants list --limit 10

# 3. Проверить лист ожидания
beermile waitlist list
```

### Сценарий 2: Обработка оплат

```bash
# 1. Посмотреть неоплаченных
beermile participants list --paid false

# 2. Отметить оплату
beermile participants mark-paid 123456789

# 3. Проверить статистику оплат
beermile stats payment
```

### Сценарий 3: Присвоение номеров

```bash
# 1. Посмотреть участников без номеров
beermile participants list

# 2. Присвоить номер
beermile participants set-bib 123456789 101

# 3. Проверить
beermile participants get 123456789
```

### Сценарий 4: Перевод из листа ожидания

```bash
# 1. Посмотреть лист ожидания
beermile waitlist list

# 2. Проверить позицию
beermile waitlist position 123456789

# 3. Перевести в участники
beermile waitlist promote 123456789
```

## 💡 Полезные советы

### Совет 1: Использование алиаса

Если алиас не работает, используйте прямой путь:

```bash
python3 /Users/olfrygt/PycharmProjects/beermile_reg/cli_admin/main.py status
```

### Совет 2: Использование другой базы данных

```bash
beermile --db /path/to/other.db participants list
```

### Совет 3: Помощь по командам

```bash
# Общая помощь
beermile --help

# Помощь по конкретной команде
beermile participants --help
beermile settings --help
```

### Совет 4: Подробный вывод

```bash
beermile --verbose participants list
```

## ❓ Решение проблем

### Проблема: "command not found: beermile"

**Решение:**
```bash
# Применить изменения в shell
source ~/.bashrc  # или ~/.zshrc

# Или использовать прямой путь
python3 /Users/olfrygt/PycharmProjects/beermile_reg/cli_admin/main.py
```

### Проблема: "ModuleNotFoundError"

**Решение:**
```bash
# Переустановить зависимости
pip3 install -r requirements_cli.txt
```

### Проблема: "Permission denied"

**Решение:**
```bash
# Дать права на выполнение
chmod +x cli_admin/main.py
chmod +x install_cli.sh
```

### Проблема: "Database not found"

**Решение:**
```bash
# Проверить путь к БД
ls -la /app/data/race_participants.db

# Или указать правильный путь
beermile --db /correct/path/to/race_participants.db status
```

## 📚 Дальнейшее изучение

После освоения основ, изучите:

1. **[CLI_README.md](CLI_README.md)** - полная документация по командам
2. **[CLI_ADMIN_TOOL_DOCUMENTATION.md](CLI_ADMIN_TOOL_DOCUMENTATION.md)** - детальная документация с примерами кода
3. Все доступные команды через `beermile --help`

## 🎉 Готово!

Теперь вы можете эффективно управлять мероприятием Beer Mile через консоль!

**Рекомендуем начать с:**
```bash
beermile interactive
```

Удачи! 🍺

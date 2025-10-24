"""
Команды управления участниками
"""

import typer
from typing import Optional
from rich.console import Console

from cli_admin.database import (
    get_all_participants,
    get_participant_by_user_id,
    get_participants_by_role,
    update_payment_status,
    set_bib_number,
    delete_participant,
    update_participant_field,
    set_participant_category,
    set_participant_cluster,
    clear_all_categories,
    clear_all_clusters,
)
from cli_admin.utils.display import (
    display_participants_table,
    display_participant_details,
    print_success,
    print_error,
    print_warning,
    confirm_action,
)
from cli_admin.utils.validators import (
    validate_telegram_id,
    validate_bib_number,
    validate_payment_status,
)

app = typer.Typer(help="👥 Управление участниками")
console = Console()


@app.command("list")
def list_participants(
    role: Optional[str] = typer.Option(None, "--role", "-r", help="Фильтр по роли (runner/volunteer)"),
    paid: Optional[bool] = typer.Option(None, "--paid", "-p", help="Фильтр по статусу оплаты"),
    limit: int = typer.Option(100, "--limit", "-l", help="Лимит вывода"),
    offset: int = typer.Option(0, "--offset", "-o", help="Смещение"),
):
    """
    📋 Просмотреть список всех участников
    """
    try:
        # Получить участников
        if role:
            participants = get_participants_by_role(role)
        else:
            participants = get_all_participants()

        if not participants:
            print_warning("Участники не найдены")
            return

        # Фильтрация по оплате
        if paid is not None:
            status = 'paid' if paid else 'pending'
            participants = [p for p in participants if p[6] == status]

        # Пагинация
        participants = participants[offset:offset+limit]

        # Отобразить таблицу
        display_participants_table(participants)

    except Exception as e:
        print_error(f"Ошибка при получении списка участников: {str(e)}")
        raise typer.Exit(1)


@app.command("get")
def get_participant(
    user_id: int = typer.Argument(..., help="Telegram ID участника")
):
    """
    🔍 Получить информацию об участнике
    """
    try:
        # Валидация
        is_valid, parsed_id, error = validate_telegram_id(str(user_id))
        if not is_valid:
            print_error(error)
            raise typer.Exit(1)

        # Получить участника
        participant = get_participant_by_user_id(parsed_id)

        if not participant:
            print_error(f"Участник с ID {parsed_id} не найден")
            raise typer.Exit(1)

        # Отобразить детали
        display_participant_details(participant)

    except Exception as e:
        print_error(f"Ошибка при получении участника: {str(e)}")
        raise typer.Exit(1)


@app.command("mark-paid")
def mark_paid(
    user_id: int = typer.Argument(..., help="Telegram ID участника"),
    force: bool = typer.Option(False, "--force", "-f", help="Без подтверждения"),
):
    """
    💳 Отметить участника как оплатившего
    """
    try:
        # Проверить существование
        participant = get_participant_by_user_id(user_id)
        if not participant:
            print_error(f"Участник с ID {user_id} не найден")
            raise typer.Exit(1)

        # Подтверждение
        if not force:
            if not confirm_action(f"Отметить участника {participant[2]} (ID: {user_id}) как оплатившего?"):
                print_warning("Отменено")
                return

        # Обновить статус
        success = update_payment_status(user_id, "paid")

        if success:
            print_success(f"Участник {user_id} отмечен как оплативший")
        else:
            print_error("Ошибка при обновлении статуса")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("set-payment")
def set_payment_status(
    user_id: int = typer.Argument(..., help="Telegram ID участника"),
    status: str = typer.Argument(..., help="Статус оплаты (paid/pending/unpaid)"),
):
    """
    💰 Установить статус оплаты
    """
    try:
        # Валидация статуса
        is_valid, error = validate_payment_status(status)
        if not is_valid:
            print_error(error)
            raise typer.Exit(1)

        # Обновить статус
        success = update_payment_status(user_id, status)

        if success:
            print_success(f"Статус оплаты обновлен на '{status}'")
        else:
            print_error("Ошибка при обновлении статуса")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("set-bib")
def set_bib(
    user_id: int = typer.Argument(..., help="Telegram ID участника"),
    number: str = typer.Argument(..., help="Стартовый номер"),
):
    """
    🔢 Присвоить стартовый номер
    """
    try:
        # Валидация номера
        is_valid, error = validate_bib_number(number)
        if not is_valid:
            print_error(error)
            raise typer.Exit(1)

        # Присвоить номер
        success = set_bib_number(user_id, number)

        if success:
            print_success(f"Номер {number} присвоен участнику {user_id}")
        else:
            print_error("Ошибка при присвоении номера")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("edit")
def edit_participant(
    user_id: int = typer.Argument(..., help="Telegram ID участника"),
    field: str = typer.Option(..., "--field", "-f", help="Поле для редактирования"),
    value: str = typer.Option(..., "--value", "-v", help="Новое значение"),
):
    """
    ✏️ Редактировать поле участника
    """
    try:
        # Обновить поле
        success = update_participant_field(user_id, field, value)

        if success:
            print_success(f"Поле '{field}' обновлено на '{value}'")
        else:
            print_error("Ошибка при обновлении поля")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("delete")
def delete(
    user_id: int = typer.Argument(..., help="Telegram ID участника"),
    force: bool = typer.Option(False, "--force", "-f", help="Удалить без подтверждения"),
):
    """
    ❌ Удалить участника
    """
    try:
        # Получить участника
        participant = get_participant_by_user_id(user_id)
        if not participant:
            print_error(f"Участник с ID {user_id} не найден")
            raise typer.Exit(1)

        # Подтверждение
        if not force:
            console.print(f"\n[yellow]⚠️ ВНИМАНИЕ: Удаление участника![/yellow]")
            console.print(f"  Участник: {participant[2]} (ID: {user_id})")
            console.print(f"  Роль: {'Бегун' if participant[4] == 'runner' else 'Волонтер'}")
            console.print(f"  Оплата: {'Оплачено' if participant[6] == 'paid' else 'Не оплачено'}\n")

            if not confirm_action("Вы уверены, что хотите удалить этого участника?"):
                print_warning("Отменено")
                return

        # Удалить
        success = delete_participant(user_id)

        if success:
            print_success(f"Участник {user_id} удален")
        else:
            print_error("Ошибка при удалении участника")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("set-category")
def set_category(
    user_id: int = typer.Argument(..., help="Telegram ID участника"),
    category: str = typer.Argument(..., help="Категория"),
):
    """
    🏷️ Установить категорию участника
    """
    try:
        success = set_participant_category(user_id, category)

        if success:
            print_success(f"Категория '{category}' установлена для участника {user_id}")
        else:
            print_error("Ошибка при установке категории")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("set-cluster")
def set_cluster(
    user_id: int = typer.Argument(..., help="Telegram ID участника"),
    cluster: str = typer.Argument(..., help="Кластер"),
):
    """
    📍 Установить кластер участника
    """
    try:
        success = set_participant_cluster(user_id, cluster)

        if success:
            print_success(f"Кластер '{cluster}' установлен для участника {user_id}")
        else:
            print_error("Ошибка при установке кластера")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("clear-categories")
def clear_categories(
    confirm: bool = typer.Option(False, "--confirm", help="Подтвердить очистку"),
):
    """
    🧹 Очистить все категории
    """
    try:
        if not confirm:
            if not confirm_action("⚠️ Вы уверены, что хотите очистить все категории?"):
                print_warning("Отменено")
                return

        success = clear_all_categories()

        if success:
            print_success("Все категории очищены")
        else:
            print_error("Ошибка при очистке категорий")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("clear-clusters")
def clear_clusters(
    confirm: bool = typer.Option(False, "--confirm", help="Подтвердить очистку"),
):
    """
    🧹 Очистить все кластеры
    """
    try:
        if not confirm:
            if not confirm_action("⚠️ Вы уверены, что хотите очистить все кластеры?"):
                print_warning("Отменено")
                return

        success = clear_all_clusters()

        if success:
            print_success("Все кластеры очищены")
        else:
            print_error("Ошибка при очистке кластеров")
            raise typer.Exit(1)

    except Exception as e:
        print_error(f"Ошибка: {str(e)}")
        raise typer.Exit(1)


@app.command("search")
def search_participants(
    query: str = typer.Argument(..., help="Поисковый запрос (имя или username)"),
):
    """
    🔍 Поиск участников по имени или username
    """
    try:
        # Получить всех участников
        participants = get_all_participants()

        if not participants:
            print_warning("Участники не найдены")
            return

        # Фильтрация по запросу
        query_lower = query.lower()
        filtered = [
            p for p in participants
            if (p[2] and query_lower in p[2].lower()) or  # Имя
               (p[1] and query_lower in p[1].lower())     # Username
        ]

        if not filtered:
            print_warning(f"Участники с запросом '{query}' не найдены")
            return

        # Отобразить результаты
        display_participants_table(filtered, title=f"Результаты поиска: '{query}'")

    except Exception as e:
        print_error(f"Ошибка при поиске: {str(e)}")
        raise typer.Exit(1)

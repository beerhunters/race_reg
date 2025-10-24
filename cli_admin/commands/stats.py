"""
Команды статистики и аналитики
"""

import typer
from rich.table import Table
from rich.console import Console

from cli_admin.database import (
    get_participant_count,
    get_participant_count_by_role,
    get_waitlist_by_role,
    get_all_teams,
    count_complete_teams,
    get_all_participants,
    get_setting,
)

app = typer.Typer(help="📊 Статистика и аналитика")
console = Console()


@app.command("overview")
def overview():
    """
    📈 Общая статистика мероприятия
    """
    try:
        # Получить данные
        total_participants = get_participant_count()
        runners = get_participant_count_by_role("runner")
        volunteers = get_participant_count_by_role("volunteer")
        waitlist = len(get_waitlist_by_role())
        teams = len(get_all_teams())
        complete_teams = count_complete_teams()

        # Получить лимиты
        max_runners = get_setting("max_runners") or 100
        max_volunteers = get_setting("max_volunteers") or 20

        # Подсчитать оплаченных
        all_p = get_all_participants()
        paid_count = sum(1 for p in all_p if p[6] == 'paid')

        # Создать таблицу
        table = Table(title="📊 Общая статистика", show_lines=True)
        table.add_column("Категория", style="cyan")
        table.add_column("Значение", style="green", justify="right")

        # Участники
        table.add_row("Всего участников", str(total_participants))
        table.add_row("Бегунов", f"{runners} / {max_runners}")
        table.add_row("Волонтеров", f"{volunteers} / {max_volunteers}")

        # Процент заполнения
        runners_percent = (runners / int(max_runners)) * 100 if max_runners else 0
        volunteers_percent = (volunteers / int(max_volunteers)) * 100 if max_volunteers else 0
        table.add_row("Заполнение (бегуны)", f"{runners_percent:.1f}%")
        table.add_row("Заполнение (волонтеры)", f"{volunteers_percent:.1f}%")

        # Оплата
        payment_percent = (paid_count / total_participants) * 100 if total_participants else 0
        table.add_row("Оплатили", f"{paid_count} / {total_participants}")
        table.add_row("Процент оплаты", f"{payment_percent:.1f}%")

        # Лист ожидания
        table.add_row("В листе ожидания", str(waitlist))

        # Команды
        table.add_row("Всего команд", str(teams))
        table.add_row("Полных команд", f"{complete_teams} / {teams}")

        console.print(table)

    except Exception as e:
        console.print(f"[red]Ошибка при получении статистики: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("payment")
def payment_stats():
    """
    💰 Статистика оплат
    """
    try:
        all_p = get_all_participants()

        if not all_p:
            console.print("[yellow]Нет участников[/yellow]")
            return

        # Подсчет по статусам
        paid = sum(1 for p in all_p if p[6] == 'paid')
        pending = sum(1 for p in all_p if p[6] == 'pending')
        unpaid = sum(1 for p in all_p if p[6] == 'unpaid')

        # Подсчет по ролям
        paid_runners = sum(1 for p in all_p if p[6] == 'paid' and p[4] == 'runner')
        paid_volunteers = sum(1 for p in all_p if p[6] == 'paid' and p[4] == 'volunteer')

        table = Table(title="💰 Статистика оплат", show_lines=True)
        table.add_column("Категория", style="cyan")
        table.add_column("Количество", style="green", justify="right")
        table.add_column("Процент", style="yellow", justify="right")

        total = len(all_p)

        table.add_row("Оплачено", str(paid), f"{(paid/total*100):.1f}%")
        table.add_row("Ожидает", str(pending), f"{(pending/total*100):.1f}%")
        table.add_row("Не оплачено", str(unpaid), f"{(unpaid/total*100):.1f}%")
        table.add_row("", "", "")  # Разделитель
        table.add_row("Оплатили (бегуны)", str(paid_runners), "")
        table.add_row("Оплатили (волонтеры)", str(paid_volunteers), "")

        console.print(table)

        # Подсчет стоимости
        participation_price = get_setting("participation_price")
        if participation_price:
            try:
                price = float(participation_price)
                total_expected = total * price
                total_received = paid * price
                console.print(f"\n[cyan]Ожидаемый доход: {total_expected:.2f} руб[/cyan]")
                console.print(f"[green]Получено: {total_received:.2f} руб[/green]")
                console.print(f"[yellow]Остается собрать: {total_expected - total_received:.2f} руб[/yellow]")
            except ValueError:
                pass

    except Exception as e:
        console.print(f"[red]Ошибка при получении статистики оплат: {str(e)}[/red]")
        raise typer.Exit(1)


@app.command("teams")
def teams_stats():
    """
    🏆 Статистика команд
    """
    try:
        teams = get_all_teams()

        if not teams:
            console.print("[yellow]Нет команд[/yellow]")
            return

        complete = count_complete_teams()
        incomplete = len(teams) - complete

        table = Table(title="🏆 Статистика команд", show_lines=True)
        table.add_column("Категория", style="cyan")
        table.add_column("Значение", style="green", justify="right")

        table.add_row("Всего команд", str(len(teams)))
        table.add_row("Полных команд (2/2)", str(complete))
        table.add_row("Неполных команд (1/2)", str(incomplete))

        if len(teams) > 0:
            table.add_row("Процент полных команд", f"{(complete/len(teams)*100):.1f}%")

        console.print(table)

    except Exception as e:
        console.print(f"[red]Ошибка при получении статистики команд: {str(e)}[/red]")
        raise typer.Exit(1)

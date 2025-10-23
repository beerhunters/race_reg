from aiogram import Dispatcher, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from .utils import (
    RegistrationForm,
    logger,
    RegistrationForm,
    create_clusters_category_keyboard,
    create_category_selection_keyboard,
    create_cluster_selection_keyboard,
    create_back_keyboard,
)
from database import (
    get_participants_by_role,
    set_participant_category,
    set_participant_cluster,
    get_participants_with_categories,
    clear_all_categories,
    clear_all_clusters,
)


def register_cluster_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков кластеров и категорий")

    @dp.callback_query(F.data == "admin_clusters")
    async def show_clusters_menu(callback_query: CallbackQuery):
        """Show clusters management menu"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.message.delete()
        await callback_query.answer()

        text = "🎯 <b>Управление кластерами и категориями</b>\n\n"
        text += "📝 <b>Добавить категории</b> - назначить участникам категории (СуперЭлита, Элита, Классика, Женский, Команда)\n"
        text += "🎯 <b>Распределить кластеры</b> - назначить участникам стартовые кластеры (A, B, C, D, E, F, G)\n"
        text += "📋 <b>Посмотреть распределение</b> - показать финальное распределение всех участников\n"
        text += "🔄 <b>Сброс</b> - очистить категории или кластеры всех участников"

        await callback_query.message.answer(
            text, reply_markup=create_clusters_category_keyboard()
        )

    @dp.callback_query(F.data == "admin_add_categories")
    async def start_category_assignment(
        callback_query: CallbackQuery, state: FSMContext
    ):
        """Start category assignment process"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        # Get all runners (only runners need categories)
        participants = get_participants_by_role("runner")

        if not participants:
            await callback_query.message.answer(
                "❌ Нет участников для назначения категорий",
                reply_markup=create_back_keyboard("admin_menu"),
            )
            return

        # Sort participants:
        # 1. First - those without category (None or empty)
        # 2. Among each group - reverse registration order (last registered first)
        # Participant tuple: (user_id, username, name, target_time, reg_date, gender, category, cluster, ...)
        participants = sorted(
            participants,
            key=lambda p: (
                bool(p[6]),  # False (no category) comes before True (has category)
                -(ord(p[4][-1]) if p[4] else 0)  # Reverse order by last char of reg_date (newest first)
            )
        )

        # Store participants list in state data
        await state.update_data(
            participants=participants, current_index=0, assignment_type="category"
        )

        await callback_query.message.delete()
        await callback_query.answer()

        # Show first participant
        await show_participant_for_assignment(callback_query.message, state, bot)

    @dp.callback_query(F.data == "admin_assign_clusters")
    async def start_cluster_assignment(
        callback_query: CallbackQuery, state: FSMContext
    ):
        """Start cluster assignment process"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        # Get all runners
        participants = get_participants_by_role("runner")

        if not participants:
            await callback_query.message.answer(
                "❌ Нет участников для назначения кластеров",
                reply_markup=create_back_keyboard("admin_menu"),
            )
            return

        # Sort participants:
        # 1. First - those without cluster (None or empty)
        # 2. Among each group - reverse registration order (last registered first)
        # Participant tuple: (user_id, username, name, target_time, reg_date, gender, category, cluster, ...)
        participants = sorted(
            participants,
            key=lambda p: (
                bool(p[7] if len(p) > 7 else None),  # False (no cluster) comes before True (has cluster)
                -(ord(p[4][-1]) if p[4] else 0)  # Reverse order by last char of reg_date (newest first)
            )
        )

        # Store participants list in state data
        await state.update_data(
            participants=participants, current_index=0, assignment_type="cluster"
        )

        await callback_query.message.delete()
        await callback_query.answer()

        # Show first participant
        await show_participant_for_assignment(callback_query.message, state, bot)

    async def show_participant_for_assignment(
        message: Message, state: FSMContext, bot: Bot
    ):
        """Show current participant for category/cluster assignment"""
        data = await state.get_data()
        participants = data.get("participants", [])
        current_index = data.get("current_index", 0)
        assignment_type = data.get("assignment_type", "category")

        if current_index >= len(participants):
            # Assignment complete, show summary
            await show_assignment_summary(message, state, bot, assignment_type)
            return

        participant = participants[current_index]
        user_id, username, name, target_time, reg_date, gender, category = participant[:7]
        cluster = participant[7] if len(participant) > 7 else None

        # Build participant info
        text = f"👤 <b>Участник {current_index + 1}/{len(participants)}</b>\n\n"
        text += f"📝 Имя: <b>{name}</b>\n"
        text += f"🆔 ID: <code>{user_id}</code>\n"
        if username:
            text += f"👤 Username: @{username}\n"
        if target_time:
            text += f"⏱️ Целевое время: {target_time}\n"
        if gender:
            text += f"👤 Пол: {gender}\n"

        # Show current assignments
        if category:
            text += f"📂 Текущая категория: <b>{category}</b>\n"
        if cluster:
            text += f"🎯 Текущий кластер: <b>{cluster}</b>\n"

        text += "\n"

        if assignment_type == "category":
            text += "📝 <b>Выберите категорию для участника:</b>"
            keyboard = create_category_selection_keyboard(current_index, len(participants))
            await state.set_state(RegistrationForm.waiting_for_category_assignment)
        else:  # cluster
            text += "🎯 <b>Выберите кластер для участника:</b>"
            keyboard = create_cluster_selection_keyboard(current_index, len(participants))
            await state.set_state(RegistrationForm.waiting_for_cluster_assignment)

        await message.answer(text, reply_markup=keyboard)

    @dp.callback_query(F.data.startswith("category_"))
    async def process_category_selection(
        callback_query: CallbackQuery, state: FSMContext
    ):
        """Process category selection for participant"""
        if callback_query.from_user.id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        # Handle navigation buttons
        if callback_query.data == "category_nav_previous":
            await callback_query.answer()
            data = await state.get_data()
            current_index = data.get("current_index", 0)
            if current_index > 0:
                await state.update_data(current_index=current_index - 1)
                await callback_query.message.delete()
                await show_participant_for_assignment(callback_query.message, state, bot)
            return

        if callback_query.data == "category_nav_next":
            await callback_query.answer()
            data = await state.get_data()
            participants = data.get("participants", [])
            current_index = data.get("current_index", 0)
            if current_index < len(participants) - 1:
                await state.update_data(current_index=current_index + 1)
                await callback_query.message.delete()
                await show_participant_for_assignment(callback_query.message, state, bot)
            return

        await callback_query.answer()

        data = await state.get_data()
        participants = data.get("participants", [])
        current_index = data.get("current_index", 0)

        if current_index >= len(participants):
            await callback_query.message.answer("❌ Ошибка: участник не найден")
            return

        participant = participants[current_index]
        user_id = participant[0]

        # Get selected category
        category_data = callback_query.data.replace("category_", "")
        category_map = {
            "superelite": "СуперЭлита",
            "elite": "Элита",
            "classic": "Классика",
            "women": "Женский",
            "team": "Команда",
        }

        selected_category = category_map.get(category_data)

        # Save category to database
        if selected_category:
            success = set_participant_category(user_id, selected_category)
            if not success:
                await callback_query.message.answer(
                    f"❌ Ошибка при сохранении категории для участника"
                )
                return

            # Show success message briefly
            await callback_query.answer(f"✅ Категория {selected_category} сохранена", show_alert=False)

            # Update participant data in state to reflect the change
            participants[current_index] = list(participants[current_index])
            participants[current_index][6] = selected_category  # Update category field
            await state.update_data(participants=participants)

            # Refresh the message to show updated category
            await callback_query.message.delete()
            await show_participant_for_assignment(callback_query.message, state, bot)

    @dp.callback_query(F.data.startswith("cluster_"))
    async def process_cluster_selection(
        callback_query: CallbackQuery, state: FSMContext
    ):
        """Process cluster selection for participant"""
        if callback_query.from_user.id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        # Handle navigation buttons
        if callback_query.data == "cluster_nav_previous":
            await callback_query.answer()
            data = await state.get_data()
            current_index = data.get("current_index", 0)
            if current_index > 0:
                await state.update_data(current_index=current_index - 1)
                await callback_query.message.delete()
                await show_participant_for_assignment(callback_query.message, state, bot)
            return

        if callback_query.data == "cluster_nav_next":
            await callback_query.answer()
            data = await state.get_data()
            participants = data.get("participants", [])
            current_index = data.get("current_index", 0)
            if current_index < len(participants) - 1:
                await state.update_data(current_index=current_index + 1)
                await callback_query.message.delete()
                await show_participant_for_assignment(callback_query.message, state, bot)
            return

        await callback_query.answer()

        data = await state.get_data()
        participants = data.get("participants", [])
        current_index = data.get("current_index", 0)

        if current_index >= len(participants):
            await callback_query.message.answer("❌ Ошибка: участник не найден")
            return

        participant = participants[current_index]
        user_id = participant[0]

        # Get selected cluster
        cluster_data = callback_query.data.replace("cluster_", "")
        selected_cluster = cluster_data

        # Save cluster to database
        if selected_cluster:
            success = set_participant_cluster(user_id, selected_cluster)
            if not success:
                await callback_query.message.answer(
                    f"❌ Ошибка при сохранении кластера для участника"
                )
                return

            # Show success message briefly
            await callback_query.answer(f"✅ Кластер {selected_cluster} сохранён", show_alert=False)

            # Update participant data in state to reflect the change
            participants[current_index] = list(participants[current_index])
            participants[current_index][7] = selected_cluster  # Update cluster field
            await state.update_data(participants=participants)

            # Refresh the message to show updated cluster
            await callback_query.message.delete()
            await show_participant_for_assignment(callback_query.message, state, bot)

    async def show_assignment_summary(
        message: Message, state: FSMContext, bot: Bot, assignment_type: str
    ):
        """Show summary of assignment process"""
        participants = get_participants_with_categories()

        if assignment_type == "category":
            text = "✅ <b>Назначение категорий завершено!</b>\n\n"
            text += "📋 <b>Сводка по категориям:</b>\n"
        else:
            text = "✅ <b>Назначение кластеров завершено!</b>\n\n"
            text += "📋 <b>Сводка по кластерам:</b>\n"

        # Count by categories/clusters
        if assignment_type == "category":
            category_counts = {}
            for participant in participants:
                category = participant[5] or "Не назначена"
                category_counts[category] = category_counts.get(category, 0) + 1

            for category, count in sorted(category_counts.items()):
                emoji = {
                    "СуперЭлита": "💎",
                    "Элита": "🥇",
                    "Классика": "🏃",
                    "Женский": "👩",
                    "Команда": "👥",
                    "Не назначена": "❓",
                }.get(category, "📂")
                text += f"• {emoji} {category}: {count} чел.\n"
        else:
            cluster_counts = {}
            for participant in participants:
                cluster = participant[6] or "Не назначен"
                cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1

            for cluster, count in sorted(cluster_counts.items()):
                emoji = {
                    "A": "🅰️",
                    "B": "🅱️",
                    "C": "🅲",
                    "D": "🅳",
                    "E": "🅴",
                    "F": "🅵",
                    "G": "🅶",
                    "Не назначен": "❓",
                }.get(cluster, "🎯")
                text += f"• {emoji} Кластер {cluster}: {count} чел.\n"

        text += f"\n📊 Всего участников обработано: {len(participants)}"

        await message.answer(text, reply_markup=create_clusters_category_keyboard())
        await state.clear()

    @dp.callback_query(F.data == "admin_view_distribution")
    async def view_distribution(callback_query: CallbackQuery):
        """View final distribution of participants"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        participants = get_participants_with_categories()

        if not participants:
            await callback_query.message.answer("❌ Нет зарегистрированных участников")
            return

        # Build distribution message
        text = "📋 <b>Полное распределение участников</b>\n\n"

        current_category = None
        current_cluster = None

        for participant in participants:
            (
                user_id,
                username,
                name,
                target_time,
                gender,
                category,
                cluster,
                role,
                result,
                bib_number,
                team_name,
                team_invite_code,
            ) = participant

            # Group by category first
            if category != current_category:
                current_category = category
                category_emoji = {
                    "СуперЭлита": "💎",
                    "Элита": "🥇",
                    "Классика": "🏃",
                    "Женский": "👩",
                    "Команда": "👥",
                }.get(category, "📂")

                category_name = category or "Без категории"
                text += f"\n{category_emoji} <b>{category_name}</b>\n"
                text += "─" * 25 + "\n"
                current_cluster = None  # Reset cluster grouping

            # Group by cluster within category
            if cluster != current_cluster:
                current_cluster = cluster
                cluster_emoji = {"A": "🅰️", "B": "🅱️", "C": "🅲", "D": "🅳", "E": "🅴"}.get(
                    cluster, "❓"
                )

                cluster_name = f"Кластер {cluster}" if cluster else "Без кластера"
                text += f"  {cluster_emoji} <i>{cluster_name}</i>\n"

            # Participant info
            participant_text = f"  • {name}"
            if target_time:
                participant_text += f" (цель: {target_time})"
            if gender:
                participant_text += f" [{gender}]"
            participant_text += "\n"

            text += participant_text

        # Split long messages
        if len(text) > 4000:
            # Send in chunks
            chunks = []
            lines = text.split("\n")
            current_chunk = ""

            for line in lines:
                if len(current_chunk + line + "\n") > 4000:
                    chunks.append(current_chunk)
                    current_chunk = line + "\n"
                else:
                    current_chunk += line + "\n"

            if current_chunk:
                chunks.append(current_chunk)

            for i, chunk in enumerate(chunks):
                if i == 0:
                    await callback_query.message.answer(chunk)
                else:
                    await bot.send_message(callback_query.from_user.id, chunk)

            await bot.send_message(
                callback_query.from_user.id,
                "📊 Распределение показано полностью.",
                reply_markup=create_clusters_category_keyboard(),
            )
        else:
            await callback_query.message.answer(
                text, reply_markup=create_clusters_category_keyboard()
            )

    @dp.callback_query(F.data == "admin_clear_categories")
    async def clear_categories(callback_query: CallbackQuery):
        """Clear all categories"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        success = clear_all_categories()
        if success:
            text = "✅ <b>Все категории участников очищены</b>\n\n"
            text += "🔄 Участники больше не имеют назначенных категорий.\n"
            text += (
                "📝 Вы можете заново назначить категории через 'Добавить категории'."
            )
        else:
            text = "❌ <b>Ошибка при очистке категорий</b>\n\n"
            text += "Попробуйте повторить операцию позже."

        await callback_query.message.answer(
            text, reply_markup=create_clusters_category_keyboard()
        )

    @dp.callback_query(F.data == "admin_clear_clusters")
    async def clear_clusters(callback_query: CallbackQuery):
        """Clear all clusters"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        success = clear_all_clusters()
        if success:
            text = "✅ <b>Все кластеры участников очищены</b>\n\n"
            text += "🔄 Участники больше не имеют назначенных кластеров.\n"
            text += (
                "🎯 Вы можете заново назначить кластеры через 'Распределить кластеры'."
            )
        else:
            text = "❌ <b>Ошибка при очистке кластеров</b>\n\n"
            text += "Попробуйте повторить операцию позже."

        await callback_query.message.answer(
            text, reply_markup=create_clusters_category_keyboard()
        )

    @dp.callback_query(F.data == "admin_notify_distribution")
    async def notify_distribution(callback_query: CallbackQuery):
        """Notify all participants about their category/cluster assignment"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        participants = get_participants_with_categories()

        if not participants:
            await callback_query.message.answer("❌ Нет участников для уведомления")
            return

        # Count participants with categories/clusters
        has_categories = any(p[5] for p in participants)  # category field
        has_clusters = any(p[6] for p in participants)  # cluster field

        if not has_categories and not has_clusters:
            await callback_query.message.answer(
                "❌ Участники не имеют назначенных категорий или кластеров.\n\n"
                "Сначала назначьте категории и/или кластеры через соответствующие команды."
            )
            return

        # Send notifications
        success_count = 0
        error_count = 0

        text = "📢 <b>Рассылаю уведомления участникам...</b>\n\n"
        await callback_query.message.answer(text)

        for participant in participants:
            (
                user_id_p,
                username,
                name,
                target_time,
                gender,
                category,
                cluster,
                role,
                result,
                bib_number,
                team_name,
                team_invite_code,
            ) = participant

            try:
                # Build personal message
                msg_text = f"🎯 <b>Распределение на забег</b>\n\n"
                msg_text += f"👤 Привет, <b>{name}</b>!\n\n"

                if category:
                    category_emoji = {
                        "СуперЭлита": "💎",
                        "Элита": "🥇",
                        "Классика": "🏃",
                        "Женский": "👩",
                        "Команда": "👥",
                    }.get(category, "📂")
                    msg_text += (
                        f"📂 <b>Ваша категория:</b> {category_emoji} {category}\n"
                    )

                if cluster:
                    cluster_emoji = {
                        "A": "🅰️",
                        "B": "🅱️",
                        "C": "🅲",
                        "D": "🅳",
                        "E": "🅴",
                        "F": "🅵",
                        "G": "🅶",
                    }.get(cluster, "🎯")
                    msg_text += f"🎯 <b>Ваш стартовый кластер:</b> {cluster_emoji} Кластер {cluster}\n"

                msg_text += "\n🏃‍♀️ Увидимся на старте!"

                await bot.send_message(user_id_p, msg_text)
                success_count += 1

            except Exception as e:
                logger.error(f"Ошибка отправки уведомления участнику {user_id_p}: {e}")
                error_count += 1

        # Send summary
        summary_text = "✅ <b>Рассылка уведомлений завершена</b>\n\n"
        summary_text += f"📤 Отправлено: {success_count}\n"
        if error_count > 0:
            summary_text += f"❌ Ошибки: {error_count}\n"
        summary_text += f"📊 Всего участников: {len(participants)}"

        await bot.send_message(
            callback_query.from_user.id,
            summary_text,
            reply_markup=create_clusters_category_keyboard(),
        )

    @dp.callback_query(F.data == "admin_create_document")
    async def create_document(callback_query: CallbackQuery):
        """Create printable document with participant distribution"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        participants = get_participants_with_categories()

        if not participants:
            await callback_query.message.answer(
                "❌ Нет участников для создания документа"
            )
            return

        # Check if we have categories and/or clusters
        has_categories = any(p[5] for p in participants)  # category field
        has_clusters = any(p[6] for p in participants)  # cluster field

        # Generate document content
        from datetime import datetime
        import pytz

        moscow_tz = pytz.timezone("Europe/Moscow")
        current_time = datetime.now(moscow_tz)

        document_text = "🏃‍♀️ <b>РАСПРЕДЕЛЕНИЕ УЧАСТНИКОВ ПИВНОГО КВАРТАЛА</b>\n"
        document_text += f"📅 Создано: {current_time.strftime('%d.%m.%Y %H:%M')} МСК\n"
        document_text += "=" * 50 + "\n\n"

        if has_categories:
            # Group by categories first
            categories = {}
            for participant in participants:
                (
                    user_id_p,
                    username,
                    name,
                    target_time,
                    gender,
                    category,
                    cluster,
                    role,
                    result,
                    bib_number,
                    team_name,
                    team_invite_code,
                ) = participant
                if role != "runner":  # Only runners have categories
                    continue

                cat_key = category or "Без категории"
                if cat_key not in categories:
                    categories[cat_key] = []
                categories[cat_key].append(participant)

            # Sort categories
            category_order = [
                "СуперЭлита",
                "Элита",
                "Классика",
                "Женский",
                "Команда",
                "Без категории",
            ]
            for cat_name in category_order:
                if cat_name not in categories:
                    continue

                participants_in_cat = categories[cat_name]
                if not participants_in_cat:
                    continue

                category_emoji = {
                    "СуперЭлита": "💎",
                    "Элита": "🥇",
                    "Классика": "🏃",
                    "Женский": "👩",
                    "Команда": "👥",
                    "Без категории": "❓",
                }.get(cat_name, "📂")

                document_text += f"{category_emoji} <b>{cat_name.upper()}</b>\n"
                document_text += "-" * 30 + "\n"

                if has_clusters:
                    # Group by clusters within category
                    clusters = {}
                    for p in participants_in_cat:
                        cluster = p[6] or "Без кластера"
                        if cluster not in clusters:
                            clusters[cluster] = []
                        clusters[cluster].append(p)

                    # Sort clusters
                    cluster_order = ["A", "B", "C", "D", "E", "F", "G", "Без кластера"]
                    for cluster_name in cluster_order:
                        if cluster_name not in clusters:
                            continue

                        cluster_participants = clusters[cluster_name]
                        if not cluster_participants:
                            continue

                        cluster_emoji = {
                            "A": "🅰️",
                            "B": "🅱️",
                            "C": "🅲",
                            "D": "🅳",
                            "E": "🅴",
                            "F": "🅵",
                            "G": "🅶",
                            "Без кластера": "❓",
                        }.get(cluster_name, "🎯")

                        document_text += (
                            f"\n  {cluster_emoji} Кластер {cluster_name}:\n"
                        )

                        for i, p in enumerate(
                            sorted(cluster_participants, key=lambda x: x[2]), 1
                        ):
                            name = p[2]
                            target_time = p[3] or "—"
                            bib_number = (
                                p[9] if len(p) > 9 else None
                            )  # Check if bib_number exists
                            bib_info = f" (№{bib_number})" if bib_number else ""
                            document_text += (
                                f"    {i}. {name}{bib_info} - {target_time}\n"
                            )
                else:
                    # Just list participants in category
                    for i, p in enumerate(
                        sorted(participants_in_cat, key=lambda x: x[2]), 1
                    ):
                        name = p[2]
                        target_time = p[3] or "—"
                        bib_number = p[9] if len(p) > 9 else None
                        bib_info = f" (№{bib_number})" if bib_number else ""
                        document_text += f"  {i}. {name}{bib_info} - {target_time}\n"

                document_text += "\n"

        elif has_clusters:
            # Only clusters, no categories
            clusters = {}
            for participant in participants:
                if participant[7] != "runner":  # role field
                    continue

                cluster = participant[6] or "Без кластера"
                if cluster not in clusters:
                    clusters[cluster] = []
                clusters[cluster].append(participant)

            cluster_order = ["A", "B", "C", "D", "E", "F", "G", "Без кластера"]
            for cluster_name in cluster_order:
                if cluster_name not in clusters:
                    continue

                cluster_participants = clusters[cluster_name]
                if not cluster_participants:
                    continue

                cluster_emoji = {
                    "A": "🅰️",
                    "B": "🅱️",
                    "C": "🅲",
                    "D": "🅳",
                    "E": "🅴",
                    "F": "🅵",
                    "G": "🅶",
                    "Без кластера": "❓",
                }.get(cluster_name, "🎯")

                document_text += f"{cluster_emoji} <b>КЛАСТЕР {cluster_name}</b>\n"
                document_text += "-" * 30 + "\n"

                for i, p in enumerate(
                    sorted(cluster_participants, key=lambda x: x[2]), 1
                ):
                    name = p[2]
                    target_time = p[3] or "—"
                    bib_number = p[9] if len(p) > 9 else None
                    bib_info = f" (№{bib_number})" if bib_number else ""
                    document_text += f"  {i}. {name}{bib_info} - {target_time}\n"

                document_text += "\n"

        else:
            document_text += "❌ Участники не имеют назначенных категорий или кластеров"

        # Add volunteers if any
        volunteers = [p for p in participants if p[7] == "volunteer"]
        if volunteers:
            document_text += "\n👥 <b>ВОЛОНТЁРЫ</b>\n"
            document_text += "-" * 30 + "\n"
            for i, v in enumerate(sorted(volunteers, key=lambda x: x[2]), 1):
                name = v[2]
                document_text += f"  {i}. {name}\n"

        document_text += "\n" + "=" * 50 + "\n"
        document_text += f"📊 Всего участников: {len([p for p in participants if p[7] == 'runner'])}\n"
        if volunteers:
            document_text += f"👥 Волонтёров: {len(volunteers)}\n"

        # Split document if too long
        if len(document_text) > 4000:
            # Send in chunks
            chunks = []
            lines = document_text.split("\n")
            current_chunk = ""

            for line in lines:
                if len(current_chunk + line + "\n") > 4000:
                    chunks.append(current_chunk)
                    current_chunk = line + "\n"
                else:
                    current_chunk += line + "\n"

            if current_chunk:
                chunks.append(current_chunk)

            await callback_query.message.answer(
                "📄 <b>Создаю документ для печати...</b>"
            )

            for i, chunk in enumerate(chunks):
                if i == 0:
                    await callback_query.message.answer(chunk)
                else:
                    await bot.send_message(callback_query.from_user.id, chunk)

            await bot.send_message(
                callback_query.from_user.id,
                "✅ <b>Документ готов!</b>\n\n📋 Скопируйте текст выше для печати.",
                reply_markup=create_clusters_category_keyboard(),
            )
        else:
            await callback_query.message.answer(
                document_text, reply_markup=create_clusters_category_keyboard()
            )

    @dp.callback_query(F.data == "admin_download_csv")
    async def download_csv(callback_query: CallbackQuery):
        """Create and send CSV file with participant distribution"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        participants = get_participants_with_categories()

        if not participants:
            await callback_query.message.answer("❌ Нет участников для создания CSV")
            return

        try:
            import csv
            import io
            from datetime import datetime
            import pytz

            moscow_tz = pytz.timezone("Europe/Moscow")
            current_time = datetime.now(moscow_tz)

            # Create CSV content
            output = io.StringIO()
            writer = csv.writer(
                output, delimiter=";", lineterminator="\n", quoting=csv.QUOTE_MINIMAL
            )

            # Check what data we have
            has_categories = any(p[5] for p in participants)  # category field
            has_clusters = any(p[6] for p in participants)  # cluster field

            # Write header
            header = ["Username", "Имя"]
            if has_categories:
                header.append("Категория")
            if has_clusters:
                header.append("Кластер")
            header.extend(["Беговой номер", "Результат"])

            writer.writerow(header)

            # Sort participants for better organization
            # Filter only runners since we're creating distribution CSV
            runners_only = [p for p in participants if p[7] == "runner"]

            sorted_participants = sorted(
                runners_only,
                key=lambda p: (
                    p[5] or "Я",  # Category sorting (Я comes after all categories)
                    p[6] or "Я",  # Cluster sorting
                    p[2],  # Name
                ),
            )

            # Write participant data
            for participant in sorted_participants:
                (
                    user_id_p,
                    username,
                    name,
                    target_time,
                    gender,
                    category,
                    cluster,
                    role,
                    result,
                    bib_number,
                    team_name,
                    team_invite_code,
                ) = participant

                # All fields are now available from the participant tuple

                # Build row
                row = [username or "", name]

                if has_categories:
                    row.append(category or "")
                if has_clusters:
                    row.append(cluster or "")

                row.extend([bib_number or "", result or ""])

                writer.writerow(row)

            # Get CSV content
            csv_content = output.getvalue()
            output.close()

            # Create file
            filename = (
                f"beer_mile_distribution_{current_time.strftime('%Y%m%d_%H%M%S')}.csv"
            )

            # Send file
            from aiogram.types import BufferedInputFile

            file_data = csv_content.encode("utf-8-sig")  # BOM for Excel compatibility
            input_file = BufferedInputFile(file_data, filename)

            # Send file first without caption or keyboard
            await bot.send_document(callback_query.from_user.id, input_file)

            # Then send info message with keyboard
            caption = f"📊 <b>Распределение участников</b>\n\n"
            caption += f"📅 Создано: {current_time.strftime('%d.%m.%Y %H:%M')} МСК\n"
            caption += f"👥 Бегунов в файле: {len(sorted_participants)}\n"

            if has_categories:
                # Count by categories
                category_counts = {}
                for p in sorted_participants:
                    cat = p[5] or "Без категории"
                    category_counts[cat] = category_counts.get(cat, 0) + 1

                caption += f"📂 Категории: {', '.join([f'{cat} ({count})' for cat, count in sorted(category_counts.items())])}\n"

            if has_clusters:
                # Count by clusters
                cluster_counts = {}
                for p in sorted_participants:
                    cluster = p[6] or "Без кластера"
                    cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1

                caption += f"🎯 Кластеры: {', '.join([f'{cluster} ({count})' for cluster, count in sorted(cluster_counts.items())])}\n"

            caption += f"\n💡 Файл готов для печати и обработки в Excel"

            await bot.send_message(
                callback_query.from_user.id,
                caption,
                reply_markup=create_clusters_category_keyboard(),
            )

            logger.info(
                f"CSV файл распределения отправлен администратору, бегунов: {len(sorted_participants)}"
            )

        except Exception as e:
            logger.error(f"Ошибка при создании CSV файла распределения: {e}")
            await callback_query.message.answer(
                "❌ <b>Ошибка при создании CSV файла</b>\n\n"
                "Попробуйте повторить операцию позже.",
                reply_markup=create_clusters_category_keyboard(),
            )

    logger.info("Обработчики кластеров и категорий зарегистрированы")

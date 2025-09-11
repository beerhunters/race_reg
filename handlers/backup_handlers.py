import os
import shutil
import sqlite3
import json
from datetime import datetime, timedelta
from aiogram import Dispatcher, Bot, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
import pytz
import zipfile
import asyncio
import logging

from .utils import logger, RegistrationForm
from database import DB_PATH

# Global variable to store backup task
backup_task = None


def register_backup_handlers(dp: Dispatcher, bot: Bot, admin_id: int):
    logger.info("Регистрация обработчиков резервного копирования")

    @dp.callback_query(F.data == "admin_create_backup")
    async def create_manual_backup(callback_query: CallbackQuery):
        """Create manual backup"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()
        await callback_query.message.delete()

        status_message = await callback_query.message.answer(
            "💾 <b>Создание резервной копии...</b>"
        )

        try:
            backup_file = await create_backup()
            if backup_file and os.path.exists(backup_file):
                # Send backup file to admin
                with open(backup_file, "rb") as f:
                    file_data = f.read()

                input_file = BufferedInputFile(file_data, os.path.basename(backup_file))

                moscow_tz = pytz.timezone("Europe/Moscow")
                current_time = datetime.now(moscow_tz)

                # Send file first without caption
                await bot.send_document(admin_id, input_file)

                # Then send info message
                caption = f"💾 <b>Резервная копия создана</b>\n\n"
                caption += f"📅 Дата: {current_time.strftime('%d.%m.%Y %H:%M')} МСК\n"
                caption += f"📁 Файл: {os.path.basename(backup_file)}\n"
                caption += f"📊 Размер: {len(file_data) / 1024:.1f} КБ\n\n"
                caption += "💡 Сохраните файл в надежном месте"

                await bot.send_message(admin_id, caption)

                await status_message.edit_text(
                    "✅ <b>Резервная копия создана и отправлена!</b>"
                )

                # Clean up local backup file
                try:
                    os.remove(backup_file)
                except:
                    pass

            else:
                await status_message.edit_text(
                    "❌ <b>Ошибка при создании резервной копии</b>"
                )

        except Exception as e:
            logger.error(f"Ошибка при создании ручной резервной копии: {e}")
            await status_message.edit_text(
                "❌ <b>Ошибка при создании резервной копии</b>\n\nПроверьте логи."
            )

    @dp.callback_query(F.data == "admin_backup_settings")
    async def backup_settings(callback_query: CallbackQuery):
        """Show backup settings and status"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        # Check backup status
        backup_dir = "/app/backups"
        backup_files = []
        if os.path.exists(backup_dir):
            backup_files = [f for f in os.listdir(backup_dir) if f.endswith(".zip")]
            backup_files.sort(reverse=True)  # Latest first

        text = "💾 <b>Система резервного копирования</b>\n\n"

        # Automatic backup status
        global backup_task
        if backup_task and not backup_task.done():
            text += "🔄 <b>Автоматические бекапы:</b> Активны\n"
            text += "⏰ Интервал: каждые 6 часов\n"
        else:
            text += "❌ <b>Автоматические бекапы:</b> Отключены\n"

        text += f"📁 Локальных бекапов: {len(backup_files)}\n\n"

        # Recent backups
        if backup_files:
            text += "📋 <b>Последние бекапы:</b>\n"
            for i, backup_file in enumerate(backup_files[:5]):  # Show last 5
                try:
                    # Extract timestamp from filename
                    timestamp_str = backup_file.replace("backup_", "").replace(
                        ".zip", ""
                    )
                    backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    formatted_time = backup_time.strftime("%d.%m.%Y %H:%M")
                    text += f"• {formatted_time}\n"
                except:
                    text += f"• {backup_file}\n"

            if len(backup_files) > 5:
                text += f"• ... и ещё {len(backup_files) - 5}\n"
        else:
            text += "📋 <b>Бекапы не найдены</b>\n"

        text += "\n🛠 <b>Доступные действия:</b>\n"
        text += "• Создать резервную копию вручную\n"
        text += "• Запустить/остановить автобекапы\n"
        text += "• Очистить старые бекапы"

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💾 Создать бекап", callback_data="admin_create_backup"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🔄 Автобекапы", callback_data="admin_toggle_auto_backup"
                    ),
                    InlineKeyboardButton(
                        text="🧹 Очистить старые", callback_data="admin_cleanup_backups"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="📥 Восстановить", callback_data="admin_restore_backup"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 Главное меню", callback_data="main_menu"
                    ),
                ],
            ]
        )

        await callback_query.message.edit_text(text, reply_markup=keyboard)

    @dp.callback_query(F.data == "admin_toggle_auto_backup")
    async def toggle_auto_backup(callback_query: CallbackQuery):
        """Toggle automatic backup system"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        global backup_task

        if backup_task and not backup_task.done():
            # Stop automatic backups
            backup_task.cancel()
            await callback_query.message.edit_text(
                "❌ <b>Автоматические резервные копии остановлены</b>\n\n"
                "💡 Вы можете запустить их снова через настройки бекапов."
            )
            logger.info("Автоматические бекапы остановлены администратором")
        else:
            # Start automatic backups
            backup_task = asyncio.create_task(automatic_backup_scheduler(bot, admin_id))
            await callback_query.message.edit_text(
                "✅ <b>Автоматические резервные копии запущены</b>\n\n"
                "⏰ Интервал: каждые 6 часов\n"
                "📤 Бекапы будут отправляться вам в личные сообщения"
            )
            logger.info("Автоматические бекапы запущены администратором")

    @dp.callback_query(F.data == "admin_cleanup_backups")
    async def cleanup_old_backups(callback_query: CallbackQuery):
        """Clean up old backup files"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        try:
            backup_dir = "/app/backups"
            if not os.path.exists(backup_dir):
                await callback_query.message.answer("📂 Директория бекапов не найдена")
                return

            # Get all backup files
            backup_files = [f for f in os.listdir(backup_dir) if f.endswith(".zip")]
            backup_files.sort()

            if len(backup_files) <= 10:  # Keep at least 10 backups
                await callback_query.message.answer(
                    f"💾 <b>Очистка не требуется</b>\n\n"
                    f"Найдено {len(backup_files)} бекапов (≤ 10)"
                )
                return

            # Remove old backups, keep last 10
            files_to_remove = backup_files[:-10]
            removed_count = 0

            for file_name in files_to_remove:
                try:
                    os.remove(os.path.join(backup_dir, file_name))
                    removed_count += 1
                except:
                    pass

            await callback_query.message.edit_text(
                f"🧹 <b>Очистка завершена</b>\n\n"
                f"• Удалено старых бекапов: {removed_count}\n"
                f"• Оставлено последних: {len(backup_files) - removed_count}\n\n"
                f"💡 Система автоматически сохраняет последние 10 бекапов"
            )

            logger.info(f"Удалено {removed_count} старых бекапов")

        except Exception as e:
            logger.error(f"Ошибка при очистке бекапов: {e}")
            await callback_query.message.answer("❌ Ошибка при очистке бекапов")

    @dp.callback_query(F.data == "admin_restore_backup")
    async def restore_backup_menu(callback_query: CallbackQuery, state: FSMContext):
        """Show restore backup menu with file upload option"""
        user_id = callback_query.from_user.id
        if user_id != admin_id:
            await callback_query.answer("❌ Доступ запрещен")
            return

        await callback_query.answer()

        text = "📥 <b>Восстановление из резервной копии</b>\n\n"
        text += "⚠️ <b>ВНИМАНИЕ!</b>\n"
        text += "• Это действие полностью заменит текущие данные\n"
        text += "• Рекомендуется создать резервную копию перед восстановлением\n"
        text += "• Операция необратима\n\n"
        text += "📎 Отправьте ZIP-файл резервной копии для восстановления"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Назад", callback_data="admin_backup_settings"
                    ),
                ]
            ]
        )

        await state.set_state(RegistrationForm.restore_backup)
        await callback_query.message.edit_text(text, reply_markup=keyboard)

    @dp.message(RegistrationForm.restore_backup)
    async def process_restore_backup(message: Message, state: FSMContext):
        """Process backup file for restoration"""
        user_id = message.from_user.id
        if user_id != admin_id:
            await message.answer("❌ Доступ запрещен")
            return

        if not message.document:
            await message.answer("❌ Пожалуйста, отправьте ZIP-файл резервной копии")
            return

        if not message.document.file_name.endswith(".zip"):
            await message.answer("❌ Файл должен быть в формате ZIP")
            return

        status_message = await message.answer(
            "📥 <b>Восстановление из резервной копии...</b>"
        )

        try:
            # Download backup file
            file_info = await bot.get_file(message.document.file_id)
            backup_file_path = f"/tmp/restore_backup_{message.document.file_name}"

            await bot.download_file(file_info.file_path, backup_file_path)

            # Restore from backup
            success = await restore_from_backup(backup_file_path)

            if success:
                await status_message.edit_text(
                    "✅ <b>Восстановление завершено успешно!</b>\n\n"
                    "🔄 Данные были восстановлены из резервной копии.\n"
                    "💡 Рекомендуется перезапустить бота для корректной работы."
                )
                logger.info(
                    f"Восстановление из резервной копии выполнено администратором: {message.document.file_name}"
                )
            else:
                await status_message.edit_text(
                    "❌ <b>Ошибка при восстановлении</b>\n\n"
                    "Проверьте формат файла и логи для подробной информации."
                )

            # Clean up downloaded file
            try:
                os.remove(backup_file_path)
            except:
                pass

        except Exception as e:
            logger.error(f"Ошибка при восстановлении из резервной копии: {e}")
            await status_message.edit_text(
                "❌ <b>Ошибка при восстановлении</b>\n\n"
                "Проверьте файл и попробуйте снова."
            )

        await state.clear()

    logger.info("Обработчики резервного копирования зарегистрированы")


async def create_backup():
    """Create a backup of all important data"""
    try:
        moscow_tz = pytz.timezone("Europe/Moscow")
        current_time = datetime.now(moscow_tz)
        timestamp = current_time.strftime("%Y%m%d_%H%M%S")

        backup_dir = "/app/backups"
        os.makedirs(backup_dir, exist_ok=True)

        backup_filename = f"backup_{timestamp}.zip"
        backup_path = os.path.join(backup_dir, backup_filename)

        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add database file
            if os.path.exists(DB_PATH):
                zipf.write(DB_PATH, "race_participants.db")
                logger.info("База данных добавлена в бекап")

            # Add configuration files
            config_files = ["config.json", "messages.json"]
            for config_file in config_files:
                if os.path.exists(config_file):
                    zipf.write(config_file, config_file)
                    logger.info(f"Файл конфигурации {config_file} добавлен в бекап")

            # Add images directory
            images_dir = "/app/images"
            if os.path.exists(images_dir):
                for root, dirs, files in os.walk(images_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_path = os.path.relpath(file_path, "/app")
                        zipf.write(file_path, arc_path)
                logger.info("Директория изображений добавлена в бекап")

            # Add backup metadata
            metadata = {
                "backup_date": current_time.isoformat(),
                "backup_version": "1.0",
                "description": "Beer Block Registration Bot Backup",
                "files_included": [],
            }

            # List all files in backup
            for info in zipf.infolist():
                metadata["files_included"].append(
                    {
                        "filename": info.filename,
                        "size": info.file_size,
                        "compressed_size": info.compress_size,
                    }
                )

            # Add metadata to backup
            zipf.writestr(
                "backup_metadata.json",
                json.dumps(metadata, indent=2, ensure_ascii=False),
            )

        logger.info(f"Резервная копия создана: {backup_path}")
        return backup_path

    except Exception as e:
        logger.error(f"Ошибка при создании резервной копии: {e}")
        return None


async def automatic_backup_scheduler(bot: Bot, admin_id: int):
    """Automatic backup scheduler - runs every 6 hours"""
    logger.info("Запущен планировщик автоматических бекапов (каждые 6 часов)")

    while True:
        try:
            # Wait 6 hours
            await asyncio.sleep(6 * 60 * 60)  # 6 hours in seconds

            logger.info("Создание автоматической резервной копии...")

            # Create backup
            backup_file = await create_backup()

            if backup_file and os.path.exists(backup_file):
                try:
                    # Send backup to admin
                    with open(backup_file, "rb") as f:
                        file_data = f.read()

                    input_file = BufferedInputFile(
                        file_data, os.path.basename(backup_file)
                    )

                    moscow_tz = pytz.timezone("Europe/Moscow")
                    current_time = datetime.now(moscow_tz)

                    # Send file first without caption
                    await bot.send_document(admin_id, input_file)

                    # Then send info message
                    caption = f"🤖 <b>Автоматическая резервная копия</b>\n\n"
                    caption += (
                        f"📅 Создана: {current_time.strftime('%d.%m.%Y %H:%M')} МСК\n"
                    )
                    caption += f"📁 Файл: {os.path.basename(backup_file)}\n"
                    caption += f"📊 Размер: {len(file_data) / 1024:.1f} КБ\n\n"
                    caption += "💾 Автоматическое резервное копирование каждые 6 часов"

                    await bot.send_message(admin_id, caption)

                    logger.info(
                        "Автоматическая резервная копия отправлена администратору"
                    )

                except Exception as e:
                    logger.error(
                        f"Ошибка при отправке автоматической резервной копии: {e}"
                    )

                # Clean up local file after sending
                try:
                    os.remove(backup_file)
                except:
                    pass
            else:
                logger.error("Не удалось создать автоматическую резервную копию")

                # Notify admin about backup failure
                try:
                    await bot.send_message(
                        admin_id,
                        "⚠️ <b>Ошибка автоматического бекапа</b>\n\n"
                        "Не удалось создать автоматическую резервную копию. "
                        "Проверьте логи и создайте бекап вручную.",
                    )
                except:
                    pass

            # Clean up old local backups (keep only last 5 local backups)
            try:
                backup_dir = "/app/backups"
                if os.path.exists(backup_dir):
                    backup_files = [
                        f for f in os.listdir(backup_dir) if f.endswith(".zip")
                    ]
                    backup_files.sort()

                    # Remove old backups, keep last 5
                    while len(backup_files) > 5:
                        oldest_backup = backup_files.pop(0)
                        os.remove(os.path.join(backup_dir, oldest_backup))
                        logger.info(f"Удален старый автобекап: {oldest_backup}")
            except Exception as e:
                logger.error(f"Ошибка при очистке старых автобекапов: {e}")

        except asyncio.CancelledError:
            logger.info("Планировщик автоматических бекапов остановлен")
            break
        except Exception as e:
            logger.error(f"Ошибка в планировщике автоматических бекапов: {e}")
            # Continue running even if there's an error


async def start_automatic_backups(bot: Bot, admin_id: int):
    """Start automatic backups on bot startup"""
    global backup_task
    if backup_task is None or backup_task.done():
        backup_task = asyncio.create_task(automatic_backup_scheduler(bot, admin_id))
        logger.info("Автоматические бекапы запущены при старте бота")


async def stop_automatic_backups():
    """Stop automatic backups on bot shutdown"""
    global backup_task
    if backup_task and not backup_task.done():
        backup_task.cancel()
        try:
            await backup_task
        except asyncio.CancelledError:
            pass
        logger.info("Автоматические бекапы остановлены при завершении работы бота")


async def restore_from_backup(backup_file_path: str) -> bool:
    """Restore data from backup file"""
    try:
        if not os.path.exists(backup_file_path):
            logger.error(f"Файл резервной копии не найден: {backup_file_path}")
            return False

        # Create temporary directory for extraction
        temp_dir = "/tmp/backup_restore"
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        os.makedirs(temp_dir, exist_ok=True)

        logger.info(f"Начинается восстановление из: {backup_file_path}")

        # Extract backup file
        with zipfile.ZipFile(backup_file_path, "r") as zipf:
            zipf.extractall(temp_dir)
            logger.info("Архив успешно извлечен")

        # Validate backup structure
        extracted_files = os.listdir(temp_dir)
        if not extracted_files:
            logger.error("Пустой архив резервной копии")
            return False

        # Check for metadata file
        metadata_file = os.path.join(temp_dir, "backup_metadata.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                logger.info(f"Найдены метаданные бекапа: {metadata.get('backup_date')}")
            except:
                logger.warning("Не удалось прочитать метаданные бекапа")

        # Restore database
        db_backup_path = os.path.join(temp_dir, "race_participants.db")
        if os.path.exists(db_backup_path):
            # Create backup of current database before restore
            if os.path.exists(DB_PATH):
                current_db_backup = f"{DB_PATH}.backup_before_restore"
                shutil.copy2(DB_PATH, current_db_backup)
                logger.info(f"Текущая база данных сохранена в: {current_db_backup}")

            # Restore database
            shutil.copy2(db_backup_path, DB_PATH)
            logger.info("База данных восстановлена")
        else:
            logger.warning("База данных не найдена в резервной копии")

        # Restore configuration files
        for config_file in ["config.json", "messages.json"]:
            config_backup_path = os.path.join(temp_dir, config_file)
            if os.path.exists(config_backup_path):
                # Backup current config
                if os.path.exists(config_file):
                    current_config_backup = f"{config_file}.backup_before_restore"
                    shutil.copy2(config_file, current_config_backup)
                    logger.info(
                        f"Текущий файл {config_file} сохранен как {current_config_backup}"
                    )

                # Restore config
                shutil.copy2(config_backup_path, config_file)
                logger.info(f"Восстановлен файл конфигурации: {config_file}")
            else:
                logger.warning(
                    f"Файл конфигурации {config_file} не найден в резервной копии"
                )

        # Restore images directory
        images_backup_dir = os.path.join(temp_dir, "images")
        images_target_dir = "/app/images"

        if os.path.exists(images_backup_dir):
            # Backup current images directory
            if os.path.exists(images_target_dir):
                current_images_backup = "/app/images_backup_before_restore"
                if os.path.exists(current_images_backup):
                    shutil.rmtree(current_images_backup)
                shutil.copytree(images_target_dir, current_images_backup)
                logger.info(
                    f"Текущая директория изображений сохранена в: {current_images_backup}"
                )

                # Remove current images
                shutil.rmtree(images_target_dir)

            # Restore images
            shutil.copytree(images_backup_dir, images_target_dir)
            logger.info("Директория изображений восстановлена")
        else:
            logger.warning("Директория изображений не найдена в резервной копии")

        # Clean up temporary directory
        shutil.rmtree(temp_dir)

        logger.info("Восстановление из резервной копии завершено успешно")
        return True

    except Exception as e:
        logger.error(f"Ошибка при восстановлении из резервной копии: {e}")

        # Clean up on error
        try:
            if "temp_dir" in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass

        return False

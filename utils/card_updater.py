"""
Модуль для обновления карточек игроков.
Вынесен отдельно, чтобы избежать циклических импортов между admin.py и economy.py
"""

from vkbottle import VKAPIError, API
from vkbottle.bot import Message
from datetime import datetime
import os

# Токен администратора для редактирования фото
ADMIN_USER_TOKEN = os.getenv("ADMIN_USER_TOKEN", "")
admin_api = None

if ADMIN_USER_TOKEN:
    admin_api = API(ADMIN_USER_TOKEN)


async def auto_update_card(api, user_db, debug_message: Message = None):
    """
    Обновляет описание фотографии игрока в альбоме группы.
    
    Args:
        api: VK API клиент (не используется, оставлен для совместимости)
        user_db: Объект пользователя из базы данных
        debug_message: Опциональное сообщение для отправки отладочной информации
    
    Требует:
        ADMIN_USER_TOKEN в .env файле - токен администратора группы
    """
    if not user_db.card_photo_id: 
        if debug_message: 
            await debug_message.answer("❌ В базе нет ID фото.")
        return

    if not admin_api:
        error_msg = (
            "⚠️ ОШИБКА: Не указан ADMIN_USER_TOKEN!\n\n"
            "Для редактирования описания фото нужен токен администратора.\n"
            "Добавьте в .env файл:\n"
            "ADMIN_USER_TOKEN=ваш_токен_пользователя"
        )
        print(error_msg, flush=True)
        if debug_message: 
            await debug_message.answer(error_msg)
        return

    # Формируем текст описания
    dossier_text = (
        f"✦ ДОСЬЕ ИГРОКА ✦\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 Игрок: {user_db.first_name}\n"
        f"☢ Ранг: {user_db.get_rank()}\n"
        f"💰 Баланс: {user_db.balance} чилликов\n"
        f"🕒 Обновлено: {datetime.now().strftime('%d.%m %H:%M')}\n"
        f"━━━━━━━━━━━━━━━"
    )

    try:
        # Парсим ID: "-123_456" -> owner_id=-123, photo_id=456
        owner_id, photo_id = map(int, user_db.card_photo_id.split('_'))

        # Используем API администратора для редактирования
        await admin_api.photos.edit(
            owner_id=owner_id,
            photo_id=photo_id,
            caption=dossier_text
        )

        print(f"✅ Описание фото {photo_id} обновлено.", flush=True)
        if debug_message: 
            await debug_message.answer(f"✅ Карточка обновлена!")

    except VKAPIError as e:
        err_msg = getattr(e, "error_msg", str(e))
        err_text = f"🔥 Ошибка ВК (Код {e.code}): {err_msg}"
        print(err_text, flush=True)
        
        if e.code == 15:
            err_text += "\n\n⚠️ Проверьте права ADMIN_USER_TOKEN."
        
        if debug_message: 
            await debug_message.answer(f"❌ {err_text}")
            
    except Exception as e:
        err_text = f"🔥 Системная ошибка: {e}"
        print(err_text, flush=True)
        if debug_message: 
            await debug_message.answer(f"❌ {err_text}")

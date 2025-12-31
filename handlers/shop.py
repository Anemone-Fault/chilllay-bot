from vkbottle.bot import BotLabeler, Message
from database.models import User, ShopRequest, RequestStatus
from settings import ADMIN_IDS

labeler = BotLabeler()


# === HELPER ===
async def get_user(message: Message) -> User:
    user_id = message.from_id
    if user_id > 0:
        try:
            users_info = await message.ctx_api.users.get(user_ids=[user_id])
            first_name = users_info[0].first_name
            last_name = users_info[0].last_name
        except:
            first_name = "Неизвестный"
            last_name = "Странник"
            
        user_db, created = await User.get_or_create(
            vk_id=user_id,
            defaults={"first_name": first_name, "last_name": last_name}
        )
        
        if user_db.first_name != first_name or user_db.last_name != last_name:
            user_db.first_name = first_name
            user_db.last_name = last_name
            await user_db.save()
            
        return user_db
    return None


# ====================
# 🛒 КОМАНДА: ХОЧУ (ПОКУПКА)
# ====================

@labeler.message(regex=r"^(?i)Хочу\s+(.*)$")
async def buy_request(message: Message, match):
    # Получаем пользователя
    user_db = await get_user(message)
    
    # Получаем текст товара
    item_text = match[0]
    
    # Проверяем длину запроса
    if len(item_text) < 3:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ СЛИШКОМ КОРОТКО! ║\n"
            "╚═════════════════════╝\n\n"
            "Опиши товар подробнее!\n\n"
            "Минимум 3 символа,\n"
            "а ты написал: «{item_text}»\n\n"
            "Админ не экстрасенс! 🔮"
        )
    
    if len(item_text) > 500:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ СЛИШКОМ ДЛИННО!  ║\n"
            "╚═════════════════════╝\n\n"
            "Максимум 500 символов!\n\n"
            "Ты написал целую поэму,\n"
            "никто не будет читать! 📖\n\n"
            "Сократи описание!"
        )
    
    # Проверяем, нет ли активных заявок
    active_request = await ShopRequest.filter(
        user=user_db,
        status__in=[RequestStatus.CREATED, RequestStatus.PRICE_SET]
    ).first()
    
    if active_request:
        return await message.answer(
            f"╔═════════════════════╗\n"
            f"║  ⚠️ ЗАЯВКА УЖЕ ЕСТЬ! ║\n"
            f"╚═════════════════════╝\n\n"
            f"📋 У тебя уже есть\n"
            f"   активная заявка #{active_request.id}!\n\n"
            f"📦 Товар:\n"
            f"   {active_request.item_text[:50]}...\n\n"
            f"{'═' * 25}\n\n"
            f"Дождись оценки этой\n"
            f"заявки, прежде чем\n"
            f"создавать новую!\n\n"
            f"Жадина-говядина! 🐷"
        )
    
    # Создаем заявку
    request = await ShopRequest.create(
        user=user_db,
        item_text=item_text,
        status=RequestStatus.CREATED
    )
    
    # Отвечаем игроку
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✅ ЗАЯВКА СОЗДАНА!  ║\n"
        f"╚═════════════════════╝\n\n"
        f"📋 Заявка №{request.id}\n\n"
        f"┌─ ИНФОРМАЦИЯ\n"
        f"│\n"
        f"├─ Товар:\n"
        f"│  └─ {item_text[:100]}\n"
        f"│\n"
        f"├─ Статус:\n"
        f"│  └─ ⏳ Ожидает оценки\n"
        f"│\n"
        f"└─ {'─' * 21}\n\n"
        f"{'═' * 25}\n\n"
        f"⏰ Жди, пока админ\n"
        f"   назначит цену!\n\n"
        f"Тебе придет уведомление\n"
        f"когда товар оценят! 📬\n\n"
        f"P.S. Надеюсь, у тебя\n"
        f"     хватит бабок! 💸"
    )
    
    # Уведомляем админов
    for admin_id in ADMIN_IDS:
        try:
            await message.ctx_api.messages.send(
                peer_id=admin_id,
                message=(
                    f"╔═════════════════════╗\n"
                    f"║  🛒 НОВАЯ ЗАЯВКА!    ║\n"
                    f"╚═════════════════════╝\n\n"
                    f"📋 Заявка №{request.id}\n\n"
                    f"┌─ ИНФОРМАЦИЯ\n"
                    f"│\n"
                    f"├─ Заказчик:\n"
                    f"│  └─ {user_db.first_name}\n"
                    f"│\n"
                    f"├─ ID:\n"
                    f"│  └─ vk.com/id{user_db.vk_id}\n"
                    f"│\n"
                    f"├─ Баланс:\n"
                    f"│  └─ {user_db.balance:,}₽\n"
                    f"│\n"
                    f"├─ Товар:\n"
                    f"│  └─ {item_text}\n"
                    f"│\n"
                    f"└─ {'─' * 21}\n\n"
                    f"{'═' * 25}\n\n"
                    f"Чтобы установить цену,\n"
                    f"ответь на это сообщение:\n\n"
                    f"Стоимость: 1000\n\n"
                    f"⚠️ Используй REPLY!"
                ),
                random_id=0
            )
        except Exception as e:
            print(f"⚠️ Не удалось уведомить админа {admin_id}: {e}")

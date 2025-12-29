from vkbottle.bot import BotLabeler, Message
from database.models import User, ShopRequest, RequestStatus
from settings import ADMIN_IDS

labeler = BotLabeler()

# --- 🛠 ПОМОЩНИК ---
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
            defaults={ "first_name": first_name, "last_name": last_name }
        )
        
        if user_db.first_name != first_name or user_db.last_name != last_name:
            user_db.first_name = first_name
            user_db.last_name = last_name
            await user_db.save()
            
        return user_db
    return None

# --- КОМАНДА: ХОЧУ (Покупка) ---
@labeler.message(regex=r"^Хочу\s+(.*)$")
async def buy_request(message: Message, match):
    # 1. Получаем пользователя
    user_db = await get_user(message)
    
    # 2. Получаем текст товара
    item_text = match[0]
    
    # 3. Создаем заявку в базе
    request = await ShopRequest.create(
        user=user_db,
        item_text=item_text,
        status=RequestStatus.CREATED
    )
    
    # 4. Отвечаем игроку
    await message.answer(
        f"╔═══════════════╗\n"
        f"  ✅ ЗАЯВКА №{request.id}\n"
        f"╚═══════════════╝\n\n"
        f"📝 Товар: {item_text}\n\n"
        f"Жди, пока Администратор\n"
        f"назовет цену. Тебе придет\n"
        f"уведомление."
    )
    
    # 5. Стучим Админам в личку (БЕЗ ТЕГА)
    for admin_id in ADMIN_IDS:
        try:
            await message.ctx_api.messages.send(
                peer_id=admin_id,
                message=(
                    f"╔═══════════════╗\n"
                    f"  🛒 НОВАЯ ЗАЯВКА\n"
                    f"╚═══════════════╝\n\n"
                    f"📋 Заявка №{request.id}\n"
                    f"👤 От: {user_db.first_name}\n"
                    f"🆔 ID: vk.com/id{user_db.vk_id}\n"
                    f"📦 Хочет: {item_text}\n\n"
                    f"━━━━━━━━━━━━━━━\n"
                    f"Чтобы установить цену,\n"
                    f"ответь на это сообщение:\n"
                    f"Стоимость: 100"
                ),
                random_id=0
            )
        except:
            pass  # Если у админа закрыта личка

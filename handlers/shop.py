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
    user_db = await get_user(message)
    item_text = match[0]
    
    # Создаем заявку в базе
    request = await ShopRequest.create(
        user=user_db,
        item_text=item_text,
        status=RequestStatus.CREATED
    )
    
    # Отвечаем игроку
    player_text = (
        "╔═══════════════════════╗\n"
        "   ✅ ЗАЯВКА ПРИНЯТА! ✅\n"
        "╚═══════════════════════╝\n\n"
        f"📝 Номер заявки: #{request.id}\n"
        f"🛍️ Товар: {item_text}\n\n"
        "┏━━━━━━━━━━━━━━━━━━━━┓\n"
        "│  ⏳ ЧТО ДАЛЬШЕ?\n"
        "┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "1️⃣ Администратор оценит товар\n"
        "2️⃣ Тебе придёт уведомление с ценой\n"
        "3️⃣ Подтверди покупку\n\n"
        "💡 Обычно это занимает\n"
        "   несколько минут!"
    )
    
    await message.answer(player_text)
    
    # Уведомляем админов
    admin_text = (
        "╔═══════════════════════╗\n"
        "   🛒 НОВАЯ ЗАЯВКА! 🛒\n"
        "╚═══════════════════════╝\n\n"
        f"📋 ЗАЯВКА №{request.id}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 Заказчик:\n"
        f"   [id{user_db.vk_id}|{user_db.first_name}]\n\n"
        f"🛍️ Желаемый товар:\n"
        f"   {item_text}\n\n"
        f"💰 Баланс игрока: {user_db.balance:,}\n\n"
        "┏━━━━━━━━━━━━━━━━━━━━┓\n"
        "│  💡 КАК УСТАНОВИТЬ ЦЕНУ?\n"
        "┗━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "Ответь на это сообщение:\n"
        "→ Стоимость: 100"
    )
    
    # Отправляем всем админам
    for admin_id in ADMIN_IDS:
        try:
            await message.ctx_api.messages.send(
                peer_id=admin_id,
                message=admin_text,
                random_id=0
            )
        except:
            pass

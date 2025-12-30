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
    """
    Команда создания заявки на покупку товара.
    
    Игрок описывает желаемый товар, администратор
    оценивает его и устанавливает цену.
    
    Использование: Хочу [описание товара]
    Пример: Хочу VIP-статус на месяц
    """
    user_db = await get_user(message)
    item_text = match[0]
    
    # Создаем заявку в базе данных
    request = await ShopRequest.create(
        user=user_db,
        item_text=item_text,
        status=RequestStatus.CREATED
    )
    
    # Отвечаем игроку
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    ✅ ЗАЯВКА СОЗДАНА\n"
        f"╚═══════════════════════╝\n\n"
        f"📋 Номер: #{request.id}\n\n"
        f"┏━━━━ ДЕТАЛИ ━━━━┓\n"
        f"│\n"
        f"│ 🛍 Товар:\n"
        f"│    {item_text}\n"
        f"│\n"
        f"│ 👤 Покупатель:\n"
        f"│    {user_db.first_name}\n"
        f"│\n"
        f"│ ⏳ Статус:\n"
        f"│    Ожидает оценки\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"📬 Администратор получил заявку!\n"
        f"   Тебе придёт уведомление с ценой.\n\n"
        f"💡 Обычно оценка занимает\n"
        f"   от нескольких минут до часа."
    )
    
    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            await message.ctx_api.messages.send(
                peer_id=admin_id,
                message=(
                    f"╔═══════════════════════╗\n"
                    f"    🛒 НОВАЯ ЗАЯВКА\n"
                    f"╚═══════════════════════╝\n\n"
                    f"📋 Заявка №{request.id}\n\n"
                    f"┏━━━━ ИНФОРМАЦИЯ ━━━━┓\n"
                    f"│\n"
                    f"│ 👤 От кого:\n"
                    f"│    {user_db.first_name} {user_db.last_name}\n"
                    f"│\n"
                    f"│ 🆔 Профиль:\n"
                    f"│    vk.com/id{user_db.vk_id}\n"
                    f"│\n"
                    f"│ 🛍 Запрос:\n"
                    f"│    {item_text}\n"
                    f"│\n"
                    f"│ 💰 Баланс игрока:\n"
                    f"│    {user_db.balance:,} чилликов\n"
                    f"│\n"
                    f"┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📝 ДЛЯ УСТАНОВКИ ЦЕНЫ:\n\n"
                    f"Ответь на это сообщение:\n"
                    f"   Стоимость: [цена]\n\n"
                    f"Пример:\n"
                    f"   Стоимость: 5000\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                random_id=0
            )
        except Exception as e:
            # Если у админа закрыта личка или другая ошибка
            print(f"⚠️ Не удалось отправить уведомление админу {admin_id}: {e}")

from vkbottle.bot import BotLabeler, Message
from database.models import User, ShopRequest, RequestStatus
from settings import ADMIN_IDS

labeler = BotLabeler()

# ═══════════════════════════════════════════════════════
# 🎨 СТИЛЬНЫЕ РАМКИ
# ═══════════════════════════════════════════════════════

def create_header(title: str, icon: str = "✦") -> str:
    """Создает красивый заголовок"""
    line = "─" * 20
    return f"╭{line}╮\n│ {icon} {title.center(16)} {icon} │\n╰{line}╯"

# ═══════════════════════════════════════════════════════
# 🔧 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════════════

async def get_user(message: Message) -> User:
    """Получает или создает пользователя"""
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

# ═══════════════════════════════════════════════════════
# 🛒 КОМАНДА: ХОЧУ (СОЗДАНИЕ ЗАЯВКИ)
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🛍️\s*)?(?:Х|х)очу\s+(.+)$")
async def buy_request(message: Message, match):
    """
    Создает заявку на покупку предмета в магазине.
    Админ получит уведомление и сможет оценить товар.
    """
    user_db = await get_user(message)
    item_text = match[0].strip()
    
    # Проверяем длину описания
    if len(item_text) < 3:
        return await message.answer(
            "❌ Описание слишком короткое\n"
            "Напиши что именно хочешь купить"
        )
    
    if len(item_text) > 500:
        return await message.answer(
            "❌ Описание слишком длинное\n"
            "Максимум 500 символов"
        )
    
    # Создаем заявку
    request = await ShopRequest.create(
        user=user_db,
        item_text=item_text,
        status=RequestStatus.CREATED
    )
    
    # Ответ игроку
    header = create_header(f"ЗАЯВКА №{request.id}", "✅")
    player_msg = (
        f"{header}\n\n"
        f"  📝 Товар: {item_text}\n\n"
        f"  ⏳ СТАТУС: Ожидание оценки\n\n"
        f"  📌 ЧТО ДАЛЬШЕ?\n"
        f"     1. Админ посмотрит заявку\n"
        f"     2. Назначит справедливую цену\n"
        f"     3. Тебе придет уведомление\n"
        f"     4. Подтверди покупку\n\n"
        f"  ⏰ Обычно это занимает 5-30 мин\n"
    )
    await message.answer(player_msg)
    
    # Уведомление админам (БЕЗ ТЕГОВ - только ссылка)
    for admin_id in ADMIN_IDS:
        try:
            admin_header = create_header("НОВАЯ ЗАЯВКА", "🛒")
            admin_msg = (
                f"{admin_header}\n\n"
                f"  📋 Заявка №{request.id}\n"
                f"  👤 От: {user_db.first_name}\n"
                f"  🆔 Профиль: vk.com/id{user_db.vk_id}\n"
                f"  💰 Баланс: {user_db.balance:,} ₽\n\n"
                f"  📦 Хочет купить:\n"
                f"  \"{item_text}\"\n\n"
                f"  ━━━━━━━━━━━━━━━\n"
                f"  ОЦЕНИТЬ ТОВАР:\n"
                f"  Ответь на это сообщение:\n"
                f"  Стоимость: [цена]\n\n"
                f"  Пример: Стоимость: 500\n"
            )
            
            await message.ctx_api.messages.send(
                peer_id=admin_id,
                message=admin_msg,
                random_id=0
            )
        except Exception as e:
            print(f"⚠️ Не удалось уведомить админа {admin_id}: {e}")
            pass

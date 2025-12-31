from vkbottle.bot import BotLabeler, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, TransactionLog, Cheque, Promo
from tortoise.transactions import in_transaction
from datetime import datetime, timezone, timedelta
from utils.helpers import get_id_from_mention, generate_cheque_code
from utils.card_updater import auto_update_card
from utils.keyboards import get_smart_keyboard, get_image_for_command
from settings import ADMIN_IDS
import random
import asyncio

labeler = BotLabeler()

# === HELPERS ===
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

def get_progress_bar(percent: int, length: int = 10) -> str:
    """Генерирует красивый прогресс-бар"""
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percent}%"

casino_mutes = {}  
def is_muted(user_id: int) -> tuple[bool, int]:
    if user_id not in casino_mutes:
        return False, 0
    until = casino_mutes[user_id]
    now = datetime.now(timezone.utc)
    if now >= until:
        del casino_mutes[user_id]
        return False, 0
    minutes_left = int((until - now).total_seconds() / 60)
    return True, minutes_left

# ====================
# 📚 ПОМОЩЬ
# ====================

@labeler.message(regex=r"^(?i)(?:Помощь|Help|Команды|📚 Помощь)$")
async def help_handler(message: Message):
    user_db = await get_user(message)
    
    text = (
        "╔═════════════════════╗\n"
        "║  📚 НАВИГАЦИЯ БОТА  ║\n"
        "╚═════════════════════╝\n\n"
        "┌─ 👤 ЛИЧНЫЙ КАБИНЕТ\n"
        "│\n"
        "├─ Профиль\n"
        "│  └─ Твоя жалкая карточка\n"
        "│\n"
        "├─ Баланс\n"
        "│  └─ Сколько чилликов\n"
        "│      ты украл у мамки\n"
        "│\n"
        "├─ Бонус\n"
        "│  └─ Подачка раз в 24ч\n"
        "│      (для нищебродов)\n"
        "│\n"
        "└─ Топ\n"
        "   └─ Кто богаче тебя\n\n"
        "┌─ 🎰 РАЗВЛЕЧЕНИЯ\n"
        "│\n"
        "├─ Казино [сумма]\n"
        "│  └─ Слить бабки за 3 сек\n"
        "│\n"
        "└─ Инвентарь\n"
        "   └─ Твоя помойка с барахлом\n\n"
        "┌─ 💸 ТРАНЗАКЦИИ\n"
        "│\n"
        "├─ Перевод @user сумма\n"
        "│  └─ Отдать чиллики лоху\n"
        "│\n"
        "├─ Чек сумма кол-во [р]\n"
        "│  └─ Создать чек-подачку\n"
        "│\n"
        "├─ +реп @user\n"
        "│  └─ Полизать жопу (100 чилликов)\n"
        "│\n"
        "└─ -реп @user\n"
        "   └─ Насрать на репу (500 чилликов)\n\n"
        "┌─ 🛒 МАГАЗИН\n"
        "│\n"
        "└─ Хочу [товар]\n"
        "   └─ Заказать что-то у админа\n"
    )
    
    # Админ-раздел
    if message.from_id in ADMIN_IDS or user_db.is_admin:
        text += (
            "\n╔═════════════════════╗\n"
            "║  ⚙️ ПАНЕЛЬ АДМИНА   ║\n"
            "╚═════════════════════╝\n\n"
            "• Начислить @user сумма\n"
            "  └─ Подкинуть бабла\n\n"
            "• Списать @user сумма\n"
            "  └─ Обнулить мамонта\n\n"
            "• Попущенный @user\n"
            "  └─ Отправить в бан\n\n"
            "• Разбан @user\n"
            "  └─ Освободить узника\n\n"
            "• Рассылка текст\n"
            "  └─ Спамить всем\n\n"
            "• !Ивенты\n"
            "  └─ Список событий\n\n"
            "• !Ивент [имя] [вкл/выкл]\n"
            "  └─ Управление событием\n\n"
            "• !СетФото [команда]\n"
            "  └─ Привязать фото к команде\n"
            "  └─ (прикрепи фото к сообщению)\n\n"
            "• !Выдать @user\n"
            "  └─ Кинуть кейс игроку\n\n"
            "• Связать photo-123_456 @user\n"
            "  └─ Привязать карточку\n\n"
            "• Стоимость: 100\n"
            "  └─ Оценить товар (reply)\n\n"
            "• Промокод код сумма лимит\n"
            "  └─ Создать промик\n"
        )

    img = await get_image_for_command("help")
    kb = await get_smart_keyboard(user_db, "help")
    await message.answer(text, attachment=img, keyboard=kb)


# ====================
# 👤 ПРОФИЛЬ
# ====================

@labeler.message(regex=r"^(?i)(?:Профиль|Стат\.?|Инфо|Я|Прф|👤 Профиль)$")
async def profile_handler(message: Message):
    user_db = await get_user(message)
    
    # Визуальный индикатор кармы
    karma_bar = ""
    if user_db.karma > 0:
        karma_bar = "✨ " + "⭐" * min(user_db.karma, 5)
    elif user_db.karma < 0:
        karma_bar = "💩 " + "💀" * min(abs(user_db.karma), 5)
    else:
        karma_bar = "😐 Нейтрал"
    
    text = (
        f"╔═════════════════════╗\n"
        f"║    👤 ДОСЬЕ ИГРОКА   ║\n"
        f"╚═════════════════════╝\n\n"
        f"┌─ ПЕРСОНАЛЬНЫЕ ДАННЫЕ\n"
        f"│\n"
        f"├─ 🆔 ID: {user_db.vk_id}\n"
        f"├─ 👤 Имя: {user_db.first_name}\n"
        f"├─ 🎭 Статус: {user_db.get_rank()}\n"
        f"│\n"
        f"└─ 💰 Баланс: {user_db.balance:,} чилликов\n"
        f"   └─ В ожидании: {user_db.rp_pending_balance:,} чилликов\n\n"
        f"┌─ РЕПУТАЦИЯ\n"
        f"│\n"
        f"└─ {karma_bar}\n"
        f"   └─ Карма: {user_db.karma:+d}\n"
    )
    
    attachment = None
    if user_db.card_photo_id:
        attachment = f"photo{user_db.card_photo_id}"
    else:
        attachment = await get_image_for_command("profile")
        
    kb = await get_smart_keyboard(user_db, "profile")
    await message.answer(text, attachment=attachment, keyboard=kb)


# ====================
# 💰 БАЛАНС
# ====================

@labeler.message(regex=r"^(?i)(?:Баланс|Бал|Money|💰 Баланс)$")
async def balance_handler(message: Message):
    user_db = await get_user(message)
    
    # Прогресс до следующего ранга
    rank_thresholds = [500, 1000, 5000, 20000, 50000, 100000, 500000, 1000000]
    current = user_db.balance
    next_rank = None
    progress = 100
    
    for threshold in rank_thresholds:
        if current < threshold:
            next_rank = threshold
            prev_threshold = rank_thresholds[rank_thresholds.index(threshold) - 1] if rank_thresholds.index(threshold) > 0 else 0
            progress = int(((current - prev_threshold) / (threshold - prev_threshold)) * 100)
            break
    
    progress_bar = get_progress_bar(progress if next_rank else 100)
    
    text = (
        f"╔═════════════════════╗\n"
        f"║   💰 КАЗНА ИГРОКА    ║\n"
        f"╚═════════════════════╝\n\n"
        f"┌─ ОСНОВНОЙ СЧЕТ\n"
        f"│\n"
        f"├─ На руках:\n"
        f"│  └─ 💵 {user_db.balance:,} чилликов\n"
        f"│\n"
        f"└─ Зарплата (конец месяца):\n"
        f"   └─ 💳 {user_db.rp_pending_balance:,} чилликов\n\n"
        f"┌─ ПРОГРЕСС РАНГА\n"
        f"│\n"
        f"└─ {progress_bar}\n"
    )
    
    if next_rank:
        text += f"   └─ До {next_rank:,} осталось {next_rank - current:,} чилликов\n"
    else:
        text += f"   └─ 👑 Максимальный ранг!\n"
    
    img = await get_image_for_command("balance")
    kb = await get_smart_keyboard(user_db, "main")
    await message.answer(text, attachment=img, keyboard=kb)


# ====================
# 🎁 БОНУС
# ====================

@labeler.message(regex=r"^(?i)(?:Бонус|Ежедневка|🎁 Бонус)$")
async def bonus_handler(message: Message):
    user_db = await get_user(message)
    now = datetime.now(timezone.utc)
    
    if user_db.last_bonus:
        diff = now - user_db.last_bonus
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            
            time_progress = int((diff.total_seconds() / (24 * 3600)) * 100)
            bar = get_progress_bar(time_progress)
            
            return await message.answer(
                f"╔═════════════════════╗\n"
                f"║   ⏳ РАНО, НИЩЕБРОД  ║\n"
                f"╚═════════════════════╝\n\n"
                f"Бонус можно забрать через:\n"
                f"⏰ {hours}ч {minutes}м\n\n"
                f"{bar}\n\n"
                f"Иди поработай, лентяй! 🦥",
                keyboard=await get_smart_keyboard(user_db, "main")
            )

    # Бонус с учетом кармы
    base_amount = random.randint(50, 150)
    karma_bonus = abs(user_db.karma) * 2
    total_amount = base_amount + karma_bonus
    
    user_db.balance += total_amount
    user_db.last_bonus = now
    await user_db.save()
    await TransactionLog.create(user=user_db, amount=total_amount, description="Ежедневный бонус")
    await auto_update_card(message.ctx_api, user_db)
    
    text = (
        f"╔═════════════════════╗\n"
        f"║   🎁 ПОДАЧКА ВЫДАНА  ║\n"
        f"╚═════════════════════╝\n\n"
        f"💰 Базовая подачка: +{base_amount}₽\n"
    )
    
    if karma_bonus > 0:
        text += f"✨ Бонус за карму: +{karma_bonus}₽\n"
    
    text += (
        f"\n{'═' * 25}\n"
        f"💵 ИТОГО: +{total_amount} чилликов\n"
        f"{'═' * 25}\n\n"
        f"📊 Баланс: {user_db.balance:,} чилликов\n\n"
        f"Приходи завтра за новой подачкой! 🐕"
    )
    
    kb = await get_smart_keyboard(user_db, "main")
    await message.answer(text, keyboard=kb)


# ====================
# 🛒 МАГАЗИН
# ====================

@labeler.message(regex=r"^(?i)(?:Магазин|Shop|Купить|🛒 Магазин)(?:\s.*)?$")
async def shop_info(message: Message):
    user_db = await get_user(message)
    img = await get_image_for_command("shop")
    await message.answer(
        "╔═════════════════════╗\n"
        "║   🛒 ЧЁРНЫЙ РЫНОК    ║\n"
        "╚═════════════════════╝\n\n"
        "Хочешь что-то купить?\n"
        "Ха! Ну попробуй!\n\n"
        "┌─ КАК ЗАКАЗАТЬ\n"
        "│\n"
        "└─ Напиши: Хочу [товар]\n\n"
        "Админ оценит твою нищету\n"
        "и назначит космическую цену! 💸\n\n"
        "P.S. Если денег нет — иди работай! 🦝",
        attachment=img,
        keyboard=await get_smart_keyboard(user_db, "main")
    )


# ====================
# 🏆 ТОП
# ====================

@labeler.message(regex=r"^(?i)(?:Топ|Рейтинг|Богачи|🏆 Топ)(?:\s.*)?$")
async def top_users(message: Message):
    user_db = await get_user(message)
    users = await User.filter(is_banned=False).order_by("-balance").limit(10)
    
    text = (
        "╔═════════════════════╗\n"
        "║  🏆 ТОП МАМОНТОВ     ║\n"
        "╚═════════════════════╝\n\n"
        "Кто богаче тебя, нищеброд:\n\n"
    )
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    for i, u in enumerate(users, 1):
        medal = medals.get(i, f"{i}.")
        rank_emoji = "👑" if i == 1 else "💰" if i <= 3 else "💸"
        text += f"{medal} {rank_emoji} {u.first_name}\n"
        text += f"   └─ {u.balance:,} чилликов\n"
        
        if i == 3:
            text += f"\n{'─' * 25}\n\n"
    
    # Позиция текущего игрока
    all_users = await User.filter(is_banned=False).order_by("-balance").all()
    user_position = next((i for i, u in enumerate(all_users, 1) if u.vk_id == user_db.vk_id), None)
    
    if user_position and user_position > 10:
        text += f"\n{'═' * 25}\n"
        text += f"📍 Ты на {user_position} месте\n"
        text += f"└─ {user_db.balance:,} чилликов\n\n"
        text += "Слабак! Качайся! 💪"
    
    await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))


# ====================
# 🎰 КАЗИНО
# ====================

@labeler.message(regex=r"^(?i)(?:Казино|Casino|🎰 Казино)(?:\s+(\d+))?$")
async def casino(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    
    # Проверка мута
    muted, minutes = is_muted(user_db.vk_id)
    if muted:
        return await message.answer(
            f"╔═════════════════════╗\n"
            f"║  🔇 ЗАТКНИСЬ, ЛУДОМАН ║\n"
            f"╚═════════════════════╝\n\n"
            f"Ты в МУТЕ на {minutes} минут!\n\n"
            f"Причина: Слишком нищий\n"
            f"для игры в казино! 🤡\n\n"
            f"Иди заработай хотя бы 200 чилликов,\n"
            f"а потом возвращайся!",
            keyboard=kb
        )
    
    if not match[0]:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  🎰 КАЗИНО ЧИЛЛОВ    ║\n"
            "╚═════════════════════╝\n\n"
            "Использование:\n"
            "└─ Казино [ставка]\n\n"
            "Пример: Казино 100\n\n"
            "⚠️ Шанс выигрыша: 5%\n"
            "💰 Выигрыш: x2 ставки\n"
            "💸 Проигрыш: -50% ставки\n\n"
            "Удачи, лох! 🎲",
            keyboard=kb
        )
    
    bet = int(match[0])
    
    if bet <= 0:
        return await message.answer("❌ Ставка должна быть > 0, еблан!", keyboard=kb)
    if user_db.balance < bet:
        return await message.answer(
            f"╔═════════════════════╗\n"
            f"║   💸 НИЩЕБРОД!       ║\n"
            f"╚═════════════════════╝\n\n"
            f"У тебя всего: {user_db.balance}₽\n"
            f"А ты хочешь поставить: {bet}₽\n\n"
            f"Математику учил? 🤡",
            keyboard=kb
        )
    
    # Анимация рулетки
    animation_msg = await message.answer(
        "╔═════════════════════╗\n"
        "║  🎰 РУЛЕТКА КРУТИТСЯ ║\n"
        "╚═════════════════════╝\n\n"
        "⏳ Ставка принята...\n"
        "🎲 Барабаны вращаются..."
    )
    
    slots = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🔥", "💀"]
    
    # 3 раунда анимации
    for i in range(3):
        await asyncio.sleep(0.6)
        s1, s2, s3 = random.choice(slots), random.choice(slots), random.choice(slots)
        visual = (
            f"╔═════════════════════╗\n"
            f"║  🎰 ВРАЩЕНИЕ #{i+1}/3   ║\n"
            f"╚═════════════════════╝\n\n"
            f"┌───────────────┐\n"
            f"│  {s1}  │  {s2}  │  {s3}  │\n"
            f"└───────────────┘\n\n"
            f"{'▓' * (i + 1)}{'░' * (3 - i - 1)}"
        )
        try:
            await message.ctx_api.messages.edit(
                peer_id=message.peer_id,
                message=visual,
                conversation_message_id=animation_msg.conversation_message_id
            )
        except:
            pass
    
    await asyncio.sleep(0.5)
    
    # Результат
    win = random.random() < 0.05
    
    if win:
        prize = bet * 2
        user_db.balance += prize
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=prize, description="Казино WIN")
        await auto_update_card(message.ctx_api, user_db)
        
        result = (
            f"╔═════════════════════╗\n"
            f"║  🎉 ДЖЕКПОТ! ЕЕЕЕБАТЬ! ║\n"
            f"╚═════════════════════╝\n\n"
            f"┌───────────────┐\n"
            f"│  7️⃣  │  7️⃣  │  7️⃣  │\n"
            f"└───────────────┘\n\n"
            f"💰 ВЫИГРЫШ: +{prize:,} чилликов\n"
            f"📊 Баланс: {user_db.balance:,} чилликов\n\n"
            f"Красавчик! Проебешь? 😎"
        )
    else:
        loss = bet // 2
        user_db.balance -= loss
        
        mute_text = ""
        if user_db.balance < 200:
            casino_mutes[user_db.vk_id] = datetime.now(timezone.utc) + timedelta(hours=1)
            mute_text = "\n\n🔇 МУТ НА 1 ЧАС!\n(Слишком нищий для игры)"
        
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=-loss, description="Казино LOSS")
        await auto_update_card(message.ctx_api, user_db)
        
        result = (
            f"╔═════════════════════╗\n"
            f"║  💀 СЛИЛ, ЛУДОМАН!   ║\n"
            f"╚═════════════════════╝\n\n"
            f"┌───────────────┐\n"
            f"│  💀  │  🔥  │  💩  │\n"
            f"└───────────────┘\n\n"
            f"💸 ПОТЕРЯ: -{loss:,} чилликов\n"
            f"📊 Баланс: {user_db.balance:,} чилликов\n\n"
            f"Лох! Иди зачиллься! 🤡{mute_text}"
        )
    
    try:
        await message.ctx_api.messages.edit(
            peer_id=message.peer_id,
            message=result,
            conversation_message_id=animation_msg.conversation_message_id,
            keyboard=kb
        )
    except:
        await message.answer(result, keyboard=kb)


# ====================
# 💸 ПЕРЕВОД
# ====================

@labeler.message(regex=r"^(?i)(?:Перевод|Скинуть|Отправить)\s+(.*?)\s+(\d+)(?:\s+(.*))?$")
async def transfer(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_raw, amount, comment = match[0], int(match[1]), match[2] or "Без комментария"
    target_id = get_id_from_mention(target_raw)
    
    if not target_id:
        return await message.answer("❌ Кому переводить, дебил?", keyboard=kb)
    
    if target_id == user_db.vk_id:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  🤡 ШИЗОФРЕНИК?      ║\n"
            "╚═════════════════════╝\n\n"
            "Сам себе переводишь?\n"
            "Иди к психологу! 🏥\n\n"
            "P.S. Таблетки принял? 💊",
            keyboard=kb
        )
    
    if amount <= 0:
        return await message.answer("❌ Сумма должна быть > 0!", keyboard=kb)
    
    if user_db.balance < amount:
        return await message.answer(
            f"╔═════════════════════╗\n"
            f"║   💸 НИЩЕБРОД!       ║\n"
            f"╚═════════════════════╝\n\n"
            f"У тебя: {user_db.balance:,} чилликов\n"
            f"Хочешь отдать: {amount:,} чилликов\n\n"
            f"Займи у мамки! 🤡",
            keyboard=kb
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        recipient = await User.get_or_none(vk_id=target_id)
        
        if not recipient:
            return await message.answer("❌ Получатель не найден в базе.", keyboard=kb)
        
        if sender.balance < amount:
            return await message.answer("❌ Недостаточно средств.", keyboard=kb)

        sender.balance -= amount
        recipient.balance += amount
        await sender.save()
        await recipient.save()
        
        await TransactionLog.create(
            user=sender,
            amount=-amount,
            description=f"Перевод → {recipient.get_mention()}"
        )
        await TransactionLog.create(
            user=recipient,
            amount=amount,
            description=f"Перевод ← {sender.get_mention()}"
        )

    await auto_update_card(message.ctx_api, sender)
    await auto_update_card(message.ctx_api, recipient)

    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✅ ПЕРЕВОД ВЫПОЛНЕН  ║\n"
        f"╚═════════════════════╝\n\n"
        f"💸 Сумма: {amount:,} чилликов\n"
        f"👤 Получатель: {recipient.first_name}\n"
        f"💬 Комментарий: {comment}\n\n"
        f"{'═' * 25}\n"
        f"📊 Твой баланс: {sender.balance:,} чилликов",
        keyboard=kb
    )


# ====================
# 🎖 РЕПУТАЦИЯ
# ====================

@labeler.message(regex=r"^\+реп\s+(.*)$")
async def plus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 100
    
    if user_db.balance < cost:
        return await message.answer(
            f"╔═════════════════════╗\n"
            f"║   💸 БОМЖ!           ║\n"
            f"╚═════════════════════╝\n\n"
            f"Нужно: {cost} чилликов\n"
            f"У тебя: {user_db.balance} чилликов\n\n"
            f"Иди попроси милостыню! 🦝",
            keyboard=kb
        )
    
    if not target_id:
        return await message.answer("❌ Кому давать +реп?", keyboard=kb)
    
    if target_id == user_db.vk_id:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  🤡 КЛОУН ДЕТЕКТЕД   ║\n"
            "╚═════════════════════╝\n\n"
            "Сам себе лайкаешь?\n"
            "Тебя мамка не любила?\n"
            "Иди потрогай траву! 🌿\n\n"
            "⛔ Репутация не изменена.",
            keyboard=kb
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        
        if not target:
            return await message.answer("❌ Получатель не найден.", keyboard=kb)
        
        sender.balance -= cost
        target.karma += 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✨ РЕСПЕКТ ОТПРАВЛЕН ║\n"
        f"╚═════════════════════╝\n\n"
        f"👤 Кому: {target.first_name}\n"
        f"⭐ Карма: {target.karma:+d}\n\n"
        f"{'═' * 25}\n"
        f"💸 Списано: {cost} чилликов\n"
        f"📊 Баланс: {sender.balance:,} чилликов\n\n"
        f"Жополиз детектед! 🫡",
        keyboard=kb
    )


@labeler.message(regex=r"^\-реп\s+(.*)$")
async def minus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 500
    
    if user_db.balance < cost:
        return await message.answer(
            f"╔═════════════════════╗\n"
            f"║   💸 НИЩИЙ!          ║\n"
            f"╚═════════════════════╝\n\n"
            f"Нужно: {cost} чилликов\n"
            f"У тебя: {user_db.balance} чилликов\n\n"
            f"Насрать в репу дорого,\n"
            f"а ты бомж! 🤡",
            keyboard=kb
        )
    
    if not target_id:
        return await message.answer("❌ На кого срать?", keyboard=kb)
    
    if target_id == user_db.vk_id:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  🚑 СУИЦИДНИК!       ║\n"
            "╚═════════════════════╝\n\n"
            "Сам себе дизлайкаешь?\n"
            "У тебя депрессия?\n\n"
            "Номер психолога: 88005553535\n\n"
            "💊 Сходи к врачу, спидозный!",
            keyboard=kb
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        
        if not target:
            return await message.answer("❌ Жертва не найдена.", keyboard=kb)
        
        sender.balance -= cost
        target.karma -= 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  💩 НАСРАЛ В РЕПУ!   ║\n"
        f"╚═════════════════════╝\n\n"
        f"👤 Жертва: {target.first_name}\n"
        f"💀 Карма: {target.karma:+d}\n\n"
        f"{'═' * 25}\n"
        f"💸 Списано: {cost} чилликов\n"
        f"📊 Баланс: {sender.balance:,} чилликов\n\n"
        f"Ненавистник детектед! 😈",
        keyboard=kb
    )


# ====================
# 🎫 ЧЕКИ
# ====================

@labeler.message(regex=r"^(?i)Чек\s+(\d+)(?:\s+(\d+))?(?:\s+(р))?$")
async def create_cheque(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    amount = int(match[0])
    activations = int(match[1]) if match[1] else 1
    is_random = bool(match[2])
    
    if user_db.balance < amount:
        return await message.answer(
            f"╔═════════════════════╗\n"
            f"║   💸 БОМЖ!           ║\n"
            f"╚═════════════════════╝\n\n"
            f"У тебя: {user_db.balance} чилликов\n"
            f"Нужно: {amount} чилликов\n\n"
            f"Займи у друзей! 🤡",
            keyboard=kb
        )
    
    code = generate_cheque_code()
    
    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        sender.balance -= amount
        await sender.save()
        await Cheque.create(
            code=code,
            creator_id=user_db.vk_id,
            total_amount=amount,
            amount_left=amount,
            activations_limit=activations,
            mode="random" if is_random else "fix"
        )

    await auto_update_card(message.ctx_api, sender)
    
    inline_kb = Keyboard(inline=True)
    inline_kb.add(
        Text("💰 Забрать подачку", payload={"cmd": "claim", "code": code}),
        color=KeyboardButtonColor.POSITIVE
    )
    
    mode_text = "🎲 Рандом" if is_random else "💰 Фикс"
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  🎫 ЧЕК СОЗДАН       ║\n"
        f"╚═════════════════════╝\n\n"
        f"🆔 Код: {code}\n"
        f"💰 Сумма: {amount:,} чилликов\n"
        f"👥 Активаций: {activations}\n"
        f"⚙️ Режим: {mode_text}\n\n"
        f"{'═' * 25}\n\n"
        f"Жми кнопку ниже,\n"
        f"чтобы забрать бабки! 💸",
        keyboard=inline_kb.get_json()
    )


@labeler.message(payload_map={"cmd": "claim"})
async def claim_cheque(message: Message):
    user_db = await get_user(message)
    code = message.get_payload_json()["code"]
    
    async with in_transaction():
        cheque = await Cheque.filter(code=code).select_for_update().first()
        
        if not cheque or cheque.activations_current >= cheque.activations_limit:
            return await message.answer(
                "╔═════════════════════╗\n"
                "║  ❌ ЧЕК ПУСТОЙ!      ║\n"
                "╚═════════════════════╝\n\n"
                "Все деньги разобрали!\n"
                "Опоздал, лох! 🤡",
                ephemeral=True
            )
        
        if user_db.vk_id in cheque.users_activated:
            return await message.answer(
                "╔═════════════════════╗\n"
                "║  ⛔ УЖЕ БРАЛ!        ║\n"
                "╚═════════════════════╝\n\n"
                "Ты уже забирал бабки\n"
                "с этого чека!\n\n"
                "Жадина-говядина! 🐷",
                ephemeral=True
            )
        
        # Расчет суммы
        prize = 0
        if cheque.mode == "fix":
            prize = cheque.total_amount // cheque.activations_limit
        else:
            remains = cheque.activations_limit - cheque.activations_current
            max_safe = cheque.amount_left - (remains - 1)
            prize = random.randint(1, max(1, max_safe)) if remains > 1 else cheque.amount_left

        cheque.amount_left -= prize
        cheque.activations_current += 1
        cheque.users_activated = list(cheque.users_activated) + [user_db.vk_id]
        await cheque.save()
        
        user_db.balance += prize
        await user_db.save()

    await auto_update_card(message.ctx_api, user_db)
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  💰 ЧЕК АКТИВИРОВАН! ║\n"
        f"╚═════════════════════╝\n\n"
        f"🎫 Код: {code}\n"
        f"💵 Получено: +{prize:,} чилликов\n"
        f"📊 Баланс: {user_db.balance:,} чилликов\n\n"
        f"{'═' * 25}\n\n"
        f"Поздравляю, нищеброд! 🎉",
        keyboard=await get_smart_keyboard(user_db, "main")
    )


# ====================
# 🎟 ПРОМОКОДЫ
# ====================

@labeler.message(regex=r"^(?i)Промо\s+(.*)$")
async def activate_promo(message: Message, match):
    user_db = await get_user(message)
    code = match[0].strip()
    promo = await Promo.get_or_none(code=code)
    kb = await get_smart_keyboard(user_db, "main")

    if not promo:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ ПРОМОКОД НЕ НАЙДЕН ║\n"
            "╚═════════════════════╝\n\n"
            f"Код: {code}\n\n"
            "Такого промика нет!\n"
            "Тебя наебали? 🤡",
            keyboard=kb
        )
    
    if promo.current_activations >= promo.max_activations:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ⏰ ПРОМИК ЗАКОНЧИЛСЯ ║\n"
            "╚═════════════════════╝\n\n"
            "Все активации исчерпаны!\n"
            "Опоздал, лох! 🐌",
            keyboard=kb
        )
    
    if user_db.vk_id in promo.users_activated:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ⛔ УЖЕ АКТИВИРОВАЛ!  ║\n"
            "╚═════════════════════╝\n\n"
            "Ты уже использовал\n"
            "этот промокод!\n\n"
            "Жадина! 🐷",
            keyboard=kb
        )
    
    async with in_transaction():
        p = await Promo.filter(code=code).select_for_update().first()
        p.current_activations += 1
        p.users_activated = list(p.users_activated) + [user_db.vk_id]
        await p.save()
        
        user_db.balance += p.amount
        await user_db.save()

    await auto_update_card(message.ctx_api, user_db)
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  🎟 ПРОМО АКТИВИРОВАН ║\n"
        f"╚═════════════════════╝\n\n"
        f"🎫 Код: {code}\n"
        f"💰 Получено: +{p.amount:,} чилликов\n"
        f"📊 Баланс: {user_db.balance:,} чилликов\n\n"
        f"{'═' * 25}\n\n"
        f"Красавчик! Проебешь? 😎",
        keyboard=kb
    )


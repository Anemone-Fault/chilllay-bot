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

# --- ПОМОЩНИК ---
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

casino_mutes = {}  # {user_id: datetime_until}
def is_muted(user_id: int) -> tuple[bool, int]:
    if user_id not in casino_mutes: return False, 0
    until = casino_mutes[user_id]
    now = datetime.now(timezone.utc)
    if now >= until:
        del casino_mutes[user_id]
        return False, 0
    minutes_left = int((until - now).total_seconds() / 60)
    return True, minutes_left

# ====================
# НОВЫЕ КОМАНДЫ (С КАРТИНКАМИ И КНОПКАМИ)
# ====================

@labeler.message(regex=r"^(?i)(?:Профиль|Стат.?|Инфо|Я|Прф)$")
async def profile_handler(message: Message):
    user_db = await get_user(message)
    text = (
        f"╔═══════════════╗\n"
        f"    👤 ПРОФИЛЬ\n"
        f"╚═══════════════╝\n\n"
        f"🆔 ID: {user_db.vk_id}\n"
        f"📜 Ранг: {user_db.get_rank()}\n"
        f"💰 Баланс: {user_db.balance}\n"
        f"🎭 Карма: {user_db.karma}\n"
    )
    img = await get_image_for_command("profile")
    kb = await get_smart_keyboard(user_db, "profile")
    await message.answer(text, attachment=img, keyboard=kb)

@labeler.message(regex=r"^(?i)(?:Баланс|Бал|Money)$")
async def balance_handler(message: Message):
    user_db = await get_user(message)
    text = (
        f"╔═══════════════╗\n"
        f"    💰 БАЛАНС\n"
        f"╚═══════════════╝\n\n"
        f"💵 На руках: {user_db.balance} чилликов\n"
        f"💳 Зарплата (в конце мес.): {user_db.rp_pending_balance}"
    )
    img = await get_image_for_command("balance")
    kb = await get_smart_keyboard(user_db, "main")
    await message.answer(text, attachment=img, keyboard=kb)

@labeler.message(regex=r"^(?i)(?:Бонус|Ежедневк.?)$")
async def bonus_handler(message: Message):
    user_db = await get_user(message)
    now = datetime.now(timezone.utc)
    
    if user_db.last_bonus:
        diff = now - user_db.last_bonus
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            return await message.answer(
                f"⏳ Рано! Бонус через {hours}ч {minutes}м.",
                keyboard=await get_smart_keyboard(user_db, "main")
            )

    amount = 50 + (abs(user_db.karma) * 2) 
    user_db.balance += amount
    user_db.last_bonus = now
    await user_db.save()
    await TransactionLog.create(user=user_db, amount=amount, description="Бонус")
    
    # Обновляем фото
    await auto_update_card(message.ctx_api, user_db)
    
    text = (
        f"╔═══════════════╗\n"
        f"    🎁 БОНУС\n"
        f"╚═══════════════╝\n\n"
        f"Получено: +{amount} чилликов!\n"
        f"Заходи завтра."
    )
    kb = await get_smart_keyboard(user_db, "main")
    await message.answer(text, keyboard=kb)

@labeler.message(regex=r"^(?i)(?:Помощь|Help|Команды)$")
async def help_handler(message: Message):
    user_db = await get_user(message)
    text = (
        f"╔═══════════════╗\n"
        f"    📚 ПОМОЩЬ\n"
        f"╚═══════════════╝\n\n"
        f"🔹 Профиль — статистика\n"
        f"🔹 Баланс — счет и зарплата\n"
        f"🔹 Инвентарь — предметы и кейсы\n"
        f"🔹 Магазин — тратить деньги\n\n"
        f"💸 ДЕЙСТВИЯ:\n"
        f"• Перевод @user 100\n"
        "• Чек 1000 3\n"
        "• +реп @user / -реп @user\n"
        "• Казино [сумма]\n\n"
        f"📝 РП: пиши посты > 1000 симв."
    )
    img = await get_image_for_command("help")
    kb = await get_smart_keyboard(user_db, "help")
    await message.answer(text, attachment=img, keyboard=kb)

# ====================
# МАГАЗИН И ТОП
# ====================

@labeler.message(regex=r"^(?i)(?:Магазин|Shop|Купить|🛒 Магазин)(?:\s.*)?$")
async def shop_info(message: Message):
    user_db = await get_user(message)
    img = await get_image_for_command("shop")
    await message.answer(
        "╔═══════════════╗\n"
        "    🛒 МАГАЗИН\n"
        "╚═══════════════╝\n\n"
        "Чтобы купить что-то, напиши:\n"
        "👉 Хочу [товар]\n\n"
        "Админ оценит товар и пришлет цену!",
        attachment=img,
        keyboard=await get_smart_keyboard(user_db, "main")
    )

@labeler.message(regex=r"^(?i)(?:Топ|Рейтинг|Богачи|🏆 Топ)(?:\s.*)?$")
async def top_users(message: Message):
    user_db = await get_user(message)
    users = await User.filter(is_banned=False).order_by("-balance").limit(10)
    text = (
        "╔═══════════════╗\n"
        "    🏆 ТОП ИГРОКОВ\n"
        "╚═══════════════╝\n\n"
    )
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(users, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        text += f"{medal} {u.first_name} — {u.balance}\n"
    
    await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

# ====================
# ВОССТАНОВЛЕННЫЕ СТАРЫЕ КОМАНДЫ
# ====================

@labeler.message(regex=r"^(?i)(?:Казино|Casino|🎰 Казино)(?:\s+(\d+))?$")
async def casino(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    
    muted, minutes = is_muted(user_db.vk_id)
    if muted:
        return await message.answer(f"🔇 ТЫ В МУТЕ!\nОсталось: {minutes} мин", keyboard=kb)
    
    if not match[0]:
        return await message.answer("Использование: Казино [сумма]", keyboard=kb)
    
    bet = int(match[0])
    if bet <= 0: return await message.answer("❌ Ставка > 0", keyboard=kb)
    if user_db.balance < bet: return await message.answer("❌ Не хватает денег.", keyboard=kb)
    
    animation_msg = await message.answer("🎰 Рулетка крутится...")
    slots = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🔥"]
    
    for _ in range(3):
        await asyncio.sleep(0.5)
        visual = f"🎰 [ {random.choice(slots)} | {random.choice(slots)} | {random.choice(slots)} ]"
        try: await message.ctx_api.messages.edit(peer_id=message.peer_id, message=visual, conversation_message_id=animation_msg.conversation_message_id)
        except: pass
    
    win = random.random() < 0.05
    
    if win:
        prize = bet * 2
        user_db.balance += prize
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=prize, description="Казино Win")
        await auto_update_card(message.ctx_api, user_db)
        
        res = (
            f"╔═══════════════╗\n"
            f"🎰 [ 7️⃣ | 7️⃣ | 7️⃣ ]\n"
            f"╚═══════════════╝\n\n"
            f"🎉 ДЖЕКПОТ! +{prize}"
        )
    else:
        loss = bet // 2
        user_db.balance -= loss
        mute_text = ""
        if user_db.balance < 200:
            casino_mutes[user_db.vk_id] = datetime.now(timezone.utc) + timedelta(hours=1)
            mute_text = "\n🔇 МУТ НА 1 ЧАС!"
        
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=-loss, description="Казино Loss")
        await auto_update_card(message.ctx_api, user_db)
        
        res = (
            f"╔═══════════════╗\n"
            f"🎰 [ 🍒 | 🍋 | 🔥 ]\n"
            f"╚═══════════════╝\n\n"
            f"💔 Потеряно: -{loss}{mute_text}"
        )
    
    try: await message.ctx_api.messages.edit(peer_id=message.peer_id, message=res, conversation_message_id=animation_msg.conversation_message_id, keyboard=kb)
    except: await message.answer(res, keyboard=kb)

@labeler.message(regex=r"^(?i)(?:Перевод|Скинуть|Отправить)\s+(.*?)\s+(\d+)(?:\s+(.*))?$")
async def transfer(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_raw, amount, comment = match[0], int(match[1]), match[2] or "Без комментария"
    target_id = get_id_from_mention(target_raw)
    
    if not target_id: return await message.answer("❌ Кому?", keyboard=kb)
    if amount <= 0: return await message.answer("❌ Сумма > 0.", keyboard=kb)
    if user_db.balance < amount: return await message.answer("❌ Не хватает.", keyboard=kb)

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        recipient = await User.get_or_none(vk_id=target_id)
        if not recipient: return await message.answer("❌ Юзер не найден.", keyboard=kb)
        if sender.balance < amount: return await message.answer("❌ Не хватает.", keyboard=kb)

        sender.balance -= amount
        recipient.balance += amount
        await sender.save()
        await recipient.save()
        await TransactionLog.create(user=sender, amount=-amount, description=f"-> {target_id}")
        await TransactionLog.create(user=recipient, amount=amount, description=f"<- {sender.vk_id}")

    await auto_update_card(message.ctx_api, sender)
    await auto_update_card(message.ctx_api, recipient)

    await message.answer(
        f"✅ Перевод выполнен\n💸 -{amount} чилликов\n👤 Получатель: {recipient.first_name}",
        keyboard=kb
    )

@labeler.message(regex=r"^\+реп\s+(.*)$")
async def plus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 100
    
    if user_db.balance < cost: return await message.answer(f"❌ Нужно {cost} чилликов.", keyboard=kb)
    if not target_id: return await message.answer("❌ Кому?", keyboard=kb)

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        if not target: return await message.answer("❌ Нет такого.", keyboard=kb)
        
        sender.balance -= cost
        target.karma += 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    await message.answer(f"🫡 Респект отправлен (+1 карма). Списано {cost}.", keyboard=kb)

@labeler.message(regex=r"^\-реп\s+(.*)$")
async def minus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 500
    
    if user_db.balance < cost: return await message.answer(f"❌ Нужно {cost} чилликов.", keyboard=kb)
    if not target_id: return await message.answer("❌ Кого?", keyboard=kb)

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        if not target: return await message.answer("❌ Нет такого.", keyboard=kb)
        
        sender.balance -= cost
        target.karma -= 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    await message.answer(f"💦 Дизлайк отправлен (-1 карма). Списано {cost}.", keyboard=kb)

@labeler.message(regex=r"^(?i)Чек\s+(\d+)(?:\s+(\d+))?(?:\s+(р))?$")
async def create_cheque(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    amount = int(match[0])
    activations = int(match[1]) if match[1] else 1
    is_random = bool(match[2])
    
    if user_db.balance < amount: return await message.answer("❌ Нет денег.", keyboard=kb)
    code = generate_cheque_code()
    
    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        sender.balance -= amount
        await sender.save()
        await Cheque.create(code=code, creator_id=user_db.vk_id, total_amount=amount, amount_left=amount, activations_limit=activations, mode="random" if is_random else "fix")

    await auto_update_card(message.ctx_api, sender)
    
    inline_kb = Keyboard(inline=True).add(Text("Забрать 🖐", payload={"cmd": "claim", "code": code}), color=KeyboardButtonColor.POSITIVE).get_json()
    await message.answer(
        f"╔═══════════════╗\n"
        f"  🤑 ЧЕК\n"
        f"╚═══════════════╝\n\n"
        f"💰 Сумма: {amount}\n"
        f"👥 Мест: {activations}",
        keyboard=inline_kb
    )

@labeler.message(payload_map={"cmd": "claim"})
async def claim_cheque(message: Message):
    user_db = await get_user(message)
    code = message.get_payload_json()["code"]
    async with in_transaction():
        cheque = await Cheque.filter(code=code).select_for_update().first()
        if not cheque or cheque.activations_current >= cheque.activations_limit:
            return await message.answer("❌ Чек пуст.", ephemeral=True)
        if user_db.vk_id in cheque.users_activated:
            return await message.answer("❌ Ты уже брал.", ephemeral=True)
        
        prize = 0
        if cheque.mode == "fix": prize = cheque.total_amount // cheque.activations_limit
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
    await message.answer(f"✅ +{prize} чилликов!", keyboard=await get_smart_keyboard(user_db, "main"))

@labeler.message(regex=r"^(?i)Промо\s+(.*)$")
async def activate_promo(message: Message, match):
    user_db = await get_user(message)
    code = match[0].strip()
    promo = await Promo.get_or_none(code=code)
    kb = await get_smart_keyboard(user_db, "main")

    if not promo: return await message.answer("❌ Не найден.", keyboard=kb)
    if promo.current_activations >= promo.max_activations: return await message.answer("❌ Закончился.", keyboard=kb)
    if user_db.vk_id in promo.users_activated: return await message.answer("❌ Уже активировал.", keyboard=kb)
    
    async with in_transaction():
        p = await Promo.filter(code=code).select_for_update().first()
        p.current_activations += 1
        p.users_activated = list(p.users_activated) + [user_db.vk_id]
        await p.save()
        
        user_db.balance += p.amount
        await user_db.save()

    await auto_update_card(message.ctx_api, user_db)
    await message.answer(f"✅ Промокод! +{p.amount}", keyboard=kb)

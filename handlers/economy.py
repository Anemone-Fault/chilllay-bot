from vkbottle.bot import BotLabeler, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, TransactionLog, Cheque, Promo
from tortoise.transactions import in_transaction
from datetime import datetime, timezone
from utils.helpers import get_id_from_mention, generate_cheque_code
from settings import ADMIN_IDS
import random

labeler = BotLabeler()

@labeler.message(text=["Помощь", "Команды", "Меню", "Help", "help"])
async def help_command(message: Message, user_db: User):
    text = (
        "📚 СПИСОК КОМАНД:\n\n"
        "👤 ЛИЧНОЕ:\n"
        "🔸 Профиль — Статистика и ранг\n"
        "🔸 Баланс — Твой кошелек\n"
        "🔸 Бонус — Ежедневная халява\n"
        "🔸 Топ — Список богачей\n\n"
        "💸 ФИНАНСЫ:\n"
        "🔸 Перевод @user 100 [коммент] — Передать деньги\n"
        "🔸 Чек 1000 3 — Создать мешок на 1000 монет для 3 человек\n"
        "🔸 Чек 1000 3 р — Рандомный чек\n\n"
        "🤝 РЕСПЕКТЫ:\n"
        "🔸 +реп @user — Уважение (100 монет)\n"
        "🔸 -реп @user — Осуждение (500 монет)\n\n"
        "🛒 МАГАЗИН:\n"
        "🔸 Хочу [название] — Заявка на покупку\n"
        "🔸 Промо [код] — Активация промокода"
    )
    
    # Скрытые команды только для админов
    if message.from_id in ADMIN_IDS:
        text += (
            "\n\n👮‍♂ АДМИН-ПАНЕЛЬ:\n"
            "🔹 Начислить @user 1000\n"
            "🔹 Списать @user 1000\n"
            "🔹 Попущенный @user [причина] — Бан\n"
            "🔹 Рассылка [текст]\n"
            "🔹 Промокод [код] [сумма] [кол-во]\n"
            "🔹 График — Статистика\n"
            "🔹 Стоимость: 100 (Реплай на заявку)"
        )
        
    await message.answer(text)

@labeler.message(text="Баланс")
async def balance(message: Message, user_db: User):
    await message.answer(f"💰 Твои Чиллики: {user_db.balance}")

@labeler.message(text="Профиль")
async def profile(message: Message, user_db: User):
    text = (
        f"👤 [id{user_db.vk_id}|{user_db.first_name}]\n"
        f"💰 Чиллики: {user_db.balance}\n"
        f"☢️ Ранг: {user_db.get_rank()}\n"
        f"☯️ Карма: {user_db.karma}"
    )
    await message.answer(text)

@labeler.message(text="Топ")
async def top_users(message: Message):
    users = await User.filter(is_banned=False).order_by("-balance").limit(10)
    text = "🏆 Топ Чилликов:\n\n"
    for i, u in enumerate(users, 1):
        text += f"{i}. [id{u.vk_id}|{u.first_name}] — {u.balance} ({u.get_rank()})\n"
    await message.answer(text)

@labeler.message(text="Бонус")
async def daily_bonus(message: Message, user_db: User):
    now = datetime.now(timezone.utc)
    if user_db.last_bonus and (now - user_db.last_bonus).total_seconds() < 86400:
        return await message.answer("🕒 Куда лезешь? Бонус раз в 24 часа.")
    
    amount = random.randint(100, 500)
    user_db.balance += amount
    user_db.last_bonus = now
    await user_db.save()
    await TransactionLog.create(user=user_db, amount=amount, description="Бонус")
    
    await message.answer(f"🎁 Халява! Ты нафармил {amount} Чилликов.")

@labeler.message(regex=r"^Перевод\s+(.*?)\s+(\d+)(?:\s+(.*))?$")
async def transfer(message: Message, match, user_db: User):
    target_raw, amount_str, comment = match[0], match[1], match[2] or "Без комментария"
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)
    
    if not target_id: return await message.answer("❌ Кому? Используй @user.")
    if target_id == user_db.vk_id: return await message.answer("🤡 Шизофрения лечится.")
    if amount <= 0: return await message.answer("❌ Сумма должна быть > 0.")
    if user_db.balance < amount: 
        return await message.answer(f"❌ Недостаточно Чилликов.\nУ тебя {user_db.balance}, а хочешь кинуть {amount}.\nНищий.")

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        recipient = await User.get_or_none(vk_id=target_id)
        
        if not recipient: return await message.answer("❌ Юзер не найден в базе.")
        if sender.balance < amount: return await message.answer("❌ Не хватает денег.")

        sender.balance -= amount
        recipient.balance += amount
        await sender.save()
        await recipient.save()
        
        await TransactionLog.create(user=sender, amount=-amount, description=f"Перевод -> {target_id}")
        await TransactionLog.create(user=recipient, amount=amount, description=f"Перевод <- {sender.vk_id}")

    await message.answer(f"✅ Перевод выполнен.\n💸 -{amount} Чилликов улетели.")
    try:
        await message.ctx_api.messages.send(
            peer_id=target_id, 
            message=f"💸 Тебе прилетело {amount} Чилликов от [id{sender.vk_id}|{sender.first_name}].\n💬 {comment}", 
            random_id=0
        )
    except: pass

@labeler.message(regex=r"^\+реп\s+(.*)$")
async def plus_rep(message: Message, match, user_db: User):
    target_id = get_id_from_mention(match[0])
    cost = 100 
    if not target_id: return await message.answer("❌ Кому респект?")
    if target_id == user_db.vk_id: return await message.answer("🤡 Себя не хвали.")
    if user_db.balance < cost: return await message.answer(f"❌ Респект стоит {cost} Чилликов. Работай иди.")

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        if not target: return await message.answer("❌ Юзер не найден.")
        if sender.balance < cost: return await message.answer("❌ Мало денег.")
        
        sender.balance -= cost
        target.karma += 1
        await sender.save()
        await target.save()
        await TransactionLog.create(user=sender, amount=-cost, description="Респект")

    await message.answer(f"🫡 Респект отправлен. Списано {cost} Чилликов.\nКарма получателя: {target.karma}")

@labeler.message(regex=r"^\-реп\s+(.*)$")
async def minus_rep(message: Message, match, user_db: User):
    target_id = get_id_from_mention(match[0])
    cost = 500
    if not target_id: return await message.answer("❌ В кого плюем?")
    if user_db.balance < cost: return await message.answer(f"❌ Хейт стоит {cost} Чилликов.")

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        if not target: return await message.answer("❌ Юзер не найден.")
        if sender.balance < cost: return await message.answer("❌ Мало денег.")
        
        sender.balance -= cost
        target.karma -= 1
        await sender.save()
        await target.save()
        await TransactionLog.create(user=sender, amount=-cost, description="Дизлайк")

    await message.answer(f"💦 Харкнул в профиль. Списано {cost} Чилликов.\nКарма жертвы: {target.karma}")

@labeler.message(regex=r"^Чек\s+(\d+)(?:\s+(\d+))?(?:\s+(р))?$")
async def create_cheque(message: Message, match, user_db: User):
    amount = int(match[0])
    activations = int(match[1]) if match[1] else 1
    is_random = bool(match[2])
    
    if amount < activations: return await message.answer("❌ Сумма меньше количества мест.")
    if activations < 1: return await message.answer("❌ Мест должно быть >= 1.")
    if user_db.balance < amount: return await message.answer(f"❌ У тебя нет {amount} Чилликов.")

    code = generate_cheque_code()
    
    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        if sender.balance < amount: return
        sender.balance -= amount
        await sender.save()
        
        await Cheque.create(
            code=code, creator_id=user_db.vk_id, 
            total_amount=amount, amount_left=amount,
            activations_limit=activations, mode="random" if is_random else "fix"
        )
        await TransactionLog.create(user=sender, amount=-amount, description=f"Чек {code}")

    type_text = "🎲 Рандомный" if is_random else "💰 Фиксированный"
    kb = Keyboard(inline=True).add(Text("Забрать 🖐", payload={"cmd": "claim", "code": code}), color=KeyboardButtonColor.POSITIVE).get_json()
    
    await message.answer(f"🤑 АТТРАКЦИОН ЩЕДРОСТИ!\n{type_text} чек на {amount} Чилликов!\nМест: {activations}", keyboard=kb)

@labeler.message(payload_map={"cmd": "claim"})
async def claim_cheque(message: Message, user_db: User):
    code = message.get_payload_json()["code"]
    
    async with in_transaction():
        # Блокируем чек
        cheque = await Cheque.filter(code=code).select_for_update().first()
        
        if not cheque: return await message.answer("❌ Чек исчез.", ephemeral=True)
        if cheque.activations_current >= cheque.activations_limit: return await message.answer("❌ Пусто. Ты слишком медленный.", ephemeral=True)
        if user_db.vk_id in cheque.users_activated: return await message.answer("❌ Ты уже брал!", ephemeral=True)
        if cheque.creator_id == user_db.vk_id: return await message.answer("🤡 Свой чек? Серьезно?", ephemeral=True)
        
        prize = 0
        if cheque.mode == "fix":
            prize = cheque.total_amount // cheque.activations_limit
        else:
            # ЧЕСТНЫЙ РАНДОМ С УЧЕТОМ ОСТАТКА
            remains_activations = cheque.activations_limit - cheque.activations_current
            if remains_activations == 1:
                prize = cheque.amount_left
            else:
                max_safe_amount = cheque.amount_left - (remains_activations - 1)
                if max_safe_amount < 1: max_safe_amount = 1
                prize = random.randint(1, max_safe_amount)

        # Вычитаем из остатка и сохраняем
        cheque.amount_left -= prize
        cheque.activations_current += 1
        
        # Обновляем список пользователей
        users = list(cheque.users_activated)
        users.append(user_db.vk_id)
        cheque.users_activated = users
        
        await cheque.save()
        
        user_db.balance += prize
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=prize, description=f"Чек {code}")

    await message.answer(f"✅ Урвал кусок!\n+{prize} Чилликов.")

@labeler.message(regex=r"^Промо\s+(.*)$")
async def activate_promo(message: Message, match, user_db: User):
    if message.peer_id != message.from_id: return
    code = match[0].strip()
    promo = await Promo.get_or_none(code=code)
    
    if not promo: return await message.answer("❌ Промокод не найден.")
    if promo.current_activations >= promo.max_activations: return await message.answer("❌ Промокод закончился.")
    if user_db.vk_id in promo.users_activated: return await message.answer("❌ Ты уже активировал.")
    
    async with in_transaction():
        p = await Promo.filter(code=code).select_for_update().first()
        if p.current_activations >= p.max_activations: return await message.answer("❌ Не успел!")
        
        p.current_activations += 1
        users = list(p.users_activated)
        users.append(user_db.vk_id)
        p.users_activated = users
        await p.save()
        
        user_db.balance += p.amount
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=p.amount, description=f"Promo {code}")
        
    await message.answer(f"✅ Промокод активирован!\nНасыпал тебе {p.amount} Чилликов.")

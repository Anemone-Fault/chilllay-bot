from vkbottle.bot import BotLabeler, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, TransactionLog, Cheque, Promo
from tortoise.transactions import in_transaction
from datetime import datetime, timezone, timedelta
from utils.helpers import get_id_from_mention, generate_cheque_code
from utils.card_updater import auto_update_card
from settings import ADMIN_IDS
import random
import asyncio

labeler = BotLabeler()

# --- 🛠 ПОМОЩНИК: ПОЛУЧЕНИЕ ИГРОКА ---
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

# --- 🎮 ОБНОВЛЕННАЯ КЛАВИАТУРА ---
def get_main_keyboard():
    """Стильная клавиатура с новыми цветами"""
    kb = Keyboard(inline=True)
    # Первый ряд: основная информация
    kb.add(Text("👤 Профиль"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("💰 Баланс"), color=KeyboardButtonColor.POSITIVE)
    kb.row()
    # Второй ряд: действия
    kb.add(Text("🎁 Бонус"), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text("🎰 Казино"), color=KeyboardButtonColor.NEGATIVE)
    kb.row()
    # Третий ряд: социальное
    kb.add(Text("🏆 Топ"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("🛒 Магазин"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    # Четвертый ряд: помощь
    kb.add(Text("❓ Помощь"), color=KeyboardButtonColor.SECONDARY)
    return kb.get_json()

# --- КАЗИНО: ХРАНИЛИЩЕ МУТОВ ---
casino_mutes = {}  # {user_id: datetime_until}

def is_muted(user_id: int) -> tuple[bool, int]:
    """Проверяет, замьючен ли игрок. Возвращает (замьючен, минут_осталось)"""
    if user_id not in casino_mutes:
        return False, 0
    
    until = casino_mutes[user_id]
    now = datetime.now(timezone.utc)
    
    if now >= until:
        del casino_mutes[user_id]
        return False, 0
    
    minutes_left = int((until - now).total_seconds() / 60)
    return True, minutes_left

# --- КОМАНДЫ ---

@labeler.message(regex=r"^(?i)(?:Fix|Убрать|Скрыть|Очистить)$")
async def clear_keyboard(message: Message):
    kb = Keyboard(one_time=True) 
    await message.answer("🧹 Старая клавиатура удалена!", keyboard=kb.get_json())

@labeler.message(regex=r"^(?i)(?:Профиль|Статус|Инфо|Profile|Стата|👤 Профиль)(?:\s.*)?$")
async def profile(message: Message):
    user_db = await get_user(message)
    text = (
        f"╔═══════════════╗\n"
        f"    👤 ПРОФИЛЬ\n"
        f"╚═══════════════╝\n\n"
        f"🎭 Игрок: {user_db.first_name}\n"
        f"💰 Чиллики: {user_db.balance}\n"
        f"☢️ Ранг: {user_db.get_rank()}\n"
        f"☯️ Карма: {user_db.karma}\n"
        f"🆔 ID: vk.com/id{user_db.vk_id}"
    )
    attachment = None
    if user_db.card_photo_id:
        attachment = f"photo{user_db.card_photo_id}"
        
    await message.answer(text, attachment=attachment, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:Обновить карту|Update card)$")
async def manual_update_card(message: Message):
    user_db = await get_user(message)
    await auto_update_card(message.ctx_api, user_db)
    await message.answer("✅ Данные на карточке обновлены!")

@labeler.message(regex=r"^(?i)(?:Помощь|Команды|Меню|Help|Start|Начать|❓ Помощь)(?:\s.*)?$")
async def help_command(message: Message):
    user_db = await get_user(message)
    text = (
        "╔═══════════════╗\n"
        "    📚 НАВИГАЦИЯ\n"
        "╚═══════════════╝\n\n"
        "👤 ЛИЧНОЕ:\n"
        "• Профиль - твоя карточка\n"
        "• Баланс - твои чиллики\n"
        "• Бонус - раз в 24 часа\n"
        "• Топ - богатейшие игроки\n\n"
        "🎰 РАЗВЛЕЧЕНИЯ:\n"
        "• Казино [сумма] - рулетка!\n\n"
        "💸 ДЕЙСТВИЯ:\n"
        "• Перевод @user 100\n"
        "• Чек 1000 3\n"
        "• +реп @user / -реп @user\n\n"
        "🛒 МАГАЗИН:\n"
        "• Хочу [товар]"
    )
    if message.from_id in ADMIN_IDS:
        text += "\n\n👮‍♂️ АДМИН:\nНачислить, Списать, Бан, Рассылка, Промокод, Стоимость, Связать [photo-123_456] [id]"
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:Магазин|Shop|Купить|🛒 Магазин)(?:\s.*)?$")
async def shop_info(message: Message):
    await message.answer(
        "╔═══════════════╗\n"
        "    🛒 МАГАЗИН\n"
        "╚═══════════════╝\n\n"
        "Чтобы купить что-то, напиши:\n"
        "👉 Хочу [товар]\n\n"
        "Админ оценит товар и пришлет цену!",
        keyboard=get_main_keyboard()
    )

@labeler.message(regex=r"^(?i)(?:Баланс|Деньги|Счет|Бабки|Money|💰 Баланс)(?:\s.*)?$")
async def balance(message: Message):
    user_db = await get_user(message)
    await message.answer(
        f"╔═══════════════╗\n"
        f"    💰 БАЛАНС\n"
        f"╚═══════════════╝\n\n"
        f"Твои Чиллики: {user_db.balance}\n"
        f"Ранг: {user_db.get_rank()}",
        keyboard=get_main_keyboard()
    )

@labeler.message(regex=r"^(?i)(?:Топ|Рейтинг|Богачи|🏆 Топ)(?:\s.*)?$")
async def top_users(message: Message):
    users = await User.filter(is_banned=False).order_by("-balance").limit(10)
    text = (
        "╔═══════════════╗\n"
        "    🏆 ТОП ИГРОКОВ\n"
        "╚═══════════════╝\n\n"
    )
    
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(users, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        # Убираем теги - просто показываем имя
        text += f"{medal} {u.first_name} — {u.balance} ({u.get_rank()})\n"
    
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:Бонус|Халява|Bonus|🎁 Бонус)(?:\s.*)?$")
async def daily_bonus(message: Message):
    user_db = await get_user(message)
    now = datetime.now(timezone.utc)
    if user_db.last_bonus and (now - user_db.last_bonus).total_seconds() < 86400:
        hours_left = int((86400 - (now - user_db.last_bonus).total_seconds()) / 3600)
        return await message.answer(
            f"⏰ Куда лезешь?\nБонус раз в 24 часа.\n\n"
            f"Осталось: ~{hours_left}ч",
            keyboard=get_main_keyboard()
        )
    
    amount = random.randint(10, 100)
    user_db.balance += amount
    user_db.last_bonus = now
    await user_db.save()
    await TransactionLog.create(user=user_db, amount=amount, description="Бонус")
    
    await auto_update_card(message.ctx_api, user_db)
    
    await message.answer(
        f"🎁 Халява!\n\n"
        f"Ты нафармил {amount} Чилликов\n"
        f"💰 Баланс: {user_db.balance}",
        keyboard=get_main_keyboard()
    )

# --- 🎰 КАЗИНО ---
@labeler.message(regex=r"^(?i)(?:Казино|Casino|🎰 Казино)(?:\s+(\d+))?$")
async def casino(message: Message, match):
    user_db = await get_user(message)
    
    # Проверяем мут
    muted, minutes = is_muted(user_db.vk_id)
    if muted:
        return await message.answer(
            f"🔇 ТЫ В МУТЕ!\n\n"
            f"Ты слишком часто сливаешь.\n"
            f"Осталось: {minutes} минут",
            keyboard=get_main_keyboard()
        )
    
    # Если сумма не указана - показываем справку
    if not match[0]:
        return await message.answer(
            "╔═══════════════╗\n"
            "    🎰 КАЗИНО\n"
            "╚═══════════════╝\n\n"
            "🎲 Шанс выигрыша: 5%\n"
            "💰 Выигрыш: x2 ставки\n"
            "📉 Проигрыш: -50% ставки\n\n"
            "⚠️ ВНИМАНИЕ:\n"
            "Если после проигрыша у тебя\n"
            "останется меньше 200 чилликов,\n"
            "тебя замутит на 1 час!\n\n"
            "Использование:\n"
            "Казино [сумма]",
            keyboard=get_main_keyboard()
        )
    
    bet = int(match[0])
    
    # Проверки
    if bet <= 0:
        return await message.answer("❌ Ставка должна быть > 0", keyboard=get_main_keyboard())
    
    if user_db.balance < bet:
        return await message.answer(
            f"❌ Недостаточно средств!\n\n"
            f"💰 Твой баланс: {user_db.balance}\n"
            f"📊 Нужно: {bet}",
            keyboard=get_main_keyboard()
        )
    
    # Анимация рулетки
    animation_msg = await message.answer("🎰 Рулетка крутится...")
    
    slots = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🔥"]
    
    # Показываем "вращение"
    for _ in range(3):
        slot1 = random.choice(slots)
        slot2 = random.choice(slots)
        slot3 = random.choice(slots)
        await asyncio.sleep(0.5)
        try:
            await message.ctx_api.messages.edit(
                peer_id=message.peer_id,
                message=f"🎰 [ {slot1} | {slot2} | {slot3} ]",
                conversation_message_id=animation_msg.conversation_message_id
            )
        except:
            pass
    
    # Определяем результат (5% на выигрыш)
    win = random.random() < 0.05
    
    if win:
        # ВЫИГРЫШ - удваиваем ставку
        prize = bet * 2
        user_db.balance += prize
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=prize, description="Казино (выигрыш)")
        await auto_update_card(message.ctx_api, user_db)
        
        final_slots = ["7️⃣", "7️⃣", "7️⃣"]
        result_text = (
            f"╔═══════════════╗\n"
            f"🎰 [ {final_slots[0]} | {final_slots[1]} | {final_slots[2]} ]\n"
            f"╚═══════════════╝\n\n"
            f"🎉 ДЖЕКПОТ!\n\n"
            f"💰 Выигрыш: +{prize}\n"
            f"📊 Баланс: {user_db.balance}"
        )
        
    else:
        # ПРОИГРЫШ - теряем половину ставки
        loss = bet // 2
        user_db.balance -= loss
        
        # Проверяем мут (если баланс < 200)
        if user_db.balance < 200:
            mute_until = datetime.now(timezone.utc) + timedelta(hours=1)
            casino_mutes[user_db.vk_id] = mute_until
            mute_text = "\n\n🔇 ТЫ В МУТЕ НА 1 ЧАС!"
        else:
            mute_text = ""
        
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=-loss, description="Казино (проигрыш)")
        await auto_update_card(message.ctx_api, user_db)
        
        final_slots = [random.choice(slots), random.choice(slots), random.choice(slots)]
        result_text = (
            f"╔═══════════════╗\n"
            f"🎰 [ {final_slots[0]} | {final_slots[1]} | {final_slots[2]} ]\n"
            f"╚═══════════════╝\n\n"
            f"💔 ПРОИГРЫШ\n\n"
            f"📉 Потеряно: -{loss}\n"
            f"📊 Баланс: {user_db.balance}{mute_text}"
        )
    
    await asyncio.sleep(0.5)
    try:
        await message.ctx_api.messages.edit(
            peer_id=message.peer_id,
            message=result_text,
            conversation_message_id=animation_msg.conversation_message_id,
            keyboard=get_main_keyboard()
        )
    except:
        await message.answer(result_text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:Перевод|Скинуть|Отправить)\s+(.*?)\s+(\d+)(?:\s+(.*))?$")
async def transfer(message: Message, match):
    user_db = await get_user(message)
    target_raw, amount_str, comment = match[0], match[1], match[2] or "Без комментария"
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)
    
    if not target_id: return await message.answer("❌ Кому?", keyboard=get_main_keyboard())
    if target_id == user_db.vk_id: return await message.answer("🤡 Шизофрения.", keyboard=get_main_keyboard())
    if amount <= 0: return await message.answer("❌ Сумма > 0.", keyboard=get_main_keyboard())
    if user_db.balance < amount: return await message.answer(f"❌ Недостаточно Чилликов.", keyboard=get_main_keyboard())

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        recipient = await User.get_or_none(vk_id=target_id)
        if not recipient: return await message.answer("❌ Юзер не найден.", keyboard=get_main_keyboard())
        if sender.balance < amount: return await message.answer("❌ Не хватает денег.", keyboard=get_main_keyboard())

        sender.balance -= amount
        recipient.balance += amount
        await sender.save()
        await recipient.save()
        await TransactionLog.create(user=sender, amount=-amount, description=f"Перевод -> {target_id}")
        await TransactionLog.create(user=recipient, amount=amount, description=f"Перевод <- {sender.vk_id}")

    await auto_update_card(message.ctx_api, sender)
    await auto_update_card(message.ctx_api, recipient)

    await message.answer(
        f"✅ Перевод выполнен\n\n"
        f"💸 Отправлено: {amount}\n"
        f"👤 Получатель: {recipient.first_name}\n"
        f"📊 Твой баланс: {sender.balance}",
        keyboard=get_main_keyboard()
    )
    
    try:
        await message.ctx_api.messages.send(
            peer_id=target_id, 
            message=(
                f"💸 ПЕРЕВОД\n\n"
                f"От: {sender.first_name}\n"
                f"Сумма: +{amount} чилликов\n"
                f"💬 {comment}"
            ),
            random_id=0
        )
    except: pass

@labeler.message(regex=r"^\+реп\s+(.*)$")
async def plus_rep(message: Message, match):
    user_db = await get_user(message)
    target_id = get_id_from_mention(match[0])
    cost = 100 
    if not target_id: return await message.answer("❌ Кому?", keyboard=get_main_keyboard())
    
    if user_db.balance < cost: return await message.answer(f"❌ Цена {cost}.", keyboard=get_main_keyboard())

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        
        if not target: return await message.answer("❌ Не найден.", keyboard=get_main_keyboard())
        if sender.balance < cost: return await message.answer("❌ Мало денег.", keyboard=get_main_keyboard())
        
        sender.balance -= cost
        target.karma += 1
        
        await sender.save()
        await target.save()
        await TransactionLog.create(user=sender, amount=-cost, description="Респект")

    await auto_update_card(message.ctx_api, sender)
    
    await message.answer(
        f"🫡 Респект отправлен\n\n"
        f"👤 Кому: {target.first_name}\n"
        f"💸 Списано: {cost} чилликов\n"
        f"📊 Баланс: {sender.balance}",
        keyboard=get_main_keyboard()
    )

@labeler.message(regex=r"^\-реп\s+(.*)$")
async def minus_rep(message: Message, match):
    user_db = await get_user(message)
    target_id = get_id_from_mention(match[0])
    cost = 500
    if not target_id: return await message.answer("❌ Кого?", keyboard=get_main_keyboard())
    
    if user_db.balance < cost: return await message.answer(f"❌ Цена {cost}.", keyboard=get_main_keyboard())

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        
        if not target: return await message.answer("❌ Не найден.", keyboard=get_main_keyboard())
        if sender.balance < cost: return await message.answer("❌ Мало денег.", keyboard=get_main_keyboard())
        
        sender.balance -= cost
        target.karma -= 1
        
        await sender.save()
        await target.save()
        await TransactionLog.create(user=sender, amount=-cost, description="Дизлайк")

    await auto_update_card(message.ctx_api, sender)
    
    await message.answer(
        f"💦 Харкнул в профиль\n\n"
        f"👤 Кому: {target.first_name}\n"
        f"💸 Списано: {cost} чилликов\n"
        f"📊 Баланс: {sender.balance}",
        keyboard=get_main_keyboard()
    )

@labeler.message(regex=r"^(?i)Чек\s+(\d+)(?:\s+(\d+))?(?:\s+(р))?$")
async def create_cheque(message: Message, match):
    user_db = await get_user(message)
    amount = int(match[0])
    activations = int(match[1]) if match[1] else 1
    is_random = bool(match[2])
    
    if user_db.balance < amount: return await message.answer(f"❌ Нет денег.", keyboard=get_main_keyboard())
    code = generate_cheque_code()
    
    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        if sender.balance < amount: return
        sender.balance -= amount
        await sender.save()
        
        await Cheque.create(code=code, creator_id=user_db.vk_id, total_amount=amount, amount_left=amount, activations_limit=activations, mode="random" if is_random else "fix")
        await TransactionLog.create(user=sender, amount=-amount, description=f"Чек {code}")

    await auto_update_card(message.ctx_api, sender)

    type_text = "🎲 Рандомный" if is_random else "💰 Фиксированный"
    kb_inline = Keyboard(inline=True).add(Text("Забрать 🖐", payload={"cmd": "claim", "code": code}), color=KeyboardButtonColor.POSITIVE).get_json()
    await message.answer(
        f"╔═══════════════╗\n"
        f"  🤑 АТТРАКЦИОН\n"
        f"    ЩЕДРОСТИ\n"
        f"╚═══════════════╝\n\n"
        f"{type_text} чек\n"
        f"💰 Сумма: {amount}\n"
        f"👥 Мест: {activations}",
        keyboard=kb_inline
    )

@labeler.message(payload_map={"cmd": "claim"})
async def claim_cheque(message: Message):
    user_db = await get_user(message)
    code = message.get_payload_json()["code"]
    async with in_transaction():
        cheque = await Cheque.filter(code=code).select_for_update().first()
        if not cheque: return await message.answer("❌ Чек исчез.", ephemeral=True)
        if cheque.activations_current >= cheque.activations_limit: return await message.answer("❌ Пусто.", ephemeral=True)
        if user_db.vk_id in cheque.users_activated: return await message.answer("❌ Ты уже брал!", ephemeral=True)
        if cheque.creator_id == user_db.vk_id: return await message.answer("🤡 Свой чек? Серьезно?", ephemeral=True)
        
        prize = 0
        if cheque.mode == "fix":
            prize = cheque.total_amount // cheque.activations_limit
        else:
            remains = cheque.activations_limit - cheque.activations_current
            if remains == 1: prize = cheque.amount_left
            else:
                max_safe = cheque.amount_left - (remains - 1)
                if max_safe < 1: max_safe = 1
                prize = random.randint(1, max(1, max_safe))

        cheque.amount_left -= prize
        cheque.activations_current += 1
        users = list(cheque.users_activated)
        users.append(user_db.vk_id)
        cheque.users_activated = users
        await cheque.save()
        
        user_db.balance += prize
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=prize, description=f"Чек {code}")

    await auto_update_card(message.ctx_api, user_db)
    await message.answer(
        f"✅ Урвал кусок!\n\n"
        f"💰 +{prize} Чилликов\n"
        f"📊 Баланс: {user_db.balance}",
        keyboard=get_main_keyboard()
    )

@labeler.message(regex=r"^(?i)Промо\s+(.*)$")
async def activate_promo(message: Message, match):
    user_db = await get_user(message)
    if message.peer_id != message.from_id: return
    code = match[0].strip()
    promo = await Promo.get_or_none(code=code)
    
    if not promo: return await message.answer("❌ Не найден.", keyboard=get_main_keyboard())
    if promo.current_activations >= promo.max_activations: return await message.answer("❌ Закончился.", keyboard=get_main_keyboard())
    if user_db.vk_id in promo.users_activated: return await message.answer("❌ Ты уже активировал.", keyboard=get_main_keyboard())
    
    async with in_transaction():
        p = await Promo.filter(code=code).select_for_update().first()
        if p.current_activations >= p.max_activations: return await message.answer("❌ Не успел!", keyboard=get_main_keyboard())
        
        p.current_activations += 1
        users = list(p.users_activated)
        users.append(user_db.vk_id)
        p.users_activated = users
        await p.save()
        
        user_db.balance += p.amount
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=p.amount, description=f"Promo {code}")

    await auto_update_card(message.ctx_api, user_db)
    await message.answer(
        f"✅ Промокод активирован!\n\n"
        f"💰 +{p.amount} Чилликов\n"
        f"📊 Баланс: {user_db.balance}",
        keyboard=get_main_keyboard()
    )

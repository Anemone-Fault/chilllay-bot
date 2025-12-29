from vkbottle.bot import BotLabeler, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, TransactionLog, Cheque, Promo
from tortoise.transactions import in_transaction
from datetime import datetime, timezone
from utils.helpers import get_id_from_mention, generate_cheque_code
from settings import ADMIN_IDS
import random

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

# --- 📸 ПОМОЩНИК: АВТО-ОБНОВЛЕНИЕ ФОТО ---
async def auto_update_card(api, user_db: User):
    """Эта функция тихо обновляет фото, если оно привязано"""
    if not user_db.card_photo_id:
        return

    await user_db.refresh_from_db()

    new_description = (
        f"╔══════════════════╗\n"
        f"  ✦ ДОСЬЕ ИГРОКА ✦\n"
        f"╚══════════════════╝\n\n"
        f"👤 Имя: {user_db.first_name}\n"
        f"☢ Ранг: {user_db.get_rank()}\n"
        f"💰 Баланс: {user_db.balance:,} чилликов\n"
        f"☯️ Карма: {user_db.karma}\n\n"
        f"🕒 Обновлено: {datetime.now().strftime('%d.%m.%Y в %H:%M')}"
    )

    try:
        owner_id, photo_id = user_db.card_photo_id.split('_')
        await api.photos.edit(
            owner_id=int(owner_id),
            photo_id=int(photo_id),
            caption=new_description
        )
    except:
        pass

# --- 🎮 КЛАВИАТУРА ---
def get_main_keyboard():
    kb = Keyboard(inline=True)
    kb.add(Text("👤 Профиль"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("💰 Баланс"), color=KeyboardButtonColor.SECONDARY)
    kb.row()
    kb.add(Text("🎁 Бонус"), color=KeyboardButtonColor.POSITIVE)
    kb.add(Text("🏆 Топ"), color=KeyboardButtonColor.PRIMARY)
    kb.row()
    kb.add(Text("🛒 Магазин"), color=KeyboardButtonColor.PRIMARY)
    kb.add(Text("❓ Помощь"), color=KeyboardButtonColor.NEGATIVE)
    return kb.get_json()

# --- КОМАНДЫ ---

@labeler.message(regex=r"^(?i)(?:Fix|Убрать|Скрыть|Очистить)$")
async def clear_keyboard(message: Message):
    kb = Keyboard(one_time=True)
    await message.answer("🧹 Клавиатура убрана!\n\n💡 Вызвать обратно: напиши Помощь", keyboard=kb.get_json())

@labeler.message(regex=r"^(?i)(?:👤\s*)?(?:Профиль|Статус|Инфо|Profile|Стата)(?:\s.*)?$")
async def profile(message: Message):
    user_db = await get_user(message)
    
    text = (
        f"╔══════════════════════╗\n"
        f"     💎 ТВОЙ ПРОФИЛЬ 💎\n"
        f"╚══════════════════════╝\n\n"
        f"👤 Игрок: [id{user_db.vk_id}|{user_db.first_name}]\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Чиллики: {user_db.balance:,}\n"
        f"☢️ Ранг: {user_db.get_rank()}\n"
        f"☯️ Карма: {user_db.karma}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 В игре с: {user_db.created_at.strftime('%d.%m.%Y')}"
    )
    
    attachment = None
    if user_db.card_photo_id:
        attachment = f"photo{user_db.card_photo_id}"
        
    await message.answer(text, attachment=attachment, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:Обновить карту|Update card)$")
async def manual_update_card(message: Message):
    user_db = await get_user(message)
    await auto_update_card(message.ctx_api, user_db)
    await message.answer(
        "✅ Карточка обновлена!\n\n"
        "📸 Данные на фото теперь актуальны.",
        keyboard=get_main_keyboard()
    )

@labeler.message(regex=r"^(?i)(?:❓\s*)?(?:Помощь|Команды|Меню|Help|Start|Начать)(?:\s.*)?$")
async def help_command(message: Message):
    user_db = await get_user(message)
    
    text = (
        "╔═══════════════════════╗\n"
        "    📚 НАВИГАЦИЯ БОТА 📚\n"
        "╚═══════════════════════╝\n\n"
        "┏━━━━━━ 👤 ПРОФИЛЬ ━━━━━━┓\n"
        "│ 👤 Профиль — твоя карточка\n"
        "│ 💰 Баланс — сколько чилликов\n"
        "│ 🎁 Бонус — халява раз в 24ч\n"
        "│ 🏆 Топ — рейтинг игроков\n"
        "┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "┏━━━━━ 💸 ДЕЙСТВИЯ ━━━━━┓\n"
        "│ Перевод @user 100\n"
        "│ Чек 1000 3 — создать чек\n"
        "│ +реп @user — уважуха (+1)\n"
        "│ -реп @user — презрение (-1)\n"
        "│ Промо CODE — активировать\n"
        "┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "┏━━━━━ 🛒 МАГАЗИН ━━━━━━┓\n"
        "│ Хочу [товар] — заявка\n"
        "│ Цену установит Админ\n"
        "┗━━━━━━━━━━━━━━━━━━━━━┛"
    )
    
    if message.from_id in ADMIN_IDS:
        text += (
            "\n\n┏━━━━ 👮 АДМИН-ПАНЕЛЬ 👮 ━━━┓\n"
            "│ Начислить @user 100\n"
            "│ Списать @user 50\n"
            "│ Попущенный @user — бан\n"
            "│ Разбан @user\n"
            "│ Рассылка [текст]\n"
            "│ Промокод CODE 100 5\n"
            "│ Связать [фото] [id]\n"
            "│ Стоимость: 100 (ответом)\n"
            "┗━━━━━━━━━━━━━━━━━━━━━┛"
        )
    
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:🛒\s*)?(?:Магазин|Shop|Купить)(?:\s.*)?$")
async def shop_info(message: Message):
    text = (
        "╔═══════════════════════╗\n"
        "      🛒 МАГАЗИН 🛒\n"
        "╚═══════════════════════╝\n\n"
        "💡 Как купить что-то?\n\n"
        "1️⃣ Напиши: Хочу [название]\n"
        "2️⃣ Админ установит цену\n"
        "3️⃣ Тебе придёт уведомление\n"
        "4️⃣ Подтверди покупку\n\n"
        "💰 Пример:\n"
        "→ Хочу роль VIP"
    )
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:💰\s*)?(?:Баланс|Деньги|Счет|Бабки|Money)(?:\s.*)?$")
async def balance(message: Message):
    user_db = await get_user(message)
    
    text = (
        f"╔═══════════════════════╗\n"
        f"      💰 ТВОЙ БАЛАНС 💰\n"
        f"╚═══════════════════════╝\n\n"
        f"💵 Чиллики: {user_db.balance:,}\n"
        f"☢️ Ранг: {user_db.get_rank()}\n\n"
        f"💡 Способы заработка:\n"
        f"→ 🎁 Бонус (раз в 24ч)\n"
        f"→ 💸 Переводы от игроков\n"
        f"→ 🎫 Чеки и промокоды"
    )
    
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:🏆\s*)?(?:Топ|Рейтинг|Богачи)(?:\s.*)?$")
async def top_users(message: Message):
    users = await User.filter(is_banned=False).order_by("-balance").limit(10)
    
    text = (
        "╔═══════════════════════╗\n"
        "    🏆 ТОП ЧИЛЛИКОВ 🏆\n"
        "╚═══════════════════════╝\n\n"
    )
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, u in enumerate(users, 1):
        medal = medals[i-1] if i <= len(medals) else f"{i}."
        text += f"{medal} [id{u.vk_id}|{u.first_name}]\n"
        text += f"   💰 {u.balance:,} ┃ {u.get_rank()}\n\n"
    
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:🎁\s*)?(?:Бонус|Халява|Bonus)(?:\s.*)?$")
async def daily_bonus(message: Message):
    user_db = await get_user(message)
    now = datetime.now(timezone.utc)
    
    if user_db.last_bonus and (now - user_db.last_bonus).total_seconds() < 86400:
        remaining = 86400 - (now - user_db.last_bonus).total_seconds()
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        
        text = (
            "╔═══════════════════════╗\n"
            "      ⏰ СЛИШКОМ РАНО ⏰\n"
            "╚═══════════════════════╝\n\n"
            f"🚫 Бонус раз в 24 часа!\n\n"
            f"⏳ Осталось: {hours}ч {minutes}м\n\n"
            f"💡 Возвращайся позже!"
        )
        return await message.answer(text, keyboard=get_main_keyboard())
    
    amount = random.randint(10, 100)
    user_db.balance += amount
    user_db.last_bonus = now
    await user_db.save()
    await TransactionLog.create(user=user_db, amount=amount, description="Бонус")
    
    await auto_update_card(message.ctx_api, user_db)
    
    text = (
        "╔═══════════════════════╗\n"
        "      🎁 ХАЛЯВА! 🎁\n"
        "╚═══════════════════════╝\n\n"
        f"✨ Ты нафармил: +{amount} 💰\n\n"
        f"💵 Новый баланс: {user_db.balance:,}\n\n"
        f"⏰ Следующий бонус через 24ч!"
    )
    
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)(?:Перевод|Скинуть|Отправить)\s+(.*?)\s+(\d+)(?:\s+(.*))?$")
async def transfer(message: Message, match):
    user_db = await get_user(message)
    target_raw, amount_str, comment = match[0], match[1], match[2] or "Без комментария"
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)
    
    if not target_id:
        return await message.answer("❌ Укажи пользователя правильно!\n\n💡 Пример: Перевод @user 100", keyboard=get_main_keyboard())
    
    if target_id == user_db.vk_id:
        return await message.answer("🤡 Себе переводить? Шизофрения?", keyboard=get_main_keyboard())
    
    if amount <= 0:
        return await message.answer("❌ Сумма должна быть больше 0!", keyboard=get_main_keyboard())
    
    if user_db.balance < amount:
        return await message.answer(
            f"╔═══════════════════════╗\n"
            f"     💸 НЕДОСТАТОЧНО 💸\n"
            f"╚═══════════════════════╝\n\n"
            f"❌ У тебя: {user_db.balance:,}\n"
            f"💰 Нужно: {amount:,}\n\n"
            f"💡 Не хватает: {amount - user_db.balance:,}",
            keyboard=get_main_keyboard()
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        recipient = await User.get_or_none(vk_id=target_id)
        
        if not recipient:
            return await message.answer("❌ Пользователь не найден в базе!", keyboard=get_main_keyboard())
        
        if sender.balance < amount:
            return await message.answer("❌ Недостаточно денег!", keyboard=get_main_keyboard())

        sender.balance -= amount
        recipient.balance += amount
        await sender.save()
        await recipient.save()
        await TransactionLog.create(user=sender, amount=-amount, description=f"Перевод → {target_id}")
        await TransactionLog.create(user=recipient, amount=amount, description=f"Перевод ← {sender.vk_id}")

    await auto_update_card(message.ctx_api, sender)
    await auto_update_card(message.ctx_api, recipient)

    text = (
        "╔═══════════════════════╗\n"
        "     ✅ ПЕРЕВОД ВЫПОЛНЕН ✅\n"
        "╚═══════════════════════╝\n\n"
        f"💸 Отправлено: {amount:,}\n"
        f"👤 Кому: [id{target_id}|{recipient.first_name}]\n"
        f"💬 Комментарий: {comment}\n\n"
        f"💰 Твой баланс: {sender.balance:,}"
    )
    
    await message.answer(text, keyboard=get_main_keyboard())
    
    try:
        notification = (
            "╔═══════════════════════╗\n"
            "     💰 ВХОДЯЩИЙ ПЕРЕВОД 💰\n"
            "╚═══════════════════════╝\n\n"
            f"✨ Получено: +{amount:,}\n"
            f"👤 От: [id{sender.vk_id}|{sender.first_name}]\n"
            f"💬 Сообщение: {comment}\n\n"
            f"💵 Твой баланс: {recipient.balance:,}"
        )
        await message.ctx_api.messages.send(peer_id=target_id, message=notification, random_id=0)
    except:
        pass

@labeler.message(regex=r"^\+реп\s+(.*)$")
async def plus_rep(message: Message, match):
    user_db = await get_user(message)
    target_id = get_id_from_mention(match[0])
    cost = 100
    
    if not target_id:
        return await message.answer("❌ Укажи пользователя!\n\n💡 Пример: +реп @user", keyboard=get_main_keyboard())
    
    if user_db.balance < cost:
        return await message.answer(
            f"╔═══════════════════════╗\n"
            f"     💸 НЕДОСТАТОЧНО 💸\n"
            f"╚═══════════════════════╝\n\n"
            f"💰 Цена: {cost:,}\n"
            f"💵 У тебя: {user_db.balance:,}\n\n"
            f"💡 Не хватает: {cost - user_db.balance:,}",
            keyboard=get_main_keyboard()
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        
        if not target:
            return await message.answer("❌ Пользователь не найден!", keyboard=get_main_keyboard())
        
        if sender.balance < cost:
            return await message.answer("❌ Недостаточно чилликов!", keyboard=get_main_keyboard())
        
        sender.balance -= cost
        target.karma += 1
        
        await sender.save()
        await target.save()
        await TransactionLog.create(user=sender, amount=-cost, description="Респект")

    await auto_update_card(message.ctx_api, sender)
    
    text = (
        "╔═══════════════════════╗\n"
        "      🫡 РЕСПЕКТ ОТПРАВЛЕН 🫡\n"
        "╚═══════════════════════╝\n\n"
        f"✅ [id{target_id}|{target.first_name}] получил +1 карму!\n\n"
        f"💸 Списано: {cost:,}\n"
        f"💰 Остаток: {sender.balance:,}"
    )
    
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^\-реп\s+(.*)$")
async def minus_rep(message: Message, match):
    user_db = await get_user(message)
    target_id = get_id_from_mention(match[0])
    cost = 500
    
    if not target_id:
        return await message.answer("❌ Кого дизлайкаем?\n\n💡 Пример: -реп @user", keyboard=get_main_keyboard())
    
    if user_db.balance < cost:
        return await message.answer(
            f"╔═══════════════════════╗\n"
            f"     💸 НЕДОСТАТОЧНО 💸\n"
            f"╚═══════════════════════╝\n\n"
            f"💰 Цена: {cost:,}\n"
            f"💵 У тебя: {user_db.balance:,}\n\n"
            f"💡 Не хватает: {cost - user_db.balance:,}",
            keyboard=get_main_keyboard()
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        
        if not target:
            return await message.answer("❌ Пользователь не найден!", keyboard=get_main_keyboard())
        
        if sender.balance < cost:
            return await message.answer("❌ Недостаточно чилликов!", keyboard=get_main_keyboard())
        
        sender.balance -= cost
        target.karma -= 1
        
        await sender.save()
        await target.save()
        await TransactionLog.create(user=sender, amount=-cost, description="Дизлайк")

    await auto_update_card(message.ctx_api, sender)
    
    text = (
        "╔═══════════════════════╗\n"
        "      💦 ХАРКНУЛ! 💦\n"
        "╚═══════════════════════╝\n\n"
        f"🎯 [id{target_id}|{target.first_name}] получил -1 карму!\n\n"
        f"💸 Списано: {cost:,}\n"
        f"💰 Остаток: {sender.balance:,}"
    )
    
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)Чек\s+(\d+)(?:\s+(\d+))?(?:\s+(р))?$")
async def create_cheque(message: Message, match):
    user_db = await get_user(message)
    amount = int(match[0])
    activations = int(match[1]) if match[1] else 1
    is_random = bool(match[2])
    
    if user_db.balance < amount:
        return await message.answer(
            f"╔═══════════════════════╗\n"
            f"     💸 НЕДОСТАТОЧНО 💸\n"
            f"╚═══════════════════════╝\n\n"
            f"💰 Нужно: {amount:,}\n"
            f"💵 У тебя: {user_db.balance:,}\n\n"
            f"💡 Не хватает: {amount - user_db.balance:,}",
            keyboard=get_main_keyboard()
        )
    
    code = generate_cheque_code()
    
    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        if sender.balance < amount:
            return
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
        await TransactionLog.create(user=sender, amount=-amount, description=f"Чек {code}")

    await auto_update_card(message.ctx_api, sender)

    type_emoji = "🎲" if is_random else "💰"
    type_text = "Рандомный" if is_random else "Фиксированный"
    
    text = (
        "╔═══════════════════════╗\n"
        f"   {type_emoji} ЧЕК СОЗДАН! {type_emoji}\n"
        "╚═══════════════════════╝\n\n"
        f"🎫 Код: {code}\n"
        f"💰 Сумма: {amount:,}\n"
        f"👥 Активаций: {activations}\n"
        f"📦 Тип: {type_text}\n\n"
        "👇 Забирай первым!"
    )
    
    kb_inline = Keyboard(inline=True)
    kb_inline.add(Text(f"💸 Забрать чек", payload={"cmd": "claim", "code": code}), color=KeyboardButtonColor.POSITIVE)
    
    await message.answer(text, keyboard=kb_inline.get_json())

@labeler.message(payload_map={"cmd": "claim"})
async def claim_cheque(message: Message):
    user_db = await get_user(message)
    code = message.get_payload_json()["code"]
    
    async with in_transaction():
        cheque = await Cheque.filter(code=code).select_for_update().first()
        
        if not cheque:
            return await message.answer("❌ Чек не найден или уже удалён!", ephemeral=True)
        
        if cheque.activations_current >= cheque.activations_limit:
            return await message.answer("❌ Все места заняты! Опоздал!", ephemeral=True)
        
        if user_db.vk_id in cheque.users_activated:
            return await message.answer("❌ Ты уже активировал этот чек!", ephemeral=True)
        
        if cheque.creator_id == user_db.vk_id:
            return await message.answer("🤡 Свой чек активировать? Гений!", ephemeral=True)
        
        prize = 0
        if cheque.mode == "fix":
            prize = cheque.total_amount // cheque.activations_limit
        else:
            remains = cheque.activations_limit - cheque.activations_current
            if remains == 1:
                prize = cheque.amount_left
            else:
                max_safe = cheque.amount_left - (remains - 1)
                if max_safe < 1:
                    max_safe = 1
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
    
    text = (
        "╔═══════════════════════╗\n"
        "      🎉 УСПЕХ! 🎉\n"
        "╚═══════════════════════╝\n\n"
        f"✨ Выигрыш: +{prize:,} 💰\n"
        f"🎫 Чек: {code}\n\n"
        f"💵 Твой баланс: {user_db.balance:,}\n\n"
        f"📊 Активаций: {cheque.activations_current}/{cheque.activations_limit}"
    )
    
    await message.answer(text, keyboard=get_main_keyboard())

@labeler.message(regex=r"^(?i)Промо\s+(.*)$")
async def activate_promo(message: Message, match):
    user_db = await get_user(message)
    
    if message.peer_id != message.from_id:
        return
    
    code = match[0].strip()
    promo = await Promo.get_or_none(code=code)
    
    if not promo:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ НЕ НАЙДЕН ❌\n"
            "╚═══════════════════════╝\n\n"
            f"🎫 Промокод '{code}' не существует!\n\n"
            "💡 Проверь правильность написания",
            keyboard=get_main_keyboard()
        )
    
    if promo.current_activations >= promo.max_activations:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     😢 ЗАКОНЧИЛСЯ 😢\n"
            "╚═══════════════════════╝\n\n"
            f"🎫 Промокод '{code}' уже использован\n"
            f"максимальное количество раз!\n\n"
            f"📊 Активаций: {promo.current_activations}/{promo.max_activations}",
            keyboard=get_main_keyboard()
        )
    
    if user_db.vk_id in promo.users_activated:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ УЖЕ ИСПОЛЬЗОВАН ❌\n"
            "╚═══════════════════════╝\n\n"
            f"🎫 Ты уже активировал промокод '{code}'!\n\n"
            "💡 Один раз на человека",
            keyboard=get_main_keyboard()
        )
    
    async with in_transaction():
        p = await Promo.filter(code=code).select_for_update().first()
        if p.current_activations >= p.max_activations:
            return await message.answer("❌ Не успел! Кто-то активировал последним!", keyboard=get_main_keyboard())
        
        p.current_activations += 1
        users = list(p.users_activated)
        users.append(user_db.vk_id)
        p.users_activated = users
        await p.save()
        
        user_db.balance += p.amount
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=p.amount, description=f"Promo {code}")

    await auto_update_card(message.ctx_api, user_db)
    
    text = (
        "╔═══════════════════════╗\n"
        "    🎉 ПРОМОКОД АКТИВИРОВАН! 🎉\n"
        "╚═══════════════════════╝\n\n"
        f"🎫 Код: {code}\n"
        f"✨ Получено: +{p.amount:,} 💰\n\n"
        f"💵 Твой баланс: {user_db.balance:,}\n\n"
        f"📊 Осталось активаций: {promo.max_activations - p.current_activations}"
    )
    
    await message.answer(text, keyboard=get_main_keyboard())

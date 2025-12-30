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

casino_mutes = {}  
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
# КОМАНДЫ
# ====================

@labeler.message(regex=r"^(?i)(?:Помощь|Help|Команды)$")
async def help_handler(message: Message):
    user_db = await get_user(message)
    
    text = (
        "╔═══════════════════════╗\n"
        "       📖 НАВИГАЦИЯ\n"
        "╚═══════════════════════╝\n\n"
        
        "┏━━━━ 👤 ЛИЧНЫЙ КАБИНЕТ ━━━━┓\n"
        "│\n"
        "│ 🎴 Профиль\n"
        "│ → Твоя игровая карточка с рангом,\n"
        "│    балансом и репутацией\n"
        "│\n"
        "│ 💰 Баланс\n"
        "│ → Текущий счёт и накопленная\n"
        "│    зарплата за РП-активность\n"
        "│\n"
        "│ 🎁 Бонус\n"
        "│ → Ежедневная награда (раз в 24ч)\n"
        "│    Сумма зависит от твоей кармы!\n"
        "│\n"
        "│ 🏆 Топ\n"
        "│ → Рейтинг самых богатых игроков\n"
        "│    сервера (топ-10)\n"
        "│\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        "┏━━━━ 🎲 РАЗВЛЕЧЕНИЯ ━━━━┓\n"
        "│\n"
        "│ 🎰 Казино [сумма]\n"
        "│ → Испытай удачу в рулетке!\n"
        "│    5% шанс удвоить ставку\n"
        "│    При низком балансе — мут на 1ч\n"
        "│\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        "┏━━━━ 💸 ТРАНЗАКЦИИ ━━━━┓\n"
        "│\n"
        "│ 💸 Перевод @user [сумма] [комментарий]\n"
        "│ → Отправь чиллики другому игроку\n"
        "│    Комментарий — необязателен\n"
        "│\n"
        "│ 🎟 Чек [сумма] [активаций] [р]\n"
        "│ → Создай подарочный чек\n"
        "│    [р] = случайные суммы на каждого\n"
        "│    Без [р] = равные доли\n"
        "│\n"
        "│ 🎫 Промо [код]\n"
        "│ → Активируй промокод от админов\n"
        "│    и получи бонусные чиллики\n"
        "│\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        "┏━━━━ ⭐ РЕПУТАЦИЯ ━━━━┓\n"
        "│\n"
        "│ 👍 +реп @user\n"
        "│ → Повысить карму игрока (100₽)\n"
        "│    Влияет на ранг и бонусы\n"
        "│\n"
        "│ 👎 -реп @user\n"
        "│ → Понизить карму игрока (500₽)\n"
        "│    Может наложить дебафф\n"
        "│\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        
        "┏━━━━ 🛒 МАГАЗИН ━━━━┓\n"
        "│\n"
        "│ 🛍 Хочу [описание товара]\n"
        "│ → Создать заявку на покупку\n"
        "│    Админ оценит и установит цену\n"
        "│\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛"
    )
    
    # Админский раздел (только для админов)
    if message.from_id in ADMIN_IDS or user_db.is_admin:
        text += (
            "\n\n"
            "┏━━━━ 🔧 АДМИНИСТРИРОВАНИЕ ━━━━┓\n"
            "│\n"
            "│ 📋 КОМАНДЫ УПРАВЛЕНИЯ:\n"
            "│\n"
            "│ • Начислить @user [сумма]\n"
            "│   → Добавить чиллики игроку\n"
            "│\n"
            "│ • Списать @user [сумма]\n"
            "│   → Снять чиллики с баланса\n"
            "│\n"
            "│ • Попущенный @user\n"
            "│   → Забанить пользователя\n"
            "│\n"
            "│ • Разбан @user\n"
            "│   → Снять бан с игрока\n"
            "│\n"
            "│ • Рассылка [текст]\n"
            "│   → Отправить всем в ЛС\n"
            "│\n"
            "│ • Промокод [код] [сумма] [лимит]\n"
            "│   → Создать промокод\n"
            "│\n"
            "│ • Связать [photo-123_456] @user\n"
            "│   → Привязать фото к карточке\n"
            "│\n"
            "│ • Стоимость: [цена]\n"
            "│   → Ответ на заявку из магазина\n"
            "│\n"
            "│ 🎉 ИВЕНТЫ:\n"
            "│\n"
            "│ • !Ивенты\n"
            "│   → Список всех событий\n"
            "│\n"
            "│ • !Ивент [название] [вкл/выкл]\n"
            "│   → Включить/выключить событие\n"
            "│\n"
            "│ 🎨 КАСТОМИЗАЦИЯ:\n"
            "│\n"
            "│ • !СетФото [команда]\n"
            "│   → Установить картинку для меню\n"
            "│     (приложи фото к сообщению)\n"
            "│\n"
            "│ 🎁 ПРЕДМЕТЫ:\n"
            "│\n"
            "│ • !Создать [Имя] [Ранг] [Тип]\n"
            "│   → Добавить предмет в базу\n"
            "│\n"
            "│ • !Выдать @user\n"
            "│   → Подарить кейс игроку\n"
            "│\n"
            "│ 💰 СИСТЕМА:\n"
            "│\n"
            "│ • !Принудительная зарплата\n"
            "│   → Сбросить месячный счётчик\n"
            "│\n"
            "│ • !id\n"
            "│   → Узнать ID текущего чата\n"
            "│\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━━━┛"
        )

    img = await get_image_for_command("help")
    kb = await get_smart_keyboard(user_db, "help")
    await message.answer(text, attachment=img, keyboard=kb)

@labeler.message(regex=r"^(?i)(?:Профиль|Стат.?|Инфо|Я|Прф)$")
async def profile_handler(message: Message):
    user_db = await get_user(message)
    text = (
        f"╔═══════════════════════╗\n"
        f"       🎴 ПРОФИЛЬ\n"
        f"╚═══════════════════════╝\n\n"
        f"┏━━━━ ЛИЧНЫЕ ДАННЫЕ ━━━━┓\n"
        f"│\n"
        f"│ 🆔 ID: {user_db.vk_id}\n"
        f"│ 👤 Игрок: {user_db.first_name} {user_db.last_name}\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"┏━━━━ СТАТИСТИКА ━━━━┓\n"
        f"│\n"
        f"│ 📊 Ранг: {user_db.get_rank()}\n"
        f"│ 💰 Баланс: {user_db.balance:,} ₽\n"
        f"│ ⭐ Карма: {user_db.karma:+d}\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"💡 Повышай карму, чтобы получать\n"
        f"   больше чилликов за бонусы!"
    )
    
    attachment = None
    if user_db.card_photo_id:
        attachment = f"photo{user_db.card_photo_id}"
    else:
        attachment = await get_image_for_command("profile")
        
    kb = await get_smart_keyboard(user_db, "profile")
    await message.answer(text, attachment=attachment, keyboard=kb)

@labeler.message(regex=r"^(?i)(?:Баланс|Бал|Money)$")
async def balance_handler(message: Message):
    user_db = await get_user(message)
    text = (
        f"╔═══════════════════════╗\n"
        f"       💰 БАЛАНС\n"
        f"╚═══════════════════════╝\n\n"
        f"┏━━━━ СЧЁТ ━━━━┓\n"
        f"│\n"
        f"│ 💵 На руках:\n"
        f"│    {user_db.balance:,} чилликов\n"
        f"│\n"
        f"│ 💳 Зарплата (к выдаче):\n"
        f"│    {user_db.rp_pending_balance:,} чилликов\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"ℹ️ Зарплата начисляется за РП-посты\n"
        f"   и выплачивается в конце месяца.\n\n"
        f"📈 Пиши больше — получай больше!"
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
                f"╔═══════════════════════╗\n"
                f"       ⏳ ОЖИДАНИЕ\n"
                f"╚═══════════════════════╝\n\n"
                f"🕒 Бонус уже получен сегодня!\n\n"
                f"⏰ Приходи через:\n"
                f"   {hours} ч. {minutes} мин.\n\n"
                f"💡 Не забывай заглядывать каждый день!",
                keyboard=await get_smart_keyboard(user_db, "main")
            )

    amount = 50 + (abs(user_db.karma) * 2) 
    user_db.balance += amount
    user_db.last_bonus = now
    await user_db.save()
    await TransactionLog.create(user=user_db, amount=amount, description="Бонус")
    
    await auto_update_card(message.ctx_api, user_db)
    
    text = (
        f"╔═══════════════════════╗\n"
        f"       🎁 БОНУС\n"
        f"╚═══════════════════════╝\n\n"
        f"✨ Ежедневная награда получена!\n\n"
        f"┏━━━━ НАЧИСЛЕНО ━━━━┓\n"
        f"│\n"
        f"│ 💰 +{amount:,} чилликов\n"
        f"│ 📊 Баланс: {user_db.balance:,} ₽\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"🔄 Возвращайся завтра за новым бонусом!\n\n"
        f"💡 Совет: Высокая карма увеличивает\n"
        f"   размер ежедневной награды!"
    )
    kb = await get_smart_keyboard(user_db, "main")
    await message.answer(text, keyboard=kb)

@labeler.message(regex=r"^(?i)(?:Магазин|Shop|Купить|🛒 Магазин)(?:\s.*)?$")
async def shop_info(message: Message):
    user_db = await get_user(message)
    img = await get_image_for_command("shop")
    await message.answer(
        "╔═══════════════════════╗\n"
        "       🛒 МАГАЗИН\n"
        "╚═══════════════════════╝\n\n"
        "🎪 Добро пожаловать в торговый центр!\n\n"
        "┏━━━━ КАК КУПИТЬ? ━━━━┓\n"
        "│\n"
        "│ 1️⃣ Напиши команду:\n"
        "│    Хочу [описание товара]\n"
        "│\n"
        "│ 2️⃣ Администратор оценит товар\n"
        "│    и установит цену\n"
        "│\n"
        "│ 3️⃣ Тебе придёт уведомление\n"
        "│    с финальной стоимостью\n"
        "│\n"
        "┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "💡 Пример:\n"
        "   Хочу пиццу пепперони\n"
        "   Хочу VIP-статус на месяц\n"
        "   Хочу игровой предмет",
        attachment=img,
        keyboard=await get_smart_keyboard(user_db, "main")
    )

@labeler.message(regex=r"^(?i)(?:Топ|Рейтинг|Богачи|🏆 Топ)(?:\s.*)?$")
async def top_users(message: Message):
    user_db = await get_user(message)
    users = await User.filter(is_banned=False).order_by("-balance").limit(10)
    text = (
        "╔═══════════════════════╗\n"
        "       🏆 РЕЙТИНГ\n"
        "╚═══════════════════════╝\n\n"
        "┏━━━━ ТОП-10 БОГАЧЕЙ ━━━━┓\n"
        "│\n"
    )
    medals = ["🥇", "🥈", "🥉"]
    for i, u in enumerate(users, 1):
        if i <= 3:
            medal = medals[i-1]
        else:
            medal = f" {i}."
        text += f"│ {medal} {u.first_name}\n│    💰 {u.balance:,} ₽\n│\n"
    
    text += "┗━━━━━━━━━━━━━━━━━━━━━┛\n\n💡 Зарабатывай больше, чтобы попасть в топ!"
    
    await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

# --- КАЗИНО ---
@labeler.message(regex=r"^(?i)(?:Казино|Casino|🎰 Казино)(?:\s+(\d+))?$")
async def casino(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    
    muted, minutes = is_muted(user_db.vk_id)
    if muted:
        return await message.answer(
            f"╔═══════════════════════╗\n"
            f"       🔇 ТАЙМАУТ\n"
            f"╚═══════════════════════╝\n\n"
            f"⚠️ Ты временно отстранён от игры!\n\n"
            f"⏰ Осталось: {minutes} минут\n\n"
            f"💡 Используй это время, чтобы\n"
            f"   заработать чиллики другими способами!",
            keyboard=kb
        )
    
    if not match[0]:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "       🎰 КАЗИНО\n"
            "╚═══════════════════════╝\n\n"
            "🎲 Испытай удачу в рулетке!\n\n"
            "┏━━━━ ПРАВИЛА ━━━━┓\n"
            "│\n"
            "│ 🎯 Шанс выигрыша: 5%\n"
            "│ 💰 Приз: x2 ставки\n"
            "│ 💸 Проигрыш: -50% ставки\n"
            "│\n"
            "┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "⚠️ При балансе < 200₽ получишь\n"
            "   мут на 1 час после проигрыша!\n\n"
            "📝 Использование:\n"
            "   Казино [сумма ставки]",
            keyboard=kb
        )
    
    bet = int(match[0])
    if bet <= 0: return await message.answer("❌ Ставка должна быть больше 0!", keyboard=kb)
    if user_db.balance < bet: return await message.answer("❌ Недостаточно средств на балансе!", keyboard=kb)
    
    animation_msg = await message.answer("🎰 Рулетка крутится...")
    slots = ["🍎", "🍋", "🍊", "🍇", "💎", "7️⃣", "🔥"]
    
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
            f"╔═══════════════════════╗\n"
            f"🎰 [ 7️⃣ | 7️⃣ | 7️⃣ ]\n"
            f"╚═══════════════════════╝\n\n"
            f"🎉 ДЖЕКПОТ!\n\n"
            f"┏━━━━ ВЫИГРЫШ ━━━━┓\n"
            f"│\n"
            f"│ 💰 +{prize:,} чилликов\n"
            f"│ 📊 Баланс: {user_db.balance:,} ₽\n"
            f"│\n"
            f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"🍀 Удача на твоей стороне!"
        )
    else:
        loss = bet // 2
        user_db.balance -= loss
        mute_text = ""
        if user_db.balance < 200:
            casino_mutes[user_db.vk_id] = datetime.now(timezone.utc) + timedelta(hours=1)
            mute_text = "\n\n⚠️ МУТ НА 1 ЧАС!\n   Баланс слишком низкий."
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=-loss, description="Казино Loss")
        await auto_update_card(message.ctx_api, user_db)
        res = (
            f"╔═══════════════════════╗\n"
            f"🎰 [ 🍎 | 🍋 | 🔥 ]\n"
            f"╚═══════════════════════╝\n\n"
            f"💔 НЕ ПОВЕЗЛО\n\n"
            f"┏━━━━ ПРОИГРЫШ ━━━━┓\n"
            f"│\n"
            f"│ 💸 -{loss:,} чилликов\n"
            f"│ 📊 Баланс: {user_db.balance:,} ₽\n"
            f"│\n"
            f"┗━━━━━━━━━━━━━━━━━━━━━┛{mute_text}\n\n"
            f"💡 Не расстраивайся! Попробуй ещё раз!"
        )
    
    try: await message.ctx_api.messages.edit(peer_id=message.peer_id, message=res, conversation_message_id=animation_msg.conversation_message_id, keyboard=kb)
    except: await message.answer(res, keyboard=kb)

# --- ПЕРЕВОДЫ ---
@labeler.message(regex=r"^(?i)(?:Перевод|Скинуть|Отправить)\s+(.*?)\s+(\d+)(?:\s+(.*))?$")
async def transfer(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_raw, amount, comment = match[0], int(match[1]), match[2] or "Без комментария"
    target_id = get_id_from_mention(target_raw)
    
    if not target_id: return await message.answer("❌ Укажи получателя (@user или vk.com/id...)", keyboard=kb)
    if target_id == user_db.vk_id: return await message.answer("❌ Нельзя переводить самому себе!", keyboard=kb)
    if amount <= 0: return await message.answer("❌ Сумма должна быть больше 0!", keyboard=kb)
    if user_db.balance < amount: return await message.answer("❌ Недостаточно средств на балансе!", keyboard=kb)

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        recipient = await User.get_or_none(vk_id=target_id)
        if not recipient: return await message.answer("❌ Получатель не найден в базе!", keyboard=kb)
        if sender.balance < amount: return await message.answer("❌ Недостаточно средств!", keyboard=kb)

        sender.balance -= amount
        recipient.balance += amount
        await sender.save()
        await recipient.save()
        await TransactionLog.create(user=sender, amount=-amount, description=f"-> {target_id}")
        await TransactionLog.create(user=recipient, amount=amount, description=f"<- {sender.vk_id}")

    await auto_update_card(message.ctx_api, sender)
    await auto_update_card(message.ctx_api, recipient)

    await message.answer(
        f"╔═══════════════════════╗\n"
        f"       💸 ПЕРЕВОД\n"
        f"╚═══════════════════════╝\n\n"
        f"✅ Перевод выполнен успешно!\n\n"
        f"┏━━━━ ДЕТАЛИ ━━━━┓\n"
        f"│\n"
        f"│ 💰 Сумма: {amount:,} ₽\n"
        f"│ 👤 Кому: {recipient.first_name}\n"
        f"│ 💬 Комментарий: {comment}\n"
        f"│\n"
        f"│ 📊 Твой баланс: {sender.balance:,} ₽\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛",
        keyboard=kb
    )

# --- РЕПУТАЦИЯ ---
@labeler.message(regex=r"^\+реп\s+(.*)$")
async def plus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 100
    
    if user_db.balance < cost: return await message.answer(f"❌ Нужно {cost:,} чилликов для отправки!", keyboard=kb)
    if not target_id: return await message.answer("❌ Укажи кому (@user или ссылку)", keyboard=kb)
    
    if target_id == user_db.vk_id:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "       🤡 САМОЛЮБ\n"
            "╚═══════════════════════╝\n\n"
            "😂 Самому себе репу не ставят!\n\n"
            "Это же нарциссизм в чистом виде.\n"
            "Попроси друзей, если так хочется.\n\n"
            "💡 Репутацию нельзя изменить себе!",
            keyboard=kb
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        if not target: return await message.answer("❌ Игрок не найден в базе!", keyboard=kb)
        sender.balance -= cost
        target.karma += 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"       👍 РЕСПЕКТ\n"
        f"╚═══════════════════════╝\n\n"
        f"✨ Репутация отправлена!\n\n"
        f"┏━━━━ ОПЕРАЦИЯ ━━━━┓\n"
        f"│\n"
        f"│ 👤 Кому: {target.first_name}\n"
        f"│ ⭐ Карма: +1\n"
        f"│ 💸 Стоимость: {cost:,} ₽\n"
        f"│\n"
        f"│ 📊 Твой баланс: {sender.balance:,} ₽\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"💡 Высокая карма увеличивает бонусы!",
        keyboard=kb
    )

@labeler.message(regex=r"^\-реп\s+(.*)$")
async def minus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 500
    
    if user_db.balance < cost: return await message.answer(f"❌ Нужно {cost:,} чилликов для отправки!", keyboard=kb)
    if not target_id: return await message.answer("❌ Укажи кого (@user или ссылку)", keyboard=kb)

    if target_id == user_db.vk_id:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "       😰 САМОБИЧЕВАНИЕ\n"
            "╚═══════════════════════╝\n\n"
            "🚨 Себе репу не ставят!\n\n"
            "Если есть проблемы — лучше\n"
            "обратись к психологу, а не\n"
            "понижай себе карму.\n\n"
            "💊 Береги ментальное здоровье!",
            keyboard=kb
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        if not target: return await message.answer("❌ Игрок не найден в базе!", keyboard=kb)
        sender.balance -= cost
        target.karma -= 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"       👎 ДИЗЛАЙК\n"
        f"╚═══════════════════════╝\n\n"
        f"💢 Дизлайк отправлен!\n\n"
        f"┏━━━━ ОПЕРАЦИЯ ━━━━┓\n"
        f"│\n"
        f"│ 👤 Кому: {target.first_name}\n"
        f"│ ⭐ Карма: -1\n"
        f"│ 💸 Стоимость: {cost:,} ₽\n"
        f"│\n"
        f"│ 📊 Твой баланс: {sender.balance:,} ₽\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"⚠️ Низкая карма наказывает игрока!",
        keyboard=kb
    )

# --- ЧЕКИ ---
@labeler.message(regex=r"^(?i)Чек\s+(\d+)(?:\s+(\d+))?(?:\s+(р))?$")
async def create_cheque(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    amount = int(match[0])
    activations = int(match[1]) if match[1] else 1
    is_random = bool(match[2])
    
    if user_db.balance < amount: return await message.answer("❌ Недостаточно средств!", keyboard=kb)
    code = generate_cheque_code()
    
    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        sender.balance -= amount
        await sender.save()
        await Cheque.create(code=code, creator_id=user_db.vk_id, total_amount=amount, amount_left=amount, activations_limit=activations, mode="random" if is_random else "fix")

    await auto_update_card(message.ctx_api, sender)
    inline_kb = Keyboard(inline=True).add(Text("🎁 Забрать", payload={"cmd": "claim", "code": code}), color=KeyboardButtonColor.POSITIVE).get_json()
    
    mode_text = "Случайные суммы" if is_random else "Равные доли"
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"       🎟 ЧЕК СОЗДАН\n"
        f"╚═══════════════════════╝\n\n"
        f"✅ Подарочный чек готов!\n\n"
        f"┏━━━━ ПАРАМЕТРЫ ━━━━┓\n"
        f"│\n"
        f"│ 🎫 Код: {code}\n"
        f"│ 💰 Сумма: {amount:,} ₽\n"
        f"│ 👥 Активаций: {activations}\n"
        f"│ 🎲 Режим: {mode_text}\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"📢 Поделись этим сообщением,\n"
        f"   чтобы другие могли забрать!",
        keyboard=inline_kb
    )

@labeler.message(payload_map={"cmd": "claim"})
async def claim_cheque(message: Message):
    user_db = await get_user(message)
    code = message.get_payload_json()["code"]
    async with in_transaction():
        cheque = await Cheque.filter(code=code).select_for_update().first()
        if not cheque or cheque.activations_current >= cheque.activations_limit: 
            return await message.answer("❌ Чек пустой или закончился!", ephemeral=True)
        if user_db.vk_id in cheque.users_activated: 
            return await message.answer("❌ Ты уже забирал этот чек!", ephemeral=True)
        
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
        f"╔═══════════════════════╗\n"
        f"       🎉 ЧЕК ЗАБРАН\n"
        f"╚═══════════════════════╝\n\n"
        f"✨ Поздравляем!\n\n"
        f"┏━━━━ ПОЛУЧЕНО ━━━━┓\n"
        f"│\n"
        f"│ 💰 +{prize:,} чилликов\n"
        f"│ 📊 Баланс: {user_db.balance:,} ₽\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛",
        keyboard=await get_smart_keyboard(user_db, "main")
    )

@labeler.message(regex=r"^(?i)Промо\s+(.*)$")
async def activate_promo(message: Message, match):
    user_db = await get_user(message)
    code = match[0].strip()
    promo = await Promo.get_or_none(code=code)
    kb = await get_smart_keyboard(user_db, "main")

    if not promo: return await message.answer("❌ Промокод не найден!", keyboard=kb)
    if promo.current_activations >= promo.max_activations: return await message.answer("❌ Промокод исчерпан!", keyboard=kb)
    if user_db.vk_id in promo.users_activated: return await message.answer("❌ Ты уже использовал этот промокод!", keyboard=kb)
    
    async with in_transaction():
        p = await Promo.filter(code=code).select_for_update().first()
        p.current_activations += 1
        p.users_activated = list(p.users_activated) + [user_db.vk_id]
        await p.save()
        user_db.balance += p.amount
        await user_db.save()

    await auto_update_card(message.ctx_api, user_db)
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"       🎫 ПРОМОКОД\n"
        f"╚═══════════════════════╝\n\n"
        f"✅ Промокод активирован!\n\n"
        f"┏━━━━ НАГРАДА ━━━━┓\n"
        f"│\n"
        f"│ 🎁 Код: {code}\n"
        f"│ 💰 +{p.amount:,} чилликов\n"
        f"│ 📊 Баланс: {user_db.balance:,} ₽\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"🎉 Следи за новостями, чтобы не\n"
        f"   пропустить следующие промокоды!",
        keyboard=kb
    )

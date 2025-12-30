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

# ═══════════════════════════════════════════════════════
# 🎨 СТИЛЬНЫЕ РАМКИ И ВИЗУАЛЬНЫЕ ЭЛЕМЕНТЫ
# ═══════════════════════════════════════════════════════

def create_header(title: str, icon: str = "✦") -> str:
    """Создает красивый заголовок"""
    line = "─" * 20
    return f"╭{line}╮\n│ {icon} {title.center(16)} {icon} │\n╰{line}╯"

def create_section(title: str, content: str) -> str:
    """Создает секцию с контентом"""
    return f"\n▸ {title}\n{content}\n"

def create_stat_line(label: str, value: str, icon: str = "●") -> str:
    """Создает строку статистики"""
    return f"  {icon} {label}: {value}"

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

casino_mutes = {}

def is_muted(user_id: int) -> tuple[bool, int]:
    """Проверяет мут в казино"""
    if user_id not in casino_mutes:
        return False, 0
    until = casino_mutes[user_id]
    now = datetime.now(timezone.utc)
    if now >= until:
        del casino_mutes[user_id]
        return False, 0
    minutes_left = int((until - now).total_seconds() / 60)
    return True, minutes_left

# ═══════════════════════════════════════════════════════
# 📚 КОМАНДА: ПОМОЩЬ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:📚\s*)?(?:Помощь|Help|Команды)$")
async def help_handler(message: Message):
    user_db = await get_user(message)
    
    header = create_header("НАВИГАЦИЯ", "📚")
    
    sections = []
    
    # Личные команды
    personal = (
        "  💼 Профиль — твоя карточка игрока\n"
        "  💰 Баланс — счет и зарплата\n"
        "  🎁 Бонус — ежедневная награда\n"
        "  🏆 Топ — рейтинг игроков\n"
    )
    sections.append(create_section("ЛИЧНОЕ", personal))
    
    # Развлечения
    entertainment = (
        "  🎰 Казино [сумма] — испытай удачу\n"
        "     ↳ Шанс х2: 5%\n"
        "     ↳ При балансе <200: мут 1ч\n"
    )
    sections.append(create_section("РАЗВЛЕЧЕНИЯ", entertainment))
    
    # Действия
    actions = (
        "  💸 Перевод @user [сумма] — отправить деньги\n"
        "  🎫 Чек [сумма] [кол-во] — создать чек\n"
        "     ↳ +р в конце = рандом сумма\n"
        "  👍 +реп @user — повысить карму (100₽)\n"
        "  👎 -реп @user — понизить карму (500₽)\n"
        "  🎟️ Промо [код] — активировать промокод\n"
    )
    sections.append(create_section("ДЕЙСТВИЯ", actions))
    
    # Магазин
    shop = (
        "  🛒 Магазин — открыть каталог\n"
        "  🛍️ Хочу [товар] — заказать предмет\n"
        "     ↳ Админ оценит и пришлет цену\n"
    )
    sections.append(create_section("МАГАЗИН", shop))
    
    # Инвентарь
    inventory = (
        "  🎒 Инвентарь — твои предметы\n"
        "  🎁 Подарки — открыть кейсы\n"
        "  🎭 Персонажи — управление персонажами\n"
    )
    sections.append(create_section("КОЛЛЕКЦИЯ", inventory))
    
    text = header + "\n" + "".join(sections)
    
    # Админский раздел
    if message.from_id in ADMIN_IDS or user_db.is_admin:
        admin_section = (
            "\n" + create_header("АДМИНИСТРИРОВАНИЕ", "⚙️") + "\n\n"
            "▸ УПРАВЛЕНИЕ ИГРОКАМИ\n"
            "  • Начислить @user [сумма]\n"
            "  • Списать @user [сумма]\n"
            "  • Попущенный @user — забанить\n"
            "  • Разбан @user — разбанить\n\n"
            "▸ СИСТЕМА\n"
            "  • Рассылка [текст] — всем игрокам\n"
            "  • Промокод [код] [сумма] [активаций]\n"
            "  • !Принудительная зарплата\n\n"
            "▸ МАГАЗИН\n"
            "  • Стоимость: [цена] — ответ на заявку\n\n"
            "▸ ИВЕНТЫ\n"
            "  • !Ивенты — список событий\n"
            "  • !Ивент [имя] [вкл/выкл]\n\n"
            "▸ ПРЕДМЕТЫ\n"
            "  • !Создать [имя] [ранг] [тип]\n"
            "  • !Выдать @user — дать кейс\n\n"
            "▸ КАРТОЧКИ\n"
            "  • Связать photo-123_456 @user\n"
            "  • !СетФото [команда] + фото\n\n"
            "▸ РАЗНОЕ\n"
            "  • !id — узнать ID чата\n"
        )
        text += admin_section

    img = await get_image_for_command("help")
    kb = await get_smart_keyboard(user_db, "help")
    await message.answer(text, attachment=img, keyboard=kb)

# ═══════════════════════════════════════════════════════
# 👤 КОМАНДА: ПРОФИЛЬ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:👤\s*)?(?:Профиль|Стат\.?|Инфо|Я|Прф)$")
async def profile_handler(message: Message):
    user_db = await get_user(message)
    
    header = create_header("ПРОФИЛЬ", "👤")
    
    # Определяем эмодзи для кармы
    karma_icon = "😇" if user_db.karma > 0 else "😈" if user_db.karma < 0 else "😐"
    
    stats = (
        f"\n{create_stat_line('ID', str(user_db.vk_id), '🆔')}\n"
        f"{create_stat_line('Имя', user_db.first_name, '📝')}\n"
        f"{create_stat_line('Ранг', user_db.get_rank(), '📊')}\n"
        f"{create_stat_line('Баланс', f'{user_db.balance:,} чилликов', '💰')}\n"
        f"{create_stat_line('Карма', f'{user_db.karma} {karma_icon}', '🎭')}\n"
    )
    
    # Дата регистрации
    reg_date = user_db.created_at.strftime("%d.%m.%Y")
    stats += f"{create_stat_line('С нами с', reg_date, '📅')}\n"
    
    text = header + stats
    
    attachment = None
    if user_db.card_photo_id:
        attachment = f"photo{user_db.card_photo_id}"
    else:
        attachment = await get_image_for_command("profile")
        
    kb = await get_smart_keyboard(user_db, "profile")
    await message.answer(text, attachment=attachment, keyboard=kb)

# ═══════════════════════════════════════════════════════
# 💰 КОМАНДА: БАЛАНС
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:💰\s*)?(?:Баланс|Бал|Money)$")
async def balance_handler(message: Message):
    user_db = await get_user(message)
    
    header = create_header("ФИНАНСЫ", "💰")
    
    # Форматирование с разделителями
    balance_formatted = f"{user_db.balance:,}".replace(",", " ")
    salary_formatted = f"{user_db.rp_pending_balance:,}".replace(",", " ")
    
    stats = (
        f"\n{create_stat_line('На руках', f'{balance_formatted} ₽', '💵')}\n"
        f"{create_stat_line('Зарплата', f'{salary_formatted} ₽', '💳')}\n"
        f"  ↳ Выплата в конце месяца\n"
    )
    
    # Прогресс до следующего ранга
    next_milestone = None
    milestones = [1000, 5000, 20000, 50000, 100000, 500000, 1000000]
    for m in milestones:
        if user_db.balance < m:
            next_milestone = m
            break
    
    if next_milestone:
        remaining = next_milestone - user_db.balance
        progress = int((user_db.balance / next_milestone) * 10)
        bar = "▰" * progress + "▱" * (10 - progress)
        stats += f"\n▸ ПРОГРЕСС ДО РАНГА\n  {bar}\n  ↳ Осталось: {remaining:,} ₽\n"
    
    text = header + stats
    
    img = await get_image_for_command("balance")
    kb = await get_smart_keyboard(user_db, "main")
    await message.answer(text, attachment=img, keyboard=kb)

# ═══════════════════════════════════════════════════════
# 🎁 КОМАНДА: БОНУС
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🎁\s*)?(?:Бонус|Ежедневк.?)$")
async def bonus_handler(message: Message):
    user_db = await get_user(message)
    now = datetime.now(timezone.utc)
    
    if user_db.last_bonus:
        diff = now - user_db.last_bonus
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            hours = int(remaining.total_seconds() // 3600)
            minutes = int((remaining.total_seconds() % 3600) // 60)
            
            header = create_header("БОНУС", "⏳")
            text = (
                f"{header}\n\n"
                f"  ⏰ Следующий бонус через:\n"
                f"     ↳ {hours} ч {minutes} мин\n\n"
                f"  💡 Совет: бонус зависит от кармы!\n"
                f"     Твоя карма: {user_db.karma} {'😇' if user_db.karma > 0 else '😈'}\n"
            )
            return await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

    # Расчет бонуса с бонусом от кармы
    base_amount = random.randint(50, 150)
    karma_bonus = abs(user_db.karma) * 2
    amount = base_amount + karma_bonus
    
    user_db.balance += amount
    user_db.last_bonus = now
    await user_db.save()
    await TransactionLog.create(user=user_db, amount=amount, description="Бонус")
    
    # Обновляем карту
    await auto_update_card(message.ctx_api, user_db)
    
    header = create_header("БОНУС ПОЛУЧЕН", "🎁")
    
    breakdown = ""
    if karma_bonus > 0:
        breakdown = f"  ↳ Базовая: {base_amount} ₽\n  ↳ Бонус кармы: +{karma_bonus} ₽\n"
    
    text = (
        f"{header}\n\n"
        f"  💰 Получено: +{amount} чилликов\n"
        f"{breakdown}\n"
        f"  📊 Новый баланс: {user_db.balance:,} ₽\n\n"
        f"  🔄 Возвращайся завтра!\n"
    )
    
    kb = await get_smart_keyboard(user_db, "main")
    await message.answer(text, keyboard=kb)

# ═══════════════════════════════════════════════════════
# 🛒 КОМАНДА: МАГАЗИН
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🛒\s*)?(?:Магазин|Shop|Купить)(?:\s.*)?$")
async def shop_info(message: Message):
    user_db = await get_user(message)
    
    header = create_header("МАГАЗИН", "🛒")
    
    text = (
        f"{header}\n\n"
        f"▸ КАК ЗАКАЗАТЬ\n"
        f"  1️⃣ Напиши: Хочу [товар]\n"
        f"  2️⃣ Админ оценит предмет\n"
        f"  3️⃣ Тебе придет уведомление с ценой\n"
        f"  4️⃣ Подтверди покупку\n\n"
        f"▸ ПРИМЕРЫ\n"
        f"  • Хочу золотой меч\n"
        f"  • Хочу способность телепорта\n"
        f"  • Хочу питомца-дракона\n\n"
        f"  💡 Цена зависит от редкости!\n"
    )
    
    img = await get_image_for_command("shop")
    await message.answer(text, attachment=img, keyboard=await get_smart_keyboard(user_db, "main"))

# ═══════════════════════════════════════════════════════
# 🏆 КОМАНДА: ТОП
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🏆\s*)?(?:Топ|Рейтинг|Богачи)(?:\s.*)?$")
async def top_users(message: Message):
    user_db = await get_user(message)
    users = await User.filter(is_banned=False).order_by("-balance").limit(10)
    
    header = create_header("РЕЙТИНГ", "🏆")
    
    text = header + "\n\n"
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    for i, u in enumerate(users, 1):
        medal = medals.get(i, f" {i}.")
        balance_fmt = f"{u.balance:,}".replace(",", " ")
        
        # Подсветка текущего пользователя
        highlight = " ◄" if u.vk_id == user_db.vk_id else ""
        
        text += f"{medal} {u.first_name} — {balance_fmt} ₽{highlight}\n"
    
    text += "\n💡 Зарабатывай и поднимайся в топе!"
    
    await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

# ═══════════════════════════════════════════════════════
# 🎰 КОМАНДА: КАЗИНО
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🎰\s*)?(?:Казино|Casino)(?:\s+(\d+))?$")
async def casino(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    
    # Проверка мута
    muted, minutes = is_muted(user_db.vk_id)
    if muted:
        header = create_header("МУТ", "🔇")
        text = (
            f"{header}\n\n"
            f"  ⏰ Ты в муте на {minutes} мин\n"
            f"  ↳ Причина: баланс упал ниже 200₽\n\n"
            f"  💡 Получи бонус или заработай в РП\n"
        )
        return await message.answer(text, keyboard=kb)
    
    if not match[0]:
        header = create_header("КАЗИНО", "🎰")
        text = (
            f"{header}\n\n"
            f"▸ ПРАВИЛА\n"
            f"  • Шанс выигрыша: 5%\n"
            f"  • Выигрыш: х2 к ставке\n"
            f"  • Проигрыш: -50% от ставки\n\n"
            f"▸ НАКАЗАНИЕ\n"
            f"  • Если баланс < 200₽\n"
            f"  • Мут на 1 час\n\n"
            f"  Используй: Казино [сумма]\n"
        )
        return await message.answer(text, keyboard=kb)
    
    bet = int(match[0])
    
    if bet <= 0:
        return await message.answer("❌ Ставка должна быть больше 0", keyboard=kb)
    if user_db.balance < bet:
        return await message.answer("❌ Недостаточно средств", keyboard=kb)
    
    # Анимация
    animation_msg = await message.answer("🎰 Рулетка вращается...")
    slots = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🔥"]
    
    for i in range(4):
        await asyncio.sleep(0.4)
        visual = f"🎰 [ {random.choice(slots)} | {random.choice(slots)} | {random.choice(slots)} ]"
        try:
            await message.ctx_api.messages.edit(
                peer_id=message.peer_id,
                message=visual,
                conversation_message_id=animation_msg.conversation_message_id
            )
        except:
            pass
    
    # Результат
    win = random.random() < 0.05
    
    if win:
        prize = bet * 2
        user_db.balance += prize
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=prize, description="Казино Win")
        await auto_update_card(message.ctx_api, user_db)
        
        header = create_header("ДЖЕКПОТ", "🎉")
        res = (
            f"{header}\n\n"
            f"🎰 [ 7️⃣ | 7️⃣ | 7️⃣ ]\n\n"
            f"  💰 Выигрыш: +{prize:,} ₽\n"
            f"  📊 Баланс: {user_db.balance:,} ₽\n\n"
            f"  🎊 Поздравляем!\n"
        )
    else:
        loss = bet // 2
        user_db.balance -= loss
        
        mute_text = ""
        if user_db.balance < 200:
            casino_mutes[user_db.vk_id] = datetime.now(timezone.utc) + timedelta(hours=1)
            mute_text = "\n\n  🔇 МУТ НА 1 ЧАС!\n  ↳ Баланс упал ниже 200₽"
        
        await user_db.save()
        await TransactionLog.create(user=user_db, amount=-loss, description="Казино Loss")
        await auto_update_card(message.ctx_api, user_db)
        
        header = create_header("ПРОИГРЫШ", "💔")
        res = (
            f"{header}\n\n"
            f"🎰 [ 🍒 | 🍋 | 🔥 ]\n\n"
            f"  💸 Потеряно: -{loss:,} ₽\n"
            f"  📊 Баланс: {user_db.balance:,} ₽"
            f"{mute_text}\n"
        )
    
    try:
        await message.ctx_api.messages.edit(
            peer_id=message.peer_id,
            message=res,
            conversation_message_id=animation_msg.conversation_message_id,
            keyboard=kb
        )
    except:
        await message.answer(res, keyboard=kb)

# ═══════════════════════════════════════════════════════
# 💸 КОМАНДА: ПЕРЕВОД
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:💸\s*)?(?:Перевод|Скинуть|Отправить)\s+(.*?)\s+(\d+)(?:\s+(.*))?$")
async def transfer(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    
    target_raw, amount, comment = match[0], int(match[1]), match[2] or "Без комментария"
    target_id = get_id_from_mention(target_raw)
    
    if not target_id:
        return await message.answer("❌ Укажи получателя (@user или ссылку)", keyboard=kb)
    
    if target_id == user_db.vk_id:
        header = create_header("ОШИБКА", "🤡")
        text = (
            f"{header}\n\n"
            f"  Нельзя переводить самому себе!\n"
            f"  Это же абсурд 😄\n"
        )
        return await message.answer(text, keyboard=kb)
    
    if amount <= 0:
        return await message.answer("❌ Сумма должна быть больше 0", keyboard=kb)
    
    if user_db.balance < amount:
        return await message.answer(f"❌ Недостаточно средств (есть {user_db.balance:,} ₽)", keyboard=kb)

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        recipient = await User.get_or_none(vk_id=target_id)
        
        if not recipient:
            return await message.answer("❌ Пользователь не найден в системе", keyboard=kb)
        
        if sender.balance < amount:
            return await message.answer("❌ Недостаточно средств", keyboard=kb)

        sender.balance -= amount
        recipient.balance += amount
        await sender.save()
        await recipient.save()
        
        await TransactionLog.create(user=sender, amount=-amount, description=f"Перевод → {recipient.first_name}")
        await TransactionLog.create(user=recipient, amount=amount, description=f"Перевод ← {sender.first_name}")

    await auto_update_card(message.ctx_api, sender)
    await auto_update_card(message.ctx_api, recipient)

    header = create_header("ПЕРЕВОД", "✅")
    text = (
        f"{header}\n\n"
        f"  💸 Сумма: {amount:,} ₽\n"
        f"  👤 Получатель: {recipient.first_name}\n"
        f"  💬 \"{comment}\"\n\n"
        f"  📊 Твой баланс: {sender.balance:,} ₽\n"
    )
    
    # Уведомление получателю
    try:
        await message.ctx_api.messages.send(
            peer_id=recipient.vk_id,
            message=(
                f"{create_header('ПОЛУЧЕН ПЕРЕВОД', '💰')}\n\n"
                f"  👤 От: {sender.first_name}\n"
                f"  💵 Сумма: {amount:,} ₽\n"
                f"  💬 \"{comment}\"\n\n"
                f"  📊 Твой баланс: {recipient.balance:,} ₽\n"
            ),
            random_id=0
        )
    except:
        pass

    await message.answer(text, keyboard=kb)

# ═══════════════════════════════════════════════════════
# 👍 КОМАНДА: +РЕП
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?:👍\s*)?[+＋]реп\s+(.*)$")
async def plus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 100
    
    if user_db.balance < cost:
        return await message.answer(f"❌ Нужно {cost:,} чилликов", keyboard=kb)
    
    if not target_id:
        return await message.answer("❌ Укажи кому отправить репутацию", keyboard=kb)
    
    if target_id == user_db.vk_id:
        header = create_header("САМОЛЮБИЕ", "🤡")
        text = (
            f"{header}\n\n"
            f"  Сам себе лайкаешь?\n"
            f"  Мамкин нарцисс, иди потрогай траву.\n\n"
            f"  ⛔ Репутация не изменена.\n"
        )
        return await message.answer(text, keyboard=kb)

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        
        if not target:
            return await message.answer("❌ Пользователь не найден", keyboard=kb)
        
        sender.balance -= cost
        target.karma += 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    
    header = create_header("РЕСПЕКТ", "👍")
    text = (
        f"{header}\n\n"
        f"  🫡 Репутация отправлена!\n"
        f"  👤 Кому: {target.first_name}\n"
        f"  ✨ +1 карма\n\n"
        f"  💸 Списано: {cost:,} ₽\n"
        f"  📊 Баланс: {sender.balance:,} ₽\n"
    )
    await message.answer(text, keyboard=kb)

# ═══════════════════════════════════════════════════════
# 👎 КОМАНДА: -РЕП
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?:👎\s*)?[-−﹣]реп\s+(.*)$")
async def minus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 500
    
    if user_db.balance < cost:
        return await message.answer(f"❌ Нужно {cost:,} чилликов", keyboard=kb)
    
    if not target_id:
        return await message.answer("❌ Укажи кого дизлайкнуть", keyboard=kb)

    if target_id == user_db.vk_id:
        header = create_header("САНЧАСТЬ", "🚑")
        text = (
            f"{header}\n\n"
            f"  Сам себя дизлайкаешь?\n"
            f"  У тебя депрессия или просто\n"
            f"  внимания не хватает?\n\n"
            f"  💊 Сходи к врачу.\n"
        )
        return await message.answer(text, keyboard=kb)

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        
        if not target:
            return await message.answer("❌ Пользователь не найден", keyboard=kb)
        
        sender.balance -= cost
        target.karma -= 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    
    header = create_header("ДИЗЛАЙК", "👎")
    text = (
        f"{header}\n\n"
        f"  💦 Дизлайк отправлен!\n"
        f"  👤 Кому: {target.first_name}\n"
        f"  ☠️ -1 карма\n\n"
        f"  💸 Списано: {cost:,} ₽\n"
        f"  📊 Баланс: {sender.balance:,} ₽\n"
    )
    await message.answer(text, keyboard=kb)

# ═══════════════════════════════════════════════════════
# 🎫 КОМАНДА: ЧЕК
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🎫\s*)?Чек\s+(\d+)(?:\s+(\d+))?(?:\s+(р))?$")
async def create_cheque(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    amount = int(match[0])
    activations = int(match[1]) if match[1] else 1
    is_random = bool(match[2])
    
    if user_db.balance < amount:
        return await message.answer(f"❌ Недостаточно средств (есть {user_db.balance:,} ₽)", keyboard=kb)
    
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
    
    header = create_header("ЧЕК СОЗДАН", "🤑")
    mode_text = "случайная сумма" if is_random else "фиксированная сумма"
    
    text = (
        f"{header}\n\n"
        f"  💰 Сумма: {amount:,} ₽\n"
        f"  👥 Активаций: {activations}\n"
        f"  🎲 Режим: {mode_text}\n\n"
        f"  📊 Твой баланс: {sender.balance:,} ₽\n"
    )
    
    inline_kb = Keyboard(inline=True)
    inline_kb.add(Text("Забрать 🖐", payload={"cmd": "claim", "code": code}), color=KeyboardButtonColor.POSITIVE)
    
    await message.answer(text, keyboard=inline_kb.get_json())

# ═══════════════════════════════════════════════════════
# 🖐 КОМАНДА: ЗАБРАТЬ ЧЕК
# ═══════════════════════════════════════════════════════

@labeler.message(payload_map={"cmd": "claim"})
async def claim_cheque(message: Message):
    user_db = await get_user(message)
    code = message.get_payload_json()["code"]
    
    async with in_transaction():
        cheque = await Cheque.filter(code=code).select_for_update().first()
        
        if not cheque or cheque.activations_current >= cheque.activations_limit:
            return await message.answer("❌ Чек пустой или не существует", ephemeral=True)
        
        if user_db.vk_id in cheque.users_activated:
            return await message.answer("❌ Ты уже активировал этот чек", ephemeral=True)
        
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
    
    header = create_header("ЧЕК АКТИВИРОВАН", "✅")
    text = (
        f"{header}\n\n"
        f"  💰 Получено: +{prize:,} ₽\n"
        f"  📊 Баланс: {user_db.balance:,} ₽\n\n"
        f"  🎉 Поздравляем!\n"
    )
    
    await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

# ═══════════════════════════════════════════════════════
# 🎟️ КОМАНДА: ПРОМОКОД
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:🎟️\s*)?Промо\s+(.*)$")
async def activate_promo(message: Message, match):
    user_db = await get_user(message)
    code = match[0].strip()
    promo = await Promo.get_or_none(code=code)
    kb = await get_smart_keyboard(user_db, "main")

    if not promo:
        return await message.answer("❌ Промокод не найден", keyboard=kb)
    
    if promo.current_activations >= promo.max_activations:
        return await message.answer("❌ Промокод закончился", keyboard=kb)
    
    if user_db.vk_id in promo.users_activated:
        return await message.answer("❌ Ты уже активировал этот промокод", keyboard=kb)
    
    async with in_transaction():
        p = await Promo.filter(code=code).select_for_update().first()
        p.current_activations += 1
        p.users_activated = list(p.users_activated) + [user_db.vk_id]
        await p.save()
        
        user_db.balance += p.amount
        await user_db.save()

    await auto_update_card(message.ctx_api, user_db)
    
    header = create_header("ПРОМОКОД", "🎫")
    text = (
        f"{header}\n\n"
        f"  ✅ Промокод активирован!\n"
        f"  💰 Получено: +{p.amount:,} ₽\n"
        f"  📊 Баланс: {user_db.balance:,} ₽\n\n"
        f"  🎉 Следи за новыми промокодами!\n"
    )
    
    await message.answer(text, keyboard=kb)

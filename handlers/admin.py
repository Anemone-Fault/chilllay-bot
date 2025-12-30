from vkbottle.bot import BotLabeler, Message
from database.models import User, SystemConfig, Item, Rarity, ItemType, GiftBox, GiftType, Promo, ShopRequest, RequestStatus
from settings import ADMIN_IDS, MAIN_CHAT_ID
from utils.helpers import get_id_from_mention
from utils.card_updater import auto_update_card
import re

labeler = BotLabeler()

# ═══════════════════════════════════════════════════════
# 🎨 СТИЛЬНЫЕ РАМКИ
# ═══════════════════════════════════════════════════════

def create_header(title: str, icon: str = "✦") -> str:
    """Создает красивый заголовок"""
    line = "─" * 20
    return f"╭{line}╮\n│ {icon} {title.center(16)} {icon} │\n╰{line}╯"

# ═══════════════════════════════════════════════════════
# ⚙️ КОМАНДА: СПИСОК ИВЕНТОВ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^!(?:И|и)венты$")
async def list_events(message: Message):
    if message.from_id not in ADMIN_IDS:
        return
    
    events = await SystemConfig.filter(key__startswith="event_").all()
    
    header = create_header("ИВЕНТЫ", "⚙️")
    text = header + "\n\n"
    
    if not events:
        text += "  📭 Нет зарегистрированных ивентов\n"
    else:
        text += "▸ АКТИВНЫЕ СОБЫТИЯ\n\n"
        for e in events:
            # Превращаем "event_new_year" -> "New Year"
            name = e.key.replace("event_", "").replace("_", " ").title()
            status = "🟢 Включен" if e.value == "True" else "🔴 Выключен"
            text += f"  • {name}\n"
            text += f"     ↳ {status}\n\n"
    
    text += (
        "▸ УПРАВЛЕНИЕ\n"
        "  Команда: !Ивент [имя] [вкл/выкл]\n"
        "  Пример: !Ивент new_year вкл\n"
    )
    
    await message.answer(text)


# ═══════════════════════════════════════════════════════
# ⚙️ КОМАНДА: ПЕРЕКЛЮЧЕНИЕ ИВЕНТА
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^!(?:И|и)вент\s+(.*?)\s+(вкл|выкл)$")
async def toggle_event(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    event_name = match[0].lower().replace(" ", "_")
    state = "True" if match[1].lower() == "вкл" else "False"
    
    key = f"event_{event_name}"
    conf, created = await SystemConfig.get_or_create(key=key, defaults={"value": state})
    
    if not created:
        conf.value = state
        await conf.save()
    
    status = "✅ Включен" if state == "True" else "❌ Выключен"
    await message.answer(f"⚙️ Ивент '{event_name}': {status}")
    
    # Объявление в главный чат
    if MAIN_CHAT_ID != 0:
        display_name = event_name.replace("_", " ").title()
        
        if state == "True":
            announcement = (
                f"{create_header(display_name.upper(), '🎄')}\n\n"
                f"  ✨ Событие официально запущено!\n\n"
                f"  🎁 Получайте кейсы за:\n"
                f"     • РП-посты в чате\n"
                f"     • Лайки на записи\n\n"
                f"  🎉 В меню появилась кнопка «Подарки»\n\n"
                f"  @all Удачи!\n"
            )
        else:
            announcement = (
                f"{create_header('ИВЕНТ ЗАВЕРШЕН', '🏁')}\n\n"
                f"  📢 Событие \"{display_name}\" закончилось\n\n"
                f"  ⚠️ Выдача кейсов остановлена\n"
                f"  ✅ Инвентарь работает как прежде\n\n"
                f"  Спасибо за участие! @all\n"
            )
        
        try:
            await message.ctx_api.messages.send(
                peer_id=MAIN_CHAT_ID,
                message=announcement,
                random_id=0
            )
        except:
            pass


# ═══════════════════════════════════════════════════════
# 🖼️ КОМАНДА: УСТАНОВИТЬ ФОТО ДЛЯ КОМАНДЫ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^!(?:С|с)ет(?:Ф|ф)ото\s+(.+)$")
async def set_cmd_photo(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    cmd = match[0].lower()
    
    if not message.attachments or message.attachments[0].type != "photo":
        return await message.answer("❌ Прикрепи фото к команде")
    
    photo = message.attachments[0].photo
    photo_id = f"photo{photo.owner_id}_{photo.id}"
    
    key = f"img_{cmd}"
    conf, _ = await SystemConfig.get_or_create(key=key, defaults={"value": photo_id})
    conf.value = photo_id
    await conf.save()
    
    header = create_header("СОХРАНЕНО", "✅")
    text = (
        f"{header}\n\n"
        f"  🖼️ Команда: {cmd}\n"
        f"  📎 ID: {photo_id}\n\n"
        f"  Теперь это фото будет\n"
        f"  показываться с командой!\n"
    )
    await message.answer(text)


# ═══════════════════════════════════════════════════════
# 🎁 КОМАНДА: ВЫДАТЬ КЕЙС
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^!(?:В|в)ыдать\s+(.+?)(?:\s+(.+?))?(?:\s+(.+?))?$")
async def admin_give_box(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    user_id = get_id_from_mention(match[0])
    if not user_id:
        return await message.answer("❌ Укажи пользователя")
    
    user = await User.get_or_none(vk_id=user_id)
    if not user:
        return await message.answer("❌ Пользователь не найден")
    
    # Параметры: редкость и тип (опционально)
    rarity = Rarity.RARE
    gift_type = GiftType.ITEM
    
    if match[1]:
        try:
            rarity = Rarity(match[1])
        except:
            pass
    
    if match[2]:
        try:
            gift_type = GiftType(match[2])
        except:
            pass
    
    box = await GiftBox.create(
        user=user,
        rarity=rarity,
        gift_type=gift_type,
        quantity=1
    )
    
    header = create_header("КЕЙС ВЫДАН", "✅")
    text = (
        f"{header}\n\n"
        f"  👤 Получатель: {user.first_name}\n"
        f"  🎁 Тип: {gift_type.value}\n"
        f"  ⭐ Редкость: {rarity.value}\n"
    )
    await message.answer(text)


# ═══════════════════════════════════════════════════════
# ⚔️ КОМАНДА: СОЗДАТЬ ПРЕДМЕТ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^!(?:С|с)оздать\s+(.+?)\s+(Обычный|Редкий|Эпический|Чилловый)\s+(Предмет|Талант|Способность)$")
async def create_item_cmd(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    name, r_str, t_str = match[0], match[1], match[2]
    
    try:
        r = Rarity(r_str)
        t = ItemType(t_str)
        item = await Item.create(name=name, rarity=r, type=t)
        
        header = create_header("СОЗДАН", "✅")
        text = (
            f"{header}\n\n"
            f"  📦 Предмет: {name}\n"
            f"  🆔 ID: {item.id}\n"
            f"  ⭐ Редкость: {r_str}\n"
            f"  🎯 Тип: {t_str}\n"
        )
        await message.answer(text)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


# ═══════════════════════════════════════════════════════
# 💰 КОМАНДА: НАЧИСЛИТЬ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:Н|н)ачислить\s+(.+?)\s+(\d+)$")
async def admin_give_money(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    
    if not target_id:
        return await message.answer("❌ Укажи пользователя")
    
    user, _ = await User.get_or_create(
        vk_id=target_id,
        defaults={"first_name": "Player", "last_name": "Player"}
    )
    
    user.balance += amount
    await user.save()
    await auto_update_card(message.ctx_api, user)
    
    header = create_header("НАЧИСЛЕНО", "✅")
    text = (
        f"{header}\n\n"
        f"  👤 Игрок: {user.first_name}\n"
        f"  💰 Сумма: +{amount:,} ₽\n"
        f"  📊 Новый баланс: {user.balance:,} ₽\n"
    )
    await message.answer(text)


# ═══════════════════════════════════════════════════════
# 💸 КОМАНДА: СПИСАТЬ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:С|с)писать\s+(.+?)\s+(\d+)$")
async def admin_remove(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    
    if not target_id:
        return await message.answer("❌ Укажи пользователя")
    
    user = await User.get_or_none(vk_id=target_id)
    if not user:
        return await message.answer("❌ Пользователь не найден в базе")
    
    user.balance -= amount
    await user.save()
    await auto_update_card(message.ctx_api, user)
    
    header = create_header("СПИСАНО", "✅")
    text = (
        f"{header}\n\n"
        f"  👤 Игрок: {user.first_name}\n"
        f"  💸 Сумма: -{amount:,} ₽\n"
        f"  📊 Новый баланс: {user.balance:,} ₽\n"
    )
    await message.answer(text)


# ═══════════════════════════════════════════════════════
# 🔨 КОМАНДА: БАН
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:П|п)опущенный\s+(.+)$")
async def admin_ban(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    user = await User.get_or_none(vk_id=target_id)
    
    if user:
        user.is_banned = True
        await user.save()
        
        header = create_header("ЗАБАНЕН", "⛔")
        text = (
            f"{header}\n\n"
            f"  👤 Игрок: {user.first_name}\n"
            f"  🆔 ID: {user.vk_id}\n\n"
            f"  Доступ к боту заблокирован\n"
        )
        await message.answer(text)


# ═══════════════════════════════════════════════════════
# ✅ КОМАНДА: РАЗБАН
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:Р|р)азбан\s+(.+)$")
async def admin_unban(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    user = await User.get_or_none(vk_id=target_id)
    
    if user:
        user.is_banned = False
        await user.save()
        
        header = create_header("РАЗБАНЕН", "✅")
        text = (
            f"{header}\n\n"
            f"  👤 Игрок: {user.first_name}\n"
            f"  🆔 ID: {user.vk_id}\n\n"
            f"  Доступ восстановлен\n"
        )
        await message.answer(text)


# ═══════════════════════════════════════════════════════
# 📢 КОМАНДА: РАССЫЛКА
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:Р|р)ассылка\s+(.+)$")
async def admin_broadcast(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    text_to_send = match[0]
    users = await User.filter(is_banned=False).all()
    
    header = create_header("РАССЫЛКА", "📢")
    progress_text = (
        f"{header}\n\n"
        f"  📤 Отправка {len(users)} пользователям...\n"
    )
    await message.answer(progress_text)
    
    success = 0
    failed = 0
    
    broadcast_msg = f"📢 ОБЪЯВЛЕНИЕ\n━━━━━━━━━━━━━━━\n\n{text_to_send}"
    
    for user in users:
        try:
            await message.ctx_api.messages.send(
                peer_id=user.vk_id,
                message=broadcast_msg,
                random_id=0
            )
            success += 1
        except:
            failed += 1
    
    result_text = (
        f"{header}\n\n"
        f"  ✅ Успешно: {success}\n"
        f"  ❌ Ошибок: {failed}\n"
    )
    await message.answer(result_text)


# ═══════════════════════════════════════════════════════
# 🔗 КОМАНДА: СВЯЗАТЬ КАРТОЧКУ
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:С|с)вязать\s+(.+)$")
async def link_card(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    full_text = match[0]
    
    # Ищем photo ID
    photo_match = re.search(r"photo(-?\d+_\d+)", full_text)
    
    if not photo_match:
        help_text = (
            "❌ Не найден ID фото\n\n"
            "▸ ПРИМЕРЫ:\n"
            "  • Связать photo-123_456 @user\n"
            "  • Связать vk.com/photo-123_456 @user\n"
        )
        return await message.answer(help_text)
    
    # Ищем пользователя
    target_id = None
    for word in full_text.split():
        uid = get_id_from_mention(word)
        if uid:
            target_id = uid
            break
    
    if not target_id:
        return await message.answer("❌ Укажи пользователя")
    
    user = await User.get_or_none(vk_id=target_id)
    if not user:
        return await message.answer("❌ Пользователь не найден")
    
    user.card_photo_id = photo_match.group(1)
    await user.save()
    
    header = create_header("СВЯЗАНО", "✅")
    text = (
        f"{header}\n\n"
        f"  👤 Игрок: {user.first_name}\n"
        f"  📎 Фото: {photo_match.group(1)}\n\n"
        f"  Обновляю карточку...\n"
    )
    await message.answer(text)
    await auto_update_card(message.ctx_api, user, message)


# ═══════════════════════════════════════════════════════
# 💵 КОМАНДА: ПРИНУДИТЕЛЬНАЯ ЗАРПЛАТА
# ═══════════════════════════════════════════════════════

@labeler.message(text="!Принудительная зарплата")
async def force_salary_cmd(message: Message):
    if message.from_id not in ADMIN_IDS:
        return
    
    conf, _ = await SystemConfig.get_or_create(key="last_salary_month", defaults={"value": ""})
    conf.value = "RESET"
    await conf.save()
    
    header = create_header("СБРОШЕНО", "✅")
    text = (
        f"{header}\n\n"
        f"  📅 Метка зарплаты сброшена\n\n"
        f"  ⏰ Зарплата будет выдана в\n"
        f"     следующем цикле (через час)\n"
        f"     или после перезагрузки бота\n"
    )
    await message.answer(text)


# ═══════════════════════════════════════════════════════
# 🎫 КОМАНДА: ПРОМОКОД
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:П|п)ромокод\s+(\w+)\s+(\d+)\s+(\d+)$")
async def create_promo(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    code, amount, max_act = match[0], int(match[1]), int(match[2])
    
    await Promo.create(
        code=code,
        amount=amount,
        max_activations=max_act
    )
    
    header = create_header("ПРОМОКОД", "🎫")
    text = (
        f"{header}\n\n"
        f"  🎟️ Код: {code}\n"
        f"  💰 Сумма: {amount:,} ₽\n"
        f"  🔢 Активаций: {max_act}\n\n"
        f"  ✅ Промокод создан!\n"
    )
    await message.answer(text)


# ═══════════════════════════════════════════════════════
# 💲 КОМАНДА: СТОИМОСТЬ (ДЛЯ ЗАЯВОК)
# ═══════════════════════════════════════════════════════

@labeler.message(regex=r"^(?i)(?:С|с)тоимость:\s+(\d+)$")
async def set_price(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    if not message.reply_message:
        return await message.answer("❌ Ответь на заявку")
    
    price = int(match[0])
    
    # Ищем ID заявки
    req_match = re.search(r"ЗАЯВКА №(\d+)", message.reply_message.text)
    user_match = re.search(r"\[id(\d+)\|", message.reply_message.text)
    
    if req_match:
        req = await ShopRequest.get_or_none(id=int(req_match.group(1)))
        if req:
            req.price = price
            req.status = RequestStatus.PRICE_SET
            await req.save()
    
    if user_match:
        target_id = int(user_match.group(1))
        try:
            user = await User.get(vk_id=target_id)
            notification = (
                f"{create_header('ОЦЕНКА ТОВАРА', '💰')}\n\n"
                f"  🛒 Твоя заявка оценена!\n"
                f"  💵 Стоимость: {price:,} ₽\n\n"
                f"  Подтверди покупку, написав админу\n"
            )
            await message.ctx_api.messages.send(
                peer_id=target_id,
                message=notification,
                random_id=0
            )
        except:
            pass
    
    await message.answer(f"✅ Цена установлена: {price:,} ₽")


# ═══════════════════════════════════════════════════════
# 🆔 КОМАНДА: УЗНАТЬ ID ЧАТА
# ═══════════════════════════════════════════════════════

@labeler.message(text="!id")
async def get_chat_id(message: Message):
    header = create_header("ID ЧАТА", "🆔")
    text = (
        f"{header}\n\n"
        f"  📍 ID этого чата: {message.peer_id}\n\n"
        f"  Используй это значение\n"
        f"  в настройках бота\n"
    )
    await message.answer(text)

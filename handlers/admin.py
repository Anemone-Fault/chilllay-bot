from vkbottle.bot import BotLabeler, Message
from database.models import User, SystemConfig, Item, Rarity, ItemType, GiftBox, GiftType, Promo, ShopRequest, RequestStatus
from settings import ADMIN_IDS, MAIN_CHAT_ID
from utils.helpers import get_id_from_mention
from utils.card_updater import auto_update_card
import re

labeler = BotLabeler()


# ====================
# ⚙️ СПИСОК ИВЕНТОВ
# ====================

@labeler.message(regex=r"^!Ивенты$")
async def list_events(message: Message):
    if message.from_id not in ADMIN_IDS:
        return
    
    events = await SystemConfig.filter(key__startswith="event_").all()
    
    text = (
        "╔═════════════════════╗\n"
        "║  ⚙️ СПИСОК ИВЕНТОВ   ║\n"
        "╚═════════════════════╝\n\n"
    )
    
    if not events:
        text += "❌ Нет зарегистрированных\n   событий."
    else:
        for e in events:
            name = e.key.replace("event_", "").replace("_", " ").title()
            status = "🟢 Активен" if e.value == "True" else "🔴 Выключен"
            text += f"• {name}\n  └─ {status}\n\n"
    
    text += (
        "{'═' * 25}\n\n"
        "Управление:\n"
        "!Ивент [имя] [вкл/выкл]"
    )
    
    await message.answer(text)


# ====================
# ⚙️ УПРАВЛЕНИЕ ИВЕНТОМ
# ====================

@labeler.message(regex=r"^!Ивент\s+(.*?)\s+(вкл|выкл)$")
async def toggle_event(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    event_name = match[0]
    state = "True" if match[1].lower() == "вкл" else "False"
    
    key = f"event_{event_name.lower().replace(' ', '_')}"
    conf, _ = await SystemConfig.get_or_create(key=key)
    conf.value = state
    await conf.save()
    
    status_emoji = "🟢" if state == "True" else "🔴"
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ⚙️ ИВЕНТ ОБНОВЛЕН   ║\n"
        f"╚═════════════════════╝\n\n"
        f"🎯 Событие: {event_name}\n"
        f"{status_emoji} Статус: {match[1].upper()}\n\n"
        f"{'═' * 25}\n\n"
        f"✅ Настройка сохранена!"
    )
    
    # Анонс в чат
    if MAIN_CHAT_ID != 0:
        if state == "True":
            announcement = (
                f"╔═════════════════════╗\n"
                f"║  🎉 ИВЕНТ ЗАПУЩЕН!   ║\n"
                f"╚═════════════════════╝\n\n"
                f"🎯 Событие: {event_name.upper()}\n\n"
                f"✨ Официально стартовал!\n"
                f"Получайте кейсы за РП\n"
                f"и лайки постов!\n\n"
                f"🎁 В меню появилась\n"
                f"   кнопка «Подарки».\n\n"
                f"{'═' * 25}\n\n"
                f"Поехали, нищеброды! 🔥\n"
                f"@all"
            )
        else:
            announcement = (
                f"╔═════════════════════╗\n"
                f"║  🏁 ИВЕНТ ЗАВЕРШЕН   ║\n"
                f"╚═════════════════════╝\n\n"
                f"🎯 Событие: {event_name.upper()}\n\n"
                f"⏰ Выдача кейсов остановлена.\n\n"
                f"📦 Инвентарь и открытие\n"
                f"   кейсов работают.\n\n"
                f"{'═' * 25}\n\n"
                f"Спасибо за участие! 🎊\n"
                f"@all"
            )
        
        try:
            await message.ctx_api.messages.send(
                peer_id=MAIN_CHAT_ID,
                message=announcement,
                random_id=0
            )
        except:
            pass


# ====================
# 🖼 УСТАНОВКА ФОТО ДЛЯ КОМАНДЫ (ИСПРАВЛЕНО!)
# ====================

@labeler.message(regex=r"^!СетФото\s+(.*?)$")
async def set_cmd_photo(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    cmd = match[0].lower().strip()
    
    # Проверяем наличие фото
    if not message.attachments or len(message.attachments) == 0:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ ОШИБКА!          ║\n"
            "╚═════════════════════╝\n\n"
            "🖼 Прикрепи фото к команде!\n\n"
            "Использование:\n"
            "!СетФото помощь\n"
            "[прикрепить фото]\n\n"
            "Доступные команды:\n"
            "• help (помощь)\n"
            "• profile (профиль)\n"
            "• balance (баланс)\n"
            "• shop (магазин)"
        )
    
    # Ищем фото среди вложений
    photo = None
    for attachment in message.attachments:
        if attachment.type.value == "photo":
            photo = attachment.photo
            break
    
    if not photo:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ НЕТ ФОТО!        ║\n"
            "╚═════════════════════╝\n\n"
            "🖼 Фотография не найдена\n"
            "   во вложениях!\n\n"
            "Прикрепи картинку\n"
            "к сообщению!"
        )
    
    # Формируем ID фото
    photo_id = f"photo{photo.owner_id}_{photo.id}"
    
    # Сохраняем в базу
    key = f"img_{cmd}"
    conf, created = await SystemConfig.get_or_create(key=key)
    conf.value = photo_id
    await conf.save()
    
    action_text = "создана" if created else "обновлена"
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✅ ФОТО СОХРАНЕНО!  ║\n"
        f"╚═════════════════════╝\n\n"
        f"🎯 Команда: {cmd}\n"
        f"🖼 ID фото: {photo_id}\n"
        f"⚙️ Настройка {action_text}\n\n"
        f"{'═' * 25}\n\n"
        f"Теперь команда «{cmd}»\n"
        f"будет отправляться\n"
        f"с этой картинкой! 🎨"
    )


# ====================
# 🎁 ВЫДАТЬ КЕЙС ИГРОКУ
# ====================

@labeler.message(regex=r"^!Выдать\s+(.*?)(?:\s+(.*))?$")
async def admin_give_box(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    user_id = get_id_from_mention(match[0])
    if not user_id:
        return await message.answer("❌ Укажи пользователя!")
    
    user = await User.get_or_none(vk_id=user_id)
    if not user:
        return await message.answer("❌ Игрок не найден в базе!")
    
    # Создаем кейс
    box = await GiftBox.create(
        user=user,
        rarity=Rarity.RARE,
        gift_type=GiftType.ITEM,
        quantity=1
    )
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✅ КЕЙС ВЫДАН!      ║\n"
        f"╚═════════════════════╝\n\n"
        f"👤 Игрок: {user.first_name}\n"
        f"🎁 Кейс: {box.gift_type.value}\n"
        f"⭐ Редкость: {box.rarity.value}\n\n"
        f"{'═' * 25}\n\n"
        f"Подарок доставлен! 🎊"
    )


# ====================
# ⚙️ СОЗДАТЬ ПРЕДМЕТ
# ====================

@labeler.message(regex=r"^!Создать\s+(.*?)\s+(.*?)\s+(.*?)$")
async def create_item_cmd(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    name, r_str, t_str = match[0], match[1], match[2]
    
    try:
        r = Rarity(r_str)
        t = ItemType(t_str)
        item = await Item.create(name=name, rarity=r, type=t)
        
        await message.answer(
            f"╔═════════════════════╗\n"
            f"║  ✅ ПРЕДМЕТ СОЗДАН!  ║\n"
            f"╚═════════════════════╝\n\n"
            f"🆔 ID: {item.id}\n"
            f"📦 Название: {name}\n"
            f"⭐ Редкость: {r_str}\n"
            f"🔖 Тип: {t_str}\n\n"
            f"{'═' * 25}\n\n"
            f"Предмет добавлен в базу!"
        )
    except ValueError as e:
        await message.answer(
            f"╔═════════════════════╗\n"
            f"║  ❌ ОШИБКА!          ║\n"
            f"╚═════════════════════╝\n\n"
            f"Неверные параметры!\n\n"
            f"Доступные редкости:\n"
            f"• Обычный\n"
            f"• Редкий\n"
            f"• Эпический\n"
            f"• Чилловый\n\n"
            f"Доступные типы:\n"
            f"• Предмет\n"
            f"• Талант\n"
            f"• Способность\n\n"
            f"Ошибка: {e}"
        )


# ====================
# 💰 НАЧИСЛИТЬ ДЕНЬГИ
# ====================

@labeler.message(regex=r"^(?i)Начислить\s+(.*?)\s+(\d+)$")
async def admin_give_money(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    
    if not target_id:
        return await message.answer("❌ Укажи пользователя!")
    
    user, created = await User.get_or_create(
        vk_id=target_id,
        defaults={"first_name": "Player", "last_name": "Player"}
    )
    
    user.balance += amount
    await user.save()
    await auto_update_card(message.ctx_api, user)
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  💰 НАЧИСЛЕНО!       ║\n"
        f"╚═════════════════════╝\n\n"
        f"👤 Игрок: {user.first_name}\n"
        f"💵 Сумма: +{amount:,}₽\n"
        f"📊 Баланс: {user.balance:,}₽\n\n"
        f"{'═' * 25}\n\n"
        f"Деньги отправлены! 💸"
    )


# ====================
# 💸 СПИСАТЬ ДЕНЬГИ
# ====================

@labeler.message(regex=r"^(?i)Списать\s+(.*?)\s+(\d+)$")
async def admin_remove(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    
    if not target_id:
        return await message.answer("❌ Укажи пользователя!")
    
    user = await User.get_or_none(vk_id=target_id)
    if not user:
        return await message.answer("❌ Игрок не найден в базе!")
    
    user.balance -= amount
    await user.save()
    await auto_update_card(message.ctx_api, user)
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  💸 СПИСАНО!         ║\n"
        f"╚═════════════════════╝\n\n"
        f"👤 Игрок: {user.first_name}\n"
        f"💵 Сумма: -{amount:,}₽\n"
        f"📊 Баланс: {user.balance:,}₽\n\n"
        f"{'═' * 25}\n\n"
        f"Деньги конфискованы! 🚔"
    )


# ====================
# ⛔ БАН / РАЗБАН
# ====================

@labeler.message(regex=r"^(?i)Попущенный\s+(.*?)$")
async def admin_ban(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    user = await User.get_or_none(vk_id=target_id)
    
    if not user:
        return await message.answer("❌ Игрок не найден!")
    
    user.is_banned = True
    await user.save()
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ⛔ ЗАБАНЕН!         ║\n"
        f"╚═════════════════════╝\n\n"
        f"👤 Попущенный: {user.first_name}\n"
        f"🆔 ID: {user.vk_id}\n\n"
        f"{'═' * 25}\n\n"
        f"Игрок отправлен в бан! 🔨\n"
        f"Причина: Попуск 🤡"
    )


@labeler.message(regex=r"^(?i)Разбан\s+(.*?)$")
async def admin_unban(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    user = await User.get_or_none(vk_id=target_id)
    
    if not user:
        return await message.answer("❌ Игрок не найден!")
    
    user.is_banned = False
    await user.save()
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✅ РАЗБАНЕН!        ║\n"
        f"╚═════════════════════╝\n\n"
        f"👤 Освобожден: {user.first_name}\n"
        f"🆔 ID: {user.vk_id}\n\n"
        f"{'═' * 25}\n\n"
        f"Игрок вернулся в игру! 🎉\n"
        f"Надеюсь, он исправится... 🙏"
    )


# ====================
# 📢 РАССЫЛКА
# ====================

@labeler.message(regex=r"^(?i)Рассылка\s+(.*)$")
async def admin_broadcast(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    text = match[0]
    users = await User.filter(is_banned=False).all()
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  📢 РАССЫЛКА...      ║\n"
        f"╚═════════════════════╝\n\n"
        f"👥 Получателей: {len(users)}\n"
        f"📝 Сообщение: {text[:50]}...\n\n"
        f"⏳ Отправка началась..."
    )
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            await message.ctx_api.messages.send(
                peer_id=user.vk_id,
                message=f"╔═════════════════════╗\n"
                        f"║  📢 ОБЪЯВЛЕНИЕ       ║\n"
                        f"╚═════════════════════╝\n\n"
                        f"{text}",
                random_id=0
            )
            success += 1
        except:
            failed += 1
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✅ РАССЫЛКА ГОТОВА! ║\n"
        f"╚═════════════════════╝\n\n"
        f"✅ Отправлено: {success}\n"
        f"❌ Не доставлено: {failed}\n\n"
        f"{'═' * 25}\n\n"
        f"Миссия выполнена! 🎯"
    )


# ====================
# 🔗 СВЯЗАТЬ КАРТОЧКУ
# ====================

@labeler.message(regex=r"^(?i)Связать\s+(.*)$")
async def link_card(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    full_text = match[0]
    
    # Ищем ID фото
    photo_match = re.search(r"photo(-?\d+_\d+)", full_text)
    
    if not photo_match:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ НЕВЕРНЫЙ ФОРМАТ! ║\n"
            "╚═════════════════════╝\n\n"
            "🖼 ID фото не найден!\n\n"
            "Примеры:\n"
            "• Связать photo-123_456 @user\n"
            "• Связать vk.com/photo-123_456 @user\n\n"
            "Где взять ID фото?\n"
            "1. Открой фото в группе\n"
            "2. Скопируй ссылку\n"
            "3. ID будет в формате\n"
            "   photo-123456_789012"
        )
    
    # Ищем упоминание пользователя
    target_id = None
    for word in full_text.split():
        uid = get_id_from_mention(word)
        if uid:
            target_id = uid
            break
    
    if not target_id:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ НЕТ ПОЛЬЗОВАТЕЛЯ ║\n"
            "╚═════════════════════╝\n\n"
            "👤 Укажи пользователя!\n\n"
            "Пример:\n"
            "Связать photo-123_456 @user"
        )
    
    user = await User.get_or_none(vk_id=target_id)
    if not user:
        return await message.answer("❌ Игрок не найден в базе!")
    
    # Связываем
    user.card_photo_id = photo_match.group(1)
    await user.save()
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✅ КАРТОЧКА СВЯЗАНА! ║\n"
        f"╚═════════════════════╝\n\n"
        f"👤 Игрок: {user.first_name}\n"
        f"🖼 Фото: {photo_match.group(1)}\n\n"
        f"{'═' * 25}\n\n"
        f"⏳ Обновляю описание..."
    )
    
    # Обновляем карточку
    await auto_update_card(message.ctx_api, user, debug_message=message)


# ====================
# 💰 ОЦЕНКА ТОВАРА (ДЛЯ МАГАЗИНА)
# ====================

@labeler.message(regex=r"^(?i)Стоимость:\s+(\d+)$")
async def set_price(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    if not message.reply_message:
        return await message.answer(
            "╔═════════════════════╗\n"
            "║  ❌ НЕТ ОТВЕТА!      ║\n"
            "╚═════════════════════╝\n\n"
            "Используй REPLY на\n"
            "сообщение с заявкой!\n\n"
            "Как использовать:\n"
            "1. Найди заявку\n"
            "2. Ответь на неё\n"
            "3. Напиши: Стоимость: 100"
        )
    
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
    
    # Уведомляем игрока
    if user_match:
        target_id = int(user_match.group(1))
        try:
            await message.ctx_api.messages.send(
                peer_id=target_id,
                message=(
                    f"╔═════════════════════╗\n"
                    f"║  💰 ТОВАР ОЦЕНЕН!    ║\n"
                    f"╚═════════════════════╝\n\n"
                    f"🛒 Твой заказ оценили!\n\n"
                    f"💵 Цена: {price:,}₽\n\n"
                    f"{'═' * 25}\n\n"
                    f"Хочешь купить?\n"
                    f"Обратись к администрации!"
                ),
                random_id=0
            )
        except:
            pass
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  ✅ ЦЕНА УСТАНОВЛЕНА! ║\n"
        f"╚═════════════════════╝\n\n"
        f"💰 Цена: {price:,}₽\n\n"
        f"{'═' * 25}\n\n"
        f"Игрок уведомлен! 📬"
    )


# ====================
# 🎟 СОЗДАТЬ ПРОМОКОД
# ====================

@labeler.message(regex=r"^(?i)Промокод\s+(\w+)\s+(\d+)\s+(\d+)$")
async def create_promo(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    code = match[0]
    amount = int(match[1])
    max_activations = int(match[2])
    
    # Проверяем, не существует ли промокод
    existing = await Promo.get_or_none(code=code)
    if existing:
        return await message.answer(
            f"╔═════════════════════╗\n"
            f"║  ⚠️ ПРОМОКОД ЕСТЬ!   ║\n"
            f"╚═════════════════════╝\n\n"
            f"🎫 Код: {code}\n\n"
            f"Такой промокод уже\n"
            f"существует в базе!\n\n"
            f"Придумай другой код."
        )
    
    await Promo.create(
        code=code,
        amount=amount,
        max_activations=max_activations
    )
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  🎟 ПРОМОКОД СОЗДАН! ║\n"
        f"╚═════════════════════╝\n\n"
        f"🎫 Код: {code}\n"
        f"💰 Сумма: {amount:,}₽\n"
        f"👥 Лимит: {max_activations} чел.\n\n"
        f"{'═' * 25}\n\n"
        f"Промокод готов к работе! ✅\n\n"
        f"Для активации:\n"
        f"Промо {code}"
    )


# ====================
# ⚡ ПРИНУДИТЕЛЬНАЯ ЗАРПЛАТА
# ====================

@labeler.message(text="!Принудительная зарплата")
async def force_salary_cmd(message: Message):
    if message.from_id not in ADMIN_IDS:
        return
    
    conf, _ = await SystemConfig.get_or_create(key="last_salary_month")
    conf.value = "RESET"
    await conf.save()
    
    await message.answer(
        "╔═════════════════════╗\n"
        "║  ⚡ ЗАРПЛАТА СБРОШЕНА ║\n"
        "╚═════════════════════╝\n\n"
        "🔄 Метка выплаты очищена!\n\n"
        "Зарплата будет выдана\n"
        "при следующей проверке\n"
        "(через час) или при\n"
        "перезапуске бота.\n\n"
        "{'═' * 25}\n\n"
        "✅ Готово!"
    )


# ====================
# 🆔 УЗНАТЬ ID ЧАТА
# ====================

@labeler.message(text="!id")
async def get_chat_id(message: Message):
    chat_type = "ЛС" if message.peer_id == message.from_id else "Беседа"
    
    await message.answer(
        f"╔═════════════════════╗\n"
        f"║  🆔 ИНФОРМАЦИЯ       ║\n"
        f"╚═════════════════════╝\n\n"
        f"🔹 Тип: {chat_type}\n"
        f"🆔 ID чата: {message.peer_id}\n"
        f"👤 Твой ID: {message.from_id}\n\n"
        f"{'═' * 25}\n\n"
        f"Используй эти ID для\n"
        f"настройки бота! ⚙️"
    )

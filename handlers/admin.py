from vkbottle.bot import BotLabeler, Message
from database.models import User, SystemConfig, Item, Rarity, ItemType, GiftBox, GiftType, Promo, ShopRequest, RequestStatus
from settings import ADMIN_IDS, MAIN_CHAT_ID
from utils.helpers import get_id_from_mention
from utils.card_updater import auto_update_card
import re

labeler = BotLabeler()

# --- ⚙️ СПИСОК ИВЕНТОВ ---
@labeler.message(regex=r"^!Ивенты$")
async def list_events(message: Message):
    if message.from_id not in ADMIN_IDS: return
    
    events = await SystemConfig.filter(key__startswith="event_").all()
    
    text = (
        "╔═══════════════════════╗\n"
        "    ⚙️ СПИСОК СОБЫТИЙ\n"
        "╚═══════════════════════╝\n\n"
    )
    
    if not events:
        text += "📭 Нет зарегистрированных ивентов.\n\n"
        text += "💡 Создай первое событие командой:\n"
        text += "   !Ивент [название] [вкл/выкл]"
    else:
        text += "┏━━━━ АКТИВНЫЕ СОБЫТИЯ ━━━━┓\n│\n"
        for e in events:
            name = e.key.replace("event_", "").replace("_", " ").title()
            status = "🟢 Активен" if e.value == "True" else "🔴 Выключен"
            text += f"│ 🎪 {name}\n│    {status}\n│\n"
        text += "┗━━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        text += "📝 Управление:\n"
        text += "   !Ивент [название] [вкл/выкл]"
    
    await message.answer(text)

# --- ⚙️ УПРАВЛЕНИЕ ИВЕНТОМ ---
@labeler.message(regex=r"^!Ивент\s+(.*?)\s+(вкл|выкл)$")
async def toggle_event(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    
    event_name = match[0] 
    state = "True" if match[1].lower() == "вкл" else "False"
    
    key = f"event_{event_name.lower().replace(' ', '_')}"
    conf, created = await SystemConfig.get_or_create(key=key)
    conf.value = state
    await conf.save()
    
    status_emoji = "🟢" if state == "True" else "🔴"
    action = "ЗАПУЩЕНО" if state == "True" else "ОСТАНОВЛЕНО"
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    {status_emoji} СОБЫТИЕ {action}\n"
        f"╚═══════════════════════╝\n\n"
        f"📋 Название: {event_name.title()}\n"
        f"⚙️ Статус: {state}\n\n"
        f"✅ Настройки применены!"
    )
    
    # Объявление в основной чат
    if MAIN_CHAT_ID != 0:
        if state == "True":
            announcement = (
                f"╔═══════════════════════╗\n"
                f"   🎉 СОБЫТИЕ НАЧАТО!\n"
                f"╚═══════════════════════╝\n\n"
                f"🎪 {event_name.upper()}\n\n"
                f"✨ Событие официально запущено!\n\n"
                f"┏━━━━ ЧТО ДОСТУПНО? ━━━━┓\n"
                f"│\n"
                f"│ 🎁 Кейсы за РП-посты\n"
                f"│ ❤️ Кейсы за лайки\n"
                f"│ 🎒 Новое меню «Подарки»\n"
                f"│\n"
                f"┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                f"🚀 Удачи в событии!\n"
                f"@all"
            )
        else:
            announcement = (
                f"╔═══════════════════════╗\n"
                f"   🏁 СОБЫТИЕ ЗАВЕРШЕНО\n"
                f"╚═══════════════════════╝\n\n"
                f"🎪 {event_name.upper()}\n\n"
                f"📊 Итоги:\n\n"
                f"┏━━━━ ВАЖНО ━━━━┓\n"
                f"│\n"
                f"│ ❌ Выдача кейсов остановлена\n"
                f"│ ✅ Инвентарь работает\n"
                f"│ ✅ Открытие кейсов доступно\n"
                f"│\n"
                f"┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                f"🙏 Спасибо за участие!\n"
                f"@all"
            )
        try: 
            await message.ctx_api.messages.send(peer_id=MAIN_CHAT_ID, message=announcement, random_id=0)
        except: 
            pass

@labeler.message(regex=r"^!СетФото\s+(.*?)$")
async def set_cmd_photo(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    cmd = match[0].lower()
    
    if not message.attachments or message.attachments[0].type != "photo":
        return await message.answer(
            "╔═══════════════════════╗\n"
            "    ❌ ОШИБКА\n"
            "╚═══════════════════════╝\n\n"
            "📎 Прикрепи фото к команде!\n\n"
            "💡 Пример:\n"
            "   !СетФото помощь\n"
            "   [прикрепить картинку]"
        )
    
    photo = message.attachments[0].photo
    photo_id = f"photo{photo.owner_id}_{photo.id}"
    
    key = f"img_{cmd}"
    conf, _ = await SystemConfig.get_or_create(key=key)
    conf.value = photo_id
    await conf.save()
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    ✅ ФОТО УСТАНОВЛЕНО\n"
        f"╚═══════════════════════╝\n\n"
        f"🎨 Команда: {cmd}\n"
        f"📸 ID: {photo_id}\n\n"
        f"Картинка будет отображаться\n"
        f"при вызове этой команды!"
    )

@labeler.message(regex=r"^!Создать\s+(.*?)\s+(.*?)\s+(.*?)$")
async def create_item_cmd(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    name, r_str, t_str = match[0], match[1], match[2]
    
    try:
        r = Rarity(r_str)
        t = ItemType(t_str)
        item = await Item.create(name=name, rarity=r, type=t)
        
        await message.answer(
            f"╔═══════════════════════╗\n"
            f"    ✅ ПРЕДМЕТ СОЗДАН\n"
            f"╚═══════════════════════╝\n\n"
            f"┏━━━━ ПАРАМЕТРЫ ━━━━┓\n"
            f"│\n"
            f"│ 🏷 Название: {name}\n"
            f"│ 🆔 ID: {item.id}\n"
            f"│ ⭐ Редкость: {r_str}\n"
            f"│ 📦 Тип: {t_str}\n"
            f"│\n"
            f"┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"💡 Предмет добавлен в базу!"
        )
    except Exception as e:
        await message.answer(
            f"╔═══════════════════════╗\n"
            f"    ❌ ОШИБКА\n"
            f"╚═══════════════════════╝\n\n"
            f"⚠️ {str(e)}\n\n"
            f"💡 Проверь параметры:\n"
            f"   Ранг: Обычный/Редкий/Эпический\n"
            f"   Тип: Предмет/Талант/Способность"
        )

@labeler.message(regex=r"^!Выдать\s+(.*?)(?:\s+(.*))?$")
async def admin_give_box(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    user_id = get_id_from_mention(match[0])
    if not user_id: return
    
    user = await User.get(vk_id=user_id)
    box = await GiftBox.create(user=user, rarity=Rarity.RARE, gift_type=GiftType.ITEM, quantity=1)
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    🎁 КЕЙС ВЫДАН\n"
        f"╚═══════════════════════╝\n\n"
        f"👤 Получатель: {user.first_name}\n"
        f"📦 Тип: Редкий предметный\n"
        f"🆔 ID кейса: {box.id}\n\n"
        f"✅ Игрок получил уведомление!"
    )

@labeler.message(regex=r"^(?i)Начислить\s+(.*?)\s+(\d+)$")
async def admin_give_money(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    if not target_id: return
    
    user = await User.get_or_create(vk_id=target_id, defaults={"first_name": "Player", "last_name": "Player"})
    user[0].balance += amount
    await user[0].save()
    await auto_update_card(message.ctx_api, user[0])
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    ✅ НАЧИСЛЕНО\n"
        f"╚═══════════════════════╝\n\n"
        f"👤 Игрок: {user[0].first_name}\n"
        f"💰 Сумма: +{amount:,} чилликов\n"
        f"📊 Новый баланс: {user[0].balance:,} ₽\n\n"
        f"🔄 Карточка обновлена!"
    )

@labeler.message(regex=r"^(?i)Списать\s+(.*?)\s+(\d+)$")
async def admin_remove(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    if not target_id: return
    
    user = await User.get_or_none(vk_id=target_id)
    if not user: 
        return await message.answer(
            "╔═══════════════════════╗\n"
            "    ❌ ОШИБКА\n"
            "╚═══════════════════════╝\n\n"
            "👤 Игрок не найден в базе!"
        )
    
    user.balance -= amount
    await user.save()
    await auto_update_card(message.ctx_api, user)
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    ✅ СПИСАНО\n"
        f"╚═══════════════════════╝\n\n"
        f"👤 Игрок: {user.first_name}\n"
        f"💸 Сумма: -{amount:,} чилликов\n"
        f"📊 Новый баланс: {user.balance:,} ₽\n\n"
        f"🔄 Карточка обновлена!"
    )

@labeler.message(regex=r"^(?i)Попущенный\s+(.*?)$")
async def admin_ban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_id = get_id_from_mention(match[0])
    user = await User.get_or_none(vk_id=target_id)
    
    if user:
        user.is_banned = True
        await user.save()
        await message.answer(
            f"╔═══════════════════════╗\n"
            f"    ⛔ БАН ВЫДАН\n"
            f"╚═══════════════════════╝\n\n"
            f"👤 Игрок: {user.first_name}\n"
            f"🚫 Статус: Забанен\n\n"
            f"Доступ к боту ограничен!"
        )

@labeler.message(regex=r"^(?i)Разбан\s+(.*?)$")
async def admin_unban(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    target_id = get_id_from_mention(match[0])
    user = await User.get_or_none(vk_id=target_id)
    
    if user:
        user.is_banned = False
        await user.save()
        await message.answer(
            f"╔═══════════════════════╗\n"
            f"    ✅ РАЗБАНЕН\n"
            f"╚═══════════════════════╝\n\n"
            f"👤 Игрок: {user.first_name}\n"
            f"🟢 Статус: Активен\n\n"
            f"Доступ к боту восстановлен!"
        )

@labeler.message(regex=r"^(?i)Рассылка\s+(.*)$")
async def admin_broadcast(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    text = match[0]
    users = await User.all()
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    📢 РАССЫЛКА\n"
        f"╚═══════════════════════╝\n\n"
        f"👥 Получателей: {len(users)}\n"
        f"📨 Сообщение:\n\n"
        f"{text}\n\n"
        f"⏳ Отправка начата..."
    )
    
    sent = 0
    for user in users:
        try: 
            await message.ctx_api.messages.send(
                peer_id=user.vk_id, 
                message=f"📢 ОБЪЯВЛЕНИЕ\n\n{text}", 
                random_id=0
            )
            sent += 1
        except: 
            pass
    
    await message.answer(
        f"✅ Рассылка завершена!\n"
        f"📨 Отправлено: {sent}/{len(users)}"
    )

@labeler.message(regex=r"^(?i)Связать\s+(.*)$")
async def link_card(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    full_text = match[0]
    
    photo_match = re.search(r"photo(-?\d+_\d+)", full_text)
    
    if not photo_match: 
        return await message.answer(
            "╔═══════════════════════╗\n"
            "    ❌ ОШИБКА\n"
            "╚═══════════════════════╝\n\n"
            "📸 Не найден ID фото!\n\n"
            "💡 Примеры:\n"
            "   Связать photo-123_456 @user\n"
            "   Связать vk.com/photo-123_456 @user"
        )
    
    target_id = None
    for word in full_text.split():
        uid = get_id_from_mention(word)
        if uid: 
            target_id = uid
            break
    
    if not target_id: 
        return await message.answer(
            "╔═══════════════════════╗\n"
            "    ❌ ОШИБКА\n"
            "╚═══════════════════════╝\n\n"
            "👤 Укажи пользователя!\n\n"
            "💡 Пример:\n"
            "   Связать photo-123_456 @user"
        )
    
    user = await User.get(vk_id=target_id)
    user.card_photo_id = photo_match.group(1)
    await user.save()
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    ✅ КАРТА СВЯЗАНА\n"
        f"╚═══════════════════════╝\n\n"
        f"👤 Игрок: {user.first_name}\n"
        f"📸 Фото: {photo_match.group(1)}\n\n"
        f"🔄 Обновление карточки..."
    )
    
    await auto_update_card(message.ctx_api, user)

@labeler.message(text="!Принудительная зарплата")
async def force_salary_cmd(message: Message):
    if message.from_id not in ADMIN_IDS: return
    
    conf, _ = await SystemConfig.get_or_create(key="last_salary_month")
    conf.value = "RESET"
    await conf.save()
    
    await message.answer(
        "╔═══════════════════════╗\n"
        "    ✅ СБРОС ВЫПОЛНЕН\n"
        "╚═══════════════════════╝\n\n"
        "💰 Метка зарплаты сброшена!\n\n"
        "⏰ Следующая проверка:\n"
        "   • В течение часа\n"
        "   • При перезапуске бота\n\n"
        "💡 Зарплата будет выплачена\n"
        "   автоматически!"
    )

@labeler.message(regex=r"^(?i)Промокод\s+(\w+)\s+(\d+)\s+(\d+)$")
async def create_promo(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    code, amount, max_uses = match[0], int(match[1]), int(match[2])
    
    await Promo.create(code=code, amount=amount, max_activations=max_uses)
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    🎫 ПРОМОКОД СОЗДАН\n"
        f"╚═══════════════════════╝\n\n"
        f"┏━━━━ ПАРАМЕТРЫ ━━━━┓\n"
        f"│\n"
        f"│ 🎟 Код: {code}\n"
        f"│ 💰 Награда: {amount:,} ₽\n"
        f"│ 👥 Активаций: {max_uses}\n"
        f"│\n"
        f"┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        f"📢 Распространи промокод игрокам!"
    )

@labeler.message(regex=r"^(?i)Стоимость:\s+(\d+)$")
async def set_price(message: Message, match):
    if message.from_id not in ADMIN_IDS: return
    if not message.reply_message: return
    
    price = int(match[0])
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
            await message.ctx_api.messages.send(
                peer_id=target_id, 
                message=(
                    f"╔═══════════════════════╗\n"
                    f"    💰 ОЦЕНКА ТОВАРА\n"
                    f"╚═══════════════════════╝\n\n"
                    f"✅ Администратор оценил заявку!\n\n"
                    f"┏━━━━ СТОИМОСТЬ ━━━━┓\n"
                    f"│\n"
                    f"│ 💵 Цена: {price:,} чилликов\n"
                    f"│\n"
                    f"┗━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
                    f"💡 Свяжись с администратором\n"
                    f"   для завершения покупки!"
                ), 
                random_id=0
            )
        except: 
            pass
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    ✅ ЦЕНА УСТАНОВЛЕНА\n"
        f"╚═══════════════════════╝\n\n"
        f"💰 Стоимость: {price:,} ₽\n\n"
        f"📨 Игрок получил уведомление!"
    )
    
@labeler.message(text="!id")
async def get_chat_id(message: Message):
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"    🆔 ID ЧАТА\n"
        f"╚═══════════════════════╝\n\n"
        f"📋 Текущий чат:\n"
        f"   {message.peer_id}\n\n"
        f"💡 Используй это значение в настройках!"
    )

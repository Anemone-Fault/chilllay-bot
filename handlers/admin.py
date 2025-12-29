from vkbottle.bot import BotLabeler, Message
from vkbottle import VKAPIError
from database.models import User, TransactionLog, Promo, Cheque, ShopRequest, RequestStatus
from settings import ADMIN_IDS
from utils.helpers import get_id_from_mention
from datetime import datetime
import re

labeler = BotLabeler()

# --- 🔥 ФУНКЦИЯ: ОБНОВЛЕНИЕ КАРТОЧКИ (Через описание фото) ---
async def auto_update_card(api, user_db, debug_message: Message = None):
    if not user_db.card_photo_id: 
        if debug_message:
            await debug_message.answer(
                "╔═══════════════════════╗\n"
                "     ❌ ОШИБКА ❌\n"
                "╚═══════════════════════╝\n\n"
                "📸 У пользователя нет привязанной карточки!"
            )
        return

    dossier_text = (
        f"╔══════════════════╗\n"
        f"  ✦ ДОСЬЕ ИГРОКА ✦\n"
        f"╚══════════════════╝\n\n"
        f"👤 Игрок: {user_db.first_name}\n"
        f"☢ Ранг: {user_db.get_rank()}\n"
        f"💰 Баланс: {user_db.balance:,} чилликов\n"
        f"☯️ Карма: {user_db.karma}\n\n"
        f"🕒 Обновлено: {datetime.now().strftime('%d.%m в %H:%M')}"
    )

    try:
        owner_id, photo_id = map(int, user_db.card_photo_id.split('_'))

        await api.photos.edit(
            owner_id=owner_id,
            photo_id=photo_id,
            caption=dossier_text
        )

        print(f"✅ Описание фото {photo_id} обновлено.", flush=True)
        
        if debug_message:
            await debug_message.answer(
                "╔═══════════════════════╗\n"
                "      ✅ УСПЕХ! ✅\n"
                "╚═══════════════════════╝\n\n"
                "📸 Карточка обновлена!\n"
                f"🆔 Фото ID: {photo_id}\n\n"
                f"👤 Игрок: {user_db.first_name}\n"
                f"💰 Баланс: {user_db.balance:,}\n"
                f"☯️ Карма: {user_db.karma}"
            )

    except VKAPIError as e:
        err_msg = getattr(e, "error_msg", str(e))
        err_text = f"🔥 Ошибка ВК (Код {e.code}): {err_msg}"
        print(err_text, flush=True)
        
        if debug_message: 
            await debug_message.answer(
                "╔═══════════════════════╗\n"
                "     ⚠️ ОШИБКА ВК ⚠️\n"
                "╚═══════════════════════╝\n\n"
                f"🔴 Код ошибки: {e.code}\n"
                f"📝 Описание: {err_msg}\n\n"
                "💡 Проверь права доступа бота!"
            )
            
    except Exception as e:
        err_text = f"🔥 Системная ошибка: {e}"
        print(err_text, flush=True)
        
        if debug_message:
            await debug_message.answer(
                "╔═══════════════════════╗\n"
                "   ⚠️ СИСТЕМНАЯ ОШИБКА ⚠️\n"
                "╚═══════════════════════╝\n\n"
                f"❌ {err_text}\n\n"
                "💡 Обратись к разработчику!"
            )


# --- ПОМОЩНИК: ПОЛУЧЕНИЕ ИМЕНИ ---
async def get_name(message: Message, user_id: int) -> str:
    user = await User.get_or_none(vk_id=user_id)
    if user and user.first_name != "Неизвестный":
        return user.first_name
    try:
        users_info = await message.ctx_api.users.get(user_ids=[user_id])
        return users_info[0].first_name
    except:
        return "User"

# --- КОМАНДА: ТЕСТ КАРТОЧКИ ---
@labeler.message(text="/test_card")
async def debug_card_cmd(message: Message):
    if message.from_id not in ADMIN_IDS:
        return
    
    user = await User.get_or_none(vk_id=message.from_id)
    
    if not user or not user.card_photo_id:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ НЕТ КАРТЫ ❌\n"
            "╚═══════════════════════╝\n\n"
            "📸 У тебя нет привязанной карточки!\n\n"
            "💡 Используй: Связать [фото] [id]"
        )
    
    await message.answer(
        "╔═══════════════════════╗\n"
        "    🔍 ДИАГНОСТИКА 🔍\n"
        "╚═══════════════════════╝\n\n"
        f"📸 Фото ID: {user.card_photo_id}\n"
        f"👤 Игрок: {user.first_name}\n\n"
        "⏳ Запускаю обновление..."
    )
    
    await auto_update_card(message.ctx_api, user, debug_message=message)

# --- КОМАНДА: НАЧИСЛИТЬ ---
@labeler.message(regex=r"^(?i)Начислить\s+(.*?)\s+(\d+)$")
async def admin_give(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_raw, amount_str = match[0], match[1]
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)

    if not target_id:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ ОШИБКА ❌\n"
            "╚═══════════════════════╝\n\n"
            "👤 Не указан пользователь!\n\n"
            "💡 Пример: Начислить @user 100"
        )
    
    name = await get_name(message, target_id)
    user = await User.get_or_none(vk_id=target_id)
    
    if not user:
        user = await User.create(vk_id=target_id, first_name=name, last_name="Player")

    old_balance = user.balance
    user.balance += amount
    user.first_name = name
    await user.save()
    
    await auto_update_card(message.ctx_api, user)
    await TransactionLog.create(user=user, amount=amount, description="Админ выдал")
    
    text = (
        "╔═══════════════════════╗\n"
        "    💰 НАЧИСЛЕНО! 💰\n"
        "╚═══════════════════════╝\n\n"
        f"👤 Игрок: [id{target_id}|{name}]\n"
        f"✨ Начислено: +{amount:,}\n\n"
        f"📊 Было: {old_balance:,}\n"
        f"📈 Стало: {user.balance:,}"
    )
    
    await message.answer(text)

# --- КОМАНДА: СПИСАТЬ ---
@labeler.message(regex=r"^(?i)Списать\s+(.*?)\s+(\d+)$")
async def admin_remove(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_raw, amount_str = match[0], match[1]
    amount = int(amount_str)
    target_id = get_id_from_mention(target_raw)

    if not target_id:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ ОШИБКА ❌\n"
            "╚═══════════════════════╝\n\n"
            "👤 Не указан пользователь!\n\n"
            "💡 Пример: Списать @user 50"
        )
    
    name = await get_name(message, target_id)
    user = await User.get_or_none(vk_id=target_id)
    
    if not user:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ НЕ НАЙДЕН ❌\n"
            "╚═══════════════════════╝\n\n"
            f"👤 [id{target_id}|{name}]\n"
            "не зарегистрирован в боте!"
        )

    old_balance = user.balance
    user.balance -= amount
    await user.save()
    
    await auto_update_card(message.ctx_api, user)
    await TransactionLog.create(user=user, amount=-amount, description="Админ забрал")
    
    text = (
        "╔═══════════════════════╗\n"
        "     💸 СПИСАНО! 💸\n"
        "╚═══════════════════════╝\n\n"
        f"👤 Игрок: [id{target_id}|{name}]\n"
        f"💰 Списано: -{amount:,}\n\n"
        f"📊 Было: {old_balance:,}\n"
        f"📉 Стало: {user.balance:,}"
    )
    
    await message.answer(text)

# --- КОМАНДА: СВЯЗАТЬ КАРТОЧКУ ---
@labeler.message(regex=r"^(?i)Связать\s+(.*)$")
async def link_card(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    full_text = match[0]
    photo_match = re.search(r"photo(-?\d+_\d+)", full_text)
    
    if not photo_match:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ ОШИБКА ❌\n"
            "╚═══════════════════════╝\n\n"
            "📸 Не найдена ссылка на фото!\n\n"
            "💡 Пример:\n"
            "Связать photo-123_456 @user"
        )
    
    full_photo_id = photo_match.group(1)

    target_id = None
    for word in full_text.split():
        uid = get_id_from_mention(word)
        if uid:
            target_id = uid
            break
    
    if not target_id:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ ОШИБКА ❌\n"
            "╚═══════════════════════╝\n\n"
            "👤 Не указан пользователь!\n\n"
            "💡 Пример:\n"
            "Связать photo-123_456 @user"
        )

    user = await User.get_or_none(vk_id=target_id)
    if not user:
        name = await get_name(message, target_id)
        user = await User.create(vk_id=target_id, first_name=name, last_name="Player")
    
    user.card_photo_id = full_photo_id
    user.card_comment_id = None
    await user.save()
    
    text = (
        "╔═══════════════════════╗\n"
        "     🔗 СВЯЗАНО! 🔗\n"
        "╚═══════════════════════╝\n\n"
        f"👤 Игрок: [id{target_id}|{user.first_name}]\n"
        f"📸 Фото ID: {full_photo_id}\n\n"
        "⏳ Обновляю описание фото..."
    )
    
    await message.answer(text)
    await auto_update_card(message.ctx_api, user, debug_message=message)

# --- КОМАНДА: БАН ---
@labeler.message(regex=r"^(?i)Попущенный\s+(.*?)(?:\s+(.*))?$")
async def admin_ban(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    
    if not target_id:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ ОШИБКА ❌\n"
            "╚═══════════════════════╝\n\n"
            "👤 Не указан пользователь!"
        )
    
    user = await User.get_or_none(vk_id=target_id)
    
    if not user:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ НЕ НАЙДЕН ❌\n"
            "╚═══════════════════════╝\n\n"
            "👤 Пользователь не в базе!"
        )
    
    user.is_banned = True
    await user.save()
    
    text = (
        "╔═══════════════════════╗\n"
        "      ⛔ ЗАБАНЕН! ⛔\n"
        "╚═══════════════════════╝\n\n"
        f"👤 [id{target_id}|{user.first_name}]\n"
        f"больше не может пользоваться ботом!\n\n"
        "🔨 Причина: Попущенный"
    )
    
    await message.answer(text)

# --- КОМАНДА: РАЗБАН ---
@labeler.message(regex=r"^(?i)Разбан\s+(.*?)$")
async def admin_unban(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    target_id = get_id_from_mention(match[0])
    user = await User.get_or_none(vk_id=target_id)
    
    if not user:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ НЕ НАЙДЕН ❌\n"
            "╚═══════════════════════╝\n\n"
            "👤 Пользователь не в базе!"
        )
    
    user.is_banned = False
    await user.save()
    
    text = (
        "╔═══════════════════════╗\n"
        "     ✅ РАЗБАНЕН! ✅\n"
        "╚═══════════════════════╝\n\n"
        f"👤 [id{target_id}|{user.first_name}]\n"
        "снова может использовать бота!\n\n"
        "🎉 Добро пожаловать обратно!"
    )
    
    await message.answer(text)

# --- КОМАНДА: РАССЫЛКА ---
@labeler.message(regex=r"^(?i)Рассылка\s+(.*)$")
async def admin_broadcast(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    text = match[0]
    users = await User.all()
    
    broadcast_text = (
        "╔═══════════════════════╗\n"
        "    📢 ОБЪЯВЛЕНИЕ! 📢\n"
        "╚═══════════════════════╝\n\n"
        f"{text}"
    )
    
    await message.answer(
        f"╔═══════════════════════╗\n"
        f"   📤 РАССЫЛКА ЗАПУЩЕНА 📤\n"
        f"╚═══════════════════════╝\n\n"
        f"👥 Получателей: {len(users)}\n"
        f"⏳ Отправка началась...\n\n"
        f"💡 Это может занять время"
    )
    
    success_count = 0
    failed_count = 0
    
    for user in users:
        try:
            await message.ctx_api.messages.send(
                peer_id=user.vk_id,
                message=broadcast_text,
                random_id=0
            )
            success_count += 1
        except:
            failed_count += 1
    
    result_text = (
        f"╔═══════════════════════╗\n"
        f"  ✅ РАССЫЛКА ЗАВЕРШЕНА! ✅\n"
        f"╚═══════════════════════╝\n\n"
        f"✅ Успешно: {success_count}\n"
        f"❌ Ошибок: {failed_count}\n"
        f"📊 Всего: {len(users)}"
    )
    
    await message.answer(result_text)

# --- КОМАНДА: СОЗДАТЬ ПРОМОКОД ---
@labeler.message(regex=r"^(?i)Промокод\s+(\w+)\s+(\d+)\s+(\d+)$")
async def create_promo(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    code = match[0]
    amount = int(match[1])
    max_activations = int(match[2])
    
    existing = await Promo.get_or_none(code=code)
    if existing:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ ОШИБКА ❌\n"
            "╚═══════════════════════╝\n\n"
            f"🎫 Промокод '{code}' уже существует!\n\n"
            "💡 Используй другое имя"
        )
    
    await Promo.create(
        code=code,
        amount=amount,
        max_activations=max_activations
    )
    
    text = (
        "╔═══════════════════════╗\n"
        "   🎫 ПРОМОКОД СОЗДАН! 🎫\n"
        "╚═══════════════════════╝\n\n"
        f"🏷️ Код: {code}\n"
        f"💰 Награда: {amount:,}\n"
        f"👥 Активаций: {max_activations}\n\n"
        f"💡 Пользователи могут активировать:\n"
        f"→ Промо {code}"
    )
    
    await message.answer(text)

# --- КОМАНДА: УСТАНОВИТЬ ЦЕНУ ---
@labeler.message(regex=r"^(?i)Стоимость:\s+(\d+)$")
async def set_price(message: Message, match):
    if message.from_id not in ADMIN_IDS:
        return
    
    if not message.reply_message:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ ОШИБКА ❌\n"
            "╚═══════════════════════╝\n\n"
            "💡 Ответь этим сообщением\n"
            "на заявку из магазина!"
        )
    
    price = int(match[0])
    user_match = re.search(r"\[id(\d+)\|", message.reply_message.text)
    req_match = re.search(r"ЗАЯВКА №(\d+)", message.reply_message.text)
    
    if not user_match:
        return await message.answer(
            "╔═══════════════════════╗\n"
            "     ❌ ОШИБКА ❌\n"
            "╚═══════════════════════╝\n\n"
            "❌ Не найден ID пользователя\n"
            "в сообщении заявки!"
        )
    
    target_id = int(user_match.group(1))
    
    if req_match:
        req = await ShopRequest.get_or_none(id=int(req_match.group(1)))
        if req:
            req.price = price
            req.status = RequestStatus.PRICE_SET
            await req.save()
    
    notification = (
        "╔═══════════════════════╗\n"
        "   💰 ЦЕНА УСТАНОВЛЕНА! 💰\n"
        "╚═══════════════════════╝\n\n"
        f"✅ Твоя заявка оценена!\n\n"
        f"💰 Стоимость: {price:,} чилликов\n\n"
        "💡 Админ свяжется с тобой\n"
        "для завершения покупки!"
    )
    
    try:
        await message.ctx_api.messages.send(
            peer_id=target_id,
            message=notification,
            random_id=0
        )
    except:
        pass
    
    text = (
        "╔═══════════════════════╗\n"
        "     ✅ ГОТОВО! ✅\n"
        "╚═══════════════════════╝\n\n"
        f"👤 Игроку [id{target_id}|] отправлено\n"
        f"уведомление о цене: {price:,}\n\n"
        "📬 Уведомление доставлено!"
    )
    
    await message.answer(text)

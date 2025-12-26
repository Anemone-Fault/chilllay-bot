from vkbottle.bot import BotLabeler, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from vkbottle.tools import PhotoMessageUploader
from database.models import User, ShopRequest, RequestStatus, TransactionLog, Promo
from utils.helpers import get_id_from_mention, get_chart_url
from settings import ADMIN_IDS
import re
import aiohttp

labeler = BotLabeler()

def is_admin(func):
    async def wrapper(message: Message, **kwargs):
        if not ADMIN_IDS: return # Если админов нет в конфиге
        if message.from_id not in ADMIN_IDS: return
        return await func(message, **kwargs)
    return wrapper

@labeler.message(regex=r"^Стоимость:\s+(\d+)$")
@is_admin
async def set_price(message: Message, match):
    price = int(match[0])
    if not message.reply_message: return await message.answer("⚠️ Реплай на заявку!")
    
    # Ищем именно "ЗАЯВКА #"
    id_match = re.search(r"ЗАЯВКА #(\d+)", message.reply_message.text)
    if not id_match: return await message.answer("⚠️ Не вижу ID заявки (формат должен быть 'ЗАЯВКА #123').")
    req_id = int(id_match.group(1))
    
    req = await ShopRequest.get_or_none(id=req_id).prefetch_related("user")
    if not req or req.status != RequestStatus.CREATED: return await message.answer("⚠️ Уже обработано.")
    
    user = req.user
    if user.balance < price:
        req.status = RequestStatus.CANCELED
        await req.save()
        await message.ctx_api.messages.send(peer_id=user.vk_id, message=f"📉 У тебя {user.balance} Чилликов. Заявка на {price} отменена.", random_id=0)
        return await message.answer("📉 У юзера нет денег. Отмена.")
        
    req.price = price
    req.status = RequestStatus.PRICE_SET
    await req.save()
    
    kb = Keyboard(inline=True).add(Text(f"Купить за {price}", payload={"cmd": "shop_buy", "req_id": req.id, "price": price}), color=KeyboardButtonColor.POSITIVE).row().add(Text("Отмена", payload={"cmd": "shop_cancel", "req_id": req.id}), color=KeyboardButtonColor.NEGATIVE).get_json()
    
    await message.ctx_api.messages.send(peer_id=user.vk_id, message=f"👮 Админ оценил товар в {price} Чилликов.\nБерешь?", keyboard=kb, random_id=0)
    await message.answer("✅ Ценник выставлен.")

@labeler.message(regex=r"^Начислить\s+(.*?)\s+(\d+)$")
@is_admin
async def admin_give(message: Message, match):
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    if not target_id: return
    
    user = await User.get_or_none(vk_id=target_id)
    if not user: return await message.answer("Нет в базе.")
    
    user.balance += amount
    await user.save()
    await TransactionLog.create(user=user, amount=amount, description="Эмиссия")
    await message.answer(f"💳 Выдано {amount} Чилликов.")
    try: await message.ctx_api.messages.send(peer_id=target_id, message=f"💳 Эмиссия: +{amount} Чилликов.", random_id=0)
    except: pass

@labeler.message(regex=r"^Списать\s+(.*?)\s+(\d+)$")
@is_admin
async def admin_take(message: Message, match):
    target_id = get_id_from_mention(match[0])
    amount = int(match[1])
    if not target_id: return
    
    user = await User.get_or_none(vk_id=target_id)
    if not user: return await message.answer("Нет в базе.")
    
    user.balance -= amount
    await user.save()
    await TransactionLog.create(user=user, amount=-amount, description="Штраф")
    await message.answer(f"📉 Раскулачен на {amount}.")
    try: await message.ctx_api.messages.send(peer_id=target_id, message=f"📉 Штраф: -{amount} Чилликов.", random_id=0)
    except: pass

@labeler.message(regex=r"^Попущенный\s+(.*?)\s+(.*)$")
@is_admin
async def ban(message: Message, match):
    target_id = get_id_from_mention(match[0])
    reason = match[1]
    if target_id:
        u = await User.get(vk_id=target_id)
        u.is_banned = True
        await u.save()
        await message.answer(f"☠️ Забанен. Причина: {reason}")

@labeler.message(regex=r"^График$")
@is_admin
async def chart(message: Message):
    txs = await TransactionLog.all().order_by("-id").limit(15)
    txs = txs[::-1]
    url = get_chart_url([str(t.id) for t in txs], [t.amount for t in txs], "Activity")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()
    
    photo = await PhotoMessageUploader(message.ctx_api).upload(data)
    await message.answer("📊 График:", attachment=photo)

@labeler.message(regex=r"^Рассылка\s+(.*)$")
@is_admin
async def broadcast(message: Message, match):
    text = match[0]
    users = await User.filter(is_banned=False).all()
    count = 0
    await message.answer(f"📡 Рассылка на {len(users)}...")
    for user in users:
        try:
            await message.ctx_api.messages.send(peer_id=user.vk_id, message=f"📢 ОБЪЯВЛЕНИЕ:\n{text}", random_id=0)
            count += 1
        except: pass
    await message.answer(f"✅ Доставлено: {count}")

@labeler.message(regex=r"^Промокод\s+(\w+)\s+(\d+)\s+(\d+)$")
@is_admin
async def create_promo(message: Message, match):
    code, amount, activations = match[0], int(match[1]), int(match[2])
    await Promo.create(code=code, amount=amount, max_activations=activations)
    await message.answer(f"🎁 Промо {code} создан (+{amount}, {activations} шт).")
from vkbottle.bot import BotLabeler, Message
from database.models import User, ShopRequest, RequestStatus, TransactionLog
from tortoise.transactions import in_transaction
from settings import ADMIN_IDS

labeler = BotLabeler()

@labeler.message(regex=r"^Хочу\s+(.*)$")
async def buy_request(message: Message, match, user_db: User):
    # Работает только в ЛС
    if message.peer_id != message.from_id:
        return
        
    item = match[0]
    req = await ShopRequest.create(user=user_db, item_text=item)
    
    await message.answer(f"📝 Заявка #{req.id} принята.\nЖди, пока Админ проснется и назовет цену в Чилликах.")
    
    # ЕДИНЫЙ ФОРМАТ: "ЗАЯВКА #..."
    msg = (
        f"🛒 ЗАЯВКА #{req.id}\n"
        f"👤 [id{user_db.vk_id}|{user_db.first_name}]\n"
        f"📦 Товар: {item}\n\n"
        f"Ответь (Reply): Стоимость: 1000"
    )
    for admin_id in ADMIN_IDS:
        try:
            await message.ctx_api.messages.send(peer_id=admin_id, message=msg, random_id=0)
        except: pass

@labeler.message(payload_map={"cmd": "shop_buy"})
async def shop_confirm(message: Message, user_db: User):
    payload = message.get_payload_json()
    req_id, price = payload["req_id"], payload["price"]
    
    req = await ShopRequest.get_or_none(id=req_id)
    if not req or req.status != RequestStatus.PRICE_SET: return await message.answer("❌ Неактуально.")
    if user_db.balance < price: return await message.answer("❌ Братан, у тебя карманы дырявые.")
        
    async with in_transaction():
        u = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        if u.balance < price: return await message.answer("❌ Не хватает Чилликов.")
        
        u.balance -= price
        await u.save()
        
        req.status = RequestStatus.COMPLETED
        await req.save()
        await TransactionLog.create(user=u, amount=-price, description=f"Shop: {req.item_text}")
    
    await message.answer(f"✅ Сделка закрыта.\nСписано {price} Чилликов.")
    for admin_id in ADMIN_IDS:
        try:
            await message.ctx_api.messages.send(peer_id=admin_id, message=f"💰 Оплачена заявка #{req_id} ({price}).", random_id=0)
        except: pass

@labeler.message(payload_map={"cmd": "shop_cancel"})
async def shop_cancel(message: Message, user_db: User):
    req_id = message.get_payload_json()["req_id"]
    req = await ShopRequest.get_or_none(id=req_id)
    if req:
        req.status = RequestStatus.CANCELED
        await req.save()
    await message.answer("❌ Отменено.")
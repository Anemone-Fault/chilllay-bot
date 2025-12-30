from vkbottle.bot import BotLabeler, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text
from database.models import User, Item, Inventory, GiftBox, Rarity, GiftType, ItemType, SystemConfig
from utils.keyboards import get_smart_keyboard
from settings import GIFT_IMAGES, ADMIN_IDS
from utils.card_updater import auto_update_card
import random
import asyncio

labeler = BotLabeler()

# --- 🎒 ИНВЕНТАРЬ ---
@labeler.message(regex=r"^(?i)(?:Инвентарь|Сумка|Inventory)$")
async def show_inventory(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    inv_items = await Inventory.filter(user=user_db).prefetch_related("item").all()
    gifts = await GiftBox.filter(user=user_db, quantity__gt=0).all()

    text = (
        f"╔═══════════════╗\n"
        f"    🎒 РЮКЗАК\n"
        f"╚═══════════════╝\n\n"
    )

    if not inv_items and not gifts:
        text += "🕸 Здесь пусто...\nПиши РП-посты, чтобы найти кейс!"
        return await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

    if gifts:
        text += "🎁 КЕЙСЫ:\n"
        for g in gifts:
            text += f"• {g.gift_type.value} ({g.rarity.value}) — {g.quantity} шт.\n"
        text += "\n"

    if inv_items:
        text += "📦 ПРЕДМЕТЫ:\n━━━━━━━━━━━━━━━\n"
        for slot in inv_items:
            icon = "⚔" if slot.item.type == ItemType.ITEM else "✨"
            text += f"{icon} {slot.item.name} ({slot.item.rarity.value}) — {slot.quantity} шт.\n"
    
    kb = Keyboard(inline=True)
    if gifts:
        kb.add(Text("🎁 Открыть кейс", payload={"cmd": "open_menu"}), color=KeyboardButtonColor.POSITIVE)
    
    await message.answer(text, keyboard=kb.get_json())


# --- 🎁 МЕНЮ ОТКРЫТИЯ ---
@labeler.message(payload_map={"cmd": "open_menu"})
async def open_gift_menu(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    gifts = await GiftBox.filter(user=user_db, quantity__gt=0).all()
    
    if not gifts:
        return await message.answer("У тебя нет подарков 😔", ephemeral=True)
    
    text = "🎁 Какой подарок открываем?"
    kb = Keyboard(inline=True)
    
    for g in gifts:
        kb.add(Text(f"{g.gift_type.value} ({g.rarity.value})", payload={"cmd": "open_anim", "rarity": g.rarity.value, "type": g.gift_type.value}))
        kb.row()
        
    await message.answer(text, keyboard=kb.get_json())


# --- 🎰 АНИМАЦИЯ И ЛОГИКА ---
@labeler.message(payload_map={"cmd": "open_anim"})
async def open_gift_process(message: Message):
    user_db = await User.get(vk_id=message.from_id)
    payload = message.get_payload_json()
    r_val = payload.get("rarity")
    t_val = payload.get("type")

    box = await GiftBox.filter(user=user_db, rarity=r_val, gift_type=t_val).first()
    if not box or box.quantity < 1:
        return await message.answer("❌ Такой коробки нет.")

    box_image = GIFT_IMAGES.get(t_val)
    wait_msg = await message.answer(f"🎁 Открываем: {t_val} ({r_val})...", attachment=box_image)
    await asyncio.sleep(1.5)

    amount = 0
    won_item = None
    pool = []

    if box.gift_type == GiftType.MONEY:
        ranges = {
            Rarity.COMMON: (10, 500), Rarity.RARE: (500, 2000),
            Rarity.EPIC: (2000, 5000), Rarity.CHILL: (5000, 10000)
        }
        mn, mx = ranges.get(box.rarity, (10, 100))
        amount = random.randint(mn, mx)
        user_db.balance += amount
        await user_db.save()
        await auto_update_card(message.ctx_api, user_db)

    elif box.gift_type in [GiftType.ITEM, GiftType.TALENT, GiftType.LUCKY]:
        target_type = ItemType.ITEM
        if box.gift_type == GiftType.TALENT: target_type = ItemType.TALENT
        if box.gift_type == GiftType.LUCKY: target_type = ItemType.ABILITY
        
        pool = await Item.filter(type=target_type, rarity=box.rarity).all()
        if not pool: pool = await Item.filter(type=target_type).all()
        
        if pool:
            won_item = random.choice(pool)
            inv, _ = await Inventory.get_or_create(user=user_db, item=won_item)
            inv.quantity += 1
            await inv.save()
            if won_item.photo_id: box_image = won_item.photo_id

    box.quantity -= 1
    if box.quantity <= 0: await box.delete()
    else: await box.save()

    header = "🎉 ОТКРЫТИЕ"
    if box.gift_type == GiftType.FATE: header = "🔮 СУДЬБА"
    
    final_text = (f"╔═══════════════╗\n    {header}\n╚═══════════════╝\n\n")

    if box.gift_type == GiftType.MONEY:
        final_text += (f"💰 Насыпало: {amount} Чилликов\n📊 Баланс: {user_db.balance}")
    elif box.gift_type == GiftType.FATE:
        final_text += "⚡ СУДЬБОНОСНОЕ СОБЫТИЕ!\nАдминистрация уведомлена."
        for admin_id in ADMIN_IDS:
            try: await message.ctx_api.messages.send(peer_id=admin_id, message=f"🚨 СУДЬБА: {user_db.first_name} выбил кейс!", random_id=0)
            except: pass
    else:
        if won_item:
            final_text += (f"Выпало: {won_item.name}\n━━━━━━━━━━━━━━━\n✨ Ранг: {won_item.rarity.value}\n📦 Тип: {won_item.type.value}\n\nСохранено в инвентарь!")
        else:
            final_text += "💨 Пусто... (База предметов пуста)"

    try:
        await message.ctx_api.messages.edit(
            peer_id=message.peer_id,
            message=final_text,
            conversation_message_id=wait_msg.conversation_message_id,
            attachment=box_image, keyboard=None
        )
    except:
        await message.answer(final_text, attachment=box_image)

@labeler.message(text="🎭 Персонажи")
async def show_chars_placeholder(message: Message):
    await message.answer("🚧 Раздел персонажей в разработке...")

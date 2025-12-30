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
        f"╔═══════════════════════╗\n"
        f"       🎒 ИНВЕНТАРЬ\n"
        f"╚═══════════════════════╝\n\n"
    )

    if not inv_items and not gifts:
        text += (
            "🕸 Здесь пока ничего нет...\n\n"
            "┏━━━━ КАК ПОЛУЧИТЬ? ━━━━┓\n"
            "│\n"
            "│ ✍️ Пиши РП-посты в чате\n"
            "│ ❤️ Ставь лайки записям\n"
            "│ 🎉 Участвуй в ивентах\n"
            "│\n"
            "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            "💡 Кейсы выпадают случайно!"
        )
        return await message.answer(text, keyboard=await get_smart_keyboard(user_db, "main"))

    if gifts:
        text += "┏━━━━ 🎁 КЕЙСЫ ━━━━┓\n│\n"
        for g in gifts:
            rarity_emoji = {
                Rarity.COMMON: "⚪",
                Rarity.RARE: "🔵",
                Rarity.EPIC: "🟣",
                Rarity.CHILL: "🌈"
            }.get(g.rarity, "⚪")
            
            text += f"│ {rarity_emoji} {g.gift_type.value}\n"
            text += f"│    {g.rarity.value} • {g.quantity} шт.\n│\n"
        text += "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"

    if inv_items:
        text += "┏━━━━ 📦 ПРЕДМЕТЫ ━━━━┓\n│\n"
        for slot in inv_items:
            type_emoji = {
                ItemType.ITEM: "⚔️",
                ItemType.TALENT: "✨",
                ItemType.ABILITY: "🎯"
            }.get(slot.item.type, "📦")
            
            rarity_emoji = {
                Rarity.COMMON: "⚪",
                Rarity.RARE: "🔵",
                Rarity.EPIC: "🟣",
                Rarity.CHILL: "🌈"
            }.get(slot.item.rarity, "⚪")
            
            text += f"│ {type_emoji} {slot.item.name}\n"
            text += f"│    {rarity_emoji} {slot.item.rarity.value} • x{slot.quantity}\n│\n"
        text += "┗━━━━━━━━━━━━━━━━━━━━━━━┛"
    
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
        return await message.answer(
            "╔═══════════════════════╗\n"
            "    😔 ПУСТО\n"
            "╚═══════════════════════╝\n\n"
            "🎁 У тебя нет кейсов!\n\n"
            "💡 Получай их за:\n"
            "   • РП-активность\n"
            "   • Лайки записям\n"
            "   • Участие в ивентах",
            ephemeral=True
        )
    
    text = (
        "╔═══════════════════════╗\n"
        "    🎁 ОТКРЫТИЕ КЕЙСА\n"
        "╚═══════════════════════╝\n\n"
        "Выбери кейс для открытия:\n\n"
    )
    
    kb = Keyboard(inline=True)
    
    for g in gifts:
        rarity_emoji = {
            Rarity.COMMON: "⚪",
            Rarity.RARE: "🔵",
            Rarity.EPIC: "🟣",
            Rarity.CHILL: "🌈"
        }.get(g.rarity, "⚪")
        
        button_text = f"{rarity_emoji} {g.gift_type.value} ({g.quantity} шт.)"
        kb.add(
            Text(button_text, payload={
                "cmd": "open_anim", 
                "rarity": g.rarity.value, 
                "type": g.gift_type.value
            }),
            color=KeyboardButtonColor.POSITIVE
        )
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
        return await message.answer(
            "╔═══════════════════════╗\n"
            "    ❌ ОШИБКА\n"
            "╚═══════════════════════╝\n\n"
            "🎁 Такого кейса нет!\n\n"
            "💡 Возможно, ты уже открыл его."
        )

    box_image = GIFT_IMAGES.get(t_val)
    wait_msg = await message.answer(
        f"╔═══════════════════════╗\n"
        f"    🎰 ОТКРЫТИЕ...\n"
        f"╚═══════════════════════╝\n\n"
        f"🎁 Кейс: {t_val}\n"
        f"⭐ Редкость: {r_val}\n\n"
        f"⏳ Ожидай результат...",
        attachment=box_image
    )
    await asyncio.sleep(1.5)

    amount = 0
    won_item = None
    pool = []

    # === ДЕНЕЖНЫЙ КЕЙС ===
    if box.gift_type == GiftType.MONEY:
        ranges = {
            Rarity.COMMON: (10, 500), 
            Rarity.RARE: (500, 2000),
            Rarity.EPIC: (2000, 5000), 
            Rarity.CHILL: (5000, 10000)
        }
        mn, mx = ranges.get(box.rarity, (10, 100))
        amount = random.randint(mn, mx)
        user_db.balance += amount
        await user_db.save()
        await auto_update_card(message.ctx_api, user_db)

    # === ПРЕДМЕТНЫЙ КЕЙС ===
    elif box.gift_type in [GiftType.ITEM, GiftType.TALENT, GiftType.LUCKY]:
        target_type = ItemType.ITEM
        if box.gift_type == GiftType.TALENT: 
            target_type = ItemType.TALENT
        if box.gift_type == GiftType.LUCKY: 
            target_type = ItemType.ABILITY
        
        pool = await Item.filter(type=target_type, rarity=box.rarity).all()
        if not pool: 
            pool = await Item.filter(type=target_type).all()
        
        if pool:
            won_item = random.choice(pool)
            inv, _ = await Inventory.get_or_create(user=user_db, item=won_item)
            inv.quantity += 1
            await inv.save()
            if won_item.photo_id: 
                box_image = won_item.photo_id

    # Уменьшаем количество кейсов
    box.quantity -= 1
    if box.quantity <= 0: 
        await box.delete()
    else: 
        await box.save()

    # === ФОРМИРОВАНИЕ РЕЗУЛЬТАТА ===
    if box.gift_type == GiftType.FATE:
        # СУДЬБОНОСНЫЙ КЕЙС
        final_text = (
            f"╔═══════════════════════╗\n"
            f"    🔮 СУДЬБА\n"
            f"╚═══════════════════════╝\n\n"
            f"⚡ СУДЬБОНОСНОЕ СОБЫТИЕ!\n\n"
            f"┏━━━━ ВАЖНО ━━━━┓\n"
            f"│\n"
            f"│ 👤 Игрок: {user_db.first_name}\n"
            f"│ 🎲 Событие ожидает...\n"
            f"│\n"
            f"┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"🔔 Администрация уведомлена!\n"
            f"   Скоро с тобой свяжутся."
        )
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            try: 
                await message.ctx_api.messages.send(
                    peer_id=admin_id, 
                    message=(
                        f"╔═══════════════════════╗\n"
                        f"    🚨 СУДЬБОНОСНЫЙ КЕЙС\n"
                        f"╚═══════════════════════╝\n\n"
                        f"⚡ Игрок открыл особый кейс!\n\n"
                        f"👤 Имя: {user_db.first_name}\n"
                        f"🆔 ID: vk.com/id{user_db.vk_id}\n\n"
                        f"💡 Требуется участие администратора!"
                    ), 
                    random_id=0
                )
            except: 
                pass
                
    elif box.gift_type == GiftType.MONEY:
        # ДЕНЕЖНЫЙ КЕЙС
        final_text = (
            f"╔═══════════════════════╗\n"
            f"    💰 ВЫИГРЫШ!\n"
            f"╚═══════════════════════╝\n\n"
            f"🎉 Поздравляем!\n\n"
            f"┏━━━━ НАГРАДА ━━━━┓\n"
            f"│\n"
            f"│ 💵 Получено: {amount:,} ₽\n"
            f"│ 📊 Баланс: {user_db.balance:,} ₽\n"
            f"│ ⭐ Редкость: {r_val}\n"
            f"│\n"
            f"┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            f"✨ Чиллики зачислены на счёт!"
        )
        
    else:
        # ПРЕДМЕТНЫЙ КЕЙС
        if won_item:
            rarity_emoji = {
                Rarity.COMMON: "⚪",
                Rarity.RARE: "🔵",
                Rarity.EPIC: "🟣",
                Rarity.CHILL: "🌈"
            }.get(won_item.rarity, "⚪")
            
            type_name = {
                ItemType.ITEM: "Предмет",
                ItemType.TALENT: "Талант",
                ItemType.ABILITY: "Способность"
            }.get(won_item.type, "Предмет")
            
            final_text = (
                f"╔═══════════════════════╗\n"
                f"    🎁 ПРЕДМЕТ!\n"
                f"╚═══════════════════════╝\n\n"
                f"✨ Выпало:\n\n"
                f"┏━━━━ {won_item.name} ━━━━┓\n"
                f"│\n"
                f"│ {rarity_emoji} Редкость: {won_item.rarity.value}\n"
                f"│ 📦 Тип: {type_name}\n"
                f"│\n"
                f"┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
            )
            
            if won_item.description and won_item.description != "Описание от администрации":
                final_text += f"📝 {won_item.description}\n\n"
            
            final_text += "💼 Предмет добавлен в инвентарь!"
        else:
            final_text = (
                f"╔═══════════════════════╗\n"
                f"    💨 ПУСТО\n"
                f"╚═══════════════════════╝\n\n"
                f"😔 В кейсе ничего не было...\n\n"
                f"⚠️ База предметов пуста.\n"
                f"   Администратор скоро добавит\n"
                f"   новые награды!"
            )

    # Отправляем результат
    try:
        await message.ctx_api.messages.edit(
            peer_id=message.peer_id,
            message=final_text,
            conversation_message_id=wait_msg.conversation_message_id,
            attachment=box_image, 
            keyboard=None
        )
    except:
        await message.answer(final_text, attachment=box_image)

@labeler.message(text="🎭 Персонажи")
async def show_chars_placeholder(message: Message):
    await message.answer(
        "╔═══════════════════════╗\n"
        "    🚧 В РАЗРАБОТКЕ\n"
        "╚═══════════════════════╝\n\n"
        "🎭 Раздел персонажей скоро появится!\n\n"
        "┏━━━━ ЧТО БУДЕТ? ━━━━┓\n"
        "│\n"
        "│ 👥 Просмотр персонажей\n"
        "│ 📋 Профили и характеристики\n"
        "│ 🎨 Просмотр карточек персонажа\n"
        "│ 📖 Навыки, способности и предметы прямо в боте!\n"
        "│\n"
        "┗━━━━━━━━━━━━━━━━━━━━━━━┛\n\n"
        "⏰ Следи за обновлениями!"
    )

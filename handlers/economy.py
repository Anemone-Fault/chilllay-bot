# --- РЕПУТАЦИЯ ---
@labeler.message(regex=r"^\+реп\s+(.*)$")
async def plus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 100
    
    if user_db.balance < cost: return await message.answer(f"❌ Нужно {cost} чилликов.", keyboard=kb)
    if not target_id: return await message.answer("❌ Кому?", keyboard=kb)
    
    # 🔥 ТОКСИЧНАЯ ОТВЕТКА (В СТИЛЕ)
    if target_id == user_db.vk_id:
        return await message.answer(
            "╔═══════════════╗\n"
            "   🤡 КЛОУН ДНЯ\n"
            "╚═══════════════╝\n\n"
            "Сам себя лайкаешь?\n"
            "Мамкин нарцисс, иди потрогай траву.\n\n"
            "⛔ Репутация не изменена.",
            keyboard=kb
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        if not target: return await message.answer("❌ Нет такого.", keyboard=kb)
        sender.balance -= cost
        target.karma += 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    await message.answer(f"🫡 Респект отправлен (+1 карма). Списано {cost}.", keyboard=kb)

@labeler.message(regex=r"^\-реп\s+(.*)$")
async def minus_rep(message: Message, match):
    user_db = await get_user(message)
    kb = await get_smart_keyboard(user_db, "main")
    target_id = get_id_from_mention(match[0])
    cost = 500
    
    if user_db.balance < cost: return await message.answer(f"❌ Нужно {cost} чилликов.", keyboard=kb)
    if not target_id: return await message.answer("❌ Кого?", keyboard=kb)

    # 🔥 ТОКСИЧНАЯ ОТВЕТКА (В СТИЛЕ)
    if target_id == user_db.vk_id:
        return await message.answer(
            "╔═══════════════╗\n"
            "   🚑 САНЧАСТЬ\n"
            "╚═══════════════╝\n\n"
            "Сам себя дизлайкаешь?\n"
            "У тебя депрессия или просто\n"
            "внимания не хватает?\n\n"
            "💊 Сходи к врачу.",
            keyboard=kb
        )

    async with in_transaction():
        sender = await User.filter(vk_id=user_db.vk_id).select_for_update().first()
        target = await User.get_or_none(vk_id=target_id)
        if not target: return await message.answer("❌ Нет такого.", keyboard=kb)
        sender.balance -= cost
        target.karma -= 1
        await sender.save()
        await target.save()

    await auto_update_card(message.ctx_api, sender)
    await message.answer(f"💦 Дизлайк отправлен (-1 карма). Списано {cost}.", keyboard=kb)

from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from database.models import User, SystemConfig, GiftBox, Rarity, GiftType
import time
import re
import random
from settings import RATE_LIMIT_SECONDS, VK_GROUP_ID, RP_CHAT_ID

user_last_msg = {}

class SystemMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        if self.event.from_id < 0:
            self.stop("Group message")
            return

        if VK_GROUP_ID > 0:
            patterns = [
                rf"^\[club{VK_GROUP_ID}\|.*?\]\s*",
                rf"^\[public{VK_GROUP_ID}\|.*?\]\s*",
                rf"^@club{VK_GROUP_ID}\s*",
                rf"^@public{VK_GROUP_ID}\s*"
            ]
            for pat in patterns:
                self.event.text = re.sub(pat, "", self.event.text, flags=re.IGNORECASE).strip()

        user_id = self.event.from_id
        
        # Анти-спам
        now = time.time()
        last_time = user_last_msg.get(user_id, 0)
        if now - last_time < RATE_LIMIT_SECONDS:
            self.stop("Throttled")
            return
        user_last_msg[user_id] = now

        # Регистрация
        user = await User.get_or_none(vk_id=user_id)
        if not user:
            first_name = "Неизвестный"
            last_name = "Игрок"
            try:
                user_infos = await self.event.ctx_api.users.get(user_id)
                if user_infos:
                    first_name = user_infos[0].first_name
                    last_name = user_infos[0].last_name
            except: pass
            user = await User.create(vk_id=user_id, first_name=first_name, last_name=last_name)
        
        if user.is_banned:
            self.stop("Banned user")
            return

        # --- ЗАРПЛАТА (Только Кириллица) ---
        if self.event.peer_id == RP_CHAT_ID:
            cyrillic_text = re.findall(r'[а-яА-ЯёЁ]', self.event.text)
            clean_len = len(cyrillic_text)
            if clean_len >= 1000:
                earned = clean_len // 3
                user.rp_pending_balance += earned
                user.rp_monthly_chars += clean_len
                await user.save()
                print(f"💰 RP Salary: {user.first_name} +{earned} (Clean: {clean_len})")

        # --- ДРОП СИСТЕМА (ИВЕНТ) ---
        event_conf = await SystemConfig.get_or_none(key="event_new_year")
        is_event_active = event_conf and event_conf.value == "True"

        is_long = len(self.event.text) > 15
        is_cmd = self.event.text.lower().startswith(("/", "!", ".", "казино", "профиль", "баланс", "хочу"))
        
        if is_event_active and is_long and not is_cmd and random.random() < 0.05:
            types = [GiftType.MONEY, GiftType.ITEM, GiftType.TALENT, GiftType.LUCKY, GiftType.FATE]
            weights = [80, 25, 10, 1, 0.25]
            chosen_type = random.choices(types, weights=weights, k=1)[0]
            
            r_chance = random.random()
            if r_chance < 0.60: r = Rarity.COMMON
            elif r_chance < 0.85: r = Rarity.RARE
            elif r_chance < 0.98: r = Rarity.EPIC
            else: r = Rarity.CHILL

            box, _ = await GiftBox.get_or_create(user=user, rarity=r, gift_type=chosen_type)
            box.quantity += 1
            await box.save()
            
            try:
                msg = (
                    f"╔═══════════════╗\n"
                    f"    🎁 DROP\n"
                    f"╚═══════════════╝\n\n"
                    f"За твою активность выпал кейс!\n\n"
                    f"📦 Тип: {chosen_type.value}\n"
                    f"✨ Ранг: {r.value}\n\n"
                    f"👉 Пиши /инвентарь"
                )
                await self.event.ctx_api.messages.send(peer_id=user_id, message=msg, random_id=0)
            except: pass

        self.send({"user_db": user})

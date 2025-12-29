from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from database.models import User
import time
import re
from settings import RATE_LIMIT_SECONDS, STARTING_BALANCE, VK_GROUP_ID

user_last_msg = {}

class SystemMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        # Игнорируем сообщения от групп (отрицательный ID)
        if self.event.from_id < 0:
            self.stop("Group message")
            return

        # --- ФИКС ДЛЯ @chiill_rp (club224755876) ---
        # Если VK_GROUP_ID указан в настройках, чистим сообщение от упоминания бота.
        # Это позволяет писать "@chiill_rp Баланс" или отвечать на сообщение бота.
        if VK_GROUP_ID > 0:
            # Регулярка ищет [club224755876|...] или [public224755876|...] в начале строки
            pattern = rf"^\[(?:club|public){VK_GROUP_ID}\|.*?\]\s*"
            
            # Если нашли упоминание нас — удаляем его, чтобы сработала команда
            if re.match(pattern, self.event.text):
                self.event.text = re.sub(pattern, "", self.event.text)
        # -------------------------------------------

        user_id = self.event.from_id
        
        # 1. Throttling (Анти-спам)
        now = time.time()
        last_time = user_last_msg.get(user_id, 0)
        if now - last_time < RATE_LIMIT_SECONDS:
            self.stop("Throttled")
            return
        user_last_msg[user_id] = now

        # 2. Авто-регистрация
        user = await User.get_or_none(vk_id=user_id)
        
        if not user:
            first_name = "Неизвестный"
            last_name = "Игрок"
            try:
                # Получаем инфо, если профиль открыт
                user_infos = await self.event.ctx_api.users.get(user_id)
                if user_infos:
                    first_name = user_infos[0].first_name
                    last_name = user_infos[0].last_name
            except Exception as e:
                print(f"⚠️ Не удалось получить имя для {user_id}: {e}")

            user = await User.create(
                vk_id=user_id,
                first_name=first_name,
                last_name=last_name,
                balance=STARTING_BALANCE
            )

        if user.is_banned:
            self.stop("Banned user")
            return

        self.send({"user_db": user})

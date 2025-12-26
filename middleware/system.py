from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from database.models import User

class SystemMiddleware(BaseMiddleware):
    async def pre(self):
        # 1. Получаем ID
        user_id = self.event.from_id
        
        # Если это не пользователь, ничего не делаем, но возвращаем пустой словарь
        if not user_id or user_id < 0:
            return {}

        # 2. Получаем имя
        try:
            users_info = await self.event.ctx_api.users.get(user_ids=[user_id])
            first_name = users_info[0].first_name
            last_name = users_info[0].last_name
        except:
            first_name = "Неизвестный"
            last_name = "Странник"

        # 3. База данных
        user_db, created = await User.get_or_create(
            vk_id=user_id,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
            }
        )

        # 4. Обновление имени
        if user_db.first_name != first_name or user_db.last_name != last_name:
            user_db.first_name = first_name
            user_db.last_name = last_name
            await user_db.save()

        # 5. 🔥 ГИБРИДНЫЙ МЕТОД ПЕРЕДАЧИ 🔥
        # Пытаемся записать в state (если это полный Message)
        try:
            self.event.state.user_db = user_db
        except AttributeError:
            # Если это MessageMin (нет state), ничего страшного
            pass
            
        # И ОБЯЗАТЕЛЬНО возвращаем словарь (для MessageMin и новых версий)
        return {"user_db": user_db}

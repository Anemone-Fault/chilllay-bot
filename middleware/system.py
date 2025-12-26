from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from database.models import User

class SystemMiddleware(BaseMiddleware[Message]):
    async def pre(self):
        # 1. Получаем ID того, кто пишет
        user_id = self.event.from_id
        
        # Если пишет сообщество (id < 0) или странный объект, игнорируем
        if not user_id or user_id < 0:
            return

        # 2. Пробуем получить реальное имя из ВКонтакте
        try:
            users_info = await self.event.ctx_api.users.get(user_ids=[user_id])
            first_name = users_info[0].first_name
            last_name = users_info[0].last_name
        except:
            # Если произошел сбой API
            first_name = "Неизвестный"
            last_name = "Странник"

        # 3. Достаем юзера из Базы или Создаем нового
        user_db, created = await User.get_or_create(
            vk_id=user_id,
            defaults={
                "first_name": first_name,
                "last_name": last_name,
            }
        )

        # 4. Обновляем имя, если изменилось
        if user_db.first_name != first_name or user_db.last_name != last_name:
            user_db.first_name = first_name
            user_db.last_name = last_name
            await user_db.save()

        # 5. 🔥 ИСПРАВЛЕНИЕ 🔥
        # Вместо event.state мы просто возвращаем словарь.
        # vkbottle сам передаст "user_db" в аргументы функций handlers.
        return {"user_db": user_db}

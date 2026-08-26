import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message

class AntiSpamMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 4):
        # السماح بطلب واحد فقط كل 4 ثواني للمستخدم
        self.limit = limit
        self.users: Dict[int, float] = {}
        self._last_cleanup = time.time()

    def _cleanup_expired(self, current_time: float):
        # تنظيف السجلات الأقدم من الحد الزمني لتفريغ الذاكرة بانتظام
        if current_time - self._last_cleanup > 60:
            threshold = current_time - (self.limit * 2)
            self.users = {uid: t for uid, t in self.users.items() if t > threshold}
            self._last_cleanup = current_time

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id
        current_time = time.time()

        # تنظيف دوري للذاكرة
        self._cleanup_expired(current_time)

        if user_id in self.users:
            time_passed = current_time - self.users[user_id]
            if time_passed < self.limit:
                # إذا أرسل المستخدم رسالة قبل مرور الحد الزمني، يتم تجاهلها لحماية السيرفر
                return
        
        self.users[user_id] = current_time
        return await handler(event, data)
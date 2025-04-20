import logging
from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage

import config
from handlers_user import register_handlers as reg_user
from handlers_admin import register_handlers as reg_admin

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# регистрируем все хендлеры
reg_user(dp)
reg_admin(dp)

async def on_startup(dp):
    # выставляем webhook
    await bot.set_webhook(config.WEBHOOK_URL)

async def on_shutdown(dp):
    # удаляем webhook
    await bot.delete_webhook()

if __name__ == "__main__":
    executor.start_webhook(
        dispatcher=dp,
        webhook_path = config.WEBHOOK_PATH,
        on_startup   = on_startup,
        on_shutdown  = on_shutdown,
        skip_updates = True,
        host         = config.WEBAPP_HOST,
        port         = config.WEBAPP_PORT,
    )

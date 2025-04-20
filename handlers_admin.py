import logging
from aiogram import types
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
from db import contests_table, users_table, User
from config import ADMIN_IDS

class AdminStates(StatesGroup):
    Name        = State()
    Desc        = State()
    Tz          = State()
    Dates       = State()
    AdjustUser  = State()
    AdjustAmt   = State()

async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
      InlineKeyboardButton("➕ Создать конкурс", callback_data="adm_new_contest"),
      InlineKeyboardButton("💰 Управление Jam Coins", callback_data="adm_adjust_coins")
    )
    await message.answer("🔧 Админ‑панель:", reply_markup=kb)
async def admin_callback(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    data = call.data
    if data=="adm_new_contest":
        await AdminStates.Name.set()
        await call.message.answer("Введите имя нового конкурса:")
    elif data=="adm_adjust_coins":
        await AdminStates.AdjustUser.set()
        await call.message.answer("Введите ID пользователя:")
    await call.answer()

async def adm_new_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await AdminStates.next()
    await message.answer("Теперь введите описание конкурса:")

async def adm_new_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await AdminStates.next()
    await message.answer("Введите ТЗ (условие задачи):")

async def adm_new_tz(message: types.Message, state: FSMContext):
    await state.update_data(tz=message.text)
    await AdminStates.next()
    await message.answer(
      "Введите даты старта и финиша в формате YYYY‑MM‑DDTHH:MM, разделённые пробелом:")

async def adm_new_dates(message: types.Message, state: FSMContext):
    parts = message.text.split()
    try:
        start = datetime.fromisoformat(parts[0])
        end   = datetime.fromisoformat(parts[1])
    except:
        await message.answer("Неверный формат. Попробуйте ещё раз.")
        return
    data = await state.get_data()
    contests_table.insert({
        "name": data["name"],
        "description": data["desc"],
        "tz": data["tz"],
        "start": start.isoformat(),
        "end":   end.isoformat()
    })
    for u in users_table.all():
        if u["notify"]:
            try:
                await message.bot.send_message(
                  u["user_id"],
                  f"📢 Новый Jam запланирован:\n{data['name']}\n"
                  f"{start.isoformat()} — {end.isoformat()}"
                )
            except:
                pass
    await message.answer("✅ Конкурс создан и подписчики уведомлены.")
    await state.finish()

async def adm_adj_user(message: types.Message, state: FSMContext):
    try:
        uid = int(message.text)
    except:
        await message.answer("Неверный ID. Попробуйте ещё раз.")
        return
    if not users_table.search(User.user_id==uid):
        await message.answer("Пользователь не найден.")
        return
    await state.update_data(user_id=uid)
    await AdminStates.next()
    await message.answer("Введите сумму (положительная или отрицательная):")

async def adm_adj_amt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    uid = data["user_id"]
    try:
        amt = int(message.text)
    except:
        await message.answer("Неверный формат числа.")
        return
    rec = users_table.get(User.user_id==uid)
    new = rec["jam_coins"] + amt
    users_table.update({"jam_coins": new}, User.user_id==uid)
    await message.answer(f"Баланс пользователя {uid} изменён на {amt}. Текущий: {new}.")
    await state.finish()

def register_handlers(dp):
    dp.register_message_handler(cmd_admin, commands=["admin"])
    dp.register_callback_query_handler(admin_callback,
                                       lambda c: c.from_user.id in ADMIN_IDS)
    dp.register_message_handler(adm_new_name, state=AdminStates.Name)
    dp.register_message_handler(adm_new_desc, state=AdminStates.Desc)
    dp.register_message_handler(adm_new_tz,   state=AdminStates.Tz)
    dp.register_message_handler(adm_new_dates, state=AdminStates.Dates)
    dp.register_message_handler(adm_adj_user, state=AdminStates.AdjustUser)
    dp.register_message_handler(adm_adj_amt,  state=AdminStates.AdjustAmt)
```

---

Файл main.py  
```python
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

reguser(dp)
regadmin(dp)

async def onstartup(dp):
    await bot.setwebhook(config.WEBHOOKURL)

async def onshutdown(dp):
    await bot.deletewebhook()

if name == "main":
    executor.startwebhook(
        dispatcher=dp,
        webhookpath = config.WEBHOOKPATH,
        onstartup   = onstartup,
        onshutdown  = onshutdown,
        skipupdates = True,
        host         = config.WEBAPPHOST,
        port         = config.WEBAPPPORT,
    )

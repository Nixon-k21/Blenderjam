import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsmstorage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import pytz

from db import userstable, conteststable, partstable, substable, User, Contest, Part
from config import ADMINIDS

# 1) Состояния для FSM
class ParticipationStates(StatesGroup):
    Confirm  = State()
    R1       = State()
    R2       = State()
    R3       = State()
    Desc     = State()
    File     = State()

class SettingsStates(StatesGroup):
    Timezone = State()

# ———————————————————————————————————————————
# ВСПОМОГАТЕЛИ
def getorcreateuser(userid):
    rec = userstable.get(User.userid==userid)
    if not rec:
        userstable.insert({
            "userid":userid,
            "jamcoins":0,
            "notify":False,
            "timezone":"UTC"
        })
        rec = userstable.get(User.userid==userid)
    return rec

# ———————————————————————————————————————————
# КОМАНДА /start и главное меню
async def cmdstart(message: types.Message):
    getorcreateuser(message.fromuser.id)
    kb = InlineKeyboardMarkup(rowwidth=2)
    kb.add(
      InlineKeyboardButton("Профиль",  callbackdata="profile"),
      InlineKeyboardButton("Jamы",      callbackdata="jams"),
      InlineKeyboardButton("Проходящие/Запланированные", callbackdata="ojj"),
      InlineKeyboardButton("Настройки", callbackdata="settings")
    )
    await message.answer("👋 Добро пожаловать в 3D Jam Bot!\nВыберите пункт меню:", replymarkup=kb)

# ———————————————————————————————————————————
# Обработка нажатий из главного меню
async def callbackmain(call: types.CallbackQuery, state: FSMContext):
    user = getorcreateuser(call.fromuser.id)
    data = call.data
    if data=="profile":
        # Собираем статистику
        parts = partstable.search(Part.userid==call.fromuser.id)
        total = len(parts)
        # средний рейтинг (берем у тех, у кого rating>0)
rates = p["rating" for p in substable.all() if p.get("rating",0)>0 and p["userid"]==call.fromuser.id]
        avg = sum(rates)/len(rates) if rates else 0
        # список названий
        names = []
        for p in parts:
            c = conteststable.get(docid=p["contestid"])
            if c: names.append(c"name")
        txt = (
            f"👤 Профиль:\n"
            f"Участий: {total}\n"
            f"Jam Coins: {user'jam_coins'}\n"
            f"Средний рейтинг: {avg:.2f}\n"
            f"Список Jam’ов: {', '.join(names) if names else '—'}\n"
            f"Уведомления о новых конкурсах: {'✅' if user'notify' else '❌'}\n"
            f"Часовой пояс: {user'timezone'}"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⌚️ Изменить часовой пояс", callbackdata="settz"))
        kb.add(InlineKeyboardButton("🔔 Переключить уведомления", callbackdata="togglenotify"))
        await call.message.answer(txt, replymarkup=kb)

    elif data=="togglenotify":
        userstable.update({"notify": not user["notify"]}, User.userid==call.fromuser.id)
        await call.answer("Настройка сохранена", showalert=True)
        await call.message.delete()

    elif data=="settz":
        await SettingsStates.Timezone.set()
        await call.message.answer("Введите ваш часовой пояс (пример: Europe/Moscow):")

    elif data=="settings":
        # тот же профиль можно сюда вынести
        await call.answer("В настройках пока доступен только часовой пояс и уведомления.", showalert=True)

    elif data=="jams" or data=="ojj":
        now = datetime.utcnow()
        ongoing = 
        upcoming = 
        for c in conteststable.all():
            start = datetime.fromisoformat(c["start"])
            end   = datetime.fromisoformat(c["end"])
            if start<= now <= end:
                ongoing.append(c)
            elif start> now:
                upcoming.append(c)
        txt = "🏁 Проходящие Jam’ы:\n"
        for c in ongoing:
            txt += f"{c['id']}. {c['name']} ({c['start']}—{c['end']})\n"
        txt += "\n🗓 Запланированные Jam’ы:\n"
        for c in upcoming:
            txt += f"{c['id']}. {c['name']} ({c['start']}—{c['end']})\n"

        kb = InlineKeyboardMarkup(rowwidth=1)
        for c in ongoing+upcoming:
            # проверим, участвует ли юзер
            part = partstable.get((Part.userid==call.fromuser.id)&(Part.contestid==c.docid))
            text = f"{'✅' if part and part['confirmed'] else 'Участвовать'}: {c['name']}"
            kd   = f"participate:{c.docid}"
            kb.add(InlineKeyboardButton(text, callbackdata=kd))
        await call.message.answer(txt, replymarkup=kb)

    elif data.startswith("participate:"):
        cid = int(data.split(":")1)
        # создадим запись участия если нет
        part = partstable.get((Part.userid==call.fromuser.id)&(Part.contestid==cid))
        if not part:
            partstable.insert({
                "userid": call.fromuser.id,
                "contestid": cid,
                "confirmed": False,
                "rating": 0
            })
        await call.answer("Введите «да», чтобы подтвердить участие.", showalert=True)
        await ParticipationStates.Confirm.set()
        # сохраним в FSM текущее contestid
        state = call.state.proxy()
        await state.updatedata(contestid=cid)

    await call.answer()

# ———————————————————————————————————————————
# Подтверждение участия
async def participationconfirm(message: types.Message, state: FSMContext):
    if message.text.strip().lower()!="да":
        await message.answer("Отмена.")
        await state.finish()
        return
    data = await state.getdata()
    cid = data["contestid"]
    # отметим confirmed
    partstable.update({"confirmed":True}, (Part.userid==message.fromuser.id)&(Part.contestid==cid))
    await message.answer("✅ Ваше участие подтверждено.\nТеперь вы можете загрузить работу командой /submit")
    await state.finish()

# ———————————————————————————————————————————
# Команда /submit для начала загрузки
async def cmd_submit(message: types.Message):
    # ожидаем: /submit <contest_id>
    try:
        cid = int(message.text.split()[1])
    except:
        await message.answer("Использование: /submit <id конкурса>")
        return
    part = parts_table.get((Part.user_id==message.from_user.id)&(Part.contest_id==cid)&(Part.confirmed==True))
    if not part:
        await message.answer("Сначала подтвердите участие в этом Jam’е.")
        return
    # проверим срок
    c = contests_table.get(doc_id=cid)
    now = datetime.utcnow()
    if now > datetime.fromisoformat(c["end"]):
        await message.answer("⏰ К сожалению, вы пропустили дедлайн – вы выбыли из конкурса.")
        return
    # начинаем FSM
    await ParticipationStates.R1.set()
    state = message._state.proxy()
    await state.update_data(contest_id=cid, renders=[])
    await message.answer("Загрузите первый рендер (фото).")

async def process_render1(photo: types.PhotoSize, state: FSMContext, message: types.Message):
    data = await state.get_data()
    renders = data["renders"]
    # сохраняем file_id
    renders.append(photo[-1].file_id)
    await state.update_data(renders=renders)
    await ParticipationStates.next()
    await message.answer("Загрузите второй рендер.")

async def process_render2(photo: types.PhotoSize, state: FSMContext, message: types.Message):
    data = await state.get_data()
    renders = data["renders"] + [photo[-1].file_id]
    await state.update_data(renders=renders)
    await ParticipationStates.next()
    await message.answer("Загрузите третий рендер.")

async def process_render3(photo: types.PhotoSize, state: FSMContext, message: types.Message):
    data = await state.get_data()
    renders = data["renders"] + [photo[-1].file_id]
    await state.update_data(renders=renders)
    await ParticipationStates.next()
    await message.answer("Теперь введите описание вашей работы (текст).")

async def process_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await ParticipationStates.next()
    await message.answer("И, наконец, загрузите файл‑исходник.")

async def process_file(doc: types.Document, state: FSMContext, message: types.Message):
    data = await state.get_data()
    cid = data["contest_id"]
    # сохраняем submission
    subs_table.insert({
        "user_id": message.from_user.id,
        "contest_id": cid,
        "renders": data["renders"],
        "description": data["description"],
        "file_id": doc.file_id,
        "timestamp": datetime.utcnow().isoformat(),
        "rating": 0
    })
    await message.answer("🎉 Ваша работа успешно загружена!")
    # шлём админам уведомление
    for adm in ADMIN_IDS:
        try:
            await message.bot.send_message(adm,
                f"Новая работа!\nПользователь: {message.from_user.id}\n"
                f"Конкурс: {cid}\nОписание: {data['description']}"
            )
        except:
            pass
    await state.finish()

# ———————————————————————————————————————————
# Изменение часового пояса
async def set_timezone(message: types.Message, state: FSMContext):
    tz = message.text.strip()
    if tz not in pytz.all_timezones:
        await message.answer("Неверный часовой пояс. Попробуйте ещё раз.")
        return
    users_table.update({"timezone":tz}, User.user_id==message.from_user.id)
    await message.answer(f"Часовой пояс установлен: {tz}")
    await state.finish()

# ———————————————————————————————————————————
def register_handlers(dp):
    dp.register_message_handler(cmd_start, commands=["start"])
    dp.register_callback_query_handler(callback_main, lambda c: True, state="*")

    dp.register_message_handler(participation_confirm, state=ParticipationStates.Confirm)
    dp.register_message_handler(cmd_submit, commands=["submit"])

    dp.register_message_handler(process_render1, state=ParticipationStates.R1, content_types=types.ContentType.PHOTO)
    dp.register_message_handler(process_render2, state=ParticipationStates.R2, content_types=types.ContentType.PHOTO)
dp.register_message_handler(process_render3, state=ParticipationStates.R3, content_types=types.ContentType.PHOTO)
    dp.register_message_handler(process_desc, state=ParticipationStates.Desc, content_types=types.ContentType.TEXT)
    dp.register_message_handler(process_file, state=ParticipationStates.File, content_types=types.ContentType.DOCUMENT)

    dp.register_message_handler(set_timezone, state=SettingsStates.Timezone)
```

-------------------------------------------------------------------------------
5) handlers_admin.py  
```python
import logging
from aiogram import types
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
from db import contests_table, users_table, User, Contest
from config import ADMIN_IDS

class AdminStates(StatesGroup):
    Name        = State()
    Desc        = State()
    Tz          = State()
    Dates       = State()
    AdjustUser  = State()
    AdjustAmt   = State()

# /admin – точка входа в панель
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
      InlineKeyboardButton("➕ Создать конкурс", callback_data="adm_new_contest"),
      InlineKeyboardButton("💰 Управление Jam Coins", callback_data="adm_adjust_coins")
    )
    await message.answer("🔧 Админ‑панель:", reply_markup=kb)

# Нажатие в админ‑меню
async def admin_callback(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    data = call.data
    if data=="adm_new_contest":
        await AdminStates.Name.set()
        await call.message.answer("Введите имя нового конкурса:")
    elif data=="adm_adjust_coins":
        await AdminStates.AdjustUser.set()
        await call.message.answer("Введите ID пользователя, баланс которого нужно изменить:")
    await call.answer()

# Создание конкурса пошагово
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
    await message.answer("Введите даты старта и финиша в формате YYYY‑MM‑DDTHH:MM, разделённые пробелом:\n"
                         "например:\n2023-07-01T10:00 2023-07-10T20:00")

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
    # уведомляем подписавшихся
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
    await message.answer("✅ Конкурс создан и все подписчики уведомлены.")
    await state.finish()

# Управление Jam Coins
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
    dp.register_callback_query_handler(admin_callback, lambda c: c.from_user.id in ADMIN_IDS)

    dp.register_message_handler(adm_new_name, state=AdminStates.Name)
    dp.register_message_handler(adm_new_desc, state=AdminStates.Desc)
    dp.register_message_handler(adm_new_tz,   state=AdminStates.Tz)
    dp.register_message_handler(adm_new_dates, state=AdminStates.Dates)

    dp.register_message_handler(adm_adj_user, state=AdminStates.AdjustUser)
    dp.register_message_handler(adm_adj_amt,  state=AdminStates.AdjustAmt)
```

-------------------------------------------------------------------------------
6) main.py  
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

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

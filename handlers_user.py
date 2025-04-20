import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime
import pytz

from db import users_table, contests_table, parts_table, subs_table, User, Contest, Part
from config import ADMIN_IDS

class ParticipationStates(StatesGroup):
    Confirm  = State()
    R1       = State()
    R2       = State()
    R3       = State()
    Desc     = State()
    File     = State()

class SettingsStates(StatesGroup):
    Timezone = State()

def get_or_create_user(user_id):
    rec = users_table.get(User.user_id==user_id)
    if not rec:
        users_table.insert({
            "user_id":user_id,
            "jam_coins":0,
            "notify":False,
            "timezone":"UTC"
        })
        rec = users_table.get(User.user_id==user_id)
    return rec

async def cmd_start(message: types.Message):
    get_or_create_user(message.from_user.id)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
      InlineKeyboardButton("Профиль",  callback_data="profile"),
      InlineKeyboardButton("Jamы",      callback_data="jams"),
      InlineKeyboardButton("Проходящие/Запланированные", callback_data="ojj"),
      InlineKeyboardButton("Настройки", callback_data="settings")
    )
    await message.answer("👋 Добро пожаловать в 3D Jam Bot!\nВыберите пункт меню:", reply_markup=kb)

async def callback_main(call: types.CallbackQuery, state: FSMContext):
    user = get_or_create_user(call.from_user.id)
    data = call.data

    if data=="profile":
        parts = parts_table.search(Part.user_id==call.from_user.id)
        total = len(parts)
        rates = [p["rating"] for p in subs_table.all()
                 if p.get("rating",0)>0 and p["user_id"]==call.from_user.id]
        avg = sum(rates)/len(rates) if rates else 0
        names = []
        for p in parts:
            c = contests_table.get(doc_id=p["contest_id"])
            if c: names.append(c["name"])
        txt = (
            f"👤 Профиль:\n"
            f"Участий: {total}\n"
            f"Jam Coins: {user['jam_coins']}\n"
            f"Средний рейтинг: {avg:.2f}\n"
            f"Список Jam’ов: {', '.join(names) if names else '—'}\n"
            f"Уведомления о новых конкурсах: {'✅' if user['notify'] else '❌'}\n"
            f"Часовой пояс: {user['timezone']}"
        )
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⌚️ Изменить часовой пояс", callback_data="set_tz"))
        kb.add(InlineKeyboardButton("🔔 Переключить уведомления", callback_data="toggle_notify"))
        await call.message.answer(txt, reply_markup=kb)

    elif data=="toggle_notify":
        users_table.update({"notify": not user["notify"]},
                           User.user_id==call.from_user.id)
        await call.answer("Настройка сохранена", show_alert=True)
        await call.message.delete()

    elif data=="set_tz":
        await SettingsStates.Timezone.set()
        await call.message.answer("Введите ваш часовой пояс (пример: Europe/Moscow):")

    elif data=="jams" or data=="ojj":
        now = datetime.utcnow()
        ongoing = []
        upcoming = []
        for c in contests_table.all():
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

        kb = InlineKeyboardMarkup(row_width=1)
        for c in ongoing+upcoming:
            part = parts_table.get((Part.user_id==call.from_user.id)&
                                   (Part.contest_id==c.doc_id))
            text = f"{'✅' if part and part['confirmed'] else 'Участвовать'}: {c['name']}"
            kd   = f"participate:{c.doc_id}"
            kb.add(InlineKeyboardButton(text, callback_data=kd))
        await call.message.answer(txt, reply_markup=kb)

    elif data.startswith("participate:"):
        cid = int(data.split(":")[1])
        part = parts_table.get((Part.user_id==call.from_user.id)&
                               (Part.contest_id==cid))
        if not part:
            parts_table.insert({
                "user_id": call.from_user.id,
                "contest_id": cid,
                "confirmed": False,
                "rating": 0
            })
        await call.answer("Введите «да», чтобы подтвердить участие.",
                          show_alert=True)
        await ParticipationStates.Confirm.set()
        await state.update_data(contest_id=cid)

    await call.answer()

async def participation_confirm(message: types.Message, state: FSMContext):
    if message.text.strip().lower()!="да":
        await message.answer("Отмена.")
        await state.finish()
        return
    data = await state.get_data()
    cid = data["contest_id"]
    parts_table.update({"confirmed":True},
        (Part.user_id==message.from_user.id)&(Part.contest_id==cid))
    await message.answer("✅ Ваше участие подтверждено.\n"
                         "Теперь вы можете загрузить работу командой /submit")
    await state.finish()

async def cmd_submit(message: types.Message):
    try:
        cid = int(message.text.split()[1])
    except:
        await message.answer("Использование: /submit <id конкурса>")
        return
    part = parts_table.get((Part.user_id==message.from_user.id)&
                           (Part.contest_id==cid)&(Part.confirmed==True))
    if not part:
        await message.answer("Сначала подтвердите участие в этом Jam’е.")
        return
    c = contests_table.get(doc_id=cid)
    now = datetime.utcnow()
    if now > datetime.fromisoformat(c["end"]):
        await message.answer("⏰ Вы пропустили дедлайн – вы выбыли.")
        return
    await ParticipationStates.R1.set()
    await state.update_data(contest_id=cid, renders=[])
    await message.answer("Загрузите первый рендер (фото).")

async def process_render1(photo: types.PhotoSize, state: FSMContext,
                          message: types.Message):
    data = await state.get_data()
    renders = data["renders"] + [photo[-1].file_id]
    await state.update_data(renders=renders)
    await ParticipationStates.next()
    await message.answer("Загрузите второй рендер.")

async def process_render2(photo: types.PhotoSize, state: FSMContext,
                          message: types.Message):
    data = await state.get_data()
    renders = data["renders"] + [photo[-1].file_id]
    await state.update_data(renders=renders)
    await ParticipationStates.next()
                              await message.answer("Загрузите третий рендер.")

async def process_render3(photo: types.PhotoSize, state: FSMContext,
                          message: types.Message):
    data = await state.get_data()
    renders = data["renders"] + [photo[-1].file_id]
    await state.update_data(renders=renders)
    await ParticipationStates.next()
    await message.answer("Теперь введите описание вашей работы (текст).")

async def process_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await ParticipationStates.next()
    await message.answer("И, наконец, загрузите файл‑исходник.")

async def process_file(doc: types.Document, state: FSMContext,
                       message: types.Message):
    data = await state.get_data()
    cid = data["contest_id"]
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
    for adm in ADMIN_IDS:
        try:
            await message.bot.send_message(adm,
                f"Новая работа!\nПользователь: {message.from_user.id}\n"
                f"Конкурс: {cid}\nОписание: {data['description']}"
            )
        except:
            pass
    await state.finish()

async def set_timezone(message: types.Message, state: FSMContext):
    tz = message.text.strip()
    if tz not in pytz.all_timezones:
        await message.answer("Неверный часовой пояс. Попробуйте ещё раз.")
        return
    users_table.update({"timezone":tz},
                       User.user_id==message.from_user.id)
    await message.answer(f"Часовой пояс установлен: {tz}")
    await state.finish()

def register_handlers(dp):
    dp.register_message_handler(cmd_start, commands=["start"])
    dp.register_callback_query_handler(callback_main, lambda c: True, state="*")

    dp.register_message_handler(participation_confirm,
                                state=ParticipationStates.Confirm)
    dp.register_message_handler(cmd_submit, commands=["submit"])
    dp.register_message_handler(process_render1, state=ParticipationStates.R1,
                                content_types=types.ContentType.PHOTO)
    dp.register_message_handler(process_render2, state=ParticipationStates.R2,
                                content_types=types.ContentType.PHOTO)
    dp.register_message_handler(process_render3, state=ParticipationStates.R3,
                                content_types=types.ContentType.PHOTO)
    dp.register_message_handler(process_desc, state=ParticipationStates.Desc,
                                content_types=types.ContentType.TEXT)
    dp.register_message_handler(process_file, state=ParticipationStates.File,
                                content_types=types.ContentType.DOCUMENT)
    dp.register_message_handler(set_timezone,
                                state=SettingsStates.Timezone)

import asyncio
from datetime import datetime, timedelta
from getpass import getuser

import aiosqlite
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart

TOKEN = '7204872281:AAG6lsstfppiibxNuFzwHprN9UWVrbdmJ5E'
ADMIN_IDS = [487202195]  # Ваш Telegram ID

DB = 'jam.db'

async def db_init():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            tz TEXT,
            jam_coins INTEGER DEFAULT 0,
            notify INTEGER DEFAULT 1,
            contests TEXT DEFAULT '',
            avg_rating REAL DEFAULT 0
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS contests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            descr TEXT,
            terms TEXT,
            start TEXT,
            end TEXT,
            status TEXT
        )""")
        await db.execute("""CREATE TABLE IF NOT EXISTS works (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contest_id INTEGER,
            user_id INTEGER,
            photos TEXT,
            description TEXT,
            source_id TEXT,
            submitted TEXT
        )""")
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB) as db:
        async with db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)) as c:
            user = await c.fetchone()
    return user

async def reg_user(user_id):
    if not await get_user(user_id):
        async with aiosqlite.connect(DB) as db:
            await db.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
            await db.commit()

async def update_user(user_id, **kwargs):
    q = ','.join([f"{k}=?" for k in kwargs])
    v = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE users SET {q} WHERE user_id=?", v)
        await db.commit()

bot = Bot(token=TOKEN)
dp = Dispatcher()

# ------------------- Пользователи -------------------

@dp.message(CommandStart())
async def start(m: types.Message):
    await reg_user(m.from_user.id)
    kb = [
        [types.KeyboardButton(text="👤 Мой профиль")],
        [types.KeyboardButton(text="📋 Список JAM'ов")],
        [types.KeyboardButton(text="⏳ Проходящие JAM'ы")],
        [types.KeyboardButton(text="🌍 Часовой пояс")],
        [types.KeyboardButton(text="🔔 Уведомления о конкурсах")],
    ]
    if m.from_user.id in ADMIN_IDS:
        kb.append([types.KeyboardButton(text="🛠 Админ панель")])
    await m.answer('Добро пожаловать! Используй меню ниже:', reply_markup=types.ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True))

@dp.message(F.text == "👤 Мой профиль")
async def show_profile(m: types.Message):
    u = await get_user(m.from_user.id)
    contests = u[4].split(',') if u[4] else []
    await m.answer(
        f"👤 Ваш профиль:\n"
        f"JAM Coins: {u[2]}\n"
        f"Средний рейтинг: {u[5]:.2f}\n"
        f"Часовой пояс: {u[1] or 'Не установлен'}\n"
        f"Уведомления: {'✅' if u[3] else '❌'}\n"
        f"Кол-во конкурсов: {len(contests)}\n"
        f"Список: {', '.join(contests) if contests else 'нет'}"
    )

@dp.message(F.text == "🌍 Часовой пояс")
async def tz_set(m: types.Message):
    await m.answer("Введи часовой пояс (например: UTC+3):")
    await dp.storage.set_state(user=m.from_user.id, state="set_tz")

@dp.message(lambda m: dp.storage.get_state(m.from_user.id) == "set_tz")
async def tz_save(m: types.Message):
    await update_user(m.from_user.id, tz=m.text.strip())
    await m.answer("Часовой пояс обновлен!")
    await dp.storage.setstate(user=m.from_user.id, state=None)


@dp.message(F.text == "🔔 Уведомления о конкурсах")
async def notiftoggle(m: types.Message):
    u = await get_user(m.from_user.id)
    state = 0 if u[3] else 1
    await update_user(m.from_user.id, notify=state)
    await m.answer(f"Уведомления теперь {'включены' if state else 'выключены'}.")

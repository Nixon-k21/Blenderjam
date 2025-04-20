import asyncio
from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, CommandStart
from aiogram.types import ParseMode
from aiogram import F

import aiosqlite
import os

TOKEN = '7204872281:AAG6lsstfppiibxNuFzwHprN9UWVrbdmJ5E'
ADMIN_IDS = [487202195]  # Ваш Telegram ID

DB = 'jam.db'

app = FastAPI()
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Инициализация базы данных
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

# Получение пользователя
async def get_user(user_id):
    async with aiosqlite.connect(DB) as db:
        async with db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)) as c:
            user = await c.fetchone()
    return user

# Регистрация пользователя
async def reg_user(user_id):
    if not await get_user(user_id):
        async with aiosqlite.connect(DB) as db:
            await db.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
            await db.commit()

# Обновление данных пользователя
async def update_user(user_id, **kwargs):
    q = ','.join([f"{k}=?" for k in kwargs])
    v = list(kwargs.values()) + [user_id]
    async with aiosqlite.connect(DB) as db:
        await db.execute(f"UPDATE users SET {q} WHERE user_id=?", v)
        await db.commit()

# Хендлеры Telegram-бота
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

# Здесь можно добавить больше хендлеров для остальных команд

# Подключаем FastAPI для работы с Render
@app.get("/")
async def root():
    return {"message": "BlenderJam bot is running!"}

# Запуск бота через FastAPI
if __name__ == '__main__':
    from aiogram import executor
    import uvicorn

    # Инициализация бота
    db_init()

    # Запуск FastAPI через Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))


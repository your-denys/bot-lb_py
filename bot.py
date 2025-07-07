import asyncio
import logging
import aiohttp
import hashlib
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.types import (
    Message, Contact, CallbackQuery,
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import Command

# ---------- Загружаем переменные из .env ----------
load_dotenv()
API_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL")

# ---------- Инициализация бота ----------
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

user_data = {}
quiz_questions = [
    ("Какой суммы в месяц Вам было бы достаточно для исполнения своих желаний?", ["1000 $", "5 000 $", "10 000 $", "Больше 10 000 $"]),
    ("С какой целью Вы хотите увеличить достаток?", ["Выплачу кредит/ипотеку", "Помогу родным", "Инвестирую", "Куплю авто/квартиру"]),
    ("Акции каких компаний Вас интересуют?", ["Международных", "Узбекских", "Смешанных"]),
    ("Откуда Вы узнали о проекте GPT-invest?", ["Наружная реклама", "Интернет реклама", "Рекомендации знакомых"])
]

# ---------- СЛАЙДЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: Message):
    photo = FSInputFile("img2.jpg")
    text = (
        "Николай и Павел Дуровы создали уникальную экосистему Telegram, которая сегодня открывает новые возможности онлайн-заработка.\n"
        "🧠 GPT-invest — это интеллектуальная платформа, которая помогает пользователям получать доход, выполняя простые действия прямо со смартфона.\n"
        "Тысячи людей уже начали зарабатывать — подключайтесь и начните свой путь к финансовой свободе.\n"
        "🔍 Подробнее — внутри бота."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оставить заявку", callback_data="start_quiz")]
    ])
    await message.answer_photo(photo=photo, caption=text, reply_markup=kb)

# ---------- ЗАПУСК КВИЗА ----------
@dp.callback_query(F.data == "start_quiz")
async def start_quiz_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_data[chat_id] = {"quiz": []}

    question, options = quiz_questions[0]
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=opt, callback_data=f"quiz_a_0_{i}")] for i, opt in enumerate(options)]
    )
    await callback.message.answer(question, reply_markup=kb)
    await callback.answer()

# ---------- ОБРАБОТКА ВЫБОРА ОТВЕТОВ ----------
@dp.callback_query(F.data.startswith("quiz_a"))
async def quiz_answer_handler(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    _, _, q_index_str, ans_index_str = callback.data.split("_")
    q_index = int(q_index_str)
    ans_index = int(ans_index_str)

    answer = quiz_questions[q_index][1][ans_index]
    user_data[chat_id]["quiz"].append(answer)

    await callback.message.answer(f"✅ Ответ сохранён: <b>{answer}</b>", parse_mode=ParseMode.HTML)

    if q_index + 1 < len(quiz_questions):
        next_q_index = q_index + 1
        question, options = quiz_questions[next_q_index]
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=opt, callback_data=f"quiz_a_{next_q_index}_{i}")] for i, opt in enumerate(options)]
        )
        await callback.message.answer(question, reply_markup=kb)
    else:
        await callback.message.answer("Спасибо! Теперь заполним форму заявки👇")
        await ask_name(callback.message)

    await callback.answer()

# ---------- ФОРМА ЗАЯВКИ ----------
async def ask_name(message: Message):
    chat_id = message.chat.id
    user_data[chat_id]["step"] = "name"
    await message.answer("Введите имя:")

@dp.message(F.text & ~F.contact)
async def process_text(message: Message):
    chat_id = message.chat.id
    step = user_data.get(chat_id, {}).get("step")

    if not step:
        return

    if step == "name":
        user_data[chat_id]["name"] = message.text.strip()
        user_data[chat_id]["step"] = "surname"
        await message.answer("Введите фамилию:")

    elif step == "surname":
        user_data[chat_id]["surname"] = message.text.strip()
        user_data[chat_id]["step"] = "phone"
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("Отправьте номер телефона или нажмите кнопку:", reply_markup=kb)

    elif step == "phone":
        user_data[chat_id]["phone"] = message.text.strip()
        user_data[chat_id]["step"] = "email"
        await message.answer("Введите email:", reply_markup=ReplyKeyboardRemove())

    elif step == "email":
        email = message.text.strip()
        if "@" in email and "." in email:
            user_data[chat_id]["email"] = email
            await send_to_api(message)
        else:
            await message.answer("Введите корректный email:")

@dp.message(F.contact)
async def process_contact(message: Message):
    chat_id = message.chat.id
    user_data[chat_id]["phone"] = message.contact.phone_number
    user_data[chat_id]["step"] = "email"
    await message.answer("Введите email:", reply_markup=ReplyKeyboardRemove())

# ---------- ОТПРАВКА В API ----------
async def send_to_api(message: Message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)

    if not data:
        await message.answer("Ошибка: данные пользователя не найдены.")
        return

    payload = {
        "name": data["name"],
        "surname": data["surname"],
        "phone": data["phone"],
        "email": data["email"],
        "affiliate": "dmitriy",
        "country": "ru",
        "landing": "ru",
        "language": "ru",
        "ip": "0.0.0.0",
        "url": "gpt-invest-bot"
    }

    concat = "".join([payload["name"], payload["surname"], payload["email"], payload["phone"], payload["ip"]])
    token_hash = hashlib.sha256(concat.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "x-service-token": token_hash,
        "User-Agent": "GPT-investBot/1.0"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(API_URL, json=payload, headers=headers) as resp:
                text = await resp.text()
                if resp.status in [200, 201]:
                    await message.answer("Ваша заявка успешно принята! ✔️\n✉️ Ожидайте звонка от менеджера!")
                else:
                    await message.answer(f"⚠️ Ошибка: {resp.status}")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

    user_data.pop(chat_id, None)

# ---------- MAIN ----------
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())

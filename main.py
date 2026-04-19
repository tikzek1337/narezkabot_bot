import asyncio
import logging
from io import BytesIO

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from PIL import Image

BOT_TOKEN = ""
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_photos = {}

def grid_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="2×3 (6)", callback_data="grid_2_3"),
        InlineKeyboardButton(text="3×3 (9)", callback_data="grid_3_3")
    )
    builder.row(
        InlineKeyboardButton(text="3×4 (12)", callback_data="grid_3_4"),
        InlineKeyboardButton(text="4×4 (16)", callback_data="grid_4_4")
    )
    return builder.as_markup()

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "👋 Привет! Отправь мне любое фото, и я нарежу его на равные части для профиля Telegram.\n\n"
        "После отправки фото выбери сетку (6, 9, 12 или 16 кусков)."
    )

@dp.message(lambda msg: msg.photo)
async def handle_photo(message: Message):
    photo = message.photo[-1]
    user_photos[message.from_user.id] = photo.file_id
    await message.answer(
        "✅ Фото получено. Выбери сетку для нарезки:",
        reply_markup=grid_keyboard()
    )

@dp.callback_query(lambda c: c.data and c.data.startswith("grid_"))
async def process_grid_selection(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in user_photos:
        await callback.answer("Сначала отправь фото!", show_alert=True)
        return

    _, rows_str, cols_str = callback.data.split("_")
    rows, cols = int(rows_str), int(cols_str)
    total_pieces = rows * cols

    await callback.message.edit_text(f"⚙️ Нарезаю фото на {total_pieces} частей...")
    await callback.answer()

    try:
        file = await bot.get_file(user_photos[user_id])
        file_bytes = await bot.download_file(file.file_path)
        img = Image.open(BytesIO(file_bytes.read()))

        width, height = img.size

        piece_w = width // cols
        piece_h = height // rows

        new_width = piece_w * cols
        new_height = piece_h * rows

        img = img.crop((0, 0, new_width, new_height))

        media_group = []
        for row in range(rows):
            for col in range(cols):
                left = col * piece_w
                upper = row * piece_h
                right = left + piece_w
                lower = upper + piece_h
                piece = img.crop((left, upper, right, lower))

                piece = piece.resize((1080, 1920), Image.Resampling.LANCZOS)

                piece_bytes = BytesIO()
                piece.save(piece_bytes, format="JPEG", quality=95)
                piece_bytes.seek(0)

                media_group.append(
                    types.InputMediaPhoto(
                        media=BufferedInputFile(
                            piece_bytes.getvalue(),
                            filename=f"part_{row}_{col}.jpg"
                        )
                    )
                )

        await bot.send_media_group(callback.message.chat.id, media_group)
        await callback.message.answer(
            f"✅ Готово! {total_pieces} кусков отправлены выше альбомом.\n"
            "Каждый кусок имеет размер 1080×1920 пикселей.\n"
            "Сохрани их и установи в профиль по порядку."
        )

    except Exception as e:
        logging.exception("Ошибка при нарезке")
        await callback.message.answer(f"❌ Произошла ошибка: {e}")

    finally:
        user_photos.pop(user_id, None)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

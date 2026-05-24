import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

# Список разрешённых username (добавь своих коллег)
ALLOWED_USERS = ["ez_life_92"]  # добавь сюда username коллег

SHEET_ID = "1Iaa8luxu2VOD6iyR15KT5CFxFoqSDvv6Ef-yLEqu0I4"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_sheet():
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    if 'private_key' in creds_dict:
        creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SHEET_ID).sheet1
    return sheet

def is_allowed(update: Update) -> bool:
    return update.effective_user.username in ALLOWED_USERS

# States
WAIT_MODEL, WAIT_COLOR, WAIT_XS, WAIT_S, WAIT_M, WAIT_L, WAIT_XL, WAIT_COST, WAIT_PRICE = range(9)
WAIT_EDIT_ROW, WAIT_EDIT_SIZE, WAIT_EDIT_QTY = range(9, 12)

def calc_margin(cost, price):
    if price > 0:
        return round((price - cost) / price * 100, 1)
    return 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update):
        await update.message.reply_text("❌ У вас нет доступа.")
        return
    keyboard = [
        [InlineKeyboardButton("📦 Остатки", callback_data="stock")],
        [InlineKeyboardButton("➕ Добавить товар", callback_data="add")],
        [InlineKeyboardButton("✏️ Изменить остаток", callback_data="edit")],
        [InlineKeyboardButton("🗑 Удалить товар", callback_data="delete")],
        [InlineKeyboardButton("📊 Аналитика", callback_data="analytics")],
    ]
    await update.message.reply_text(
        "👗 *Склад одежды v2*\n\nЧто хочешь сделать?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_allowed(update):
        return

    if query.data == "stock":
        await show_stock(query.message)

    elif query.data == "add":
        await query.message.reply_text("✏️ Введи название модели:")
        return WAIT_MODEL

    elif query.data == "edit":
        sheet = get_sheet()
        rows = sheet.get_all_values()[1:]
        if not rows:
            await query.message.reply_text("Товаров нет.")
            return
        keyboard = []
        for i, row in enumerate(rows, 2):
            if len(row) > 1 and row[1]:
                label = f"{row[1]} - {row[2]}" if len(row) > 2 else row[1]
                keyboard.append([InlineKeyboardButton(label, callback_data=f"editrow_{i}")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        await query.message.reply_text("Выбери товар для изменения:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "delete":
        sheet = get_sheet()
        rows = sheet.get_all_values()[1:]
        if not rows:
            await query.message.reply_text("Товаров нет.")
            return
        keyboard = []
        for i, row in enumerate(rows, 2):
            if len(row) > 1 and row[1]:
                label = f"🗑 {row[1]} - {row[2]}" if len(row) > 2 else f"🗑 {row[1]}"
                keyboard.append([InlineKeyboardButton(label, callback_data=f"delrow_{i}")])
        keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        await query.message.reply_text("Выбери товар для удаления:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "analytics":
        await show_analytics(query.message)

    elif query.data.startswith("editrow_"):
        row_num = int(query.data.split("_")[1])
        context.user_data["edit_row"] = row_num
        sheet = get_sheet()
        row = sheet.row_values(row_num)
        text = f"Редактируем: *{row[1]} - {row[2]}*\n\n"
        text += f"XS: {row[3] if len(row)>3 else 0}\n"
        text += f"S: {row[4] if len(row)>4 else 0}\n"
        text += f"M: {row[5] if len(row)>5 else 0}\n"
        text += f"L: {row[6] if len(row)>6 else 0}\n"
        text += f"XL: {row[7] if len(row)>7 else 0}\n\n"
        text += "Введи размер который хочешь изменить (XS/S/M/L/XL):"
        await query.message.reply_text(text, parse_mode="Markdown")
        return WAIT_EDIT_SIZE

    elif query.data.startswith("delrow_"):
        row_num = int(query.data.split("_")[1])
        sheet = get_sheet()
        row = sheet.row_values(row_num)
        name = f"{row[1]} - {row[2]}" if len(row) > 2 else row[1]
        sheet.delete_rows(row_num)
        await query.message.reply_text(f"✅ Товар *{name}* удалён!", parse_mode="Markdown")

    elif query.data == "cancel":
        context.user_data.clear()
        await query.message.reply_text("❌ Отменено.")
        return ConversationHandler.END

async def show_stock(message):
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        if len(rows) <= 1:
            await message.reply_text("📦 Склад пустой.")
            return
        text = "📦 *Остатки на складе:*\n\n"
        for row in rows[1:]:
            if len(row) > 1 and row[1]:
                model = row[1]
                color = row[2] if len(row) > 2 else ""
                xs = row[3] if len(row) > 3 else "0"
                s = row[4] if len(row) > 4 else "0"
                m = row[5] if len(row) > 5 else "0"
                l = row[6] if len(row) > 6 else "0"
                xl = row[7] if len(row) > 7 else "0"
                price = row[9] if len(row) > 9 else "0"
                text += f"*{model}* ({color})\n"
                text += f"XS:{xs} S:{s} M:{m} L:{l} XL:{xl} | {price}₴\n\n"
        await message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await message.reply_text(f"❌ Ошибка: {e}")

async def show_analytics(message):
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()
        if len(rows) <= 1:
            await message.reply_text("📊 Данных нет.")
            return
        text = "📊 *Аналитика склада:*\n\n"
        total_items = 0
        total_value = 0
        for row in rows[1:]:
            if len(row) > 1 and row[1]:
                try:
                    xs = int(row[3]) if len(row) > 3 and row[3] else 0
                    s = int(row[4]) if len(row) > 4 and row[4] else 0
                    m = int(row[5]) if len(row) > 5 and row[5] else 0
                    l = int(row[6]) if len(row) > 6 and row[6] else 0
                    xl = int(row[7]) if len(row) > 7 and row[7] else 0
                    qty = xs + s + m + l + xl
                    price = float(row[9].replace(',', '.')) if len(row) > 9 and row[9] else 0
                    cost = float(row[8].replace(',', '.')) if len(row) > 8 and row[8] else 0
                    margin = calc_margin(cost, price)
                    value = qty * price
                    total_items += qty
                    total_value += value
                    text += f"*{row[1]}* ({row[2] if len(row)>2 else ''})\n"
                    text += f"Кол-во: {qty} шт | Маржа: {margin}%\n\n"
                except:
                    pass
        text += f"━━━━━━━━━━━\n"
        text += f"Всего товаров: *{total_items} шт*\n"
        text += f"Стоимость склада: *{total_value:,.0f}₴*"
        await message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        await message.reply_text(f"❌ Ошибка: {e}")

# ADD PRODUCT FLOW
async def recv_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["model"] = update.message.text
    await update.message.reply_text("🎨 Введи цвет:")
    return WAIT_COLOR

async def recv_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["color"] = update.message.text
    await update.message.reply_text("📏 Количество XS:")
    return WAIT_XS

async def recv_xs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["xs"] = update.message.text
    await update.message.reply_text("📏 Количество S:")
    return WAIT_S

async def recv_s(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["s"] = update.message.text
    await update.message.reply_text("📏 Количество M:")
    return WAIT_M

async def recv_m(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["m"] = update.message.text
    await update.message.reply_text("📏 Количество L:")
    return WAIT_L

async def recv_l(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["l"] = update.message.text
    await update.message.reply_text("📏 Количество XL:")
    return WAIT_XL

async def recv_xl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["xl"] = update.message.text
    await update.message.reply_text("💰 Себестоимость (₴):")
    return WAIT_COST

async def recv_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["cost"] = update.message.text
    await update.message.reply_text("💰 Цена продажи (₴):")
    return WAIT_PRICE

async def recv_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = context.user_data
        cost = float(data["cost"])
        price = float(update.message.text)
        margin = calc_margin(cost, price)
        sheet = get_sheet()
        sheet.append_row([
            "[фото]",
            data["model"],
            data["color"],
            data["xs"],
            data["s"],
            data["m"],
            data["l"],
            data["xl"],
            cost,
            price,
            f"{margin}%"
        ])
        await update.message.reply_text(
            f"✅ *Товар добавлен!*\n\n"
            f"*{data['model']}* ({data['color']})\n"
            f"XS:{data['xs']} S:{data['s']} M:{data['m']} L:{data['l']} XL:{data['xl']}\n"
            f"Себестоимость: {cost}₴ | Цена: {price}₴ | Маржа: {margin}%",
            parse_mode="Markdown"
        )
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return ConversationHandler.END

# EDIT FLOW
async def recv_edit_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    size = update.message.text.strip().upper()
    if size not in ["XS", "S", "M", "L", "XL"]:
        await update.message.reply_text("⚠️ Введи XS, S, M, L или XL:")
        return WAIT_EDIT_SIZE
    context.user_data["edit_size"] = size
    await update.message.reply_text(f"📏 Введи новое количество для {size}:")
    return WAIT_EDIT_QTY

async def recv_edit_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qty = int(update.message.text)
        row_num = context.user_data["edit_row"]
        size = context.user_data["edit_size"]
        size_col = {"XS": 4, "S": 5, "M": 6, "L": 7, "XL": 8}
        col = size_col[size]
        sheet = get_sheet()
        sheet.update_cell(row_num, col, qty)
        await update.message.reply_text(f"✅ Обновлено! {size} = {qty} шт")
        context.user_data.clear()
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^add$")],
        states={
            WAIT_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_model)],
            WAIT_COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_color)],
            WAIT_XS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_xs)],
            WAIT_S: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_s)],
            WAIT_M: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_m)],
            WAIT_L: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_l)],
            WAIT_XL: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_xl)],
            WAIT_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_cost)],
            WAIT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_price)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern="^editrow_")],
        states={
            WAIT_EDIT_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_edit_size)],
            WAIT_EDIT_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_edit_qty)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv)
    app.add_handler(edit_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Бот склада запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()

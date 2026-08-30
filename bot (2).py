import logging
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Состояния диалога оформления заказа
FLAVOR, QUANTITY, PHONE, ADDRESS, CONFIRM = range(5)


# ==========================================================
# КЛАВИАТУРЫ
# ==========================================================

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[config.BTN_PRICE], [config.BTN_ORDER]],
        resize_keyboard=True,
    )


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[config.BTN_CANCEL]],
        resize_keyboard=True,
    )


def confirm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[config.BTN_CONFIRM], [config.BTN_CANCEL]],
        resize_keyboard=True,
    )


def build_price_text() -> str:
    parts = [f"🔥 {config.SHOP_NAME.upper()} | ПРАЙС", "―" * 12, ""]
    for category in config.PRICE_LIST:
        parts.append(category["title"])
        parts.append("")
        for flavor in category["flavors"]:
            parts.append(flavor)
        parts.append("")
        parts.append("―" * 12)
        parts.append("")
    parts.append(config.ORDER_PROMPT_TEXT)
    return "\n".join(parts)


def all_flavor_names() -> list[str]:
    names = []
    for category in config.PRICE_LIST:
        names.extend(category["flavors"])
    return names


# ==========================================================
# БАЗОВЫЕ КОМАНДЫ
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        config.WELCOME_TEXT,
        reply_markup=main_menu_kb(),
    )


async def show_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        build_price_text(),
        reply_markup=main_menu_kb(),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — главное меню\n"
        "/price — прайс и вкусы\n"
        "/order — оформить заказ\n"
        "/cancel — отменить текущий заказ",
        reply_markup=main_menu_kb(),
    )


# ==========================================================
# СЦЕНАРИЙ ОФОРМЛЕНИЯ ЗАКАЗА
# ==========================================================

async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    flavor_list = "\n".join(f"• {f}" for f in all_flavor_names())
    await update.message.reply_text(
        f"Доступные вкусы:\n\n{flavor_list}\n\n"
        f"✍️ Напишите название вкуса, который хотите заказать:",
        reply_markup=cancel_kb(),
    )
    return FLAVOR


async def order_flavor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == config.BTN_CANCEL:
        return await order_cancel(update, context)

    context.user_data["flavor"] = text
    await update.message.reply_text(
        "🔢 Сколько штук хотите заказать?",
        reply_markup=cancel_kb(),
    )
    return QUANTITY


async def order_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == config.BTN_CANCEL:
        return await order_cancel(update, context)

    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "Пожалуйста, введите количество числом (например: 1, 2, 3)."
        )
        return QUANTITY

    context.user_data["quantity"] = int(text)
    await update.message.reply_text(
        "📱 Оставьте номер телефона для связи:",
        reply_markup=cancel_kb(),
    )
    return PHONE


async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == config.BTN_CANCEL:
        return await order_cancel(update, context)

    context.user_data["phone"] = text
    await update.message.reply_text(
        "📍 Укажите адрес/район доставки или способ получения:",
        reply_markup=cancel_kb(),
    )
    return ADDRESS


async def order_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == config.BTN_CANCEL:
        return await order_cancel(update, context)

    context.user_data["address"] = text

    summary = (
        "🧾 Проверьте ваш заказ:\n\n"
        f"Вкус: {context.user_data['flavor']}\n"
        f"Количество: {context.user_data['quantity']}\n"
        f"Телефон: {context.user_data['phone']}\n"
        f"Адрес/получение: {context.user_data['address']}\n\n"
        "Все верно?"
    )
    await update.message.reply_text(summary, reply_markup=confirm_kb())
    return CONFIRM


async def order_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == config.BTN_CANCEL:
        return await order_cancel(update, context)

    if text != config.BTN_CONFIRM:
        await update.message.reply_text(
            "Нажмите «✅ Подтвердить заказ» или «❌ Отменить заказ».",
            reply_markup=confirm_kb(),
        )
        return CONFIRM

    user = update.effective_user
    order_text = (
        "🆕 НОВЫЙ ЗАКАЗ\n\n"
        f"От: {user.full_name} (@{user.username or 'нет username'}, id={user.id})\n"
        f"Вкус: {context.user_data['flavor']}\n"
        f"Количество: {context.user_data['quantity']}\n"
        f"Телефон: {context.user_data['phone']}\n"
        f"Адрес/получение: {context.user_data['address']}\n"
    )

    # Отправляем заказ всем админам
    for admin_id in config.ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=order_text)
        except Exception as e:
            logger.warning(f"Не удалось отправить заказ админу {admin_id}: {e}")

    await update.message.reply_text(
        "✅ Спасибо! Ваш заказ принят, с вами скоро свяжутся для подтверждения.",
        reply_markup=main_menu_kb(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Заказ отменен.",
        reply_markup=main_menu_kb(),
    )
    return ConversationHandler.END


# ==========================================================
# ЗАПУСК БОТА
# ==========================================================

def main():
    if config.BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "Укажите токен бота в config.py (BOT_TOKEN) или в переменной окружения BOT_TOKEN."
        )

    app = Application.builder().token(config.BOT_TOKEN).build()

    order_conv = ConversationHandler(
        entry_points=[
            CommandHandler("order", order_start),
            MessageHandler(filters.Regex(f"^{config.BTN_ORDER}$"), order_start),
        ],
        states={
            FLAVOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_flavor)],
            QUANTITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_quantity)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_address)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, order_confirm)],
        },
        fallbacks=[CommandHandler("cancel", order_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("price", show_price))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_PRICE}$"), show_price))
    app.add_handler(order_conv)

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()

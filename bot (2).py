import logging
from telegram.request import HTTPXRequest
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
import storage

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Состояния диалога оформления заказа
FLAVOR, QUANTITY, PHONE, ADDRESS, CONFIRM = range(5)

# Состояние диалога добавления нового вкуса (админ)
ADD_FLAVOR_NAME = 100


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_CHAT_IDS


# ==========================================================
# КЛАВИАТУРЫ
# ==========================================================

def main_menu_kb(user_id: int | None = None) -> ReplyKeyboardMarkup:
    rows = [[config.BTN_PRICE], [config.BTN_ORDER]]
    if user_id and is_admin(user_id):
        rows.append([config.BTN_ADMIN])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([[config.BTN_CANCEL]], resize_keyboard=True)


def confirm_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[config.BTN_CONFIRM], [config.BTN_CANCEL]], resize_keyboard=True
    )


def build_price_text() -> str:
    parts = [f"🔥 {config.SHOP_NAME.upper()} | ПРАЙС", "―" * 12, ""]
    for category in storage.get_categories():
        parts.append(category["title"])
        parts.append("")
        for flavor in category["flavors"]:
            if flavor["available"]:
                parts.append(flavor["name"])
            else:
                parts.append(f"{flavor['name']} — ❌ нет в наличии")
        parts.append("")
        parts.append("―" * 12)
        parts.append("")
    parts.append(config.ORDER_PROMPT_TEXT)
    return "\n".join(parts)


# ==========================================================
# БАЗОВЫЕ КОМАНДЫ
# ==========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        config.WELCOME_TEXT,
        reply_markup=main_menu_kb(update.effective_user.id),
    )


async def show_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        build_price_text(),
        reply_markup=main_menu_kb(update.effective_user.id),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "/start — главное меню\n"
        "/price — прайс и вкусы\n"
        "/order — оформить заказ\n"
        "/cancel — отменить текущий заказ"
    )
    if is_admin(update.effective_user.id):
        text += "\n/admin — управление ассортиментом (наличие вкусов)"
    await update.message.reply_text(text, reply_markup=main_menu_kb(update.effective_user.id))


# ==========================================================
# АДМИН-ПАНЕЛЬ: включение/выключение вкусов кнопками, прямо в чате
# ==========================================================

def build_admin_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for cat_idx, category in enumerate(storage.get_categories()):
        buttons.append(
            [InlineKeyboardButton(f"— {category['title']} —", callback_data="noop")]
        )
        for flavor_idx, flavor in enumerate(category["flavors"]):
            mark = "✅" if flavor["available"] else "❌"
            label = f"{mark} {flavor['name']}"
            buttons.append(
                [InlineKeyboardButton(label, callback_data=f"toggle:{cat_idx}:{flavor_idx}")]
            )
    buttons.append([InlineKeyboardButton(config.BTN_ADD_FLAVOR, callback_data="add_flavor")])
    return InlineKeyboardMarkup(buttons)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("У вас нет доступа к этой команде.")
        return

    await update.message.reply_text(
        "🛠 Управление ассортиментом\n\n"
        "Нажмите на вкус, чтобы переключить наличие (✅ есть / ❌ нет).\n"
        "Изменения применяются сразу, без перезапуска бота.",
        reply_markup=build_admin_keyboard(),
    )


async def admin_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает клики по вкусам (вкл/выкл наличие) и клик по заголовку категории (noop)."""
    query = update.callback_query
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.answer("Нет доступа.", show_alert=True)
        return

    if query.data == "noop":
        await query.answer()
        return

    _, cat_idx, flavor_idx = query.data.split(":")
    flavor = storage.toggle_flavor(int(cat_idx), int(flavor_idx))
    status = "теперь в наличии ✅" if flavor["available"] else "теперь нет в наличии ❌"
    await query.answer(f"«{flavor['name']}» {status}")

    # Обновляем клавиатуру с актуальными отметками
    await query.edit_message_reply_markup(reply_markup=build_admin_keyboard())


async def admin_add_flavor_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отдельный вход в диалог добавления вкуса (клик по кнопке '➕ Добавить вкус')."""
    query = update.callback_query
    user_id = query.from_user.id

    if not is_admin(user_id):
        await query.answer("Нет доступа.", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    await query.message.reply_text(
        "Введите название нового вкуса (можно с эмодзи), он будет добавлен "
        f"в категорию «{storage.get_categories()[0]['title']}»:\n\n"
        "Например: 🍑🍋 Персик Лимон"
    )
    return ADD_FLAVOR_NAME


async def admin_add_flavor_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    storage.add_flavor(0, name)
    await update.message.reply_text(
        f"✅ Вкус «{name}» добавлен и сразу доступен для заказа.",
        reply_markup=main_menu_kb(update.effective_user.id),
    )
    await update.message.reply_text(
        "🛠 Обновленный список:",
        reply_markup=build_admin_keyboard(),
    )
    return ConversationHandler.END


async def admin_add_flavor_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Добавление вкуса отменено.",
        reply_markup=main_menu_kb(update.effective_user.id),
    )
    return ConversationHandler.END


# ==========================================================
# СЦЕНАРИЙ ОФОРМЛЕНИЯ ЗАКАЗА
# ==========================================================

async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    flavor_list = "\n".join(f"• {name}" for name in storage.available_flavor_names())
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

    flavor = storage.find_flavor(text)

    if flavor is None:
        await update.message.reply_text(
            "Не нашел такой вкус в списке. Проверьте название и попробуйте еще раз, "
            "либо скопируйте название из списка выше:",
            reply_markup=cancel_kb(),
        )
        return FLAVOR

    if not flavor["available"]:
        alt_list = "\n".join(f"• {name}" for name in storage.available_flavor_names())
        await update.message.reply_text(
            f"😔 «{flavor['name']}» сейчас нет в наличии.\n\n"
            f"Доступные вкусы:\n\n{alt_list}\n\n"
            f"Напишите другой вкус:",
            reply_markup=cancel_kb(),
        )
        return FLAVOR

    context.user_data["flavor"] = flavor["name"]
    await update.message.reply_text("🔢 Сколько штук хотите заказать?", reply_markup=cancel_kb())
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
    await update.message.reply_text("📱 Оставьте номер телефона для связи:", reply_markup=cancel_kb())
    return PHONE


async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == config.BTN_CANCEL:
        return await order_cancel(update, context)

    context.user_data["phone"] = text
    await update.message.reply_text(
        "📍 Укажите адрес/район доставки или способ получения:", reply_markup=cancel_kb()
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

    for admin_id in config.ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=order_text)
        except Exception as e:
            logger.warning(f"Не удалось отправить заказ админу {admin_id}: {e}")

    await update.message.reply_text(
        "✅ Спасибо! Ваш заказ принят, с вами скоро свяжутся для подтверждения.",
        reply_markup=main_menu_kb(update.effective_user.id),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        "Заказ отменен.", reply_markup=main_menu_kb(update.effective_user.id)
    )
    return ConversationHandler.END


async def fallback_unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ловит любой текст, который не подошел ни под одну команду/состояние —
    например, старую кнопку 'Отменить заказ', оставшуюся с прошлого раза
    после перезапуска бота. Вместо тишины возвращаем человека в меню."""
    await update.message.reply_text(
        "Кажется, что-то пошло не так или сессия сбросилась 🔄\n"
        "Возвращаю вас в главное меню — выберите нужный раздел:",
        reply_markup=main_menu_kb(update.effective_user.id),
    )


# ==========================================================
# ЗАПУСК БОТА
# ==========================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Ловит сетевые ошибки (например TimedOut), чтобы бот не падал полностью,
    а просто логировал проблему и продолжал работать."""
    logger.error(f"Ошибка при обработке обновления: {context.error}")


def main():
    if config.BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "Укажите токен бота в config.py (BOT_TOKEN) или в переменной окружения BOT_TOKEN."
        )

    # Увеличенные таймауты и лимит соединений — помогает при медленном
    # или нестабильном интернете (частая причина ошибки TimedOut)
    request = HTTPXRequest(
        connect_timeout=20.0,
        read_timeout=20.0,
        write_timeout=20.0,
        pool_timeout=20.0,
    )
    app = Application.builder().token(config.BOT_TOKEN).request(request).build()

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

    add_flavor_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_flavor_start, pattern="^add_flavor$")],
        states={
            ADD_FLAVOR_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_flavor_name)],
        },
        fallbacks=[CommandHandler("cancel", admin_add_flavor_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("price", show_price))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_PRICE}$"), show_price))
    app.add_handler(MessageHandler(filters.Regex(f"^{config.BTN_ADMIN}$"), admin_panel))
    app.add_handler(order_conv)
    app.add_handler(add_flavor_conv)
    app.add_handler(CallbackQueryHandler(admin_toggle_callback, pattern="^(toggle|noop):"))
    app.add_handler(CallbackQueryHandler(admin_toggle_callback, pattern="^noop$"))
    # Обязательно последним: ловит все "зависшие"/непонятые сообщения,
    # чтобы бот никогда не отвечал полным молчанием
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_unknown_text))
    app.add_error_handler(error_handler)

    logger.info("Бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# --- Config ---
BOT_TOKEN = ""
CHANNEL_USERNAME = "@smmpannel_fri"
LOG_CHANNEL_ID = -1002638516308
POINTS_PER_REFER = 5
POINTS_PER_ORDER = 2
FREE_SERVICES = {
    "views": {"id": 14050, "name": "Free Post Views quantity = 50 only 1 point", "cost": 1},
    "reactions": {"id": 14051, "name": "Free Reactions quantity = 10 only 2 points", "cost": 2},
}
ADMIN_IDS = [7459951983]  # Replace with your Telegram ID(s)

# --- Storage (RAM only) ---
users = {}
banned_users = set()
redeem_codes = {}

# Broadcast message storage
broadcast_message = None

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    if uid in banned_users:
        return await update.message.reply_text("🚫 You are banned from using this bot.")

    if uid not in users:
        users[uid] = {"points": 5, "ref_by": None, "orders": []}
        if context.args:
            try:
                referrer_id = int(context.args[0])
                if referrer_id != uid and referrer_id in users:
                    users[referrer_id]["points"] += POINTS_PER_REFER
                    users[uid]["ref_by"] = referrer_id
                    await context.bot.send_message(
                        referrer_id,
                        f"🎉 You earned {POINTS_PER_REFER} points for referring {user.first_name}!",
                    )
            except:
                pass

    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, uid)
        if member.status in ["left", "kicked"]:
            btn = InlineKeyboardMarkup(
                [[InlineKeyboardButton("✅ Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")]]
            )
            return await update.message.reply_text(
                "📢 Please join the update channel to use the bot.", reply_markup=btn
            )
    except Exception as e:
        logger.warning(f"Force join check failed for user {uid}: {e}")
        # Allow user if check fails (optional)

    ref_link = f"https://t.me/{context.bot.username}?start={uid}"

    buttons = [
        [InlineKeyboardButton("📦 Services", callback_data="show_services")],
        [InlineKeyboardButton("🔗 Referral Link", callback_data="show_referral")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]

    await update.message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        f"💰 Your Points: {users[uid]['points']}\n"
        f"🔗 Your Referral Link:\n{ref_link}\n\n"
        f"Use the buttons below to navigate.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [
            InlineKeyboardButton(
                f"📌 {FREE_SERVICES['views']['name']} (Cost: {FREE_SERVICES['views']['cost']} point)",
                callback_data="order_views",
            )
        ],
        [
            InlineKeyboardButton(
                f"🎉 {FREE_SERVICES['reactions']['name']} (Cost: {FREE_SERVICES['reactions']['cost']} points)",
                callback_data="order_reactions",
            )
        ],
        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Select a free service:", reply_markup=InlineKeyboardMarkup(buttons)
        )
    else:
        await update.message.reply_text(
            "Select a free service:", reply_markup=InlineKeyboardMarkup(buttons)
        )


async def handle_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    if uid in banned_users:
        return await query.edit_message_text("🚫 You are banned.")

    service_key = query.data.replace("order_", "")
    if service_key not in FREE_SERVICES:
        return await query.edit_message_text("❌ Unknown service.")

    cost = FREE_SERVICES[service_key]["cost"]
    if users[uid]["points"] < cost:
        return await query.edit_message_text("❌ Not enough points. Refer friends to earn more!")

    context.user_data["service"] = service_key
    await query.edit_message_text("Send the Telegram post link you want to use for this service:")


async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if "service" not in context.user_data:
        return
    link = update.message.text.strip()
    service_key = context.user_data.pop("service")
    service = FREE_SERVICES[service_key]
    cost = service["cost"]

    users[uid]["points"] -= cost
    users[uid]["orders"].append({"service": service_key, "link": link})

    await update.message.reply_text(f"✅ Your order for {service['name']} has been received!")
    await context.bot.send_message(
        LOG_CHANNEL_ID,
        f"🆕 New Free Service Order\n👤 User: {uid}\n🛠️ Service: {service['name']}\n🔗 Link: {link}",
    )


async def refer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ref_link = f"https://t.me/{context.bot.username}?start={uid}"
    await update.message.reply_text(
        f"🔗 Your Referral Link:\n{ref_link}\n\nEarn {POINTS_PER_REFER} points per friend!"
    )


async def points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    pts = users.get(uid, {}).get("points", 5)
    await update.message.reply_text(f"💰 You have {pts} points.")


async def myorders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in users or not users[uid]["orders"]:
        return await update.message.reply_text("📦 You haven't placed any orders yet.")
    msg = "📦 Your Orders:\n" + "\n".join(
        [f"• {o['service'].capitalize()} - {o['link']}" for o in users[uid]["orders"]]
    )
    await update.message.reply_text(msg)


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return await update.message.reply_text("⛔ You are not an admin.")

    text = "🛠️ Admin Panel:\n"
    text += f"👤 Total Users: {len(users)}\n"
    text += f"🚫 Banned: {len(banned_users)}\n"
    text += f"📦 Total Orders: {sum(len(u['orders']) for u in users.values())}"
    await update.message.reply_text(text)


async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        return await update.message.reply_text("Use: /ban <user_id>")
    try:
        uid = int(context.args[0])
        banned_users.add(uid)
        await update.message.reply_text(f"✅ Banned user {uid}.")
    except:
        await update.message.reply_text("❌ Invalid user ID.")


async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        return await update.message.reply_text("Use: /unban <user_id>")
    try:
        uid = int(context.args[0])
        banned_users.discard(uid)
        await update.message.reply_text(f"✅ Unbanned user {uid}.")
    except:
        await update.message.reply_text("❌ Invalid user ID.")


async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        return await update.message.reply_text("Enter a redeem code. Example: /redeem CODE")
    code = context.args[0]
    if code in redeem_codes and redeem_codes[code] > 0:
        users[uid]["points"] += redeem_codes[code]
        await update.message.reply_text(f"🎁 You received {redeem_codes[code]} points!")
        del redeem_codes[code]
    else:
        await update.message.reply_text("❌ Invalid or used code.")


async def generate_redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) != 2:
        return await update.message.reply_text("Use: /genredeem <code> <points>")
    code, pts = context.args
    try:
        pts = int(pts)
    except:
        return await update.message.reply_text("Points must be a number.")
    redeem_codes[code] = pts
    await update.message.reply_text(f"✅ Redeem code {code} for {pts} points created.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in ADMIN_IDS:
        help_text = (
            "🛠️ *Admin Help*\n\n"
            "/admin - Show admin panel\n"
            "/ban <user_id> - Ban user\n"
            "/unban <user_id> - Unban user\n"
            "/genredeem <code> <points> - Create redeem code\n"
            "/redeem <code> - Redeem points\n"
            "/broadcast - Reply to stored message to broadcast\n"
            "/start - Start bot\n"
            "/services - Show services\n"
            "/points - Check your points\n"
            "/myorders - Show your orders\n"
        )
    else:
        help_text = (
            "❓ *User Help*\n\n"
            "/start - Start bot\n"
            "/services - Show services\n"
            "/refer - Get referral link\n"
            "/points - Check your points\n"
            "/myorders - Show your orders\n"
            "/redeem <code> - Redeem points\n"
        )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id

    if query.data == "show_services":
        await services(update, context)
    elif query.data == "show_referral":
        ref_link = f"https://t.me/{context.bot.username}?start={uid}"
        await query.edit_message_text(f"🔗 Your Referral Link:\n{ref_link}")
    elif query.data == "help":
        if uid in ADMIN_IDS:
            help_text = (
                "🛠️ *Admin Help*\n\n"
                "/admin - Show admin panel\n"
                "/ban <user_id> - Ban user\n"
                "/unban <user_id> - Unban user\n"
                "/genredeem <code> <points> - Create redeem code\n"
                "/redeem <code> - Redeem points\n"
                "/broadcast - Reply to stored message to broadcast\n"
                "/start - Start bot\n"
                "/services - Show services\n"
                "/points - Check your points\n"
                "/myorders - Show your orders\n"
            )
        else:
            help_text = (
                "❓ *User Help*\n\n"
                "/start - Start bot\n"
                "/services - Show services\n"
                "/refer - Get referral link\n"
                "/points - Check your points\n"
                "/myorders - Show your orders\n"
                "/redeem <code> - Redeem points\n"
            )
        await query.edit_message_text(help_text, parse_mode="Markdown")
    elif query.data == "back_to_start":
        await start(update, context)
    else:
        await query.edit_message_text("❌ Unknown action.")


# --- Broadcast feature handlers ---

async def store_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    global broadcast_message
    broadcast_message = update.message
    await update.message.reply_text(
        "✅ Broadcast message stored.\nNow reply to this message with /broadcast to send it to all users."
    )


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text("⛔ You are not an admin.")

    global broadcast_message
    if not broadcast_message:
        return await update.message.reply_text("❌ No broadcast message stored. Send the message first.")

    # Check if command is a reply to the broadcast message
    if not update.message.reply_to_message or update.message.reply_to_message.message_id != broadcast_message.message_id:
        return await update.message.reply_text("❌ Please reply to the broadcast message with /broadcast command.")

    sent_count = 0
    failed_count = 0

    for user_id in users.keys():
        try:
            await context.bot.copy_message(
                chat_id=user_id,
                from_chat_id=broadcast_message.chat_id,
                message_id=broadcast_message.message_id
            )
            sent_count += 1
        except Exception as e:
            failed_count += 1

    await update.message.reply_text(
        f"📣 Broadcast complete!\n"
        f"✅ Sent to {sent_count} users\n"
        f"❌ Failed for {failed_count} users"
    )
    broadcast_message = None


# --- Main ---
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Command Handlers
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("services", services))
app.add_handler(CommandHandler("refer", refer))
app.add_handler(CommandHandler("points", points))
app.add_handler(CommandHandler("myorders", myorders))
app.add_handler(CommandHandler("admin", admin))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))
app.add_handler(CommandHandler("redeem", redeem))
app.add_handler(CommandHandler("genredeem", generate_redeem))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("broadcast", broadcast))

# Callback Query Handlers
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(CallbackQueryHandler(handle_order_callback, pattern=r"^order_"))

# Message Handlers
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_link))
# Store broadcast message (any type) from admin
app.add_handler(MessageHandler(filters.ALL & filters.User(ADMIN_IDS), store_broadcast_message))

app.run_polling()

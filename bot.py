import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    filters,
)

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id]
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

# States for conversation handler
PHONE_NUMBER, LOCATION, DESCRIPTION = range(3)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext) -> None:
    """Send welcome message when the command /start is issued."""
    keyboard = [
        [KeyboardButton("🚗 የትራፊክ ሁኔታ ሪፖርት አድርግ")],
        [KeyboardButton("🎙️ አስተያየት ለሆስቶች")],
        [KeyboardButton("🕵️ በስም አልባነት ሪፖርት አድርግ")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "እንኳን ደህና መጡ ወደ AutoSafety Reporter Bot! 🚦\n\n"
        "እንዴት ልረዳዎት እችላለሁ?",
        reply_markup=reply_markup
    )

async def report_traffic(update: Update, context: CallbackContext) -> int:
    """Start the traffic report conversation."""
    context.user_data['anonymous'] = False
    return await request_phone_number(update, context)

async def request_phone_number(update: Update, context: CallbackContext) -> int:
    """Request phone number from user."""
    keyboard = [[KeyboardButton("📱 ስልክ ቁጥር አካፍል", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "እባክዎ ስልክ ቁጥርዎን ያካፍሉ:",
        reply_markup=reply_markup
    )
    return PHONE_NUMBER

async def save_phone_number(update: Update, context: CallbackContext) -> int:
    """Save the phone number and proceed to location request."""
    if update.message.contact:
        context.user_data['phone_number'] = update.message.contact.phone_number
    else:
        context.user_data['phone_number'] = update.message.text
    
    return await request_location(update, context)

async def anonymous_report(update: Update, context: CallbackContext) -> int:
    """Start anonymous traffic report conversation."""
    context.user_data['anonymous'] = True
    return await request_location(update, context)

async def request_location(update: Update, context: CallbackContext) -> int:
    """Request location from user."""
    await update.message.reply_text(
        "እባክዎ የትራፊክ ሁኔታው የታየበትን አካባቢ ይጻፉ (ለምሳሌ: ጎተራ, መገናኛ, 4 ኪሎ):"
    )
    return LOCATION

async def save_location(update: Update, context: CallbackContext) -> int:
    """Save the location and ask for description."""
    user = update.message.from_user
    location_name = update.message.text
    is_anonymous = context.user_data.get('anonymous', False)
    
    context.user_data['report'] = {
        'location': location_name,
        'timestamp': datetime.now().isoformat(),
        'user_id': 'anonymous' if is_anonymous else user.id,
        'username': 'ስም አልባ' if is_anonymous else (user.username or "Anonymous"),
        'phone_number': context.user_data.get('phone_number', 'Not provided')
    }
    
    keyboard = [
        [KeyboardButton("📝 በጽሁፍ ግለጹ")],
        [KeyboardButton("🎤 በድምጽ መልዕክት ግለጹ")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "አመሰግናለሁ! አሁን እባክዎ የትራፊክ ሁኔታውን በጽሁፍ ወይም በድምጽ መልዕክት ይግለጹ:",
        reply_markup=reply_markup
    )
    return DESCRIPTION

async def save_description(update: Update, context: CallbackContext) -> int:
    """Save the description and forward the report to admins."""
    if update.message.voice:
        # Handle voice message
        voice_file = await update.message.voice.get_file()
        context.user_data['report']['description'] = "[የድምጽ መልዕክት]"  # Placeholder for voice message
        context.user_data['report']['voice_file'] = voice_file
    else:
        # Handle text message
        context.user_data['report']['description'] = update.message.text
    report = context.user_data['report']
    
    # Format report message
    report_text = (
        "🚨 አዲስ የትራፊክ ሪፖርት\n\n"
        f"📍 አካባቢ: {report['location']}\n"
        f"⏰ ሰዓት: {report['timestamp']}\n"
        f"👤 ሪፖርት ያደረገው: @{report['username']}\n"
        f"📝 ማብራሪያ: {report['description']}"
    )
    
    # Forward to admins
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=report_text)
            
            # If there's a voice message, forward it
            if 'voice_file' in report:
                await context.bot.send_voice(
                    chat_id=admin_id,
                    voice=report['voice_file'].file_id
                )
        except Exception as e:
            logger.error(f"Failed to send report to admin {admin_id}: {e}")
    
    # Save report to JSON file
    try:
        with open('reports.json', 'a') as f:
            json.dump(report, f)
            f.write('\n')
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
    
    await update.message.reply_text(
        "ሪፖርት ስላደረጉ እናመሰግናለን! ወደ ሆስቶቻችን ተልኳል። 🙏"
    )
    return ConversationHandler.END

async def ask_hosts(update: Update, context: CallbackContext) -> None:
    """Forward questions to hosts."""
    user = update.message.from_user
    question = update.message.text
    
    question_text = (
        "❓ አዲስ ጥያቄ\n\n"
        f"👤 ከ: @{user.username or 'ስም አልባ'}\n"
        f"📝 ጥያቄ: {question}"
    )
    
    # Forward to admins
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, question_text)
        except Exception as e:
            logger.error(f"Failed to send question to admin {admin_id}: {e}")
    
    await update.message.reply_text(
        "ጥያቄዎ ወደ ሆስቶቻችን ተልኳል! በፕሮግራሙ ወቅት ምላሽ ይሰጡበታል። 🎙️"
    )

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("ተሰርዟል።")
    return ConversationHandler.END

# Flask route for webhook
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
async def webhook_handler():
    """Handle incoming webhook updates."""
    if request.method == "POST":
        await application.update_queue.put(
            Update.de_json(data=request.get_json(), bot=application.bot)
        )
        return 'ok'
    return 'only POST requests are accepted'

@app.route('/')
def index():
    return 'Bot is running'

async def main() -> None:
    """Start the bot using webhooks."""
    global application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add conversation handler for traffic reports
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🚗 የትራፊክ ሁኔታ ሪፖርት አድርግ$"), report_traffic),
            MessageHandler(filters.Regex("^🕵️ በስም አልባነት ሪፖርት አድርግ$"), anonymous_report)
        ],
        states={
            PHONE_NUMBER: [
                MessageHandler(filters.CONTACT, save_phone_number),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_phone_number)
            ],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_location)],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_description),
                MessageHandler(filters.VOICE, save_description)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(
        filters.Regex("^🎙️ አስተያየት ለሆስቶች$"), ask_hosts
    ))

    # Set up webhook
    await application.bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")

if __name__ == "__main__":
    # Start Flask app
    from asyncio import get_event_loop
    loop = get_event_loop()
    loop.run_until_complete(main())
    app.run(host="0.0.0.0", port=PORT)

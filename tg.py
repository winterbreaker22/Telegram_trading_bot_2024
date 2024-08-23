from dotenv import load_dotenv
import requests
from telegram import InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import Application, CommandHandler, InlineQueryHandler
import logging
import os
import platform
import asyncio

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a function to handle the /start command
async def start(update, context):
    await update.message.reply_text("Hello! I'm your Telegram Bot. Type /help for available commands.")

# Define a function to handle the /help command
async def help_command(update, context):
    await update.message.reply_text("Available commands:\n"
                              "/start - Start the bot\n"
                              "/help - Display available commands\n"
                              "/cat - Get a random cat picture")

# Define a function to handle the /cat command
async def cat(update, context):
    response = requests.get("https://api.thecatapi.com/v1/images/search")
    data = response.json()
    cat_url = data[0]['url']
    print(cat_url)
    await update.message.reply_photo(cat_url)

# Define a function to handle text messages
async def echo(update, context):
    await update.message.reply_text(update.message.text)

# Define a function to handle inline queries
def inline_query(update, context):
    query = update.inline_query.query
    results = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Echo",
            input_message_content=InputTextMessageContent(query)
        )
    ]
    update.inline_query.answer(results)

def main():

    api_key = TELEGRAM_BOT_TOKEN
    application = Application.builder().token(api_key).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cat", cat))

    # Register an inline query handler
    application.add_handler(InlineQueryHandler(inline_query))

    # Start the Bot
    application.run_polling(1.0)

    # Run the bot until you press Ctrl-C
    application.idle()

if __name__ == '__main__':
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    main()

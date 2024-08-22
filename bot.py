from telegram.ext import Updater, CommandHandler, MessageHandler, filters
from telegram import Update
from telegram.ext import CallbackContext

# Load the bot token from environment variables
import os
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def start(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome to the Trading Bot!')

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text('Use /buy, /sell, /deposit, /withdraw')

def main():
    # updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()

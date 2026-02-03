#  Copyright (c) S.Chirva 2025

import telebot
import os
from main import bot

# Import chat users
TG_BOT_CHATS = os.getenv("TG_BOT_CHATS").lower().split(",")

# The bot entery point. Message loading, converrtin from JSON, check message format
def handler(event, context):

    update = telebot.types.Update.de_json(event['body'])

    if (
        update.message is not None
        and update.message.from_user.username.lower() in TG_BOT_CHATS
    ):
        try:
            bot.process_new_updates([update])
        except Exception as e:
            print(e)

    return {
        "statusCode": 200,
        "body": "ok",
    }

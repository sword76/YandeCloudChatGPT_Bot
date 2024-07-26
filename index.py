#  Copyright (c) S.Chirva 2024

import telebot
import os
from main import bot

# Import 
TG_BOT_CHATS = os.getenv("TG_BOT_CHATS").lower().split(",")

# The bot entery point. Message loading, converrtin from JSON, check message format
def handler(event, context):

    update = telebot.types.Update.de_json(event['body'])

    if (
        update.message is not None
        and update.message.from_user.username.lower() in TG_BOT_CHATS
    ):
        bot.process_new_updates([update])

    return {
        "statusCode": 200,
        "body": "ok",
    }

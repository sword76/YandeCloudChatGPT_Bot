#  Copyright (c) S.Chirva 2024

import logging
import telebot
import os
import openai
import json
import boto3
import time
import multiprocessing

# Import enviroment variables
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
PROXY_API_KEY = os.getenv("PROXY_API_KEY")
YANDEX_KEY_ID = os.getenv("YANDEX_KEY_ID")
YANDEX_KEY_SECRET = os.getenv("YANDEX_KEY_SECRET")
YANDEX_BUCKET = os.getenv("YANDEX_BUCKET")

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

# Init Telebot library
bot = telebot.TeleBot(TG_BOT_TOKEN, threaded=False)

# Redirect requests to OpenAI via ProxyAI 
client = openai.Client (
    api_key=PROXY_API_KEY,
    base_url="https://api.proxyapi.ru/openai/v1",
)

# Function to safe message logs to the Yandex Object Storage
def get_s3_client():
    session = boto3.session.Session (
        aws_access_key_id=YANDEX_KEY_ID, aws_secret_access_key=YANDEX_KEY_SECRET)
    return session.client (
        service_name="s3", endpoint_url="https://storage.yandexcloud.net")

# Function to show "typing..." message while waiting tha ChatGPT answer
def typing(chat_id):
    while True:
        bot.send_chat_action(chat_id, "typing...")
        time.sleep(5)

# The bot welcome message
@bot.message_handler(commands=['help', 'start'])
def send_welcome(message):
    bot.reply_to(
        message,
        ("Привет! Я твой ChatGPT бот. Задай мне вопрос!"),)

# The bot message handler
@bot.message_handler(func=lambda message: True, content_types=["text"])
def echo_message(message):
    typing_process = multiprocessing.Process(target=typing, args=(message.chat.id,))
    typing_process.start()

    try:
        text = message.text
        ai_response = process_text_message(text, message.chat.id)
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка, попробуйте позже! {e}")
        return

    typing_process.terminate()
    bot.reply_to(message, ai_response)

def process_text_message(text, chat_id) -> str:
    model = "gpt-3.5-turbo"

    # Read current chat history
    s3client = get_s3_client()
    history = []
    try:
        history_object_response = s3client.get_object(
            Bucket=YANDEX_BUCKET, Key=f"{chat_id}.json"
        )
        history = json.loads(history_object_response["Body"].read())
    except:
        pass

    history.append({"role": "user", "content": text})

    try:
        chat_completion = client.chat.completions.create(
            model=model, messages=history
        )
    except Exception as e:
        if type(e).__name__ == "BadRequestError":
            clear_history_for_chat(chat_id)
            return process_text_message(text, chat_id)
        else:
            raise e

    ai_response = chat_completion.choices[0].message.content
    history.append({"role": "assistant", "content": ai_response})

    # Save current chat history
    s3client.put_object(
        Bucket=YANDEX_BUCKET,
        Key=f"{chat_id}.json",
        Body=json.dumps(history),
    )

    return ai_response


def clear_history_for_chat(chat_id):
    try:
        s3client = get_s3_client()
        s3client.put_object(
            Bucket=YANDEX_BUCKET,
            Key=f"{chat_id}.json",
            Body=json.dumps([]),
        )
    except:
        pass

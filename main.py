#  Copyright (c) S.Chirva 2025

import logging
import telebot
import threading
import os
import openai
import json
import boto3
import time
import requests
import base64
from telebot.types import InputFile

# Temp. For sound file mathadata exctruction
import mutagen
import tempfile

# For 4096 characters long answer message splitting 
from itertools import batched
import re

# Import enviroment variables
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
PROXY_API_KEY = os.getenv("PROXY_API_KEY")
YANDEX_KEY_ID = os.getenv("YANDEX_KEY_ID")
YANDEX_KEY_SECRET = os.getenv("YANDEX_KEY_SECRET")
YANDEX_BUCKET = os.getenv("YANDEX_BUCKET")
CHATGPT_MODEL = os.getenv("CHATGPT_MODEL")
CHATGPT_SEARCH_MODEL = os.getenv("CHATGPT_SEARCH_MODEL")
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
VOICE_MODEL = os.getenv("VOICE_MODEL")
OPENAI_VOICE = os.getenv("OPENAI_VOICE")

# Variable for typing functions 
is_typing = False

logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

# Init Telebot library
bot = telebot.TeleBot(TG_BOT_TOKEN, threaded=False)

# Redirect requests to OpenAI via ProxyAI 
client = openai.Client(
    api_key=PROXY_API_KEY,
    base_url="https://api.proxyapi.ru/openai/v1",
)

# Function to safe message logs to the Yandex Object Storage
def get_s3_client():
    session = boto3.session.Session (
        aws_access_key_id=YANDEX_KEY_ID, aws_secret_access_key=YANDEX_KEY_SECRET
    )
    return session.client (
        service_name="s3", endpoint_url="https://storage.yandexcloud.net"
    )

# Function to show "Typing" message while waiting tha ChatGPT answer

def start_typing(chat_id):
    global is_typing
    is_typing = True
    typing_thread = threading.Thread(target = typing, args = (chat_id,))
    typing_thread.start()

def typing(chat_id):
    global is_typing
    while is_typing:
        # For some unknown reason this action does not work
        # bot.send_chat_action(chat_id=chat_id, action=telebot.ChatAction.TYPING)
        bot.send_chat_action(chat_id, "typing")
        time.sleep(4)

def stop_typing():
    global is_typing
    is_typing = False

# Welcome and help messages
@bot.message_handler(commands=["start"])
def send_welcome(message):
    bot.reply_to(
        message,
        ("Привет! Я твой ChatGPT бот. Задай мне вопрос!"),)

@bot.message_handler(commands=["help"])
def send_welcome(message):
    bot.reply_to(
        message, 
        ("Напиши свой вопрос обычным языком, отправь изображение для распознования или голосовое сообщение для ответа."),)
     
@bot.message_handler(commands=["new"])
def clear_history(message):
    clear_history_for_chat(message.chat.id)
    bot.reply_to(message, "История чата очищена!")

# ProxyAPI balance request
@bot.message_handler(commands=["balance"])
def request_balance(message):
    
    headers = headers = {
        'Authorization': f'Bearer {PROXY_API_KEY}'
    }

    response = requests.get('https://api.proxyapi.ru/proxyapi/balance', headers = headers)

    if response.status_code == 200:
        balance = round(response.json()['balance'], 2)
        bot.reply_to(message, f'Ваш текущий баланс на proxyapi.ru: {balance}')
    else:
        bot.reply_to(message, 'Произошла ошибка при получении баланса.')

# Message handler for search function
@bot.message_handler(commands=["search"])
def process_search_message(message):
    
    start_typing(message.chat.id)

    try:
        prompt = message.text.split("/search")[1].strip()
        # logger.info(prompt)
        ai_response = process_text_message(prompt, message.chat.id, is_search = True)
        # logger.info(ai_response)

    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка поиска, попробуйте позже! {e}")
        return

    stop_typing()
    
    for msg_batch in batched(ai_response, 4096):
        text = ''.join(msg_batch)
        bot.reply_to(message, text, parse_mode="Markdown") 
        time.sleep(1)
        
    # bot.reply_to(message, ai_response, parse_mode="HTML")

# Image generator
@bot.message_handler(commands=["image"])
def image(message):

    start_typing(message.chat.id)

    prompt = message.text.split("/image")[1].strip()
    if len(prompt) == 0:
        bot.reply_to(message, "Введите запрос после команды /image")
        return

    try:
        response = client.images.generate(
            prompt=prompt, n=1, size="1024x1024", model=OPENAI_MODEL
        )
    except:
        bot.reply_to(message, "Произошла ошибка в генерации изображения, попробуйте позже!")
        return

    stop_typing()

    bot.send_photo(
        message.chat.id,
        response.data[0].url,
        reply_to_message_id=message.message_id,
    )

# Audio file voice recognition
@bot.message_handler(commands=["recognition"])
def recognition(message):

    msg = bot.send_message(message.chat.id, "Отправь аудиофайл (mp3 или ogg) для обработки.")

    start_typing(message.chat.id)

    # Check if audiofile handlet
    if msg.audio:
        audio_file = msg.audio
    elif msg.document.mime_type in ['audio/mpeg', 'audio/ogg'] or msg.document.file_name.lower().endswith(('.mp3', '.ogg')):
        audio_file = msg.document

    if not audio_file:
        bot.send_message(message.chat_id, "Пожалуйста, отправь файл в формате mp3 или ogg.")
        return

    # Download file to tmp folder
    file_info = bot.get_file(audio_file.file_id)
    file_path = file_info.file_path
    downloaded_file = bot.download_file(file_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_path)[1]) as tmp_file:
        tmp_file.write(downloaded_file)
        tmp_filename = tmp_file.name
    
    # Speech recognition
    try:
        response = client.audio.transcriptions.create(
            file=("file.ogg", tmp_filename, "audio/ogg"),
            model="whisper-1",
        )
        ai_response = process_text_message(response.text, message.chat.id, is_search = False)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка распознавания аудио-файла: {e}")
    
    finally:
        os.unlink(tmp_filename)  # Delete tmp file

    stop_typing()

    for msg_batch in batched(ai_response, 4096):
        text = ''.join(msg_batch)
        bot.reply_to(message.chat.id, text, parse_mode="Markdown") 
        time.sleep(1)

    # bot.register_next_step_handler(msg, process_audio)

# Voice request and voice answer
@bot.message_handler(func = lambda msg: msg.voice.mime_type == "audio/ogg", content_types=["voice"])
def voice(message):

    start_typing(message.chat.id)

    file_info = bot.get_file(message.voice.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    try:
        response = client.audio.transcriptions.create(
            file=("file.ogg", downloaded_file, "audio/ogg"),
            model="whisper-1",
        )
        ai_response = process_text_message(response.text, message.chat.id, is_search = False)
        ai_voice_response = client.audio.speech.create(
            input=ai_response,
            voice=OPENAI_VOICE,
            model=VOICE_MODEL,
            response_format="opus",
        )
        with open("/tmp/ai_voice_response.ogg", "wb") as f:
            f.write(ai_voice_response.content)
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка в генерации голосового ответа, попробуйте позже! {e}")
        return

    stop_typing()

    with open("/tmp/ai_voice_response.ogg", "rb") as f:
        bot.send_voice(
            message.chat.id,
            voice=InputFile(f),
            reply_to_message_id=message.message_id,
        )

# Message handler, text and photo recognition
@bot.message_handler(func=lambda message: True, content_types=["text", "photo"])
def echo_message(message):

    start_typing(message.chat.id)

    try:
        text = message.text
        image_content = None

        photo = message.photo
        if photo is not None:
            photo = photo[0]
            file_info = bot.get_file(photo.file_id)
            image_content = bot.download_file(file_info.file_path)
            text = message.caption
            if text is None or len(text) == 0:
                text = "Что изображено на картинке?"

        ai_response = process_text_message(text, message.chat.id, image_content, is_search = False)

    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка в распознавании картинки, попробуйте позже! {e}")
        return

    stop_typing()

    for msg_batch in batched(ai_response, 4096):
        text = ''.join(msg_batch)
        bot.reply_to(message, text, parse_mode="Markdown") 
        time.sleep(1)

#        bot.reply_to(message, ai_response, parse_mode="Markdown")

# Message processing function
def process_text_message(text, chat_id, image_content = None, is_search = None) -> str:

    # Condition to use ChatGPT search model
    model = CHATGPT_SEARCH_MODEL if is_search else CHATGPT_MODEL

    # logger.info(f"is_search value: {is_search}")
    # logger.info(f"Обработка сообщение: {text}, cо значение search: {is_search}, Модель: {model}")

    max_tokens = None
    web_search_options = None

    # Read current chat history
    s3client = get_s3_client()
    history = []
    
    try:
        history_object_response = s3client.get_object(
            Bucket=YANDEX_BUCKET, Key=f"{chat_id}.json"
        )
        history = json.loads(history_object_response["Body"].read())
    except:
        logging.error(f"Failed to add history log for chat_id {chat_id}: {e}")

    history_text_only = history.copy()
    history_text_only.append({"role": "user", "content": text})

    # Image recognition response
    if image_content is not None:
        model = "gpt-4-vision-preview"
        max_tokens = 4000
        base64_image_content = base64.b64encode(image_content).decode("utf-8")
        base64_image_content = f"data:image/jpeg;base64,{base64_image_content}"
        history.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": base64_image_content}},
                ],
            }
        )
    else:
        if is_search:
            web_search_options = {
                "search_context_size": "medium",
                "user_location": {
                    "type": "approximate",
                    "approximate": {
                        "country": "RU",
                        "city": "",
                        "region": ""
                    }
                }
            }
        
        history.append({"role": "user", "content": text})

    try:
        chat_completion = client.chat.completions.create(
            model = model, web_search_options = web_search_options, messages = history, max_tokens = max_tokens
        )
        
    except Exception as e:
        if type(e).__name__ == "BadRequestError":

            logging.error(f"Caught BadRequestError: {e}") # Find BadRequestError reason

            clear_history_for_chat(chat_id)
            return process_text_message(text, chat_id)
        else:
            raise e

    ai_response = chat_completion.choices[0].message.content
    history_text_only.append({"role": "assistant", "content": ai_response})

    # save current chat history
    s3client.put_object(
        Bucket=YANDEX_BUCKET,
        Key=f"{chat_id}.json",
        Body=json.dumps(history_text_only),
    )

    return ai_response

# Clear message history function
def clear_history_for_chat(chat_id):
    try:
        s3client = get_s3_client()
        s3client.put_object(
            Bucket=YANDEX_BUCKET,
            Key=f"{chat_id}.json",
            Body=json.dumps([]),
        )
    except:
        logging.error(f"Failed to clear history for chat_id {chat_id}: {e}")

# Split message on 4096 long and send message
def split_and_send(message, response, parse_mode = "Markdown", max_length = 4096):
    pass

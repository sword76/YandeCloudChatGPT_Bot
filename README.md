## YandeCloudChatGPT_Bot
Свой ChatGPT бот в Telegram

Знаменитый AI чат-бот ChatGPT заблокирован в России. Отличным выходом из этой ситуации были и есть Telegram-боты, которые не только позволяют обходить блокировку, но и в целом делают использование бота гораздо более удобным прямо из мессенджера.
Я решил сделать свою интеграцию ChatGPT в Telegram, чтобы лучше понять, как работает ChatGPT API, какие настройки мне доступны и пользоваться ботом без всяких ограничений, а также иметь свободный доступ к модели GPT-4.
Мне не хотелось для этого проекта держать отдельный сервер, покупать домен и делать под него SSL сертификат, который требует Telegram для настройки WebHook. Поэтому я решил настроить всю систему с помощью serverless-технологий.
Подготовка
Для реализации проекта мне понадобится:
API-ключ для ChatGPT API
Доступ к API, как и к самому ChatGPT заблокирован в России. К счастью, есть простое решение этой проблемы - ChatGPT API в России от компании ProxyAPI. Не нужен ни иностранный телефон, ни VPN, ни карта иностранного банка. 
Регистрируемся, идём в раздел Ключи API и создаём ключ. Одна минута и готово. Красота!

![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/b69/dbd/c71/b69dbdc7135c1be7f4e6a64b043cd02b.png)

# Аккаунт в Яндекс.Облако
Если аккаунта ещё нет его нужно создать здесь. Убедитесь, что у вас подключён платёжный аккаунт, и он находится в статусе ACTIVE или TRIAL_ACTIVE.

Все ресурсы, которые мы будем использовать, имеют ежемесячный бесплатный лимит потребления. Об этом я напишу ниже и, честно говоря, вряд ли возможно исчерпать такие лимиты, если бот предназначен только для личного использования. Так что вся система будет обходиться нам бесплатно, кроме расходов на ProxyAPI. 

# Telegram-бот
Для создания и управления своими ботами в Telegram есть, собственно, специальный бот под названием BotFather. Он поможет вам создать бота и в результате даст токен - сохраните его, он нам ещё понадобится.

# Облачные ресурсы
Теперь возвращаемся в Яндекс Облако и заводим все]ресурсы, необходимые для работы нашего проекта.

# 1. Сервисный аккаунт
На домашней странице консоли в верхнем меню есть вкладка "Сервисные аккаунты". Переходим туда и создаём новый аккаунт. Здесь и везде далее я использую одно и то же имя для всех ресурсов "chatgpt-telegram-bot" просто, чтобы не запутаться. Аккаунту надо присвоить следующие роли:
```
  serverless.functions.invoker
  storage.uploader`
```
![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/fb6/36e/2c4/fb636e2c4670b26a0b34242881ab2a95.png)

После того как аккаунт создан, перейдите в него и создайте статический ключ доступа, сохраните полученные идентификатор и секретный ключ, а также идентификатор самого сервисного аккаунта.
![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/a35/ef6/767/a35ef6767681b1e506ac7a6e8e8a13e3.png)

# 2. Бакет
Теперь переходим в раздел "Object Storage" и создаём новый бакет. Я не менял никакие настройки.
![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/6a3/f32/97f/6a3f3297f9040064abdbc1c80d4807c8.png)

# 3. Облачная функция
Следующий шаг — создание облачной функции. Именно она будет получать ваши запросы от Telegram, перенаправлять их в ProxyAPI и посылать ответ обратно в Telegram-бот.
Переходим в раздел "Cloud Functions" и жмём "Создать функцию".
После создания сразу откроется редактор, в который мы собственно и положим код функции. 
Выбираем среду выполнения Python 3.12:
![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/d14/d60/8b7/d14d608b74f868e729c4e8a2ac73f4e8.png)

В редакторе сначала создадим новый файл, назовём его `requirements.txt` и положим туда следующий код:
```
  openai==1.3.7
  pyTelegramBotAPI==4.14.0
  boto3==1.33.7
```
Это список зависимостей для Python, которые облако автоматически подгрузит во время сборки так, чтобы мы могли пользоваться ими в коде самой функции.
Теперь переключимся на редактирование `index.py` и запишем в него этот код:
```
import logging
import telebot
import os
import openai
import json
import boto3
import time
import multiprocessing

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
TG_BOT_CHATS = os.environ.get("TG_BOT_CHATS").lower().split(",")
PROXY_API_KEY = os.environ.get("PROXY_API_KEY")
YANDEX_KEY_ID = os.environ.get("YANDEX_KEY_ID")
YANDEX_KEY_SECRET = os.environ.get("YANDEX_KEY_SECRET")
YANDEX_BUCKET = os.environ.get("YANDEX_BUCKET")


logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

bot = telebot.TeleBot(TG_BOT_TOKEN, threaded=False)

client = openai.Client(
    api_key=PROXY_API_KEY,
    base_url="https://api.proxyapi.ru/openai/v1",
)


def get_s3_client():
    session = boto3.session.Session(
        aws_access_key_id=YANDEX_KEY_ID, aws_secret_access_key=YANDEX_KEY_SECRET
    )
    return session.client(
        service_name="s3", endpoint_url="https://storage.yandexcloud.net"
    )


def typing(chat_id):
    while True:
        bot.send_chat_action(chat_id, "typing")
        time.sleep(5)


@bot.message_handler(commands=["help", "start"])
def send_welcome(message):
    bot.reply_to(
        message,
        ("Привет! Я ChatGPT бот. Спроси меня что-нибудь!"),
    )


@bot.message_handler(commands=["new"])
def clear_history(message):
    clear_history_for_chat(message.chat.id)
    bot.reply_to(message, "История чата очищена!")


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

    # read current chat history
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

    # save current chat history
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


def handler(event, context):
    message = json.loads(event["body"])
    update = telebot.types.Update.de_json(message)

    if (
        update.message is not None
        and update.message.from_user.username.lower() in TG_BOT_CHATS
    ):
        bot.process_new_updates([update])

    return {
        "statusCode": 200,
        "body": "ok",
    }
```
Разберём, что делает этот код.
Сперва подключаем все необходимые библиотеки и читаем переменные окружения.
Инициируем библиотеку для работы с Telegram:
`bot = telebot.TeleBot(TG_BOT_TOKEN, threaded=False)`
# Важно! 
Обязательно укажите параметр `threaded=False`, иначе обработка сообщений от Telegram будет запускаться в отдельном потоке, однако в связи с тем, что это не полноценный сервер, который включён всегда, а облачная функция, она прекратит свою работу как только будет получен ответ от метода `handler` и просто проигнорирует исполняющийся на другом потоке процесс. В результате вы просто не получите ответ.
Далее переопределяем API-ключ и путь к API для OpenAI SDK, чтобы библиотека обращалась к нашему ProxyAPI, а не к OpenAI напрямую:
```
openai.api_key = os.getenv("PROXY_API_KEY")
openai.api_base = "https://api.proxyapi.ru/openai/v1"

def get_s3_client()
```
Метод для получения клиента для работы с Object Storage. В наш бакет мы будем сохранять историю беседы.
```
def typing(chat_id)
```
Метод, который будет посылать в Telegram статус "Набирает сообщение…", чтобы ожидание ответа не было таким томительным :)
```
@bot.message_handler(commands=["help", "start"])
```
Приветственное сообщение, которое пришлёт бот в ответ на команды `/start` или `/help`
```
@bot.message_handler(commands=["new"])
```
Команда `/new` позволяет очистить текущую историю чата, чтобы ChatGPT больше не использовал нерелевантный контекст, когда вы, например, хотите начать обсуждать новую тему так, чтобы бот не "отвлекался" на предыдущую беседу.
```
@bot.message_handler(func=lambda message: True, content_types=["text"])
```
Обработчик входящего текстового сообщения.
```
def process_text_message(text, chat_id)
```
Метод, который собственно обрабатывает ваше сообщение, сохраняет его в историю, посылает запрос в ProxyAPI и возвращает ответ, который тоже сохраняет в историю. В случае ошибки `BadRequestError` мы самостоятельно очищаем историю и снова запускаем запрос. Хотя эта ошибка может означать не только переполнение контекстного окна, у меня она возникала в основном только из-за этого.
```
def handler(event, context)
```
Это "входная точка" для вызова облачной функции. Здесь мы просто декодируем сообщение в JSON, проверяем, что оно поступило из списка чатов, которые мы хотим поддерживать, то есть запрос прислали вы, а не кто-то другой и отдаём его на обработку библиотеке Telegram-бота.

В параметрах функции поставим таймаут 60 секунд - ответы от ChatGPT приходится обычно ждать какое-то время, 60 секунд должно быть достаточно.
А также надо заполнить все переменные окружения, которые использует наша функция.
![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/1cd/44f/7f0/1cd44f7f02ab33b5440220ff50273129.png)
```
TG_BOT_TOKEN
```
Токен Telegram-бота
```
TG_BOT_CHATS
```
Имена пользователей, которым хотите дать доступ к боту, разделённых через запятую
```
PROXY_API_KEY
```
API-ключ от ProxyAPI
```
YANDEX_KEY_ID
YANDEX_KEY_SECRET
```
Идентификатор и секретный ключ статического ключа сервисного аккаунта Яндекс
```
YANDEX_BUCKET
```
Имя бакета, который вы создали в Object Storage.

На этом наша работа с функцией закончена. Жмём "Сохранить изменения" и смотрим, как Облако собирает нашу функцию. Для следующего шага нам понадобится идентификатор функции. Перейдите во вкладку "Обзор" для нашей функции и скопируйте его оттуда.
![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/b50/b2b/321/b50b2b3214db22af215072e5213e5471.png)

# АПИ шлюз
Для того чтобы сообщения, которые мы посылаем в Telegram-бот, приходили на обработку в нашу функцию, у неё должен быть какой-то публичный адрес. Сделать это очень легко с помощью инструмента API-шлюз. Переходим в раздел и создаём новый шлюз. В спецификации указываем:
```
openapi: 3.0.0
info:
  title: Sample API
  version: 1.0.0
paths:
  /:
    post:
      x-yc-apigateway-integration:
        type: cloud-functions
        function_id: <FUNCTION-ID>
        service_account_id: <SERVICE-ACCOUNT-ID>
```

В спецификации используйте свой индентификатор функции и сервисного аккаунта для значений `<FUNCTION-ID>` и `<SERVICE-ACCOUNT-ID>`. Выглядеть это будет вот так:
![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/548/b4a/ee3/548b4aee39aba6af2573ed6d24a4da41.png)
После сохранения вы увидите сводную информацию о шлюзе. Сохраните оттуда строку "Служебный домен".

# Telegram WebHook
Теперь надо сообщить Telegram-боту, куда пересылать сообщения, которые он от нас получает. Для этого достаточно выполнить POST-запрос к API Telegram такого формата:
```
curl \
  --request POST \
  --url https://api.telegram.org/bot<токен бота>/setWebhook \
  --header 'content-type: application/json' \
  --data '{"url": "<домен API-шлюза>"}'
```
`<токен бота>` заменяем на токен Telegram-бота, который мы получили еще на третьем шаге этого туториала
`<домен API-шлюза>` заменяем на Служебный домен нашего API-шлюза, созданный на прошлом шаге.
Я использовал Postman для этой задачи, просто удобнее, когда всё наглядно и с user-friendly интерфейсом:
![](https://habrastorage.org/r/w1560/getpro/habr/upload_files/acc/523/05f/acc52305f983558df18c2a50cf06dac8.png)
На этом вся наша работа закончена, осталось только проверить.

# Тест
Спрошу у своего чат-бота топ-10 стран по численности населения, а потом уточню, что интересуют страны только в Европе. Проверим, сможет ли он поддерживать диалог и работать с уточнениями.

# Стоимость ресурсов
Мы используем три типа ресурсов на Яндекс Облаке. Вот бесплатные лимиты потребления для каждого из них за каждый месяц.
Cloud Functions
1 миллион вызовов;
10 Гб/час использования памяти
Подробнее: (https://cloud.yandex.ru/docs/functions/pricing)

# Object Storage
первый 1 ГБ в месяц хранения;
первые 10 000 операций PUT, POST;
первые 100 000 операций GET, HEAD, OPTIONS
Подробнее:
(https://cloud.yandex.ru/docs/storage/pricing)

# API-шлюз
Каждый месяц не тарифицируются первые 100 000 запросов к API-шлюзам.
Подробнее:
(https://cloud.yandex.ru/docs/api-gateway/pricing)
Таким образом, на мой взгляд, при простом личном использовании бота, в эти ограничения можно укладываться каждый месяц с большим запасом. То есть вся инфраструктура для нашего бота нам будет обходиться бесплатно.
Единственные расходы будут связаны с использованием ChatGPT API. Цены здесь.
# Итог
Теперь у нас есть свой личный ChatGPT бот в Telegram, при этом мы использовали только serverless-технологии для обработки запросов и ProxyAPI для быстрого и лёгкого доступа к ChatGPT API в России.

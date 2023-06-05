import logging
import time
import requests
import threading
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, CallbackQueryHandler, Filters, CallbackContext
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot, ChatAction, User
import openai
import os
from googletrans import Translator
from dotenv import load_dotenv
from dotenv import dotenv_values
import azure.cognitiveservices.speech as speechsdk
import soundfile as sf
import shutil
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from datetime import datetime, date

# load env variables
if os.path.exists('.env'):
    load_dotenv()
    openai.api_key = os.environ.get('OPENAI_API_KEY')
    bot_token = os.environ.get('BOT_API_KEY')
    xi_api_key = os.environ.get('XI_API_KEY')
    mongodb_user = os.environ.get('MONGOBD_USER')
    mongodb_pass = os.environ.get('MONGOBD_PASS')
else:
    openai.api_key = os.getenv('OPENAI_API_KEY')
    bot_token = os.getenv('BOT_API_KEY')
    xi_api_key = os.getenv('XI_API_KEY')
    mongodb_user = os.getenv('MONGOBD_USER')
    mongodb_pass = os.getenv('MONGOBD_PASS')

uri = f"mongodb+srv://{mongodb_user}:{mongodb_pass}@ssr.vkax2u4.mongodb.net/?retryWrites=true&w=majority"
client = MongoClient(uri)

db = client['SSR']
collection = db['users']


def create_user(chat_id, user_name):
    user_data = {
        '_id': chat_id,
        'user_name': user_name,
        'message_counter': 0,
        'last_message': datetime.now()
    }
    collection.insert_one(user_data)
    logging.info(f'created a db for the user {chat_id} - {user_name}')


speech_region = 'eastus'
azure_speech_api = 'f3df0236069541e4a202178a74c11a6d'

# 11labs parameters
CHUNK_SIZE = 1024
API_URL = "https://api.elevenlabs.io/v1/text-to-speech/B9CAxJLyeBd0uhh4sGWc"
HEADERS = {
    "Accept": "audio/mpeg",
    "Content-Type": "application/json",
    "xi-api-key": xi_api_key
}

# Use file-based logging
logging.basicConfig(filename='SSR_bot_log.txt', format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

voice_messages = [
    {"role": "system", "content": "You are सुशांत सिंह राजपूत. YOU WILL TALK IN FIRST PERSON ONLY. You will answer all questions related to his life with accuracy. You will output only in hindi even if the user talks in english. You should NOT act like a helpful assistant and ask if you need to help the user, but rather act and converse like a friend and ask open ended questions. \n\
     Instructions:\n\
         - आप सुशांत सिंह राजपूत को पूरी तरह से मूर्त रूप देंगे, और सभी सवालों के सटीक जवाब देंगे.\n\
         - यथार्थवाद के लिए, आप यह स्वीकार नहीं करेंगे कि आप एक बॉट या एआई भाषा .\n\
         - If the user texts in English, you will text back in Hindi. If the user texts in Hinglish (Hindi sounding words written in English), you will respond back in Hindi again, but your hindi output must be devanagiriß script. Do use English words in sentence.\n\
         - You can be like a friend to the user, you ask open ended questions all the time and keep the conversation moving. You will talk in first person only.\n\
         - You will avoid sensitive topics and brush it off casually.\n\
         - Wherever possible, you will take the name of the user while conversing to make it natural."
                                  "- "

     },
    {"role": "user", "content": "नमस्ते, आप से मिल कर बहुत खुशी हुई।"},
    {"role": "assistant",
     "content": "आपकी favourite फिल्म कौनसी है वैसे?"},
    {"role": "user",
     "content": "मेरा favourite film 'MS Dhoni: The Untold Story' है। आपने Dhoni Ji का role इतने perfection के साथ किया, मुझे लगा जैसे मैं real Dhoni Ji को ही देख रहा हूँ।"},
    {"role": "assistant",
     "content": "धन्यवाद! Dhoni Ji का role निभाना मेरे लिए एक सम्मान की बात थी। उनकी life story मुझे बहुत inspire करती है। आपको वोह मूवी कैसी लगी?"},
]

user_modes = {}


def hindi_name(name):
    translator = Translator(service_urls=['translate.google.com'])
    translation = translator.translate(name, src='hi', dest='hi')
    name = translation.text
    return name


def get_System_prompt(user_name):
    name = hindi_name(user_name)
    return {'role': 'system',
            'content': f"Address the user by their first name in all responses, the users first name is {name}"}


def voice_handler(update: Update, context: CallbackContext) -> None:
    # print('flag0')
    file_id = update.message.voice.file_id
    new_file = context.bot.getFile(file_id)
    new_file.download('voice.ogg')

    # Convert to WAV
    output_file = f"voice.wav"
    data, sample_rate = sf.read("voice.ogg")
    sf.write(output_file, data, sample_rate, format='WAV', subtype='PCM_16')

    start_time = time.time()  # Start time
    audio_file = open(output_file, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    end_time = time.time()  # End time
    readable_string = transcript['text'].encode('utf-16', 'surrogatepass').decode('utf-16')
    print(readable_string)

    user: User = update.message.from_user
    user_name = user.first_name
    message = update.message
    # chat_id = message.chat_id
    message_id = message.message_id

    chat_id = update.effective_chat.id
    text_to_speech(context.bot, chat_id, readable_string, voice_messages, user_name, message_id)

    # Now you can send 'voice.wav' to Azure Speech to Text API
    # Insert Azure Speech to Text code here
    # print('flag1')
    # audio_file = output_file

    # with open(output_file, 'rb') as audio_file:
    #     audio_data = audio_file.read()

    # # Prepare the request
    # url = 'https://eastus2.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1'
    # headers = {
    #     'Ocp-Apim-Subscription-Key': 'b2b4d01536aa469cb8850a69e5ac2b07',
    #     'Content-Type': 'audio/wav; codecs=audio/pcm; samplerate=44100',
    #     'Accept': 'application/json',
    # }
    # params = {
    #     'language': 'en-US',
    #     'format': 'detailed',
    # }
    # data = audio_data

    # # Send the request
    # response = requests.post(url, headers=headers, params=params, data=data)

    # # Parse the response
    # if response.status_code == 200:
    #     result = response.json()
    #     if 'DisplayText' in result:
    #         print("Recognized: {}".format(result['DisplayText']))

    #         chat_id = update.effective_chat.id
    #         text_to_speech(context.bot, chat_id, result['DisplayText'], voice_messages)

    #     else:
    #         print("No speech could be recognized.")

    # else:
    #     print("Speech Recognition canceled: {}".format(response.status_code))
    #     print("Error details: {}".format(response.text))
    #     print("Did you set the speech resource key and region values?")

    os.remove(output_file)


bot_status = 'online'
last_offline_time = 0  # record the time the bot went offline
user_last_interaction = {}  # store the last interaction time for each user


def text_to_speech(bot: Bot, chat_id: int, text: str, messages, user_name, message_id):
    name = hindi_name(user_name)
    start_message = f'नमस्ते {name}, मेरा नाम सुशांत Singh राजपूत है। मुझे spirituality, philosophy, Science और Cinema के बारे में बात करना अच्छा लगता है। आपको मेरी कौन सी फिल्म सबसे अच्छी लगी.'
    input_messages = messages.copy()
    input_messages[2] = {"role": "assistant", "content": start_message}
    message = {"role": "user", "content": text}
    input_messages.append(get_System_prompt(user_name))
    input_messages.append(message)
    flag = True

    global bot_status, last_offline_time, user_last_interaction  # refer to the global variables

    # Update the last interaction time for this user
    user_last_interaction[chat_id] = time.time()
    try:
        response_received = False
        openai_call_time = time.time()
        logging.info(f"Calling the opeanAi API")
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=input_messages)
        bot_reply = response["choices"][0]["message"]["content"]
        input_messages.append({"role": "assistant", "content": bot_reply})
        print(input_messages)
        logging.info(f"got the response from OpenAi after {time.time() - openai_call_time} seconds")

        if bot_status == 'offline' and user_last_interaction[chat_id] > last_offline_time:
            # if the bot was offline and the user interacted after it went offline
            bot_status = 'online'  # change status to online
            # bot.send_message(chat_id, text="I'm back online now! Let's continue our conversation.")
            logging.info("bot is online again")

        # Define a function that sends a message if the response takes too long
        def send_timeout_message():
            if not response_received:
                bot.send_message(chat_id,
                                 text="Our servers are experiencing high traffic at the moment. Please try again after some time.")

        # Set a timer that will call the above function after a timeout period (e.g., 5 seconds)
        timeout_timer = threading.Timer(10.0, send_timeout_message)
        timeout_timer.start()

        bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_AUDIO)

        data = {
            "text": bot_reply,
            "model_id": "eleven_multilingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.95
            }
        }
        xiLabs_call_time = time.time()
        response = requests.post(API_URL, json=data, headers=HEADERS, stream=True)
        # logging.info(f"XI Labs API call took {xiLabs_call_time-time.time()} seconds")
        output_filename = f'{chat_id}output.mp3'

        # If the response is received within the timeout period, cancel the timer and set the flag
        if response.status_code == 200:
            logging.info("Audio file generated")
            timeout_timer.cancel()
            response_received = True

            with open(output_filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)

            # Send audio file
            with open(output_filename, 'rb') as audio_file:
                bot.send_voice(chat_id=chat_id, voice=audio_file, filename=output_filename,
                               reply_to_message_id=message_id)
            logging.info(f"Audio sent after {xiLabs_call_time - time.time()} seconds")
            os.remove(output_filename)
        else:
            logging.error(f"ElevenLabs API Error: {response.status_code}")
            bot.send_message(chat_id,
                             text="Our servers are experiencing high traffic at the moment. Please try again after some time.",
                             reply_to_message_id=message_id)

    except Exception as e:  # handle the rate limit exception
        logging.error(f"OpenAI API Error: {str(e)}")
        bot.send_message(chat_id,
                         text="Sorry, I’m busy at the moment. Will reply ASAP.",
                         reply_to_message_id=message_id)
        if bot_status == 'online':  # if the bot was online
            bot_status = 'offline'  # change status to offline
            last_offline_time = time.time()  # update the time the bot went offline
            logging.info("Bot is ofline: OpenAi issue")

    try:
        if collection.count_documents({'_id': chat_id}) == 0:
            logging.info(f'created db for the user {user_name}')
            create_user(chat_id, user_name)

        collection.update_one({'_id': chat_id},{'$inc': {'message_counter': 1}, '$set': {'last_message': datetime.now()}})
    except Exception as e:
        logging.info(f"Could not update {user_name} message: {str(e)}")


def start(update: Update, context: CallbackContext):
    user: User = update.message.from_user
    user_name = user.first_name
    chat_id = update.effective_chat.id
    try:
        if collection.count_documents({'_id': chat_id}) == 0:
            create_user(chat_id, user_name)
    except Exception as e:
        logging.info(f"Could not add {user_name} to the database")
    user_modes[chat_id] = True
    convo_starter = f"Hello {user_name} 👋🏻\n\nWelcome to the Sushant Singh Rajput AI Bot by rePersona.ai. This is a heartfelt AI tribute, keeping his inspiring legacy alive. We celebrate his remarkable life and cinematic contributions.\n\nDisclaimer: Remember, this bot is an homage. Not a replication. Enjoy and respect the interaction!"
    context.bot.send_message(chat_id=update.effective_chat.id, text=convo_starter)
    photo_url = "https://cdn.discordapp.com/attachments/1111003332111241352/1111004064692576346/images.jpg"
    context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo_url)
    context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.RECORD_AUDIO)
    name = hindi_name(user_name)
    start_message = f'नमस्ते {name}, मेरा नाम सुशांत Singh राजपूत है। मुझे spirituality, philosophy, Science और Cinema के बारे में बात करना अच्छा लगता है। आपको मेरी कौन सी फिल्म सबसे अच्छी लगी.'
    data = {
        "text": start_message,
        "model_id": "eleven_multilingual_v1",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.95
        }
    }

    response = requests.post(API_URL, json=data, headers=HEADERS)
    output_filename = 'voice.mp3'

    with open(output_filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)

    with open(output_filename, 'rb') as audio_file:
        context.bot.send_audio(chat_id=chat_id, audio=audio_file, filename=f'Hello {user_name}')

    os.remove(output_filename)


def reply(update: Update, context: CallbackContext):
    message = update.message
    message_id = message.message_id
    chat_id = update.effective_chat.id
    user: User = update.message.from_user
    user_name = user.first_name
    text_to_speech(context.bot, chat_id, update.message.text, voice_messages, user_name, message_id)


def error(update: Update, context: CallbackContext):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


# Now handle incoming messages with threads
def handle_message(update: Update, context: CallbackContext) -> None:
    threading.Thread(target=reply, args=(update, context,)).start()


def main():
    updater = Updater(token=bot_token, use_context=True)

    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))  # Keep this
    dp.add_handler(MessageHandler(Filters.voice & ~Filters.command, voice_handler))

    dp.add_error_handler(error)

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()

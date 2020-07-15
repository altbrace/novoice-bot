import vk_api.vk_api
from vk_api import exceptions
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import random
import requests
import time
from google.cloud import speech_v1p1beta1
from google.cloud.speech import enums
from google.cloud.speech_v1p1beta1 import enums
import os
import redis


def google_stt(raw):
    client = speech_v1p1beta1.SpeechClient.from_service_account_json('google-credentials.json')

    encoding = enums.RecognitionConfig.AudioEncoding.MP3
    config = {
        "language_code": "ru-RU",
        "sample_rate_hertz": 44100,
        "encoding": encoding,
        "enable_automatic_punctuation": True,
    }
    audio = {"content": raw}

    print("Voice recognition initiated...")
    t0 = time.time()
    response = client.recognize(config, audio)
    for result in response.results:
        # First alternative is the most probable result
        alternative = result.alternatives[0]
        seconds = time.time() - t0
        print(f"Voice recognition completed in {round(seconds)} sec.\n"
              f"Content: {alternative.transcript}\n"
              f"Confidence: {int(alternative.confidence * 100)}%\n")
        return alternative.transcript


def get_random_id():
    return random.getrandbits(31) * random.choice([-1, 1])


class Bot:

    def __init__(self, api_token, group_id):

        self.group_id = group_id

        self.triggers = ['!', '-', '/']
        self.commands = {
            "engine": self.switch_engine
        }

        self.vk = vk_api.VkApi(token=api_token)
        self.bot_long_poll = VkBotLongPoll(self.vk, group_id)
        self.vk_api = self.vk.get_api()
        self.upload = vk_api.upload.VkUpload(self.vk)

        redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')
        self.redis_ins = redis.from_url(redis_url)

        self.session = requests.session()

    def switch_engine(self, event):
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button('Google STT', color=VkKeyboardColor.DEFAULT)
        keyboard.add_line()
        keyboard.add_button('Yandex SpeechKit', color=VkKeyboardColor.DEFAULT)

        self.send_msg(event.object.peer_id, event.object.id, 'Выберите движок', keyboard.get_keyboard())

    def send_msg(self, peer_id, fwd, message, keyboard=None, *attachment):
        self.vk_api.messages.send(peer_id=peer_id,
                                  message=message,
                                  random_id=get_random_id(),
                                  attachment=attachment,
                                  keyboard=keyboard,
                                  forward_messages=fwd)

    def start(self):
        for event in self.bot_long_poll.listen():
            attachments = event.object.attachments
            if event.type == VkBotEventType.MESSAGE_NEW and attachments:

                for attachment in attachments:
                    if attachment['type'] == 'audio_message':
                        response = self.session.get(attachment['audio_message']['link_mp3'])
                        raw = response.content
                        transcribed = google_stt(raw)
                        if not transcribed:
                            transcribed = "[неразборчиво]"
                        self.send_msg(event.object.peer_id, event.object.id, transcribed)

            if event.type == VkBotEventType.MESSAGE_NEW and event.object.text[0] in self.triggers:
                chunks = event.object.text.split()
                command = chunks[0][1:]

                try:
                    chat_members = self.vk_api.messages.getConversationMembers(peer_id=event.object.peer_id,
                                                                               group_id=self.group_id)
                    for member in chat_members['items']:
                        if member['member_id'] == event.object.from_id and 'is_admin' in member:
                            if command in self.commands.keys():
                                self.commands[command](event)
                            else:
                                self.send_msg(event.object.peer_id, event.object.id, "Команда не существует.")

                        elif member['member_id'] == event.object.from_id and 'is_admin' not in member:
                            self.send_msg(event.object.peer_id, event.object.id, "Ты не администратор.")

                except vk_api.exceptions.ApiError:
                    self.send_msg(event.object.peer_id, event.object.id,
                                  "Невозможно выполнить команду без прав администратора у бота")

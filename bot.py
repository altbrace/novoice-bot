import vk_api.vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import random
import requests
import time
from google.cloud import speech_v1p1beta1
from google.cloud.speech import enums
from google.cloud.speech_v1p1beta1 import enums
import os
import json


def speechToText(raw):

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

        self.vk = vk_api.VkApi(token=api_token)
        self.bot_long_poll = VkBotLongPoll(self.vk, group_id)
        self.vk_api = self.vk.get_api()
        self.upload = vk_api.upload.VkUpload(self.vk)

        self.session = requests.session()

    def send_msg(self, peer_id, fwd, message, *attachment):
        self.vk_api.messages.send(peer_id=peer_id,
                                  message=message,
                                  random_id=get_random_id(),
                                  attachment=attachment,
                                  forward_messages=fwd)

    def start(self):
        for event in self.bot_long_poll.listen():
            attachments = event.object.attachments
            if event.type == VkBotEventType.MESSAGE_NEW and attachments:

                for attachment in attachments:
                    if attachment['type'] == 'audio_message':
                        response = self.session.get(attachment['audio_message']['link_mp3'])
                        raw = response.content
                        transcribed = speechToText(raw)
                        if not transcribed:
                            transcribed = "[неразборчиво]"
                        self.send_msg(event.object.peer_id, event.object.id, transcribed)

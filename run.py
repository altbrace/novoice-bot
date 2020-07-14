from bot import Bot
import os

api_token = os.environ.get('VK_API_TOKEN')
group_id = os.environ.get('VK_GROUP_ID')

bot = Bot(api_token, group_id)

bot.start()

import asyncio
import os
import subprocess
import nest_asyncio
import Credentials
from datetime import datetime, timedelta
from telegram.ext import Application

nest_asyncio.apply()


STORIES_DIR = os.path.join(os.path.dirname(__file__), 'InstaStoryLoader/stories/'+Credentials.STORIES_PROVIDER_USERNAME)
SENT_STORIES_FILE = 'sent_stories.txt'  # File to keep track of sent stories


def extract_datetime(filename):
    second_date_time_str = filename.split('__')[1].split('.')[0]
    return datetime.strptime(second_date_time_str, '%Y-%m-%d_%H-%M-%S')


def get_files_in_directory(directory):
    return set(os.listdir(directory))


def read_sent_stories():
    if not os.path.exists(SENT_STORIES_FILE):
        return set()
    with open(SENT_STORIES_FILE, 'r') as file:
        return set(file.read().splitlines())


def write_sent_stories(sent_stories):
    with open(SENT_STORIES_FILE, 'w') as file:
        file.write('\n'.join(sent_stories))


def clean_stories_folder():
    for filename in os.listdir(STORIES_DIR):
        file_path = os.path.join(STORIES_DIR, filename)
        os.remove(file_path)
    open(SENT_STORIES_FILE, 'w').close()


async def download_stories():
    command = ['python3', 'InstaStoryLoader/StoryLoader.py', '-u',
               Credentials.INSTAGRAM_USERNAME, '-p', Credentials.INSTAGRAM_PASSWORD, '-d',
               Credentials.STORIES_PROVIDER_USERNAME, '--no-thumbs', '--taken-at']
    subprocess.run(command)


async def send_new_stories(context):
    existing_files = get_files_in_directory(STORIES_DIR)
    sent_stories = read_sent_stories()

    new_files = existing_files - sent_stories
    if len(new_files) == 0:
        print('[I] All existing stories are already sent.')
    else:
        print('[I] Sending new stories to channel.')
    sorted_filenames = sorted(new_files, key=extract_datetime)
    for filename in sorted_filenames:
        file_path = os.path.join(STORIES_DIR, filename)
        if filename.endswith('.jpg'):
            with open(file_path, 'rb') as f:
                await context.bot.send_photo(chat_id=Credentials.TELEGRAM_CHANNEL_CHAT_ID, photo=f)
        elif filename.endswith('.mp4'):
            with open(file_path, 'rb') as f:
                await context.bot.send_video(chat_id=Credentials.TELEGRAM_CHANNEL_CHAT_ID, video=f)
        sent_stories.add(filename)

    write_sent_stories(sent_stories)

async def remove_credentials_periodically():
    credentials_file_path = os.path.join(os.path.dirname(__file__), 'InstaStoryLoader/credentials.json')
    while True:
        if os.path.exists(credentials_file_path):
            os.remove(credentials_file_path)
            print('[I] Credentials file removed.')
        else:
            print('[I] No credentials file found to remove.')

        await asyncio.sleep(14400)  # 4 hours in seconds

async def periodic_task(context):
    last_cleanup = datetime.now()
    while True:
        await download_stories()
        await send_new_stories(context)

        # Check if a day has passed to clean up the folder
        if datetime.now() - last_cleanup >= timedelta(days=1):
            clean_stories_folder()
            last_cleanup = datetime.now()

        await asyncio.sleep(3600)  # Wait for 1 hour


async def main():
    credentials_file_path = os.path.join(os.path.dirname(__file__), 'InstaStoryLoader/credentials.json')
    feed_file_path = os.path.join(os.path.dirname(__file__), 'InstaStoryLoader/feed_json.json')
    if os.path.exists(credentials_file_path):
        os.remove(credentials_file_path)
    if os.path.exists(feed_file_path):
        os.remove(feed_file_path)
    application = Application.builder().token(Credentials.BOT_KEY).build()
    asyncio.create_task(periodic_task(application))
    asyncio.create_task(remove_credentials_periodically())
    await application.run_polling()


if __name__ == '__main__':
    asyncio.run(main())

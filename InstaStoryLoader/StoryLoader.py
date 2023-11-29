import argparse
import codecs
import datetime
import json
import os
import sys
import time
import subprocess

try:
    import urllib.request as urllib
except ImportError:
    import urllib as urllib

try:
    from instagram_private_api import (
        Client, ClientError, ClientLoginError,
        ClientCookieExpiredError, ClientLoginRequiredError,
        __version__ as client_version)
except ImportError:
    import sys

    sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
    from instagram_private_api import (
        Client, ClientError, ClientLoginError,
        ClientCookieExpiredError, ClientLoginRequiredError,
        __version__ as client_version)

from instagram_private_api import ClientError
from instagram_private_api import Client

script_version = "2.6"
python_version = sys.version.split(' ')[0]

download_dest = os.getcwd()


# Login


def to_json(python_object):
    if isinstance(python_object, bytes):
        return {'__class__': 'bytes',
                '__value__': codecs.encode(python_object, 'base64').decode()}
    raise TypeError(repr(python_object) + ' is not JSON serializable')


def from_json(json_object):
    if '__class__' in json_object and json_object.get('__class__') == 'bytes':
        return codecs.decode(json_object.get('__value__').encode(), 'base64')
    return json_object


def onlogin_callback(api, settings_file):
    cache_settings = api.settings
    with open(settings_file, 'w') as outfile:
        json.dump(cache_settings, outfile, default=to_json)
        print('[I] New auth cookie file was made: {0!s}'.format(settings_file))


def login(username="", password=""):
    device_id = None
    try:
        settings_file = "InstaStoryLoader/credentials.json"
        if not os.path.isfile(settings_file):
            # settings file does not exist
            print('[W] Unable to find auth cookie file: {0!s} (creating a new one...)'.format(settings_file))

            # login new
            api = Client(
                username, password,
                on_login=lambda x: onlogin_callback(x, settings_file))
        else:
            with open(settings_file) as file_data:
                cached_settings = json.load(file_data, object_hook=from_json)

            device_id = cached_settings.get('device_id')
            # reuse auth settings
            api = Client(
                username, password,
                settings=cached_settings)

            print('[I] Using cached login cookie for "' + api.authenticated_user_id + '".')

    except (ClientCookieExpiredError, ClientLoginRequiredError) as e:
        print('[E] ClientCookieExpiredError/ClientLoginRequiredError: {0!s}'.format(e))
        api = Client(
            username, password,
            device_id=device_id,
            on_login=lambda x: onlogin_callback(x, settings_file))

    except ClientLoginError as e:
        print('[E] Could not login: {:s}.\n[E] {:s}\n\n{:s}'.format(
            json.loads(e.error_response).get("error_title", "Error title not available."),
            json.loads(e.error_response).get("message", "Not available"), e.error_response))
        sys.exit(9)
    except ClientError as e:
        print('[E] Client Error: {:s}'.format(e.error_response))
        sys.exit(9)

    print('[I] Login to "' + api.authenticated_user_id + '" OK!')
    cookie_expiry = api.cookie_jar.auth_expires
    print('[I] Login cookie expiry date: {0!s}'.format(
        datetime.datetime.fromtimestamp(cookie_expiry).strftime('%Y-%m-%d at %I:%M:%S %p')))

    return api


# Downloader


def check_directories(user_to_check):
    global download_dest
    try:
        if not os.path.isdir(download_dest + "/InstaStoryLoader/stories/{}/".format(user_to_check)):
            os.makedirs(download_dest + "/InstaStoryLoader/stories/{}/".format(user_to_check))
        return True
    except Exception as e:
        print(str(e))
        return False


def get_media_story(user_to_check, user_id, ig_client, taken_at=False, no_video_thumbs=False):
    global download_dest
    try:
        try:
            feed = ig_client.user_story_feed(user_id)
        except Exception as e:
            print("[W] An error occurred trying to get user feed: " + str(e))
            return
        try:
            feed_json = feed['reel']['items']
            open("InstaStoryLoader/feed_json.json", 'w').write(json.dumps(feed_json))
        except TypeError:
            print("[I] There are no recent stories to process for this user.")
            return

        list_video = []
        list_image = []

        list_video_new = []
        list_image_new = []

        for media in feed_json:
            if not taken_at:
                taken_ts = None
            else:
                if media.get('imported_taken_at'):
                    imported_taken_at = media.get('imported_taken_at', "")
                    if imported_taken_at > 10000000000:
                        imported_taken_at /= 1000
                    taken_ts = datetime.datetime.utcfromtimestamp(media.get('taken_at', "")).strftime(
                        '%Y-%m-%d_%H-%M-%S') + "__" + datetime.datetime.utcfromtimestamp(
                        imported_taken_at).strftime(
                        '%Y-%m-%d_%H-%M-%S')
                else:
                    taken_ts = datetime.datetime.utcfromtimestamp(media.get('taken_at', "")).strftime(
                        '%Y-%m-%d_%H-%M-%S')

            is_video = 'video_versions' in media and 'image_versions2' in media

            if 'video_versions' in media:
                list_video.append([media['video_versions'][0]['url'], taken_ts])
            if 'image_versions2' in media:
                if (is_video and not no_video_thumbs) or not is_video:
                    list_image.append([media['image_versions2']['candidates'][0]['url'], taken_ts])

        print("[I] Downloading video stories. ({:d} stories detected)".format(len(list_video)))
        for index, video in enumerate(list_video):
            filename = video[0].split('/')[-1]
            if taken_at:
                try:
                    final_filename = video[1] + ".mp4"
                except:
                    final_filename = filename.split('.')[0] + ".mp4"
                    print("[E] Could not determine timestamp filename for this file, using default: " + final_filename)
            else:
                final_filename = filename.split('.')[0] + ".mp4"
            save_path = download_dest + "/InstaStoryLoader/stories/{}/".format(user_to_check) + final_filename
            if not os.path.exists(save_path):
                print("[I] ({:d}/{:d}) Downloading video: {:s}".format(index + 1, len(list_video), final_filename))
                try:
                    download_file(video[0], save_path)
                    list_video_new.append(save_path)
                except Exception as e:
                    print("[W] An error occurred while iterating video stories: " + str(e))
                    exit(1)
            else:
                print("[I] Story already exists: {:s}".format(final_filename))

        print("[I] Downloading image stories. ({:d} stories detected)".format(len(list_image)))
        for index, image in enumerate(list_image):
            filename = (image[0].split('/')[-1]).split('?', 1)[0]
            if taken_at:
                try:
                    final_filename = image[1] + ".jpg"
                except:
                    final_filename = filename.split('.')[0] + ".jpg"
                    print("[E] Could not determine timestamp filename for this file, using default: " + final_filename)
            else:
                final_filename = filename.split('.')[0] + ".jpg"
            save_path = download_dest + "/InstaStoryLoader/stories/{}/".format(user_to_check) + final_filename
            if not os.path.exists(save_path):
                print("[I] ({:d}/{:d}) Downloading image: {:s}".format(index + 1, len(list_image), final_filename))
                try:
                    download_file(image[0], save_path)
                    list_image_new.append(save_path)
                except Exception as e:
                    print("[W] An error occurred while iterating image stories: " + str(e))
                    exit(1)
            else:
                print("[I] Story already exists: {:s}".format(final_filename))

        if (len(list_image_new) != 0) or (len(list_video_new) != 0):
            print("[I] Story downloading ended with " + str(len(list_image_new)) + " new images and " + str(
                len(list_video_new)) + " new videos downloaded.")
        else:
            print("[I] No new stories were downloaded.")
    except Exception as e:
        print("[E] A general error occurred: " + str(e))
        exit(1)
    except KeyboardInterrupt as e:
        print("[I] User aborted download.")
        exit(1)


def download_file(url, path, attempt=0):
    try:
        urllib.urlretrieve(url, path)
        urllib.urlcleanup()
    except Exception as e:
        if not attempt == 3:
            attempt += 1
            print("[E] ({:d}) Download failed: {:s}.".format(attempt, str(e)))
            print("[W] Trying again in 5 seconds.")
            time.sleep(5)
            download_file(url, path, attempt)
        else:
            print("[E] Retry failed three times, skipping file.")


def command_exists(command):
    try:
        fnull = open(os.devnull, 'w')
        subprocess.call([command], stdout=fnull, stderr=subprocess.STDOUT)
        return True
    except OSError:
        return False


def start():
    print("-" * 70)
    print('[I] PYINSTASTORIES (SCRIPT V{:s} - PYTHON V{:s}) - {:s}'.format(script_version, python_version,
                                                                           time.strftime('%I:%M:%S %p')))
    print("-" * 70)

    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--username', dest='username', type=str, required=False,
                        help="Instagram username to login with.")
    parser.add_argument('-p', '--password', dest='password', type=str, required=False,
                        help="Instagram password to login with.")
    parser.add_argument('-d', '--download', nargs='+', dest='download', type=str, required=False,
                        help="Instagram user to download stories from.")
    parser.add_argument('-ta', '--taken-at', dest='takenat', action='store_true',
                        help="Append the taken_at timestamp to the filename of downloaded items.")
    parser.add_argument('-nt', '--no-thumbs', dest='novideothumbs', action='store_true',
                        help="Do not download video thumbnails.")
    parser.add_argument('-o', '--output', dest='output', type=str, required=False,
                        help="Destination folder for downloads.")

    args, unknown = parser.parse_known_args()

    if args.download:
        users_to_check = args.download
    else:
        print('[E] No usernames provided. Please use the -d argument.')
        print("-" * 70)
        sys.exit(1)

    if args.username and args.password:
        ig_client = login(args.username, args.password)
    else:
        settings_file = "InstaStoryLoader/credentials.json"
        if not os.path.isfile(settings_file):
            print("[E] No username/password provided, but there is no login cookie present either.")
            print("[E] Please supply --username and --password arguments.")
            exit(1)
        else:
            ig_client = login()

    print("-" * 70)
    global download_dest
    if args.output:
        if os.path.isdir(args.output):
            download_dest = args.output
        else:
            print("[W] Destination '{:s}' is invalid, falling back to default location.".format(args.output))
            download_dest = os.getcwd()
    print("[I] Files will be downloaded to {:s}".format(download_dest))
    print("-" * 70)

    def download_user(ind, user, attempt=0):
        try:
            if not user.isdigit():
                user_res = ig_client.username_info(user)
                user_id = user_res['user']['pk']
            else:
                user_id = user
                user_info = ig_client.user_info(user_id)
                if not user_info.get("user", None):
                    raise Exception("No user is associated with the given user id.")
                else:
                    user = user_info.get("user").get("username")
            print("[I] Getting stories for: {:s}".format(user))
            if check_directories(user):
                follow_res = ig_client.friendships_show(user_id)
                if follow_res.get("is_private") and not follow_res.get("following"):
                    raise Exception("You are not following this private user.")
                get_media_story(user, user_id, ig_client, args.takenat, args.novideothumbs)
            else:
                print("[E] Could not make required directories. Please create a 'stories' folder manually.")
                exit(1)
            if (ind + 1) != len(users_to_check):
                print('[I] ({}/{}) 5 second time-out until next user...'.format((ind + 1), len(users_to_check)))
                time.sleep(5)
        except Exception as e:
            if not attempt == 3:
                attempt += 1
                print("[E] ({:d}) Download failed: {:s}.".format(attempt, str(e)))
                print("[W] Trying again in 5 seconds.")
                time.sleep(5)
                download_user(ind, user, attempt)
            else:
                print("[E] Retry failed three times, skipping user.")

    for index, user_to_check in enumerate(users_to_check):
        try:
            download_user(index, user_to_check)
        except KeyboardInterrupt:
            print("[I] The operation was aborted.")
            exit(0)
    exit(0)


start()

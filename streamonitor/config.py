import json
import os
import sys
import time

from parameters import CONFIG_PATH
from streamonitor.bot import Bot
from streamonitor.log import Logger

logger = Logger('[CONFIG]').get_logger()
config_loc = CONFIG_PATH


def load_config():
    try:
        with open(config_loc, "r+") as f:
            return json.load(f)
    except FileNotFoundError:
        os.makedirs(os.path.dirname(config_loc) or ".", exist_ok=True)
        with open(config_loc, "w+") as f:
            json.dump([], f, indent=4)
            return []
    except ValueError:
        logger.error('Corrupted config.json')
        sys.exit(1)
    except Exception as e:
        logger.exception(e)
        sys.exit(1)


def save_config(config):
    try:
        os.makedirs(os.path.dirname(config_loc) or ".", exist_ok=True)
        with open(config_loc, "w+") as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        logger.exception(e)
        sys.exit(1)


def saveStreamers(streamers):
    save_config([s.export() for s in streamers])


def loadStreamers():
    streamers = []
    for streamer in load_config():
        username = streamer["username"]
        site = streamer["site"]

        bot_class = Bot.str2site(site)
        if not bot_class:
            logger.warning(f'Unknown site: {site} (user: {username})')
            continue

        streamer_bot = bot_class.fromConfig(streamer)
        streamers.append(streamer_bot)
        streamer_bot.start()
        time.sleep(0.1)
    saveStreamers(streamers)
    return streamers

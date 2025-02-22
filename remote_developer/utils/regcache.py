"""A generic utility module for managing a platform-specific cache."""

import os
import json
import platform
from utils.logger import Logger  # Assuming you have a logger

logger = Logger(__name__)  # Initialize logger

# Platform-specific cache storage
if platform.system() == "Windows":
    import winreg

    CACHE_LOCATION = "Software\\RemoteDeveloper"  # Registry key
elif platform.system() == "Darwin":  # macOS
    import plistlib

    CACHE_LOCATION = os.path.expanduser("~/Library/Preferences/remote_developer.plist")
else:  # Linux
    CACHE_LOCATION = os.path.expanduser("~/.config/remote_developer_cache.json")


def load_cache(cache_location=CACHE_LOCATION):
    """Loads the cache from storage."""
    logger.debug(f"Loading cache from: {cache_location} (Platform: {platform.system()})")
    try:
        if platform.system() == "Windows":
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cache_location)
                logger.debug(f"Successfully opened Windows Registry key: {cache_location}")
            except FileNotFoundError:
                logger.info(
                    f"Windows Registry key not found: {cache_location}. Returning empty cache."
                )
                return {}  # Return empty dictionary if key doesn't exist
            cache = {}
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    cache[name] = json.loads(value)  # Store as JSON string in registry
                    i += 1
                except OSError:
                    break  # No more values
            winreg.CloseKey(key)
            return cache
        elif platform.system() == "Darwin":
            if os.path.exists(cache_location):
                logger.debug(f"Loading cache from plist file: {cache_location}")
                with open(cache_location, "rb") as f:
                    cache = plistlib.load(f)
                    return cache
            else:
                logger.info(f"plist file not found: {cache_location}. Returning empty cache.")
                return {}
        else:
            if os.path.exists(cache_location):
                logger.debug(f"Loading cache from JSON file: {cache_location}")
                with open(cache_location) as f:
                    cache = json.load(f)
                    return cache
            else:
                logger.info(f"JSON file not found: {cache_location}. Returning empty cache.")
                return {}
    except Exception as e:
        logger.error(f"Error loading cache: {e}")
        return {}


def save_cache(cache, cache_location=CACHE_LOCATION):
    """Saves the cache to storage."""
    logger.debug(f"Saving cache to: {cache_location} (Platform: {platform.system()})")
    try:
        if platform.system() == "Windows":
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, cache_location)
                logger.debug(f"Successfully created Windows Registry key: {cache_location}")
            except FileNotFoundError:
                logger.debug(
                    f"Registry key not found, attempting to open for write: {cache_location}"
                )
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cache_location, 0, winreg.KEY_WRITE)
                logger.debug(f"Successfully opened Registry key for write: {cache_location}")
            for name, value in cache.items():
                winreg.SetValueEx(
                    key, name, 0, winreg.REG_SZ, json.dumps(value)
                )  # Store as JSON string in registry
            winreg.CloseKey(key)
        elif platform.system() == "Darwin":
            os.makedirs(os.path.dirname(cache_location), exist_ok=True)
            with open(cache_location, "wb") as f:
                plistlib.dump(cache, f)
        else:
            os.makedirs(os.path.dirname(cache_location), exist_ok=True)
            with open(cache_location, "w") as f:
                json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


def get_cache_item(key, cache_location=CACHE_LOCATION):
    """Retrieves a specific item from the cache."""
    logger.debug(f"Getting cache item: Key={key}, Cache Location={cache_location}")
    cache = load_cache(cache_location)
    item = cache.get(key)
    return item


def set_cache_item(key, value, cache_location=CACHE_LOCATION):
    """Sets a specific item in the cache."""
    logger.debug(f"Setting cache item: Key={key}, Cache Location={cache_location}")
    cache = load_cache(cache_location)
    cache[key] = value
    save_cache(cache, cache_location)


def delete_cache_item(key, cache_location=CACHE_LOCATION):
    """Deletes a specific item from the cache."""
    logger.debug(f"Deleting cache item: Key={key}, Cache Location={cache_location}")
    cache = load_cache(cache_location)
    if key in cache:
        del cache[key]
        save_cache(cache, cache_location)
    else:
        logger.debug(f"Cache item not found, deletion skipped: Key={key}")

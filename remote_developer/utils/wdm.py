"""Utility module for file system monitoring using watchdog."""

import asyncio
import time
import watchdog.events
import watchdog.observers

from utils.logger import Logger, get_level_from_env

from components import syncing

logger = Logger(__name__, level=get_level_from_env())


class SyncEventHandler(watchdog.events.PatternMatchingEventHandler):
    """Handles file system events and triggers synchronization."""

    def __init__(
        self,
        config,
        patterns=None,
        ignore_patterns=None,
        ignore_directories=False,
        case_sensitive=False,
    ):
        """Initializes the event handler."""
        super().__init__(patterns, ignore_patterns, ignore_directories, case_sensitive)
        self.config = config
        self.sync_debounce_delay = 1
        self.last_sync_time = 0

    def on_any_event(self, event):
        """Called when any event occurs."""
        current_time = time.time()
        if current_time - self.last_sync_time > self.sync_debounce_delay:
            logger.info(f"Detected change: {event.event_type}  path : {event.src_path}")
            asyncio.create_task(syncing.sync_files(self.config))
            self.last_sync_time = current_time
        else:
            logger.debug(f"Debouncing sync for {event.src_path}")


async def start_watching(config):
    """Starts watching the local directory for changes."""
    path = config["local_dir"]
    event_handler = SyncEventHandler(config)
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    logger.info(f"Watching for changes in {path}...")
    try:
        while True:
            # Keep the task alive
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("Stopping file watching...")
    finally:
        observer.stop()
        observer.join()
        logger.info("File watching stopped.")

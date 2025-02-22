"""Syncing module."""

import time
from utils.logger import Logger, get_level_from_env
from utils.cli_command_executor import CLICommandExecutor

logger = Logger(__name__, level=get_level_from_env())

cli_executor = CLICommandExecutor()


async def sync_files(config):
    """Syncs files from the local directory to the remote directory using rsync.

    Args:
        config (dict): Configuration dictionary containing local directory, remote host,
                       remote directory, and private key path.

    Returns:
        None: This function does not return a value; it runs indefinitely.
    """
    local_dir = config["local_dir"]
    remote_host = config["remote_host"]
    remote_dir = config["remote_dir"]

    # Construct the rsync command
    rsync_command = [
        "rsync",
        "-avz",  # Archive mode (preserves permissions, etc.), verbose, compress
        "--delete",  # Delete extraneous files from dest dirs
        "-e",
        f"ssh -o StrictHostKeyChecking=no -i {config.get('private_key_path', '')} -o UserKnownHostsFile=/dev/null",  # -i is important for the key.
        f"{local_dir}/",  # Source directory (note the trailing slash)
        f"{remote_host}:{remote_dir}",  # Destination directory
    ]
    # Run this forever to ensure the changes
    while True:
        try:
            logger.debug(f"Running rsync command: {' '.join(rsync_command)}")
            result = await cli_executor.execute_command(rsync_command)

            if result.stdout:
                logger.debug(f"rsync output: {result.stdout.strip()}")
            if result.stderr:
                logger.warning(f"rsync error: {result.stderr.strip()}")

        except FileNotFoundError:
            logger.critical("rsync command not found. Please install rsync.")
            exit(1)
        except Exception as e:
            logger.error(f"Error syncing files: {e}")
        except KeyboardInterrupt:
            logger.info("Sync interrupted")
            exit()

        time.sleep(1)

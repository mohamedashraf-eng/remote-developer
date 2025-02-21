"""Execution module."""

from utils.logger import Logger, get_level_from_env
from components.connectivity import execute_remote_command
import posixpath
import os
from utils import regcache

logger = Logger(__name__, level=get_level_from_env())

CACHE_LOCATION = os.getenv("CACHE_LOCATION")


async def run_command_in_devcontainer(config, ssh_client, command_parts):
    """Runs a command inside the running devcontainer.

    Args:
        config (dict): Configuration dictionary containing remote directory and container name.
        ssh_client (paramiko.SSHClient): SSH client object for connecting to the remote server.
        command_parts (list): A list of strings representing the command and its arguments.
    """
    remote_host = config["remote_host"]
    remote_dir = config["remote_dir"]
    workspace_dir = posixpath.join(remote_dir, "workspace")

    # Get container name from cache
    connection_info = regcache.get_cache_item(remote_host, CACHE_LOCATION) or {}
    container_id = connection_info.get("container_id")

    # Construct the command to execute inside the container
    command = " ".join(command_parts)
    docker_exec_command = f'docker exec -t $(docker ps -q --filter "name={container_id}" | head -n 1) bash -c "cd {workspace_dir} && {command}"'

    try:
        logger.info(f"Executing command in devcontainer: {command}")
        output, error = await execute_remote_command(ssh_client, docker_exec_command)

        if error:
            logger.error(f"Error executing command in devcontainer: {error}")
        else:
            logger.info("Command executed successfully in devcontainer.")
            print(f"Command output:\n {output.strip()}")

    except Exception as e:
        logger.error(
            f"An unexpected error occurred while running the command in the devcontainer: {e}"
        )

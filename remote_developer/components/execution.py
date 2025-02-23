"""Execution module."""

from utils.logger import Logger, get_level_from_env
from components.connectivity import execute_remote_command, execute_interactive_command
import posixpath
import os
from utils import regcache
import sys
import select

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
        logger.debug(f"Executing command in devcontainer: {command}")
        output, error = await execute_remote_command(ssh_client, docker_exec_command)

        if error:
            logger.error(f"Error executing command in devcontainer: {error}")
        else:
            logger.debug("Command executed successfully in devcontainer.")
            print(f"Command output:\n {output.strip()}")

    except Exception as e:
        logger.error(
            f"An unexpected error occurred while running the command in the devcontainer: {e}"
        )


async def execute_container_shell(config, ssh_client):
    """Opens an interactive shell session in the running devcontainer.

    Args:
        config (dict): Configuration dictionary containing remote directory and container name.
        ssh_client (paramiko.SSHClient): SSH client object for connecting to the remote server.
    """
    remote_host = config["remote_host"]
    connection_info = regcache.get_cache_item(remote_host, CACHE_LOCATION) or {}
    container_id = connection_info.get("container_id")

    if not container_id:
        logger.error("No container ID found in cache")
        return None

    docker_shell_command = (
        f'docker exec -it $(docker ps -q --filter "name={container_id}" | head -n 1) bash'
    )

    try:
        logger.debug("Opening interactive shell in devcontainer")
        channel = await execute_interactive_command(ssh_client, docker_shell_command)

        if channel is None:
            return

        try:
            # Windows doesn't support termios, so we need a different approach
            if os.name == "nt":
                import msvcrt

                while True:
                    # Check if there's data to read from the channel
                    if channel.recv_ready():
                        data = channel.recv(1024)
                        if len(data) == 0:
                            break
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()

                    # Check if there's input from the user
                    if msvcrt.kbhit():
                        char = msvcrt.getch()
                        channel.send(char)

                    # Add a small sleep to prevent high CPU usage
                    import time

                    time.sleep(0.01)
            else:
                # Unix-like systems can use termios
                import termios
                import tty

                old_tty = termios.tcgetattr(sys.stdin)
                try:
                    tty.setraw(sys.stdin.fileno())
                    tty.setcbreak(sys.stdin.fileno())
                    channel.settimeout(0.0)

                    while True:
                        r, w, e = select.select([channel, sys.stdin], [], [])
                        if channel in r:
                            try:
                                data = channel.recv(1024)
                                if len(data) == 0:
                                    break
                                sys.stdout.buffer.write(data)
                                sys.stdout.buffer.flush()
                            except Exception:
                                break
                        if sys.stdin in r:
                            x = sys.stdin.read(1)
                            if len(x) == 0:
                                break
                            channel.send(x)
                finally:
                    # Restore terminal settings on Unix-like systems
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

        finally:
            channel.close()

    except Exception as e:
        error_msg = f"An unexpected error occurred while opening the shell in the devcontainer: {e}"
        logger.error(error_msg)

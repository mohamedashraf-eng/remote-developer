"""Connectivity module."""

from utils.logger import Logger, get_level_from_env

logger = Logger(__name__, level=get_level_from_env())


async def execute_remote_command(ssh_client, command):
    """Executes a command on the remote host."""
    if (
        not ssh_client
        or not ssh_client.get_transport()
        or not ssh_client.get_transport().is_active()
    ):
        logger.error("SSH connection is not active")
        return None

    try:
        logger.debug(f"Executing remote command: {command}")
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()

        return output, error
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return None, str(e)


async def execute_interactive_command(ssh_client, command):
    """Executes a command with interactive PTY session."""
    if (
        not ssh_client
        or not ssh_client.get_transport()
        or not ssh_client.get_transport().is_active()
    ):
        logger.error("SSH connection is not active")
        return None

    try:
        channel = ssh_client.get_transport().open_session()
        channel.get_pty()
        channel.exec_command(command)
        return channel
    except Exception as e:
        logger.error(f"Error executing interactive command: {e}")
        return None


async def ensure_remote_directory(config, ssh_client):
    """Ensures that the remote directory exists."""
    remote_host = config["remote_host"]
    remote_dir = config["remote_dir"]

    logger.info(f"Ensuring remote directory exists: {remote_dir} on {remote_host}")
    command = f"[ -d {remote_dir} ] || mkdir -p {remote_dir}"
    output, error = await execute_remote_command(ssh_client, command)
    if error:
        logger.error(f"Error creating remote directory: {error.strip()}")
        return False
    return True

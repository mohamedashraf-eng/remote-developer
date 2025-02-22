"""Connectivity module."""

from utils.logger import Logger, get_level_from_env

logger = Logger(__name__, level=get_level_from_env())


async def execute_remote_command(ssh_client, command):
    """Executes a command on the remote server using the SSH client."""
    try:
        logger.debug(f"Executing remote command: {command}")
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = stdout.read().decode("utf-8")
        error = stderr.read().decode("utf-8")
        if output:
            logger.debug(f"Command output: {output.strip()}")
        if error:
            logger.error(f"Command error: {error.strip()}")
        return output, error
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return None, str(e)


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

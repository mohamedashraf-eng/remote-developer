"""Security module."""

import paramiko
import os
import click
import datetime
from utils.logger import Logger, get_level_from_env
from utils.cli_command_executor import CLICommandExecutor
from utils import regcache

logger = Logger(__name__, level=get_level_from_env())

cli_executor = CLICommandExecutor()

CACHE_LOCATION = os.getenv("CACHE_LOCATION")


async def check_and_setup_ssh_keys(config, config_path):
    """Checks for existing SSH keys and guides the user through setup if needed.

    Args:
        config (dict): Configuration dictionary.
        config_path (str): Path to the configuration file.

    Returns:
        bool: True if the configuration file was updated successfully, False otherwise.
    """
    connection_info = regcache.get_cache_item(config["remote_host"], CACHE_LOCATION) or {}
    private_key_path = connection_info.get("private_key_path", None)

    if private_key_path and os.path.exists(private_key_path):
        logger.info(f"Using existing SSH key at: {private_key_path}")
    else:
        username = config["remote_host"].split("@")[0]
        date_str = datetime.datetime.now().strftime("%Y%m%d")  # Get current date in YYYYMMDD format
        key_name = f"{username}_{date_str}_ed25519"  # Construct the key name
        private_key_path = os.path.expanduser(
            os.path.join("~/.ssh", key_name)
        )  # Expand ~ to the user's home directory
        public_key_path = private_key_path + ".pub"

        if os.path.exists(private_key_path) and os.path.exists(public_key_path):
            logger.info(f"SSH key pair found at: {private_key_path} and {public_key_path}")
            logger.info("Skipping key generation as key already exists.")
        else:
            logger.warning("No SSH key pair found or not paired.  Starting SSH key setup...")
            if not await generate_ssh_key_pair(private_key_path):
                return False  # Key generation failed
            logger.info("SSH key pair generated successfully.")

        # Update connection info in cache
        connection_info["remote_host"] = config["remote_host"]
        connection_info["private_key_path"] = private_key_path
        connection_info["ssh_paired"] = os.path.exists(private_key_path) and os.path.exists(
            public_key_path
        )
        regcache.set_cache_item(config["remote_host"], connection_info, CACHE_LOCATION)

    return True


async def generate_ssh_key_pair(private_key_path):
    """Generates a new SSH key pair using ssh-keygen (Ed25519).

    Args:
        private_key_path (str): The path where the private key should be stored.

    Returns:
        bool: True if the key pair was generated successfully, False otherwise.
    """
    try:
        # Use subprocess to run ssh-keygen
        command = [
            "ssh-keygen",
            "-t",
            "ed25519",
            "-f",
            private_key_path,
            "-N",
            "",
        ]  # Generate Ed25519 key
        logger.debug(f"Running command: {' '.join(command)}")
        result = await cli_executor.execute_command(command)

        logger.debug(f"ssh-keygen output: {result.stdout.strip()}")
        if result.stderr:
            logger.warning(f"ssh-keygen warning: {result.stderr.strip()}")
        return True
    except FileNotFoundError:
        logger.critical("ssh-keygen command not found. Please ensure openssh-client is installed.")
        return False
    except Exception as e:
        logger.error(f"Error generating SSH key pair: {e}")
        return False


async def automate_copy_public_key(config, public_key_path, ssh_client):
    """Automates the process of copying the public key to the remote host.

    Args:
        config (dict): Configuration dictionary containing remote host.
        public_key_path (str): Path to the public key file.
        ssh_client (paramiko.SSHClient): Established SSH client connection.

    Returns:
        bool: True if the public key was copied successfully, False otherwise.
    """
    try:
        # Read the public key
        with open(public_key_path) as f:
            public_key = f.read().strip()

        # Construct the SSH command to append the public key to authorized_keys
        ssh_command = (
            "mkdir -p -m 700 ~/.ssh && "  # Ensure .ssh directory exists with secure permissions
            "touch ~/.ssh/authorized_keys && "  # Create authorized_keys if it doesn't exist
            f"echo '{public_key}' >> ~/.ssh/authorized_keys && "  # Append public key
            "chmod 600 ~/.ssh/authorized_keys"  # Set correct permissions
        )

        # Execute the SSH command
        stdin, stdout, stderr = ssh_client.exec_command(ssh_command)
        output = stdout.read().decode("utf-8")
        error = stderr.read().decode("utf-8")

        if error:
            logger.error(f"Error copying public key: {error.strip()}")
            return False
        else:
            logger.debug(f"Public key copied successfully. Output: {output.strip()}")
        return True

    except Exception as e:
        logger.error(f"Error occurred while copying the public key: {e}")
        return False


class SavingKeyVerifier(paramiko.MissingHostKeyPolicy):
    """A custom MissingHostKeyPolicy that saves the host key and prompts the user."""

    def __init__(self):
        """Initializes the key verifier."""
        self.key = None
        self.hostname = None
        self.keytype = None

    def missing_host_key(self, client, hostname, key):
        """Called when a host key is not found in the known_hosts file."""
        logger.debug(f"missing_host_key called for {hostname}")  # Added debug log
        self.key = key
        self.hostname = hostname
        self.keytype = key.get_name()
        return


async def establish_ssh_connection(config, config_path):
    """Establishes an SSH connection to the remote host, reusing a cached connection if available.

    Args:
        config (dict): Configuration dictionary.
        config_path (str): Path to the configuration file.

    Returns:
        paramiko.SSHClient: An SSH client object if the connection was established
                            successfully, None otherwise.
    """
    hostname = config["remote_host"].split("@")[1]
    username = config["remote_host"].split("@")[0]
    remote_host = config["remote_host"]

    try:
        logger.info(f"Connecting to remote host: {remote_host}")

        # Load connection info from cache
        connection_info = regcache.get_cache_item(remote_host, CACHE_LOCATION)
        private_key_path = connection_info.get("private_key_path") if connection_info else None
        public_key_path = private_key_path + ".pub" if private_key_path else None
        status = connection_info.get("status") if connection_info else "disconnected"
        ssh_paired = connection_info.get("ssh_paired", False) if connection_info else False

        # Check if there's a cached connection and if it's healthy
        if (
            connection_info
            and status == "connected"
            and private_key_path
            and os.path.exists(private_key_path)
        ):
            logger.info(f"Reusing cached connection for {remote_host} with key: {private_key_path}")
            # TODO(Wx): Add validation to check if the connection is still alive.
            ssh_client = create_ssh_client(private_key_path, hostname, username, config)
            return ssh_client

        # If no cached connection or it's not healthy, establish a new connection
        logger.info(f"Establishing new SSH connection for {remote_host}")
        ssh_client = create_ssh_client(private_key_path, hostname, username, config)

        key_verifier = SavingKeyVerifier()  # Instance of the custom policy
        ssh_client.set_missing_host_key_policy(key_verifier)  # Set the custom policy

        # Try connecting with the private key first
        if private_key_path and os.path.exists(private_key_path):
            logger.debug(f"Attempting SSH connection with key: {private_key_path}")
            try:
                ssh_client.connect(
                    hostname=hostname,
                    username=username,
                    key_filename=private_key_path,
                    look_for_keys=False,
                    allow_agent=False,
                )  # Agent disabled
            except Exception as e:
                logger.error(f"Connection failed with key: {e}")
                # If key auth fails, try password auth
                logger.debug("Attempting SSH connection with password after key failure.")
                password = click.prompt("Enter password for remote host", hide_input=True)
                ssh_client.connect(
                    hostname=hostname, username=username, password=password, allow_agent=False
                )  # Agent disabled

        else:
            # Prompt for password only if no key is available
            password = click.prompt("Enter password for remote host", hide_input=True)
            logger.debug("Attempting SSH connection with password.")
            ssh_client.connect(
                hostname=hostname, username=username, password=password, allow_agent=False
            )  # Agent disabled

        logger.info("SSH connection established.")

        # Automate public key transfer after successful connection
        if not ssh_paired:
            if not await automate_copy_public_key(config, public_key_path, ssh_client):
                logger.error("Failed to automate public key transfer.")
                ssh_client.close()
                return None
            # Update connection info in cache
            connection_info = regcache.get_cache_item(remote_host, CACHE_LOCATION) or {}
            connection_info["ssh_paired"] = True
            regcache.set_cache_item(remote_host, connection_info, CACHE_LOCATION)
            logger.info("Public key copied and ssh_paired set to True in cache.")
        else:
            logger.info("Skipping public key copy as connection is already paired.")

        # Update connection info in cache
        connection_info = regcache.get_cache_item(remote_host, CACHE_LOCATION) or {}
        connection_info["status"] = "connected"
        connection_info["last_connected"] = datetime.datetime.now().isoformat()
        # connection_info["metadata"] = {"local_ip": get_local_ip()} # Implement get_local_ip()
        regcache.set_cache_item(remote_host, connection_info, CACHE_LOCATION)

        return ssh_client

    except paramiko.AuthenticationException:
        logger.error("Authentication failed. Check your username, password, and SSH keys.")
        click.echo("Authentication failed.")
        if ssh_client:
            ssh_client.close()
        return None
    except paramiko.ssh_exception.SSHException as e:
        logger.warning(f"SSH Key Verification Failed: {e}")

        if key_verifier.key:  # Check if the key was captured
            if click.confirm(
                f"Do you trust this host ({hostname}) and want to add it to your known_hosts file?"
            ):
                try:
                    # Add the host key to known_hosts
                    known_hosts_path = os.path.expanduser("~/.ssh/known_hosts")
                    with open(known_hosts_path, "a") as f:
                        f.write(
                            f"{hostname} {key_verifier.key.get_name()} {key_verifier.key.get_base64()}\n"
                        )
                    logger.info(f"Added host key for {hostname} to {known_hosts_path}")
                    click.echo(f"Added host key for {hostname} to {known_hosts_path}")

                    # Retry the connection
                    ssh_client.close()  # Close the previous client

                    ssh_client = paramiko.SSHClient()
                    ssh_client.load_system_host_keys()
                    key_verifier = SavingKeyVerifier()  # Instance of the custom policy
                    ssh_client.set_missing_host_key_policy(key_verifier)  # Set the custom policy

                    if "private_key_path" in config and os.path.exists(config["private_key_path"]):
                        logger.debug(
                            f"Attempting SSH connection with key: {config['private_key_path']}"
                        )
                        ssh_client.connect(
                            hostname=hostname,
                            username=username,
                            key_filename=config["private_key_path"],
                            look_for_keys=False,
                            allow_agent=False,
                        )  # Agent disabled
                    else:
                        # Prompt for password only if no key is available
                        password = click.prompt("Enter password for remote host", hide_input=True)
                        logger.debug("Attempting SSH connection with password.")
                        ssh_client.connect(
                            hostname=hostname,
                            username=username,
                            password=password,
                            allow_agent=False,
                        )  # Agent disabled

                    # Automate public key transfer after successful connection
                    if not await automate_copy_public_key(config, public_key_path, ssh_client):
                        logger.error("Failed to automate public key transfer.")
                        ssh_client.close()
                        return None

                    return ssh_client

                except Exception as e:
                    logger.error(f"Error adding host key to known_hosts: {e}")
                    click.echo(f"Error adding host key to known_hosts: {e}")
                    if ssh_client:
                        ssh_client.close()
                    return None
            else:
                click.echo("Host key verification failed. Connection rejected.")
                if ssh_client:
                    ssh_client.close()
                return None
        else:
            logger.error("Host key was not captured during initial connection attempt.")
            click.echo("Host key was not captured during initial connection attempt.")
            if ssh_client:
                ssh_client.close()
            return None

    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        click.echo(f"An unexpected error occurred: {e}")
        if ssh_client:
            ssh_client.close()
        return None


def create_ssh_client(private_key_path, hostname, username, config):
    """Creates and configures an SSH client."""
    ssh_client = paramiko.SSHClient()
    ssh_client.load_system_host_keys()
    key_verifier = SavingKeyVerifier()  # Instance of the custom policy
    ssh_client.set_missing_host_key_policy(key_verifier)  # Set the custom policy
    return ssh_client


async def close_ssh_connection(ssh_client, remote_host):
    """Closes the SSH connection and updates the cache.

    Args:
        ssh_client (paramiko.SSHClient): The SSH client object to close.
        remote_host (str): The remote host address.

    Returns:
        None
    """
    if ssh_client:
        ssh_client.close()
        logger.info("SSH connection closed.")
        # Update connection info in cache
        connection_info = regcache.get_cache_item(remote_host, CACHE_LOCATION) or {}
        connection_info["status"] = "disconnected"
        regcache.set_cache_item(remote_host, connection_info, CACHE_LOCATION)

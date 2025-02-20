"""Validation module."""

import ipaddress
import socket
from utils.logger import Logger, get_level_from_env
from utils.cli_command_executor import CLICommandExecutor

logger = Logger("validation", level=get_level_from_env())
cli_executor = CLICommandExecutor()


async def is_valid_ip_address(ip_address):
    """Checks if the given string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip_address)
        return True
    except ValueError:
        logger.warning(f"Invalid IP address: {ip_address}")
        return False


async def is_host_pingable(hostname):
    """Checks if the given hostname is pingable."""
    try:
        # Use subprocess to run ping command
        command = ["ping", "-c", "1", hostname]  # -c 1 to send only one ping
        logger.debug(f"Running command: {' '.join(command)}")
        result = await cli_executor.execute_command(command)

        output = result.stdout.strip()
        logger.debug(f"Ping output: {output}")
        if "Destination host unreachable" in output:  # Adjusted check
            return False
        return True
    except Exception as e:
        logger.error(f"Error pinging host: {hostname}. Error: {e}")
        return False


async def is_port_available(port):
    """Checks if the given port is available on the local machine."""
    try:
        # Create a socket and try to bind to the given port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("localhost", port))
        sock.close()
        logger.debug(f"Port {port} is available on localhost.")
        return True
    except OSError as e:
        logger.warning(f"Port {port} is not available on localhost. Error: {e}")
        return False


async def validate_config_values(config):
    """Validates the configuration values."""
    # Remote Host Validation
    if "remote_host" not in config:
        logger.error("Missing remote_host in config.")
        return False
    remote_host_data = config["remote_host"].split("@")
    if len(remote_host_data) != 2:
        logger.error("Remote Host, doesn't have the correct user@host format.")
        return False
    host = remote_host_data[1]
    if not await is_valid_ip_address(host):
        logger.error("Invalid IP for Remote Host.")
        return False
    if not await is_host_pingable(host):
        logger.error("Cannot Ping Remote Host.")
        return False

    # Port Mapping Validation
    if "port_mappings" in config:
        for port_mapping in config["port_mappings"]:
            try:
                local_port = int(port_mapping.split(":")[0])
                # remote_port = int(port_mapping.split(":")[1]) #Remove due to local checking
                if not await is_port_available(local_port):
                    logger.error(f"Local port {local_port} is not available.")
                    return False
            except (ValueError, IndexError):
                logger.error("Invalid port mapping format")
                return False
    logger.info("All Config Validations has passed")
    return True

"""Building module."""

import os
import tempfile
import posixpath
import yaml
import json
import uuid
from utils.logger import Logger, get_level_from_env
from components.connectivity import execute_remote_command
from utils import regcache

logger = Logger(__name__, level=get_level_from_env())

CACHE_LOCATION = os.getenv("CACHE_LOCATION")


async def create_devcontainer_files(config, ssh_client):
    """Creates the devcontainer files (docker-compose.yml, Dockerfile) and copies the project to the remote server.

    Args:
        config (dict): Configuration dictionary containing remote directory, Docker image,
                       port mappings, template file paths, and local directory.
        ssh_client (paramiko.SSHClient): SSH client object for connecting to the remote server.

    Returns:
        bool: True if the files were created and uploaded successfully, False otherwise.
    """
    remote_dir = config["remote_dir"]
    docker_image = config["docker_image"]
    port_mappings = config.get("port_mappings", [])
    local_dir = config["local_dir"]
    remote_host = config["remote_host"]

    # Define the new directory structure
    devcontainer_dir = posixpath.join(remote_dir, ".devcontainer")
    docker_dir = posixpath.join(remote_dir, "docker")
    workspace_dir = posixpath.join(remote_dir, "workspace")

    # Get or generate container name
    connection_info = regcache.get_cache_item(remote_host, CACHE_LOCATION) or {}
    container_id = connection_info.get("container_id")

    if not container_id:
        container_id = str(uuid.uuid4())  # Generate a new UUID
        connection_info["container_id"] = container_id
        regcache.set_cache_item(remote_host, connection_info, CACHE_LOCATION)
        logger.info(f"Generated new container name for {remote_host}: {container_id}")
    else:
        logger.debug(f"Retrieved container name from cache for {remote_host}: {container_id}")

    config["container_id"] = container_id  # Add container_id to config

    sftp = ssh_client.open_sftp()
    try:
        # Create the directory structure
        await create_remote_directory(sftp, devcontainer_dir, ssh_client)
        await create_remote_directory(sftp, docker_dir, ssh_client)
        await create_remote_directory(sftp, workspace_dir, ssh_client)

        # Define the files to upload with their templates and remote paths
        files_to_upload = [
            {
                "template_path": config["devcontainer_template"],
                "remote_path": posixpath.join(devcontainer_dir, "devcontainer.json"),
                "description": "devcontainer.json",
                "template_vars": {
                    "_project_id": uuid.uuid4(),
                },
                "is_yaml": True,
            },
            {
                "template_path": config["dockerfile_template"],
                "remote_path": posixpath.join(docker_dir, "Dockerfile"),
                "description": "Dockerfile",
                "template_vars": {"_from": docker_image, "_workdir": workspace_dir},
            },
            {
                "template_path": config["docker_compose_template"],
                "remote_path": posixpath.join(docker_dir, "docker-compose.yml"),
                "description": "docker-compose.yml",
                "template_vars": {
                    "_workspace_dir": workspace_dir,
                    "_port_mappings": "\n      ".join([f"- {p}" for p in port_mappings]),
                },
            },
            {
                "template_path": config["dockerignore_template"],
                "remote_path": posixpath.join(docker_dir, ".dockerignore"),
                "description": ".dockerignore",
            },
        ]

        # Upload the files
        for file_info in files_to_upload:
            if not await upload_templated_file(sftp, file_info, ssh_client):
                return False

        # Copy the project files to the workspace directory
        logger.info(f"Copying project from {local_dir} to {workspace_dir}")
        await upload_directory(sftp, local_dir, workspace_dir, ssh_client)
        logger.debug(f"Project copied successfully from {local_dir} to {workspace_dir}")

        # Build and start the devcontainer
        if not await build_and_start_devcontainer(config, ssh_client):
            return False

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return False
    finally:
        sftp.close()
    return True


async def upload_templated_file(sftp, file_info, ssh_client):
    """Uploads a file to the remote server, substituting variables in the template.

    Args:
        sftp (paramiko.sftp_client.SFTPClient): SFTP client object.
        file_info (dict): Dictionary containing template path, remote path, description, and template variables.
        ssh_client (paramiko.SSHClient): SSH client object (not currently used, but kept for potential future use).

    Returns:
        bool: True if the file was uploaded successfully, False otherwise.
    """
    template_path = file_info.get("template_path")
    remote_path = file_info.get("remote_path")
    description = file_info.get("description")
    template_vars = file_info.get("template_vars", {})
    is_yaml = file_info.get("is_yaml", False)  # Check if it's a YAML file

    try:
        with open(template_path) as f:
            template_content = f.read()
        logger.debug(f"Template loaded from {template_path}")
    except FileNotFoundError:
        logger.error(f"Template not found at {template_path}")
        return False

    try:
        if is_yaml:
            # Load YAML and convert to JSON
            template_content = template_content.format(**template_vars)
            yaml_data = yaml.safe_load(template_content)
            file_contents = json.dumps(yaml_data, indent=2)
        else:
            # Substitute variables in the template
            file_contents = template_content.format(**template_vars)
    except (KeyError, yaml.YAMLError) as e:
        logger.error(f"Error processing template: {e}")
        return False

    try:
        sftp.stat(remote_path)
        logger.info(f"{description} already exists at {remote_path}. Skipping upload.")
        return True
    except OSError:
        logger.info(f"Uploading {description} to {remote_path}")
        try:
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
                tmp.write(file_contents)
                tmp.close()
                sftp.put(tmp.name, remote_path)
                os.remove(tmp.name)
            logger.debug(f"{description} uploaded successfully.")
            return True
        except Exception as e:
            logger.error(f"Error uploading {description} to {remote_path}: {e}")
            return False


async def upload_directory(sftp, local_path, remote_path, ssh_client):
    """Uploads a directory and its contents to the remote server, creating non-existent directories.

    Args:
        sftp (paramiko.sftp_client.SFTPClient): SFTP client object.
        local_path (str): Path to the local directory.
        remote_path (str): Path to the remote directory.
        ssh_client (paramiko.SSHClient): SSH client object for executing remote commands.
    """
    ignored_files = [
        ".venv",
        ".cache",
        ".mypy_cache",
        "__pycache__",
        ".pytest_cache",
        ".tox",
        ".eggs",
        ".egg-info",
        "dist",
        "build",
        "buck-out",
        "coverage.xml",
        "nosetests.xml",
        "coverage_html_report",
        "htmlcov",
        "nose2.html-report",
        "nose2.junit-xml-report",
        "nose2.junit-xml-report.xml",
    ]

    for item in os.listdir(local_path):
        if item in ignored_files:
            continue
        local_item_path = os.path.join(local_path, item)
        remote_item_path = posixpath.join(remote_path, item)  # Use posixpath.join

        if os.path.isfile(local_item_path):
            try:
                # Double-check that local_item_path is the correct file path
                if not os.path.exists(local_item_path):
                    logger.error(f"Local file does not exist: {local_item_path}")
                    raise FileNotFoundError(f"Local file does not exist: {local_item_path}")

                # Check if the remote file exists
                try:
                    sftp.stat(remote_item_path)
                    logger.debug(f"File already exists at {remote_item_path}. Skipping upload.")
                except OSError:
                    logger.debug(f"Uploading file: {local_item_path} to {remote_item_path}")
                    sftp.put(local_item_path, remote_item_path)
                    logger.debug(
                        f"File uploaded successfully: {local_item_path} to {remote_item_path}"
                    )

            except Exception as e:
                logger.error(f"Failed to upload file {local_item_path} to {remote_item_path}: {e}")
                raise
        elif os.path.isdir(local_item_path):
            # Check if the remote directory exists
            try:
                sftp.stat(remote_item_path)
                logger.debug(f"Remote directory already exists: {remote_item_path}")
            except FileNotFoundError:
                # Create the remote directory if it doesn't exist
                logger.debug(f"Remote directory does not exist: {remote_item_path}. Creating it.")
                try:
                    sftp.mkdir(remote_item_path)
                    logger.debug(f"Remote directory created successfully: {remote_item_path}")
                except Exception as e:
                    logger.error(f"Error creating remote directory: {remote_item_path}: {e}")
                    raise Exception(f"Failed to create remote directory: {remote_item_path}") from e

            await upload_directory(sftp, local_item_path, remote_item_path, ssh_client)


async def create_remote_directory(sftp, remote_path, ssh_client):
    """Creates a directory on the remote server if it doesn't exist.

    Args:
        sftp (paramiko.sftp_client.SFTPClient): SFTP client object.
        remote_path (str): Path to the remote directory.
        ssh_client (paramiko.SSHClient): SSH client object for executing remote commands.
    """
    try:
        sftp.stat(remote_path)
        logger.debug(f"Remote directory already exists: {remote_path}")
    except FileNotFoundError:
        logger.debug(f"Remote directory does not exist: {remote_path}. Creating it.")
        try:
            sftp.mkdir(remote_path)
            logger.debug(f"Remote directory created successfully: {remote_path}")
        except Exception as e:
            logger.error(f"Error creating remote directory: {remote_path}: {e}")
            raise Exception(f"Failed to create remote directory: {remote_path}") from e


async def validate_and_install_docker_requirements(ssh_client):
    """Validates Docker and Docker Compose requirements on the remote server and installs them if missing.

    Args:
        ssh_client (paramiko.SSHClient): SSH client object for connecting to the remote server.

    Returns:
        bool: True if all requirements are met or successfully installed, False otherwise.
    """
    try:
        # Check if Docker is installed
        docker_installed, docker_version = await check_docker_installed(ssh_client)
        if not docker_installed:
            logger.warning("Docker is not installed. Attempting to install Docker.")
            if not await install_docker(ssh_client):
                logger.error("Failed to install Docker.")
                return False
            docker_installed, docker_version = await check_docker_installed(ssh_client)
            if not docker_installed:
                logger.error("Docker installation failed.")
                return False
        logger.info(f"Docker is installed (Version: {docker_version})")

        # Check if Docker Compose is installed
        docker_compose_installed, docker_compose_version = await check_docker_compose_installed(
            ssh_client
        )
        if not docker_compose_installed:
            logger.warning("Docker Compose is not installed. Attempting to install Docker Compose.")
            if not await install_docker_compose(ssh_client):
                logger.error("Failed to install Docker Compose.")
                return False
            docker_compose_installed, docker_compose_version = await check_docker_compose_installed(
                ssh_client
            )
            if not docker_compose_installed:
                logger.error("Docker Compose installation failed.")
                return False
        logger.info(f"Docker Compose is installed (Version: {docker_compose_version})")

        return True

    except Exception as e:
        logger.error(f"An error occurred while validating Docker requirements: {e}")
        return False


async def check_docker_installed(ssh_client):
    """Checks if Docker is installed on the remote server and returns the version."""
    try:
        command = "docker --version"
        output, error = await execute_remote_command(ssh_client, command)
        if error:
            logger.debug(f"Docker not installed: {error}")
            return False, None
        version = output.splitlines()[0].split("version ")[1].strip()
        logger.debug(f"Docker version: {version}")
        return True, version
    except Exception as e:
        logger.error(f"Error checking Docker version: {e}")
        return False, None


async def check_docker_compose_installed(ssh_client):
    """Checks if Docker Compose is installed on the remote server and returns the version."""
    try:
        command = "docker compose version"
        output, error = await execute_remote_command(ssh_client, command)
        if error:
            logger.debug(f"Docker Compose not installed: {error}")
            return False, None
        version = output.splitlines()[0].split(" ")[3].strip()
        logger.debug(f"Docker Compose version: {version}")
        return True, version
    except Exception as e:
        logger.error(f"Error checking Docker Compose version: {e}")
        return False, None


async def install_docker(ssh_client):
    """Installs Docker on the remote server (Ubuntu/Debian)."""
    try:
        # Update package index
        command1 = "apt-get update"
        output1, error1 = await execute_remote_command(ssh_client, command1)
        if error1:
            logger.error(f"Error updating package index: {error1}")
            return False

        # Install Docker
        command2 = "apt-get install -y docker.io"
        output2, error2 = await execute_remote_command(ssh_client, command2)
        if error2:
            logger.error(f"Error installing Docker: {error2}")
            return False

        # Start Docker service
        command3 = "systemctl start docker"
        output3, error3 = await execute_remote_command(ssh_client, command3)
        if error3:
            logger.warning(f"Error starting Docker service: {error3}")
            # Non-critical error, continue anyway

        logger.info("Docker installed successfully.")
        return True
    except Exception as e:
        logger.error(f"Error installing Docker: {e}")
        return False


async def install_docker_compose(ssh_client):
    """Installs Docker Compose on the remote server (in user's home directory)."""
    try:
        # Ensure ~/.local/bin exists
        command0 = "mkdir -p ~/.local/bin"
        output0, error0 = await execute_remote_command(ssh_client, command0)
        if error0:
            logger.error(f"Error creating ~/.local/bin directory: {error0}")
            return False

        # Download Docker Compose
        command1 = 'curl -sL "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o ~/.local/bin/docker-compose'
        output1, error1 = await execute_remote_command(ssh_client, command1)
        if error1:
            logger.error(f"Error downloading Docker Compose: {error1}")
            return False

        # Apply executable permissions
        command2 = "chmod +x ~/.local/bin/docker-compose"
        output2, error2 = await execute_remote_command(ssh_client, command2)
        if error2:
            logger.error(f"Error applying executable permissions to Docker Compose: {error2}")
            return False

        # Add ~/.local/bin to PATH (if not already there)
        command3 = "if ! grep -q ~/.local/bin ~/.profile; then echo 'export PATH=$PATH:~/.local/bin' >> ~/.profile; fi"
        output3, error3 = await execute_remote_command(ssh_client, command3)
        if error3:
            logger.warning(f"Error adding ~/.local/bin to PATH: {error3}")
            # Non-critical error, continue anyway

        # Source ~/.profile to update the PATH in the current session
        command4 = "source ~/.profile"
        output4, error4 = await execute_remote_command(ssh_client, command4)
        if error4:
            logger.warning(f"Error sourcing ~/.profile: {error4}")
            # Non-critical error, continue anyway

        # Check if Docker Compose is installed (after updating PATH)
        docker_compose_installed, _ = await check_docker_compose_installed(ssh_client)
        if not docker_compose_installed:
            logger.error("Docker Compose installation failed after updating PATH.")
            return False

        logger.info("Docker Compose installed successfully in ~/.local/bin.")
        return True
    except Exception as e:
        logger.error(f"Error installing Docker Compose: {e}")
        return False


async def build_and_start_devcontainer(config, ssh_client):
    """Builds the Docker image and starts the devcontainer on the remote server.

    Args:
        config (dict): Configuration dictionary containing remote directory.
        ssh_client (paramiko.SSHClient): SSH client object for connecting to the remote server.

    Returns:
        bool: True if the devcontainer was built and started successfully, False otherwise.
    """
    is_valid = await validate_and_install_docker_requirements(ssh_client)

    if not is_valid:
        logger.error("Failed to validate and install Docker requirements.")
        return False

    remote_dir = config["remote_dir"]
    docker_dir = posixpath.join(remote_dir, "docker")
    container_id = config["container_id"]
    try:
        command = f"cd {docker_dir} && docker compose -p {container_id} build && docker compose -p {container_id} up -d"
        output, error = await execute_remote_command(ssh_client, command)

        if error:
            if "created" in error.lower():
                logger.info("Devcontainer already created.")
            elif "running" in error.lower():
                logger.info("Devcontainer already running.")
            elif "starting" in error.lower():
                logger.info("Devcontainer already starting.")
            else:
                logger.error(f"Error starting devcontainer: {error}")
                return False
            return True
        else:
            logger.info("Devcontainer started successfully.")
            logger.debug(f"Devcontainer start output: {output.strip()}")
            return True
    except Exception as e:
        logger.error(
            f"An unexpected error occurred building the docker image and running the docker compose: {e}"
        )
        return False

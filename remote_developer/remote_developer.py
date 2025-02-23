"""Main entry point for the remote_developer CLI."""

import click
import json
import asyncio
import os

from utils.logger import Logger, get_level_from_env
from utils import validation

from components import security, connectivity, building, syncing, execution
from utils.wdm import start_watching

logger = Logger(__name__, level=get_level_from_env())

CACHE_LOCATION = os.getenv("CACHE_LOCATION")


async def setup_and_connect(ctx):
    """Sets up the environment and establishes an SSH connection.

    Returns:
        An SSH client object if successful, None otherwise.
    """
    config_path = ctx.obj["config_path"]
    config = ctx.obj["config"]
    ssh_client = None

    try:
        # Validate Configurations
        if not await validation.validate_config_values(config):
            raise Exception("Configuration validation failed.")

        # Check and setup SSH keys
        if not await security.check_and_setup_ssh_keys(config, config_path):
            raise Exception("SSH key setup failed.")

        # Reload the configuration from file
        logger.info("Reloading configuration after SSH key setup.")
        with open(config_path) as f:
            config = json.load(f)
        ctx.obj["config"] = config

        # Establish SSH connection
        ssh_client = await security.establish_ssh_connection(config, config_path)
        if not ssh_client:
            raise Exception("Failed to establish SSH connection.")

        if not await connectivity.ensure_remote_directory(config, ssh_client):
            raise Exception("Failed to ensure remote directory exists.")
        if not await building.create_devcontainer_files(config, ssh_client):
            raise Exception("Failed to create devcontainer files.")
        if not await building.build_and_start_devcontainer(config, ssh_client):
            raise Exception("Failed to build and start devcontainer.")

        return ssh_client

    except Exception as e:
        logger.error(f"An error occurred during setup: {e}")
        if ssh_client:
            try:
                await security.close_ssh_connection(ssh_client, config["remote_host"])
            except Exception as close_err:
                logger.error(f"Error closing SSH connection during setup failure: {close_err}")
        return None


async def run_rdc_command(ctx, ssh_client, command):
    """Runs a command in the remote devcontainer."""
    try:
        await execution.run_command_in_devcontainer(ctx.obj["config"], ssh_client, command)
    except Exception as e:
        logger.error(f"An error occurred while running the command: {e}")


async def open_shell(ctx, ssh_client):
    """Opens a shell in the remote devcontainer."""
    try:
        await execution.execute_container_shell(ctx.obj["config"], ssh_client)
    except Exception as e:
        logger.error(f"An error occurred while starting the shell: {e}")


async def interactive_shell(ctx, ssh_client):
    """Opens an interactive shell to the devcontainer."""
    logger.info("Entering interactive shell. Type 'exit' to quit.")
    try:
        await open_shell(ctx, ssh_client)
    except KeyboardInterrupt:
        logger.debug("\nExiting interactive shell.")
    except Exception as e:
        logger.error(f"Error running interactive shell: {e}")
    finally:
        try:
            await security.close_ssh_connection(ssh_client, ctx.obj["config"]["remote_host"])
        except Exception as close_err:
            logger.error(f"Error closing SSH connection: {close_err}")


@click.group()
@click.pass_context
@click.option("--config", required=True, help="Path to the config.json file.")
@click.option("--path", required=True, help="Path to the project directory.")
@click.option(
    "--auto-sync", is_flag=True, help="Automatically syncs the local and remote directories."
)
@click.option(
    "--keep-alive", is_flag=True, help="Keep the SSH connection alive after the command completes."
)
def cli(ctx, config, path, auto_sync, keep_alive):
    """Remote development automation."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["project_path"] = path
    ctx.obj["auto_sync"] = auto_sync
    ctx.obj["keep_alive"] = keep_alive

    try:
        logger.info(f"Loading configuration from {config}")
        with open(config) as f:
            ctx.obj["config"] = json.load(f)
        logger.debug(f"Configuration loaded: {ctx.obj['config']}")

        # Modify the config to update the local_dir field
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        if not os.path.isdir(path):
            logger.error(f"Invalid path: {path}. Please provide a valid directory path.")
            exit(1)
        ctx.obj["config"]["local_dir"] = path
        logger.info(f"Setting local_dir to: {path}")

        # Save the updated config back to the file
        with open(config, "w") as f:
            json.dump(ctx.obj["config"], f, indent=2)
            logger.debug("Configuration updated with new local_dir")

    except FileNotFoundError:
        logger.error(f"Config file not found at {config}")
        exit(1)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in config file.")
        exit(1)


@cli.command()
@click.pass_context
def start(ctx):
    """Starts the devcontainer."""

    async def start_devcontainer_async():
        ssh_client = await setup_and_connect(ctx)
        if ssh_client:
            if ctx.obj.get("keep_alive"):
                await interactive_shell(ctx, ssh_client)
            else:
                try:
                    await security.close_ssh_connection(
                        ssh_client, ctx.obj["config"]["remote_host"]
                    )
                except Exception as close_err:
                    logger.error(f"Error closing SSH connection: {close_err}")

    asyncio.run(start_devcontainer_async())

    if ctx.obj.get("auto_sync"):
        config = ctx.obj["config"]
        asyncio.create_task(start_watching(config), name="file-watching")


@cli.command()
@click.pass_context
def sync(ctx):
    """Syncs files from the local directory to the remote directory."""
    config = ctx.obj["config"]
    asyncio.run(syncing.sync_files(config))


@cli.command()
@click.argument("command", nargs=-1)
@click.pass_context
def run(ctx, command):
    """Runs a command on the remote host."""
    config = ctx.obj["config"]
    config_path = ctx.obj["config_path"]

    async def run_remote_command_async():
        ssh_client = await security.establish_ssh_connection(config, config_path)
        if not ssh_client:
            raise Exception("Failed to establish SSH connection.")
        if ssh_client:
            try:
                await run_rdc_command(ctx, ssh_client, command)
            finally:
                try:
                    await security.close_ssh_connection(
                        ssh_client, ctx.obj["config"]["remote_host"]
                    )
                except Exception as close_err:
                    logger.error(f"Error closing SSH connection: {close_err}")

    asyncio.run(run_remote_command_async())


if __name__ == "__main__":
    cli(obj={})

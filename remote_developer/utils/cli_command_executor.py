"""Utility module for executing CLI commands."""

import asyncio
import subprocess
import shlex
import re
from utils.logger import Logger

logger = Logger(__name__)


class CommandResult:
    """Represents the result of a command execution."""

    def __init__(self, stdout, stderr, returncode):
        """Initializes a new CommandResult instance."""
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class CLICommandExecutor:
    """Executes CLI commands using subprocess."""

    def __init__(self, allowed_commands=None, disallowed_patterns=None):
        """
        Initializes the CLICommandExecutor with optional security configurations.

        Args:
            allowed_commands (list, optional): A list of explicitly allowed commands
                                                (e.g., ['rsync', 'ping']). If None, all
                                                commands are allowed subject to disallowed_patterns.
                                                Defaults to None.
            disallowed_patterns (list, optional): A list of regular expression patterns
                                                    that, if matched in a command, will cause
                                                    the execution to be rejected.  This is a
                                                    secondary safety net. Defaults to None.
        """
        self.allowed_commands = allowed_commands
        self.disallowed_patterns = (
            disallowed_patterns
            if disallowed_patterns is not None
            # Default disallowed patterns for security.
            else [
                r";",  # Prevent command chaining
                r"\|",  # Prevent command piping
                r">>",  # Prevent output redirection/overwriting
                r"`",  # Prevent command substitution
                r"\$",  # Prevent variable expansion
            ]
        )
        logger.debug(
            f"CLICommandExecutor initialized with allowed_commands: {self.allowed_commands} and disallowed_patterns: {self.disallowed_patterns}"
        )

    async def execute_command(self, command):
        """Executes a command using subprocess and returns the output."""
        logger.debug(f"Attempting to execute command: {command}")
        if not self._is_command_safe(command):
            logger.warning(f"Command {command} is not safe to execute, blocking execution.")
            return CommandResult(
                "", "Command execution blocked due to security policy.", 1
            )  # Or raise an exception

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            logger.debug(f"Process started with PID: {process.pid}")
            stdout, stderr = await process.communicate()
            logger.debug(f"Process finished with return code: {process.returncode}")
            result = CommandResult(stdout.decode(), stderr.decode(), process.returncode)
            logger.debug(
                f"Command execution result: stdout='{result.stdout}', stderr='{result.stderr}', returncode={result.returncode}"
            )
            return result
        except FileNotFoundError as e:
            logger.error(f"Command not found: {e}")
            return CommandResult(
                "", f"Command not found: {e}", 127
            )  # Mimic shell return code for command not found
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            return CommandResult("", f"An unexpected error occurred: {e}", 1)

    def _is_command_safe(self, command):
        """Checks if a command is safe to execute based on allowed commands and disallowed patterns."""
        # Check if command is allowed (if allowed_commands is specified)
        if self.allowed_commands is not None and command[0] not in self.allowed_commands:
            logger.warning(f"Command {command[0]} is not in the list of allowed commands.")
            return False

        # Check for disallowed patterns
        command_string = " ".join(shlex.quote(arg) for arg in command)  # Quote arguments for safety
        logger.debug(f"Command string after quoting: {command_string}")
        for pattern in self.disallowed_patterns:
            if re.search(pattern, command_string):
                logger.warning(f"Command blocked due to matching disallowed pattern: {pattern}")
                return False

        return True

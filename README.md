# 🚀 Remote Developer CLI 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Automate your remote development workflow with this powerful CLI tool! 💻✨

## 🌟 Features

- **Devcontainer Automation:** Effortlessly create, build, and start devcontainers on remote hosts. 📦
- **Interactive Shell:** Access your devcontainer with an interactive shell for seamless command execution. 🐚
- **Automatic File Synchronization:** Keep your local and remote directories in sync with real-time file monitoring. 🔄
- **SSH Key Management:** Securely manage SSH keys for authentication. 🔑
- **Docker Integration:** Validate and install Docker and Docker Compose on remote servers. 🐳
- **Configuration Management:** Easily configure your remote development environment with a JSON configuration file. ⚙️
- **Caching:** Reuses SSH connections and container names for faster subsequent runs. ⚡
- **Logging:** Detailed logging for debugging and monitoring. 📝

## 🛠️ Prerequisites

- Python >=3.11
- [uv](https://docs.astral.sh/uv/getting-started/installation/) python package manager

- A remote host with SSH access
- Docker and Docker Compose installed on the remote host

> **Note**: The CLI can install them for you!

## 📦 Installation

1.  Clone the repository:

    ```bash
    git clone github.com/mohamedashraf-eng/remote-developer
    cd remote-developer
    ```

2.  Install the required Python packages:

    ```bash
    uv venv
    uv sync && uv sync --upgrade
    ```

## ⚙️ Configuration

1.  Create a `config.json` file (or copy and modify `remote-developer-config.example.json`):

    ```json
    {
      "remote_host": "user@remote-host.example.com",
      "docker_image": "example-image:latest",
      "remote_dir": "/home/user/example-project",
      "port_mappings": [
        "1234:1234",
        "5678:5678"
      ],
      "devcontainer_template": "./templates/devcontainer-template.txt.example",
      "dockerfile_template": "./templates/dockerfile-template.txt.example",
      "docker_compose_template": "./templates/docker-compose-template.txt.example",
      "dockerignore_template": "./templates/dockerignore-template.txt.example"
    }
    ```

    - `remote_host`: SSH user and host (e.g., `user@192.168.1.100`).
    - `docker_image`: Docker image to use for the devcontainer.
    - `remote_dir`: Remote directory where the project will be stored.
    - `port_mappings`: List of port mappings (e.g., `["8080:8080", "3000:3000"]`).
    - `devcontainer_template`, `dockerfile_template`, `docker_compose_template`, `dockerignore_template`: Paths to template files.

2.  Customize the template files in the `templates/` directory as needed.  Example templates are provided with the `.example` extension.

> **Tip:** The base templates function correctly as is.

## 🚀 Usage

```bash
uv run remote_developer.py --config config.json --path /path/to/your/project <command>
```

- `--config`: Path to the `config.json` file.
- `--path`: Path to your local project directory.

### Commands

#### `start`

Starts the devcontainer.

```bash
python remote_developer.py --config config.json --path /path/to/your/project start
```

Options:

- `--auto-sync`: Automatically syncs the local and remote directories.
- `--keep-alive`: Keeps the SSH connection alive and opens an interactive shell after starting the devcontainer.

Example:

```bash
python remote_developer.py --config config.json --path /path/to/your/project start --auto-sync --keep-alive
```

#### `sync`

Syncs files from the local directory to the remote directory.

```bash
python remote_developer.py --config config.json --path /path/to/your/project sync
```

Options:

- `--auto-sync`: Starts auto-sync in the background, monitoring for file changes.

Example:

```bash
python remote_developer.py --config config.json --path /path/to/your/project sync --auto-sync
```

#### `run`

Runs a command on the remote host inside the devcontainer.

```bash
python remote_developer.py --config config.json --path /path/to/your/project run <command>
```

Example:

```bash
python remote_developer.py --config config.json --path /path/to/your/project run ls -l /home/user/example-project/workspace
```

## 💡 Examples

1.  **Start the devcontainer and keep the shell open:**

    ```bash
    python remote_developer.py --config config.json --path /path/to/your/project start --keep-alive
    ```

    This will start the devcontainer and open an interactive shell. You can then execute commands directly in the devcontainer. Type `exit` to close the shell.

2.  **Start the devcontainer with automatic file synchronization:**

    ```bash
    python remote_developer.py --config config.json --path /path/to/your/project start --auto-sync
    ```

    This will start the devcontainer and automatically sync files between your local and remote directories.

3.  **Run a specific command in the devcontainer:**

    ```bash
    python remote_developer.py --config config.json --path /path/to/your/project run python --version
    ```

    This will execute the `python --version` command inside the devcontainer and print the output.

## 🔒 Security

- SSH keys are used for authentication. The CLI will guide you through generating and setting up SSH keys if needed.
- The CLI uses `rsync` over SSH for file synchronization, ensuring secure data transfer.
- The `CLICommandExecutor` class includes security measures to prevent command injection vulnerabilities.

## 📝 Logging

Detailed logs are generated to help you troubleshoot any issues. The log level can be configured using the `LOG_LEVEL` environment variable (e.g., `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

Example:

```bash
LOG_LEVEL=DEBUG python remote_developer.py --config config.json --path /path/to/your/project start
```

## ⚙️ Advanced Configuration

### Environment Variables

- `CACHE_LOCATION`: Specifies the location of the cache file. Defaults to platform-specific locations (Windows Registry, macOS plist, Linux JSON file).
- `LOG_LEVEL`: Specifies the log level. Defaults to `INFO`.

### Templates

The CLI uses template files for generating the `devcontainer.json`, `Dockerfile`, and `docker-compose.yml` files. You can customize these templates to suit your specific needs.

## 🤝 Contributing

Contributions are welcome! Please submit a pull request with your changes.

## 📜 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

`Copyright (c) 2025 MoWx`

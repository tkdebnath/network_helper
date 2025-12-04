# Network Helper App

A robust FastAPI-based application designed to automate the management and upgrading of Cisco IOS devices. This tool streamlines network operations by handling firmware upgrades, device information gathering, and pre-upgrade checks with concurrency control and safety mechanisms.

## Key Features

*   **Automated IOS Upgrades**: Orchestrate firmware upgrades across multiple devices in parallel.
*   **Concurrency Control**: Configurable worker limits (default: 10) to prevent network congestion.
*   **Queue Management**: Robust queuing system with status tracking (Queued, Running, Completed, Failed).
*   **Resilience**: Automatic queue clearing on application startup to ensure a clean state.
*   **Security**: API Key authentication for sensitive operations (POST requests).
*   **Operations**:
    *   **Upgrade**: Download image, verify checksum/size, install, and reboot.
    *   **Refresh Device**: Collect and update device details (Model, OS, Serial, etc.).
    *   **Cancel Schedule**: Cancel pending scheduled operations on devices.
    *   **Prechecks**: Run and compare pre-upgrade checks.

## Installation & Setup

### Prerequisites

*   Python 3.10 or higher
*   `uv` (Recommended for dependency management) or `pip`

### Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd network_helper
    ```

2.  **Install dependencies:**
    ```bash
    uv sync
    # OR
    pip install -r requirements.txt
    ```

3.  **Configure Environment:**
    Create a `env.env` file in the root directory (see [Configuration](#configuration) below).

## Configuration

The application uses a `env.env` file for configuration. Ensure the following variables are set:

```ini
# Device Credentials
DEVICE_USERNAME=admin
DEVICE_PASSWORD=your_password
DEVICE_ENABLE_PASSWORD=your_enable_password

# Security
API_KEY=your-secure-api-key-here

# Concurrency
WORKER_COUNT=10

# IOS Image Settings
FULL_IOS_FILENAME=cat9k_iosxe.17.12.05.SPA.bin
TARGET_IOS_VERSION=17.12.5
FULL_IOS_FILESIZE=1312262395
FLASH_FREE_SPACE_THRESHOLD=7516192768

# File Server URLs (Region specific)
DEFAULT_HTTP_FILE_SERVER_URL="http://x.x.x.x/Cisco/C9XXX/cat9k_iosxe.17.12.05.SPA.bin"
AMER_HTTP_FILE_SERVER_URL="http://x.x.x.x/Cisco/C9XXX/cat9k_iosxe.17.12.05.SPA.bin"
# Add other regions as needed (APAC, EMEA, etc.)

# Webhooks
BLINKOPS_WEBHOOK_URL=https://your-webhook-url
```

## Usage

### Starting the Server

Run the application using `uvicorn`:

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Deployment

You can also run the application using Docker Compose:

1.  **Build and Run:**
    ```bash
    docker compose up -d --build
    ```

2.  **View Logs:**
    ```bash
    docker compose logs -f
    ```

3.  **Stop:**
    ```bash
    docker compose down
    ```

### Fresh Rebuild

To completely wipe the environment (containers, image, database) and start fresh:

```bash
chmod +x rebuild.sh
./rebuild.sh
```

### Authentication

All **POST** requests require an API Key header:

*   **Header Name**: `access_token`
*   **Value**: The value set in `API_KEY` env var.

### API Endpoints

#### Operations

*   **POST** `/api/upgrade`: Trigger bulk operations.
    *   **Payload**: List of device objects.
    *   **Operation Types**: `upgrade`, `refresh_device`, `cancel_schedule`.
    *   **Example**:
        ```json
        [
          {
            "device_name": "switch-01",
            "ip_address": "192.168.1.10",
            "device_type": "cisco_ios",
            "operation_type": "upgrade",
            "region": "AMER"
          }
        ]
        ```

#### Monitoring

*   **GET** `/api/queue`: View currently queued and in-progress tasks.
*   **GET** `/api/history`: View execution history of completed/failed tasks.
*   **GET** `/api/status/{task_id}`: Get detailed status and logs for a specific task.

#### Prechecks

*   **GET** `/api/prechecks/devices`: List devices with available prechecks.
*   **GET** `/api/prechecks/{device_name}`: List precheck files for a device.
*   **POST** `/api/prechecks/diff`: Compare two precheck files.

## Project Structure

*   `app/`: Core application logic.
    *   `api/`: FastAPI route definitions (`endpoints.py`).
    *   `core/`: Task execution engine (`executor.py`).
    *   `db/`: Database models and session management.
*   `tasks/`: Network automation logic.
    *   `upgrade_task.py`: Main upgrade workflow.
    *   `refresh_device.py`: Device info collection.
    *   `templates/`: Jinja2 templates for EEM applets.
*   `env.env`: Configuration file.

## Extending Functionality

To add a new operation (e.g., `backup_config`):

1.  **Create a Task File**:
    Create a new file in `tasks/` (e.g., `tasks/backup_task.py`) and implement your logic.
    ```python
    async def execute_backup(device_connection, request_data, log_callback):
        # Your logic here
        return {"status": "completed", "logs": "Backup done"}
    ```

2.  **Register Operation**:
    Update `tasks/operations.py` to import your function and add it to the `perform_operations` dispatcher.
    ```python
    from tasks.backup_task import execute_backup
    
    # ... inside perform_operations ...
    elif operation_type == "backup_config":
        return await execute_backup(device_connection, request_data, log_callback)
    ```

3.  **Trigger**:
    Send a POST request with `operation_type: "backup_config"`.

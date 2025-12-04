import asyncio
import os
from typing import Optional
from tasks.base_task import LogCallback, base_log
from tasks.__helpers import verify_target_model, verify_file_exist, flash_free_space, software_version_check
from scrapli import AsyncScrapli
from jinja2 import Template

async def test_execute_cancel_schedule(device_connection: dict, request_data: dict, log_callback: Optional[LogCallback] = None) -> dict:
    """
    Executes the cancel schedule operation.
    """
    device_name = request_data.get("device_name")
    logs = []
    
    async def log(msg: str):
        await base_log(logs, msg, log_callback)

    await log(f"Starting upgrade for {device_name} with params: {request_data}...")
    await asyncio.sleep(2) # Simulate connection time
    
    if "error" in device_name.lower():
        await log("Connection failed: Host unreachable.")
        return {"status": "failed", "logs": "\n".join(logs)}
        
    await log(f"Connected to {device_name}.")
    await asyncio.sleep(1)
    
    await log("Checking current version...")
    await asyncio.sleep(1)
    
    if "warning" in device_name.lower():
         await log("Warning: Disk space low, but proceeding...")
    else:
        await log("Free space available.")
    
    await log("Target file exists in flash.")
    await log("Transferring new image...")
    await asyncio.sleep(3) # Simulate transfer
    
    await log("Installing image...")
    await asyncio.sleep(2)
    
    await log("Running configuration saved.")
    await log("Rebooting device...")

    
    await log(f"Upgrade completed for {device_name}.")
    
    status = "completed"
    if "warning" in device_name.lower():
        status = "warning"
    
    return {"status": status, "logs": "\n".join(logs)}


async def execute_cancel_schedule(device_connection: dict, request_data: dict, log_callback: Optional[LogCallback] = None) -> dict:
    """
    Executes the cancel schedule operation.
    """
    device_name = request_data.get("device_name")
    logs = []

    async def log(msg: str):
        await base_log(logs, msg, log_callback)

    # Connect to device
    async with AsyncScrapli(**device_connection) as conn:
        await log("Checking connectivity...")
        await asyncio.sleep(1)

        await log(f"Cancelling Install IOS Image schedule for {device_name}...")
        await asyncio.sleep(2)

        await log(f"Connected to {device_name}.")
        await asyncio.sleep(1)
        
        commands = [
            "no event manager applet InstallIOSImage",
        ]

        # send config set
        config_set = await conn.send_configs(commands, stop_on_failed=True)
        if config_set.failed:
            await log("Failed to cancel Install IOS Image schedule.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("Install IOS Image schedule cancelled successfully.")
            await asyncio.sleep(1)
        
        # save the running configuration
        save_running_config = await conn.send_command("write memory", timeout_ops=600)
        if save_running_config.failed:
            await log("Failed to save running configuration.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("Running configuration saved successfully.")
            await asyncio.sleep(1)
        
        await log(f"Install IOS Image schedule cancelled for {device_name}.")
        return {"status": "completed", "logs": "\n".join(logs)}
        
        
        

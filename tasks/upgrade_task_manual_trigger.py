import asyncio
import os
from typing import Optional
from tasks.base_task import LogCallback, base_log
from tasks.__helpers import verify_target_model, verify_file_exist, flash_free_space, software_version_check
from scrapli import AsyncScrapli
from jinja2 import Template

async def test_execute_upgrade_manual(device_connection: dict, request_data: dict, log_callback: Optional[LogCallback] = None) -> dict:
    """
    Executes the upgrade operation.
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


async def execute_upgrade_manual(device_connection: dict, request_data: dict, log_callback: Optional[LogCallback] = None) -> dict:
    """
    Executes the upgrade operation.
    """
    device_name = request_data.get("device_name")
    logs = []
    
    template_dir = os.path.join(os.path.dirname(__file__), "templates")

    async def log(msg: str):
        await base_log(logs, msg, log_callback)

    # Connect to device
    async with AsyncScrapli(**device_connection) as conn:
        await log("Checking connectivity...")
        await asyncio.sleep(1)

        await log(f"Starting upgrade for {device_name} with params: {request_data}...")
        await asyncio.sleep(2)
            
        await log(f"Connected to {device_name}.")
        await asyncio.sleep(1)
        
        # Check Version
        await log("Checking current version...")
        await asyncio.sleep(1)

        # Get device version
        show_version = await conn.send_command("show version")
        parsed_version = show_version.genie_parse_output()

        # Verify target model
        if not verify_target_model(parsed_version):
            await log("Device is not a Catalyst 9K series.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("Device is a Catalyst 9K series.")
            await asyncio.sleep(1)
            
        # Check version compatibility
        target_version = os.getenv("TARGET_IOS_VERSION", "17.12.5")
        current_version_info = software_version_check(parsed_version['version']['version'])
        target_version_info = software_version_check(target_version)

        upgrade_required = is_upgrade_required(current_version_info, target_version_info)
        if not upgrade_required:
            await log("Device is already running the target version.")
            return {"status": "completed", "logs": "\n".join(logs)}
        else:
            await log("Upgrade is required.")
            await asyncio.sleep(1)
            
        # Check free space
        await log("Checking free space...")
        await asyncio.sleep(1)
        show_file_systems = await conn.send_command("show file systems")
        parsed_file_systems = show_file_systems.genie_parse_output()
        free_space = flash_free_space(parsed_file_systems)

        if not free_space:
            await log("Not enough free space for upgrade.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("Free space available.")
            await asyncio.sleep(1)

        # Verify file exist
        await log("Checking file exist...")
        await asyncio.sleep(1)

        full_ios_filename = os.getenv("FULL_IOS_FILENAME")
        full_ios_filesize = os.getenv("FULL_IOS_FILESIZE")
        if not full_ios_filename:
            await log("Full IOS filename not found.")
            return {"status": "failed", "logs": "\n".join(logs)}
        if not full_ios_filesize:
            await log("Full IOS filesize not found.")
            return {"status": "failed", "logs": "\n".join(logs)}

        show_flash = await conn.send_command(f"show flash:{full_ios_filename}")
        parsed_flash = show_flash.genie_parse_output()

        file_exist = verify_file_exist(parsed_flash)

        if not file_exist:
            await log("File does not exist in flash.")
        else:
            await log("File exists in flash.")
            await asyncio.sleep(1)
        # If file does not exist in flash, then abort, manual intervention required
        if not file_exist:
            await log("File does not exist in flash. Manual intervention required.")
            return {"status": "failed", "logs": "\n".join(logs)}
        # If free space is not enough, then abort, manual intervention required
        if not free_space:
            await log("Not enough free space for upgrade. Manual intervention required.")
            return {"status": "failed", "logs": "\n".join(logs)}
        
        # save the running configuration
        save_running_config = await conn.send_command("write memory", timeout_ops=600)
        if save_running_config.failed:
            await log("Failed to save running configuration.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("Running configuration saved successfully.")
            await asyncio.sleep(1)

        
        # Check if applet already exists and is pending with while loop for 360 seconds
        while True:
            applet_pending = await conn.send_command("show event manager policy active | i InstallIOSImage")
            if "pending" in applet_pending.result or "running" in applet_pending.result:
                await log("IOS install applet is pending.")
                return {"status": "failed", "logs": "\n".join(logs)}
            else:
                await log("IOS install applet is not pending.")
                await asyncio.sleep(1)
                break
        
        # Delete existing applet InstallIOSImage and create new applet
        # Render jinja2 template for ios_file_install
        ios_file_install_template = Template(open(os.path.join(template_dir, "ios_file_install.j2")).read(), keep_trailing_newline=True)
        ios_file_install_config = ios_file_install_template.render(full_ios_filename=full_ios_filename, schedule_date_time=None, full_ios_filesize=full_ios_filesize)

        # send rendered config to device
        ios_file_install_applet = await conn.send_configs(ios_file_install_config.strip().splitlines(), stop_on_failed=True)
        if ios_file_install_applet.failed:
            await log("Failed to create IOS file install applet.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("IOS file install applet created successfully.")
            await asyncio.sleep(1)

        # save running config
        save_running_config = await conn.send_command("write memory", timeout_ops=600)
        if save_running_config.failed:
            await log("Failed to save running configuration.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("Running configuration saved successfully.")
            await asyncio.sleep(1)
        
        # run IOS install applet
        ios_install_applet_run = await conn.send_command("event manager run InstallIOSImage", timeout_ops=600)
        if ios_install_applet_run.failed:
            await log("Failed to run IOS install applet.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("IOS install applet run successfully.")
            await asyncio.sleep(15)
        
        # Check IOS install applet status
        # Check if applet already exists and is pending with while loop for 360 seconds
        while True:
            applet_pending = await conn.send_command("show event manager policy active | i InstallIOSImage")
            if "pending" in applet_pending.result or "running" in applet_pending.result:
                await log("IOS install applet is running.")
                await asyncio.sleep(20)
            else:
                await log("IOS install applet is completed.")
                await log("Rebooting device...")
                await asyncio.sleep(1)
                break
        await log("Task completed successfully.")
        return {"status": "completed", "logs": "\n".join(logs)}

import asyncio
import os
from typing import Optional
from tasks.base_task import LogCallback, base_log
from tasks.__helpers import verify_target_model, verify_file_exist, flash_free_space, software_version_check, is_upgrade_required, convert_date_time_to_applet_cron_format
from tasks.__connection_helpers import http_client_source_set, verify_ios_downloading
from scrapli import AsyncScrapli
from jinja2 import Template

async def execute_upgrade_auto(device_connection: dict, request_data: dict, log_callback: Optional[LogCallback] = None) -> dict:
    """
    Executes the upgrade operation.
    """
    device_name = request_data.get("device_name")
    logs = []
    
    async def log(msg: str):
        await base_log(logs, msg, log_callback)

    template_dir = os.path.join(os.path.dirname(__file__), "templates")

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
        # If free space is not enough and file exist in flash, then abort, manual intervention required
        if not free_space and file_exist:
            await log("Not enough free space for upgrade. Manual intervention required.")
            return {"status": "failed", "logs": "\n".join(logs)}
        # If free space is not enough, and file is also not exist in flash, then clear the flash
        if not free_space and not file_exist:
            await log("Not enough free space for upgrade. Clearing flash...")
            await asyncio.sleep(1)
            # Create event manager applet to clear the flash
            event_manager_applet = os.path.join(template_dir, "event_applet_clean_flash.txt")
            push_event_manager_applet = await conn.send_configs_from_file(event_manager_applet)

            if push_event_manager_applet.failed:
                await log("Failed to create event manager applet.")
                return {"status": "failed", "logs": "\n".join(logs)}

            await log("Event manager applet created successfully.")
            await asyncio.sleep(1)

            # Run event manager applet
            run_event_manager_applet = await conn.send_command("event manager run CLEAN_FLASH", timeout_ops=600)
            await asyncio.sleep(20)

            # Check event manager applet status
            policy_pending = await conn.send_command("show event manager policy active | i CLEAN_FLASH")
            if "running" in policy_pending.result or "pend" in policy_pending.result:
                # Wait for the event manager applet to complete
                await asyncio.sleep(20)
            else:
                # recheck the flash
                show_file_systems = await conn.send_command("show file systems")
                parsed_file_systems = show_file_systems.genie_parse_output()
                free_space = flash_free_space(parsed_file_systems)
                if not free_space:
                    await log("Not enough free space for upgrade. Manual intervention required.")
                    return {"status": "failed", "logs": "\n".join(logs)}

                await log("Flash cleared successfully.")
                await asyncio.sleep(1)
        
        # Transfer new image
        # TODO: disable file prompt and set http client source interface
        # TODO: transfer new image
        http_client_source_configure = await http_client_source_set(conn, request_data)
        if not http_client_source_configure:
            await log("Failed to set HTTP client source interface.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("HTTP client source interface set successfully.")
            await asyncio.sleep(1)
        
        
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
            applet_pending = await conn.send_command("show event manager policy active | i CopyIOSImage")
            if "pending" in applet_pending.result or "running" in applet_pending.result:
                await log("IOS download applet is pending.")
                await asyncio.sleep(20)
            else:
                await log("IOS download applet is not pending.")
                await asyncio.sleep(1)
                break

        # Download IOS file as per region
        target_ios_url = os.getenv(f"{request_data['region'].upper()}_HTTP_FILE_SERVER_URL", os.getenv("DEFAULT_HTTP_FILE_SERVER_URL"))
        ios_download_template = Template(open(os.path.join(template_dir, "ios_download.j2")).read(), keep_trailing_newline=True)
        ios_download_config = ios_download_template.render(target_ios_url=target_ios_url)
        ios_download_applet = await conn.send_configs(ios_download_config.strip().splitlines(), stop_on_failed=True)
        if ios_download_applet.failed:
            await log("Failed to create IOS download applet.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("IOS download applet created successfully.")
            await asyncio.sleep(1)
        
        # Run IOS download applet
        ios_download_applet_run = await conn.send_command("event manager run CopyIOSImage", timeout_ops=600)
        if ios_download_applet_run.failed:
            await log("Failed to run IOS download applet.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("IOS download applet run successfully.")
            await asyncio.sleep(1)
        
        # Check IOS download applet status
        download_status = await verify_ios_downloading(conn)
        if not download_status:
            await log("IOS download failed.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("IOS is downloading.")
            await asyncio.sleep(1)
        

        # Checking for schedule time
        schedule_time = request_data.get("schedule_time", None)
        schedule_date_time = None
        if schedule_time:
            schedule_date_time = convert_date_time_to_applet_cron_format(schedule_time)
            if not schedule_date_time:
                await log("Invalid schedule time format.")
                return {"status": "failed", "logs": "\n".join(logs)}
                

        # Render jinja2 template for ios_file_install
        ios_file_install_template = Template(open(os.path.join(template_dir, "ios_file_install.j2")).read(), keep_trailing_newline=True)
        ios_file_install_config = ios_file_install_template.render(full_ios_filename=full_ios_filename, schedule_date_time=schedule_date_time, full_ios_filesize=full_ios_filesize)

        # send rendered config to device
        ios_file_install_applet = await conn.send_configs(ios_file_install_config.strip().splitlines(), stop_on_failed=True)
        if ios_file_install_applet.failed:
            await log("Failed to create IOS file install applet.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("IOS file install applet created successfully.")
            await log("Applet scheduled for: " + schedule_time)
        
        # save the running configuration
        save_running_config = await conn.send_command("write memory", timeout_ops=600)
        if save_running_config.failed:
            await log("Failed to save running configuration.")
            return {"status": "failed", "logs": "\n".join(logs)}
        else:
            await log("Running configuration saved successfully.")
            await asyncio.sleep(1)
        
        if not schedule_date_time:
            await log("Schedule time not provided. Manual trigger will be handled seperately.")
            return {"status": "completed", "logs": "\n".join(logs)}
        
        await log(f"IOS file install applet scheduled for {device_name}.")
        return {"status": "completed", "logs": "\n".join(logs)}
        
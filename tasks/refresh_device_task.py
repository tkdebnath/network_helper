import asyncio
from typing import Optional
from tasks.base_task import LogCallback, base_log
from scrapli import AsyncScrapli
import os
from datetime import datetime


async def execute_refresh_device(device_connection: dict, request_data: dict, log_callback: Optional[LogCallback] = None) -> dict:
    """
    Executes the refresh operation.
    """
    device_name = request_data.get("device_name")
    device_ip = request_data.get("ip_address")
    logs = []
    
    async def log(msg: str):
        await base_log(logs, msg, log_callback)

    await log(f"Starting refresh for {device_name}...")
    await asyncio.sleep(1)

    # Connect to device
    async with AsyncScrapli(**device_connection) as conn:
        await log("Checking connectivity...")
        await asyncio.sleep(1)
        
        await log("Connection successful.")
        await asyncio.sleep(1)

        await log("Collecting device information...")
        await asyncio.sleep(1)

        show_version = await conn.send_command("show version")
        parsed_version = show_version.genie_parse_output()

        if not parsed_version or not parsed_version.get('version', None):
            await log("Failed to collect device information.")
            return {"status": "failed", "logs": "\n".join(logs)}
        
        parsed_version = dict(parsed_version)
        payload = {}
        payload["action"] = "Device_Record"
        payload["hostname"] = device_name
        payload["site"] = request_data["site"]
        payload["region"] = request_data["region"]
        payload["model"] = parsed_version['version']['chassis']
        payload["platform"] = parsed_version['version']['os']
        payload["ip_address"] = request_data["ip_address"]
        payload["software_version"] = parsed_version['version']['version']
        payload["boot_method"] = parsed_version['version']['system_image']
        payload["boot_mode"] = "Install Mode" if ".conf" in parsed_version['version']['system_image'] else "Bundle Mode"
        
        switch_data_new(**payload)

        target_version = os.getenv("TARGET_IOS_VERSION", "17.12.5")
        if target_version and parsed_version['version']['version']:
            current_version_info = software_version_check(parsed_version['version']['version'])
            target_version_info = software_version_check(target_version)

            if current_version_info and target_version_info:
                upgrade_required = is_upgrade_required(current_version_info, target_version_info)
                if upgrade_required and file_flag and space_flag:
                    phase = "Phase_1"

                if not file_flag or not space_flag:
                    phase = "Phase_0"
                
                if not upgrade_required:
                    phase = "Phase_2"
                    
                            
        # update phase in host data
        phase_payload = {}
        phase_payload["action"] = phase
        phase_payload["hostname"] = device_name
        switch_data_new(**phase_payload)
        
        await log("Device information collected successfully.")
        return {"status": "completed", "logs": "\n".join(logs)}
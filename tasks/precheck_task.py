import asyncio
from typing import Optional
from tasks.base_task import LogCallback, base_log
from scrapli import AsyncScrapli
import os
from datetime import datetime

async def test_execute_precheck(device_connection: dict, request_data: dict, log_callback: Optional[LogCallback] = None) -> dict:
    """
    Executes the precheck operation.
    """
    device_name = request_data.get("device_name")
    logs = []
    
    async def log(msg: str):
        await base_log(logs, msg, log_callback)

    await log(f"Starting precheck for {device_name}...")
    await asyncio.sleep(1)
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{device_name}_{timestamp}.txt"
    filepath = os.path.join("app/static/prechecks", filename)
    
    await log("Checking connectivity...")
    await asyncio.sleep(1)
    
    await log("Running 'show running-config'...")
    await asyncio.sleep(1)
    
    await log("Running 'show version'...")
    await asyncio.sleep(1)
    
    # Simulate output
    output = f"""! Device: {device_name}
! Time: {timestamp}
! Command: show running-config
!
hostname {device_name}
!
interface GigabitEthernet1/0/1
 description Uplink
 switchport mode trunk
!
interface GigabitEthernet1/0/2
 description Access Port
 switchport mode access
 switchport access vlan 10
!
! Command: show version
Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 15.2(2)E6, RELEASE SOFTWARE (fc1)
System image file is "flash:/c2960-lanbasek9-mz.152-2.E6.bin"
"""
    
    # Write to file
    try:
        with open(filepath, "w") as f:
            f.write(output)
        await log(f"Output saved to {filename}")
    except Exception as e:
        await log(f"Error saving file: {e}")
        return {"status": "failed", "logs": "\n".join(logs)}
    
    await log("Precheck completed successfully.")
    
    return {"status": "completed", "logs": "\n".join(logs)}



async def execute_precheck(device_connection: dict, request_data: dict, log_callback: Optional[LogCallback] = None) -> dict:
    """
    Executes the precheck operation.
    """
    device_name = request_data.get("device_name")
    device_ip = request_data.get("ip_address")
    logs = []
    
    async def log(msg: str):
        await base_log(logs, msg, log_callback)

    await log(f"Starting precheck for {device_name}...")
    await asyncio.sleep(1)


    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{device_name}_{timestamp}.txt"
    filepath = os.path.join("app/static/prechecks", filename)

    # Connect to device
    async with AsyncScrapli(**device_connection) as conn:
        await log("Checking connectivity...")
        await asyncio.sleep(1)
        
        check_commands = [
            "show file systems",
            "show boot",
            "show version",
            "show mac address-table",
            "show ip protocols",
            "show ip arp",
            "show cdp neighbors detail",
            "show ip interface brief",
            "show interface status",
            "show power inline",
            "show running-config"
            ]

        output = f"! Device: {device_name}\n! IP Address: {device_ip}\n! Time: {timestamp}\n\n"

        for command in check_commands:
            await log(f"Running '{command}'...")
            await asyncio.sleep(1)
            result = await conn.send_command(command)
            output += f"==================================================================\n\n! Command: {command}\n! Output:\n\n{result.result}\n\n"
        
        # Write to file
        try:
            with open(filepath, "w") as f:
                f.write(output)
            await log(f"Output saved to {filename}")
        except Exception as e:
            await log(f"Error saving file: {e}")
            return {"status": "failed", "logs": "\n".join(logs)}
        
        await log("Precheck completed successfully.")
        
        return {"status": "completed", "logs": "\n".join(logs)}
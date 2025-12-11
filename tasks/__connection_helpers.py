import os
import asyncio
from scrapli import AsyncScrapli
from rich import print


async def connect_to_device(device_details: dict):

    # Map NetBox platform to Scrapli platform
    platform_map = {
        "ios": "cisco_iosxe",
        "cisco_ios": "cisco_iosxe",
        "iosxe": "cisco_iosxe",
        "cisco_xe": "cisco_iosxe",
        "ios-xe": "cisco_iosxe",
    }
    # Supported platform only IOS-XE
    platform = platform_map.get(device_details.get('platform', '').lower(), None)

    # Load credentials from environment variables
    username = os.getenv("DEVICE_USERNAME")
    password = os.getenv("DEVICE_PASSWORD")
    enable_password = os.getenv("DEVICE_ENABLE_PASSWORD")

    # verify all required fields are present
    if not username or not password or not enable_password:
        raise ValueError("Missing credentials")
    
    if not device_details['ip_address']:
        raise ValueError("Missing IP address")
    
    if not platform:
        raise ValueError("Unsupported platform")
    
    # Prepare Scrapli connection parameters
    timeout = 30  # Default to 30 if None
    device_connection = {
        "host": device_details['ip_address'],
        "platform": platform,
        "auth_username": username,
        "auth_password": password,
        "auth_secondary": enable_password,
        "auth_strict_key": False,
        "transport": "asyncssh",
        "timeout_socket": timeout,
        "timeout_transport": timeout * 2,
        "ssh_config_file": False,
        "transport_options": {
                "open_cmd": [
                    "-o", "KexAlgorithms=+diffie-hellman-group1-sha1,diffie-hellman-group-exchange-sha1,diffie-hellman-group14-sha1",
                    "-o", "HostKeyAlgorithms=+ssh-rsa,ssh-dss",
                    "-o", "Ciphers=+aes128-cbc,3des-cbc",
                    "-o", "ServerAliveInterval=30",    # Safe - SSH protocol level
                    "-o", "ServerAliveCountMax=3",     # Max failures before disconnect
                    "-o", "TCPKeepAlive=yes",          # TCP level keepalive
                ]
            }
    }
    return device_connection

async def verify_ios_downloading(conn: AsyncScrapli):
    """
    {
    'dir': {
        'flash0:/cat9k_iosxe.17.12.05.SPA.bin': {
            'files': {'cat9k_iosxe.17.12.05.SPA.bin': {'index': '270', 'permissions': '-rw-', 'size': '9999360', 'last_modified_date': 'Dec 4 2025 06:27:04 +00:00'}},
            'bytes_total': '2142715904',
            'bytes_free': '2020167680'
        },
        'dir': 'flash0:/cat9k_iosxe.17.12.05.SPA.bin'
    }
   }
    """
    """Verify if the IOS file is downloading with size increasing"""
    full_ios_filename = os.getenv("FULL_IOS_FILENAME")

    
    if not full_ios_filename:
        return
    try:
        current_size = 0
        previous_size = 0
        await asyncio.sleep(20)
        max_retries = 15 # 5 minutes total (15 * 20s)
        retries = 0
        
        while(current_size < int(os.getenv("FULL_IOS_FILESIZE", 1312262395))):
            if retries > max_retries:
                return False
            
            ios_file = await conn.send_command(f"dir flash:{full_ios_filename}")
            parse_ios = ios_file.genie_parse_output()
            parse_ios = dict(parse_ios)

            print(parse_ios)

            if parse_ios and parse_ios.get('dir', ''):
                previous_size = current_size
                # Handle potential path variations in genie output
                file_info = parse_ios['dir'].get(f'flash:/{full_ios_filename}', {}).get('files', {}).get(f'{full_ios_filename}', {})
                if not file_info:
                     # Try alternative path if needed or just fail safely
                     file_info = parse_ios['dir'].get(f'flash0:/{full_ios_filename}', {}).get('files', {}).get(f'{full_ios_filename}', {})
                
                if file_info:
                    current_size = int(file_info.get('size', 0))
                
                print(file_info)
                print(f"Current size: {current_size}, Previous size: {previous_size}")
            
            # Check for success (size increasing or complete)
            if (current_size > 0 and previous_size > 0 and current_size > previous_size) or current_size == int(os.getenv("FULL_IOS_FILESIZE", 1312262395)):
                return True

            # If size is 0 and we've waited a bit, it might not have started yet, but if it stays 0 it's a failure.
            # However, the original logic returned None (False) if current_size == 0 immediately.
            # Let's allow a few retries even if 0, but if it stays 0 for too long, fail.
            
            await asyncio.sleep(20)
            retries += 1
            
        return True
    except:
        return False


async def http_client_source_set(conn: AsyncScrapli, device_details):
    """Set HTTP client source interface on the device"""
    try:
        # Find tacacs source interface
        source_interface = None
        tacacs_source_intf = await conn.send_command("show running-config | i ip tacacs source-interface")
        if not tacacs_source_intf.failed and "ip tacacs source-interface" in tacacs_source_intf.result:
            text = tacacs_source_intf.result.split()[-1]
            if text.startswith("Vlan") or text.startswith("Ten") or text.startswith("Twe") or text.startswith("Gig") or text.startswith("Port"):
                source_interface = text
        
        if not source_interface:
            show_interfaces = await conn.send_command("show interfaces")
            show_interfaces_parsed = show_interfaces.textfsm_parse_output()
            if isinstance(show_interfaces_parsed, list) and len(show_interfaces_parsed) > 0:
                for interface in show_interfaces_parsed:
                    if interface.get('ip_address', 0) == device_details['ip_address']:
                        source_interface = interface['interface']
        
        if not source_interface:
            return

        config_commands = [
            "file prompt quiet",
            f"ip http client source-interface {source_interface}"
        ]
        response = await conn.send_configs(config_commands, stop_on_failed=True)
        if response.failed:
            return False
        return True
    except Exception as e:
        return False
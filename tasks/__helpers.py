"""
Shared utility functions for device operations across the application.

This module contains common helper functions used by multiple API endpoints
for device validation, version checking, and external integrations.
"""

import os
import re
import requests
from datetime import datetime
from dateutil import parser


def verify_target_model(show_version):
    """
    Target model is C9300 and C9500
    """
    # Check if device is Catalyst 9K series
    if show_version and show_version.get('version', None):
        chassis_model = show_version['version'].get('chassis', '')
        if "C9300" in chassis_model or "C9500" in chassis_model:
            return True
    return False

def switch_data_new(**kwargs):
    """
    Send device data to BlinkOps webhook for tracking and monitoring.
    
    Args:
        **kwargs: Arbitrary keyword arguments containing device data.
                 Must include 'hostname' key for the webhook to be triggered.
    
    Returns:
        requests.Response: Response object from the webhook POST request if successful.
        None: If hostname is not provided or webhook URL is not configured.
    
    Environment Variables:
        BLINKOPS_WEBHOOK_URL: The URL endpoint for the BlinkOps webhook.
    """
    HEADERS = {
        "Content-Type": "application/json"
    }
    if "hostname" in kwargs.keys():
        blinkops_webhook_url = os.getenv("BLINKOPS_WEBHOOK_URL")
        if blinkops_webhook_url:
            response = requests.post(url=blinkops_webhook_url, headers=HEADERS, json=kwargs, verify=False)
            response.raise_for_status()
            return response


def verify_file_exist(show_flash):
    """
    Verify if the IOS file exists in flash with the correct file size.
    
    Args:
        show_flash (dict): Parsed output from 'show flash' command containing
                          directory structure and file information.
    
    Returns:
        bool: True if the file exists with matching size.
        None: If file doesn't exist, size doesn't match, or required env vars are missing.
    
    Environment Variables:
        FULL_IOS_FILENAME: The complete filename of the IOS image to verify.
        FULL_IOS_FILESIZE: Expected file size in bytes (default: 1312262395).
    """
    full_ios_filename = os.getenv("FULL_IOS_FILENAME")
    
    if not full_ios_filename:
        return
    try:
        size = show_flash['dir'][f'flash:/{full_ios_filename}']['files'][f'{full_ios_filename}']['size']
        if size == int(os.getenv("FULL_IOS_FILESIZE", 1312262395)):
            return True
        return
    except:
        return


def software_version_check(software_version: str) -> dict:
    """
    Parse software version string into major, minor, and patch components.
    
    Extracts numeric version components from a version string, removing any
    non-numeric characters except periods.
    
    Args:
        software_version (str): Version string (e.g., "17.9.4a", "16.12.8").
    
    Returns:
        dict: Dictionary with 'major', 'minor', 'patch' keys containing integer values.
              Returns empty dict if input is empty or None.
    
    Examples:
        >>> software_version_check("17.9.4a")
        {'major': 17, 'minor': 9, 'patch': 4}
        >>> software_version_check("16.12")
        {'major': 16, 'minor': 12, 'patch': 0}
    """
    if not software_version:
        return {}

    software_version = re.sub(r'[^\d.]', '', software_version)

    major_version = software_version.split(".")[0]
    minor_version = software_version.split(".")[1] if len(software_version.split(".")) > 1 else "0"
    patch_version = software_version.split(".")[2] if len(software_version.split(".")) > 2 else "0"

    return {
        "major": int(major_version),
        "minor": int(minor_version),
        "patch": int(patch_version)
    }


def flash_free_space(show_file_systems, post_download: bool = False):
    """
    Check if flash storage has sufficient free space for IOS operations.
    
    Validates that the flash filesystem has enough free space compared to
    a configured threshold to safely perform IOS upgrades.
    
    Args:
        show_file_systems (dict): Parsed output from 'show file systems' command
                                 containing filesystem information.
    
    Returns:
        bool: True if sufficient free space is available.
        None: If free space is below threshold or flash filesystem not found.
    
    Environment Variables:
        FLASH_FREE_SPACE_THRESHOLD: Minimum free bytes required (default: 6516192768 / ~6GB).
    """
    file_systems = show_file_systems.get('file_systems', None)
    ios_file_size = 0
    if post_download:
        ios_file_size = int(os.getenv("FULL_IOS_FILESIZE", 1312262395))

    flash_free_space_threshold = int(os.getenv("FLASH_FREE_SPACE_THRESHOLD", 7516192768))

    if file_systems and flash_free_space_threshold:
        for index in file_systems:
            if "flash" in file_systems[index].get('prefixes', ''):
                free_size = file_systems[index].get('free_size', '')
                # free space is less than threshold
                if free_size and free_size < (flash_free_space_threshold - ios_file_size):  # ~6 GB
                    return
        return True


def is_upgrade_required(current_version, target_version) -> bool:
    """
    Compare current and target versions to determine if upgrade is required.
    
    Compares semantic versions by checking major, minor, and patch components
    in order to determine if an upgrade from current to target version is needed.
    
    Args:
        current_version (dict): Dictionary with 'major', 'minor', 'patch' keys
                               containing integer values of current version.
        target_version (dict): Dictionary with 'major', 'minor', 'patch' keys
                              containing integer values of target version.
    
    Returns:
        bool: True if target version is higher than current version (upgrade needed).
              False if current version is equal to or higher than target version.
    
    Examples:
        >>> is_upgrade_required({'major': 16, 'minor': 12, 'patch': 8}, 
        ...                     {'major': 17, 'minor': 9, 'patch': 4})
        True
        >>> is_upgrade_required({'major': 17, 'minor': 12, 'patch': 5}, 
        ...                     {'major': 17, 'minor': 9, 'patch': 4})
        False
    """
    # Compare major version first
    if target_version['major'] > current_version['major']:
        return True
    elif target_version['major'] < current_version['major']:
        return False
    
    # If major versions are equal, compare minor version
    if target_version['minor'] > current_version['minor']:
        return True
    elif target_version['minor'] < current_version['minor']:
        return False
    
    # If both major and minor are equal, compare patch version
    if target_version['patch'] > current_version['patch']:
        return True
    elif target_version['patch'] < current_version['patch']:
        return False
    
    # All versions are equal, no upgrade required
    return False

def convert_date_time_to_applet_cron_format(date_time_str):
    """
    Convert a date-time string in any common format to
    Cisco Event Applet cron format 'MM HH DD MM DOW'.
 
    Args:
        date_time_str (str): The date-time string to convert in any common format.
                           Examples:
                           - '08:59:34.021 UTC Thu Nov 20 2025'
                           - '2025-11-20 08:59:34'
                           - 'Nov 20, 2025 8:59 AM'
                           - '20/11/2025 08:59:34'
 
    Returns:
        str: The converted date-time string in Cisco Event Applet cron format.
    """
    # Common datetime formats to try
    common_formats = [
        '%H:%M:%S.%f UTC %a %b %d %Y',  # 08:59:34.021 UTC Thu Nov 20 2025
        '%Y-%m-%d %H:%M:%S',            # 2025-11-20 08:59:34
        '%Y-%m-%d %H:%M:%S.%f',         # 2025-11-20 08:59:34.021
        '%d/%m/%Y %H:%M:%S',            # 20/11/2025 08:59:34
        '%m/%d/%Y %H:%M:%S',            # 11/20/2025 08:59:34
        '%Y%m%d %H:%M:%S',              # 20251120 08:59:34
        '%d-%m-%Y %H:%M:%S',            # 20-11-2025 08:59:34
        '%b %d, %Y %I:%M %p',           # Nov 20, 2025 8:59 AM
        '%B %d, %Y %I:%M:%S %p',        # November 20, 2025 8:59:34 AM
    ]
   
    dt = None
   
    # Try common formats first
    for fmt in common_formats:
        try:
            dt = datetime.strptime(date_time_str, fmt)
            break
        except ValueError:
            continue
   
    # If common formats fail, use dateutil parser as fallback
    if dt is None:
        try:
            dt = parser.parse(date_time_str)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Unable to parse datetime string: {date_time_str}. Error: {e}")
   
    # Format as Cisco Event Applet cron: minute hour day month weekday
    cron_format = f"{dt.minute} {dt.hour} {dt.day} {dt.month} {dt.weekday()}"
    return cron_format
import requests
import os
from typing import List, Optional, Dict, Any

def fetch_devices_from_netbox(site_name: Optional[str] = None, region: Optional[str] = None, device_model: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch devices from Netbox using GraphQL.
    
    Args:
        site_name: Optional site name to filter devices.
        region: Optional region to filter devices.
        device_model: Optional device model to filter devices.
        
    Returns:
        List of dictionaries containing device details.
    """
    netbox_url = os.getenv("NETBOX_URL")
    netbox_token = os.getenv("NETBOX_TOKEN")
    
    if not netbox_url or not netbox_token:
        raise ValueError("NETBOX_URL and NETBOX_TOKEN must be set in environment variables.")
    
    # Ensure URL ends with /graphql/
    if not netbox_url.endswith("/graphql/"):
        netbox_url = f"{netbox_url.rstrip('/')}/graphql/"
        
    headers = {
        "Authorization": f"Token {netbox_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Build GraphQL query filters based on the provided parameters
    filters_parts = []
    
    # Device model filter (i_contains for partial match)
    if device_model:
        filters_parts.append(f'device_type: {{model: {{i_contains: "{device_model}"}}}}')
    
    # Site filter (i_exact for exact match)
    if site_name:
        filters_parts.append(f'site: {{name: {{i_exact: "{site_name}"}}}}')
        
    # Region filter (if provided)
    if region:
        filters_parts.append(f'region: {{name: {{i_exact: "{region}"}}}}')
    
    # Primary IP status
    filters_parts.append(f'primary_ip4: {{status: STATUS_ACTIVE}}')
    # Device status
    filters_parts.append(f'status: STATUS_ACTIVE')
    
    # Combine all filters
    filter_string = ", ".join(filters_parts) if filters_parts else ""
    
    # GraphQL query based on your provided structure
    query = f"""
    query MyQuery {{
      device_list(filters: {{{filter_string}}}) {{
        id
        name
        virtual_chassis {{
          name
        }}
        platform {{
          name
          slug
        }}
        primary_ip4 {{
          address
        }}
        site {{
          name
          region {{
            name
          }}
        }}
        device_type {{
          part_number
        }}
        role {{
          name
        }}
        status
        tags {{
          name
        }}
        custom_fields
      }}
    }}
    """
    
    payload = {
        "query": query,
        "variables": {}
    }
    
    try:
        response = requests.post(netbox_url, json=payload, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        data = response.json()
        
        if "errors" in data:
            raise Exception(f"GraphQL Error: {data['errors']}")
            
        devices = data.get("data", {}).get("device_list", [])
        
        processed_devices = []
        import logging
        logger = logging.getLogger(__name__)
        
        for device in devices:
            # Get device name - prefer virtual chassis name if it exists
            hostname = device.get("name")
            if not hostname:
                logger.warning(f"Device missing name, skipping: {device}")
                continue
            
            # Check if device is part of a virtual chassis
            virtual_chassis_name = None
            if device.get("virtual_chassis") and device["virtual_chassis"].get("name"):
                virtual_chassis_name = device["virtual_chassis"]["name"]
                logger.info(f"Device {hostname} is part of virtual chassis: {virtual_chassis_name}")
            
            # Use virtual chassis name if it exists, otherwise use device name
            effective_hostname = virtual_chassis_name if virtual_chassis_name else hostname
            
            # Get primary IP
            primary_ip = None
            if device.get("primary_ip4"):
                # Extract IP from CIDR notation (e.g., "192.168.1.1/24" -> "192.168.1.1")
                ip_with_mask = device["primary_ip4"].get("address", "")
                primary_ip = ip_with_mask.split("/")[0] if ip_with_mask else None
            
            
            if not primary_ip:
                logger.warning(f"Device {hostname} has no primary IP, skipping")
                continue
            
            # Get platform
            platform_slug = "ios" # Default
            if device.get("platform"):
                platform_slug = device["platform"].get("slug", "ios")

            processed_devices.append({
                "device_name": effective_hostname,
                "ip_address": primary_ip,
                "site": device.get("site", {}).get("name"),
                "region": device.get("site", {}).get("region", {}).get("name"),
                "platform": platform_slug,
                "model": device.get("device_type", {}).get("part_number")
            })
        return processed_devices
        
    except requests.HTTPError as e:
        raise Exception(f"Netbox API Error: {e}. Response: {e.response.text}")
    except requests.RequestException as e:
        raise Exception(f"Failed to connect to Netbox: {str(e)}")
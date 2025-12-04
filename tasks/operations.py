from typing import Callable, Optional
from tasks.upgrade_task import execute_upgrade
from tasks.precheck_task import execute_precheck
from tasks.upgrade_task_manual_trigger import execute_upgrade_manual
from tasks.refresh_device import execute_refresh_device
from tasks.__connection_helpers import connect_to_device
from tasks.cancel_schedule import execute_cancel_schedule

async def perform_operations(request_data: dict, log_callback: Optional[Callable[[str], None]] = None) -> dict:
    """
    Dispatches the operation to the appropriate task function based on operation_type.
    """
    
    # TODO: Add connection logic here
    device_connection = await connect_to_device(request_data)
    if not device_connection:
        return {"status": "failed", "logs": "Failed to generate device connection parameters."}
    
    operation_type = request_data.get("operation_type", "not_specified").lower()
    
    if operation_type == "upgrade":
        return await execute_upgrade(device_connection, request_data, log_callback)
    elif operation_type == "precheck":
        return await execute_precheck(device_connection, request_data, log_callback)
    elif operation_type == "upgrade_manual":
        return await execute_upgrade_manual(device_connection, request_data, log_callback)
    elif operation_type == "refresh_device":
        return await execute_refresh_device(device_connection, request_data, log_callback)
    elif operation_type == "cancel_schedule":
        return await execute_cancel_schedule(device_connection, request_data, log_callback)
    else:
        return {"status": "failed", "logs": f"Unknown operation type: {operation_type}. Please specify a valid operation type."}

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Security, status
from fastapi.security import APIKeyHeader
from sqlmodel import Session, select
from typing import List
import uuid

from app.db.session import get_session
from app.db.models import DeviceQueue, ExecutionStatus, TaskStatus
from app.core.executor import run_batch_operations
import os
import difflib
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

router = APIRouter()

api_key_header = APIKeyHeader(name="access_token", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    api_key = os.getenv("API_KEY")
    if not api_key:
        # Log error or handle missing config? For now, just fail auth securely.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: API_KEY not set",
        )
        
    if api_key_header == api_key:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials",
    )

from typing import Optional

class UpgradeRequest(BaseModel):
    device_name: str
    operation_type: Optional[str] = "upgrade"
    site: Optional[str] = None
    region: Optional[str] = None
    ip_address: str
    device_type: str
    schedule_time: Optional[str] = None
    target_file: Optional[str] = None
    target_version: Optional[str] = None

from sqlalchemy import func

@router.post("/upgrade", dependencies=[Depends(get_api_key)])
async def trigger_upgrade(
    requests: List[UpgradeRequest], 
    background_tasks: BackgroundTasks, 
    session: Session = Depends(get_session)
    ):
    """
    Trigger firmware upgrade for a list of devices.
    
    Parameters (Required):
    - ip_address: Device IP or hostname
    - platform: Scrapli platform name (e.g., IOS-XE, IOS)
    - operation_type: Type of operation to perform. Valid values:
        * refresh_device: Collect device information and determine upgrade phase
        * precheck: Execute and save specific commands (show version, running-config, mac address-table, ip protocols, ip arp)
        * upgrade_auto: IOS Activation and Installation (creates applet, triggers installation)
        * upgrade_manual: IOS Activation and Installation (creates applet, triggers installation)
        * cancel_schedule: Cancel scheduled upgrade
    """

    results = []
    for req in requests:
        device_name = req.device_name
        
        # Check if device is already in queue or running
        existing_op = session.exec(select(DeviceQueue).where(func.lower(DeviceQueue.device_name) == device_name.lower())).first()
        if existing_op:
            results.append({"device_name": device_name, "status": "skipped", "reason": "Already in queue or processing"})
            continue
        
        # Add to queue
        queue_item = DeviceQueue(device_name=device_name, operation_type=req.operation_type, status="queued")
        session.add(queue_item)
        session.commit()
        session.refresh(queue_item)
        
        # Create execution record
        task_id = str(uuid.uuid4())
        execution_record = ExecutionStatus(
            task_id=task_id,
            device_name=device_name,
            status=TaskStatus.QUEUED
        )
        session.add(execution_record)
        session.commit()
        
        # Trigger background task
        results.append({"device_name": device_name, "task_id": task_id, "status": "triggered"})
        
    # Trigger all tasks in parallel
    tasks_data = []
    for res in results:
        if res["status"] == "triggered":
            # Find the original request data
            req_data = next(r.dict() for r in requests if r.device_name == res["device_name"])
            tasks_data.append({"task_id": res["task_id"], "request_data": req_data})
            
    if tasks_data:
        background_tasks.add_task(run_batch_operations, tasks_data)
    
    return {"results": results}

class DiffRequest(BaseModel):
    file1: str
    file2: str

@router.get("/prechecks/devices")
def list_precheck_devices():
    precheck_dir = "app/static/prechecks"
    if not os.path.exists(precheck_dir):
        return []
    
    devices = set()
    for filename in os.listdir(precheck_dir):
        if filename.endswith(".txt") and "_" in filename:
            # Filename format: device_name_timestamp.txt
            # We need to handle cases where device_name might contain underscores too, 
            # but our current format is {device_name}_{timestamp}.txt
            # Let's assume the last part is timestamp.
            parts = filename.rsplit("_", 2) # Split from right, max 2 splits (date, time)
            if len(parts) >= 2:
                device_name = parts[0]
                devices.add(device_name)
    
    return list(sorted(devices))

@router.get("/prechecks/{device_name}")
def list_prechecks(device_name: str):
    precheck_dir = "app/static/prechecks"
    if not os.path.exists(precheck_dir):
        return []
    
    # Case-insensitive matching
    device_name_lower = device_name.lower()
    files = []
    for f in os.listdir(precheck_dir):
        if f.endswith(".txt") and "_" in f:
             # Check if the device name part matches case-insensitively
             # Filename: actualDeviceName_timestamp.txt
             if f.lower().startswith(device_name_lower + "_"):
                 files.append(f)
                 
    files.sort(reverse=True) # Newest first
    return files

@router.get("/prechecks/download/{filename}")
def download_precheck(filename: str):
    file_path = os.path.join("app/static/prechecks", filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=filename)

@router.post("/prechecks/diff", dependencies=[Depends(get_api_key)])
def diff_prechecks(request: DiffRequest):
    file1_path = os.path.join("app/static/prechecks", request.file1)
    file2_path = os.path.join("app/static/prechecks", request.file2)
    
    if not os.path.exists(file1_path) or not os.path.exists(file2_path):
        raise HTTPException(status_code=404, detail="One or both files not found")
        
    with open(file1_path, "r") as f1, open(file2_path, "r") as f2:
        lines1 = f1.readlines()
        lines2 = f2.readlines()
        
    diff = difflib.HtmlDiff().make_file(lines1, lines2, request.file1, request.file2)
    return HTMLResponse(content=diff)

@router.get("/status/{task_id}", response_model=ExecutionStatus)
def get_status(task_id: str, session: Session = Depends(get_session)):
    task = session.exec(select(ExecutionStatus).where(ExecutionStatus.task_id == task_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.get("/queue", response_model=List[DeviceQueue])
def get_queue(session: Session = Depends(get_session)):
    return session.exec(select(DeviceQueue)).all()

@router.get("/history", response_model=List[ExecutionStatus])
def get_history(session: Session = Depends(get_session)):
    return session.exec(select(ExecutionStatus).order_by(ExecutionStatus.created_at.desc())).all()

from tasks.netbox_graphql import fetch_devices_from_netbox
import asyncio

class NetboxRefreshRequest(BaseModel):
    site_name: Optional[str] = None
    region: Optional[str] = None
    device_model: Optional[str] = None

@router.post("/netbox/refresh", dependencies=[Depends(get_api_key)])
async def trigger_netbox_refresh(
    request: NetboxRefreshRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Fetch devices from Netbox and trigger refresh operation for each.
    """
    try:
        # Run synchronous Netbox fetch in a thread
        devices = await asyncio.to_thread(fetch_devices_from_netbox, request.site_name, request.region, request.device_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    results = []
    tasks_data = []
    
    for device in devices:
        device_name = device["device_name"]
        
        # Check if device is already in queue or running
        existing_op = session.exec(select(DeviceQueue).where(func.lower(DeviceQueue.device_name) == device_name.lower())).first()
        if existing_op:
            results.append({"device_name": device_name, "status": "skipped", "reason": "Already in queue or processing"})
            continue
            
        # Add to queue
        queue_item = DeviceQueue(device_name=device_name, operation_type="refresh_device", status="queued")
        session.add(queue_item)
        session.commit()
        session.refresh(queue_item)
        
        # Create execution record
        task_id = str(uuid.uuid4())
        execution_record = ExecutionStatus(
            task_id=task_id,
            device_name=device_name,
            status=TaskStatus.QUEUED
        )
        session.add(execution_record)
        session.commit()
        
        results.append({"device_name": device_name, "task_id": task_id, "status": "triggered"})
        
        # Prepare request data for the task
        # We need to map the Netbox data to what refresh_device_task expects
        # refresh_device_task expects: device_name, ip_address, site, region (and connection params via operations.py)
        # operations.py calls connect_to_device which needs: ip_address, platform (optional but good), device_type?
        # UpgradeRequest has device_type. connect_to_device likely uses it or platform.
        # Let's check connect_to_device in tasks/__connection_helpers.py to be sure what keys are needed.
        
        req_data = {
            "device_name": device_name,
            "ip_address": device["ip_address"],
            "site": device["site"],
            "region": device["region"],
            "platform": device["platform"],
            "operation_type": "refresh_device",
        }
        
        tasks_data.append({"task_id": task_id, "request_data": req_data})
        
    if tasks_data:
        background_tasks.add_task(run_batch_operations, tasks_data)
        
    return {"results": results, "total_found": len(devices), "triggered": len(tasks_data)}

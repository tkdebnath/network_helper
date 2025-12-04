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

import os
import asyncio
from datetime import datetime
from sqlmodel import Session, select
from app.db.models import ExecutionStatus, DeviceQueue, TaskStatus
from app.db.session import engine
from tasks.operations import perform_operations

from sqlalchemy import func

async def run_operation_task(task_id: str, request_data: dict):
    """
    Wrapper to run the upgrade task and update the database status.
    """
    device_name = request_data.get("device_name")
    with Session(engine) as session:
        # Update status to RUNNING
        task = session.exec(select(ExecutionStatus).where(ExecutionStatus.task_id == task_id)).first()
        if task:
            task.status = TaskStatus.RUNNING
            task.updated_at = datetime.utcnow()
            session.add(task)
            
            # Also update queue status
            queue_item = session.exec(select(DeviceQueue).where(func.lower(DeviceQueue.device_name) == device_name.lower(), DeviceQueue.status == "queued")).first()
            if queue_item:
                queue_item.status = "in_progress"
                session.add(queue_item)
            
            session.commit()
            
    async def append_log(message: str):
        with Session(engine) as session:
            task = session.exec(select(ExecutionStatus).where(ExecutionStatus.task_id == task_id)).first()
            if task:
                current_logs = task.log_output or ""
                task.log_output = current_logs + message + "\n"
                task.updated_at = datetime.utcnow()
                session.add(task)
                session.commit()

    try:
        # Run the actual task
        result = await perform_operations(request_data, log_callback=append_log)
        log_output = result["logs"] # This might be redundant if we are logging in real-time, but let's keep it for final status.
        # Actually, if we log in real-time, result["logs"] should probably be the full log or we just rely on DB.
        # But perform_upgrade returns the full log list joined. Let's keep updating it at the end to be sure.
        result_status = result["status"]
        
        if result_status == "failed":
            status = TaskStatus.FAILED
        elif result_status == "warning":
            status = TaskStatus.WARNING
        else:
            status = TaskStatus.COMPLETED
            
    except Exception as e:
        log_output = f"Error: {str(e)}"
        status = TaskStatus.FAILED
        
    with Session(engine) as session:
        # Update status to COMPLETED/FAILED
        task = session.exec(select(ExecutionStatus).where(ExecutionStatus.task_id == task_id)).first()
        if task:
            task.status = status
            task.log_output = log_output
            task.updated_at = datetime.utcnow()
            session.add(task)
            
            # Remove from queue or update queue status
            queue_item = session.exec(select(DeviceQueue).where(func.lower(DeviceQueue.device_name) == device_name.lower(), DeviceQueue.status == "in_progress")).first()
            if queue_item:
                session.delete(queue_item) # Remove from queue as it's done
            
            session.commit()

async def run_batch_operations(tasks_data: list[dict]):
    """
    Runs multiple upgrade tasks in parallel, limited to 10 concurrent tasks.
    """
    worker_count = int(os.getenv("WORKER_COUNT", 1))

    semaphore = asyncio.Semaphore(worker_count)

    async def run_with_semaphore(task_id: str, request_data: dict):
        async with semaphore:
            await run_operation_task(task_id, request_data)

    tasks = []
    for data in tasks_data:
        tasks.append(run_with_semaphore(data["task_id"], data["request_data"]))
    
    await asyncio.gather(*tasks)

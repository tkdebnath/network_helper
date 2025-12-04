from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel
from enum import Enum

class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ERROR = "error"
    WARNING = "warning"

class DeviceQueue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_name: str = Field(index=True)
    operation_type: str
    status: str = Field(default="queued") # queued, in_progress
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ExecutionStatus(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(index=True)
    device_name: str
    status: TaskStatus = Field(default=TaskStatus.QUEUED)
    log_output: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PrecheckRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_name: str = Field(index=True)
    check_type: str
    result: str # JSON string or text
    timestamp: datetime = Field(default_factory=datetime.utcnow)

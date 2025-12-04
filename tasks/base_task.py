from typing import Callable, Optional, Protocol, Dict, Any

class LogCallback(Protocol):
    async def __call__(self, message: str) -> None: ...

async def base_log(logs: list[str], msg: str, callback: Optional[LogCallback] = None):
    logs.append(msg)
    if callback:
        await callback(msg)

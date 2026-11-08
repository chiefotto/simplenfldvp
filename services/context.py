from dataclasses import dataclass


@dataclass
class RequestContext:
    interface: str = "service"
    caller_id: str = "unknown"
    access_level: str = "PUBLIC"

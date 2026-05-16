"""事件基类"""
import uuid
from datetime import datetime


class BaseEvent:
    """事件基类"""
    def __init__(self):
        self.event_id = str(uuid.uuid4())
        self.timestamp = datetime.utcnow()

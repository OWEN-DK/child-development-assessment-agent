"""事件基类（独立模块，避免循环导入）"""

import time


class BaseEvent:
    """事件基类"""

    def __init__(self):
        self.timestamp = time.time()

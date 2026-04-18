import time
from enum import Enum

from src.utils.logger import logger


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """熔断器打开异常"""

    pass


class CircuitBreaker:
    """熔断器实现"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0

    async def execute(self, func, *args, **kwargs):
        """执行带熔断保护的方法"""
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info(f"熔断器 {self.name} 进入半开状态")
            else:
                raise CircuitBreakerOpenError(
                    f"熔断器 {self.name} 处于打开状态，快速失败"
                )

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """成功回调"""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            logger.info(f"熔断器 {self.name} 恢复正常状态")

    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if (
            self.failure_count >= self.failure_threshold
            and self.state != CircuitState.OPEN
        ):
            self.state = CircuitState.OPEN
            logger.warning(
                f"熔断器 {self.name} 已打开（连续失败 {self.failure_count} 次），{self.recovery_timeout}秒后尝试恢复"
            )


mysql_circuit_breaker = CircuitBreaker(
    failure_threshold=5, recovery_timeout=60, name="mysql"
)
redis_circuit_breaker = CircuitBreaker(
    failure_threshold=3, recovery_timeout=30, name="redis"
)

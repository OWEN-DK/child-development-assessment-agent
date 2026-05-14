"""管道引擎异常"""


class PipelineError(Exception):
    """管道引擎异常基类"""
    pass


class NodeNotRegisteredError(PipelineError):
    """节点类型未注册"""

    def __init__(self, node_type: str):
        self.node_type = node_type
        super().__init__(f"节点类型未注册: {node_type}")


class PipelineCompilationError(PipelineError):
    """管道编译失败"""

    def __init__(self, message: str, errors: list[str] | None = None):
        self.errors = errors or []
        super().__init__(message)


class NodeExecutionError(PipelineError):
    """节点执行失败"""

    def __init__(self, node_id: str, node_type: str, message: str, cause: Exception | None = None):
        self.node_id = node_id
        self.node_type = node_type
        self.cause = cause
        super().__init(f"节点执行失败 [{node_type}:{node_id}]: {message}")


class DegradationChainExhaustedError(PipelineError):
    """降级链耗尽"""

    def __init__(self, node_id: str, strategies_tried: list[str]):
        self.node_id = node_id
        self.strategies_tried = strategies_tried
        super().__init__(f"节点 {node_id} 降级链耗尽，已尝试: {strategies_tried}")


class DomainTimeoutError(PipelineError):
    """域管道执行超时"""

    def __init__(self, domain_id: str, timeout_ms: int):
        self.domain_id = domain_id
        self.timeout_ms = timeout_ms
        super().__init__(f"域 {domain_id} 执行超时 ({timeout_ms}ms)")

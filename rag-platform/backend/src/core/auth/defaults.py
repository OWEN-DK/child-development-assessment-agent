"""内置角色定义与默认权限集

三个内置角色：admin（全部权限）、editor（读写）、viewer（只读）
"""

# 所有可用权限点定义
PERMISSION_SET: dict[str, str] = {
    # 知识库
    "kb:read": "查看知识库",
    "kb:write": "创建/编辑知识库",
    "kb:delete": "删除知识库",
    "kb:manage_acl": "管理知识库权限",
    # 管道
    "pipeline:read": "查看管道",
    "pipeline:write": "创建/编辑管道",
    "pipeline:delete": "删除管道",
    "pipeline:publish": "发布管道",
    # 搜索
    "search:execute": "执行搜索",
    "search:stream": "流式搜索",
    # 评估
    "eval:read": "查看评估",
    "eval:write": "创建/运行评估",
    # 系统
    "system:config": "系统配置",
    "system:monitor": "系统监控",
    # 用户管理
    "user:manage": "管理用户",
    "role:manage": "管理角色",
}

# 内置角色默认权限
DEFAULT_ROLES: dict[str, dict] = {
    "admin": {
        "name": "管理员",
        "slug": "admin",
        "is_builtin": True,
        "permissions": ["*"],  # 通配符 = 全部权限
    },
    "editor": {
        "name": "编辑者",
        "slug": "editor",
        "is_builtin": True,
        "permissions": [
            "kb:read",
            "kb:write",
            "kb:delete",
            "pipeline:read",
            "pipeline:write",
            "pipeline:delete",
            "pipeline:publish",
            "search:execute",
            "search:stream",
            "eval:read",
            "eval:write",
        ],
    },
    "viewer": {
        "name": "查看者",
        "slug": "viewer",
        "is_builtin": True,
        "permissions": [
            "kb:read",
            "pipeline:read",
            "search:execute",
            "eval:read",
        ],
    },
}

# 默认配额
DEFAULT_QUOTAS: dict[str, int] = {
    "max_knowledge_bases": 10,
    "max_documents": 1_000_000,
    "max_users": 100,
    "max_storage_gb": 50,
    "max_search_qps": 50,
    "max_concurrent_eval_runs": 2,
}

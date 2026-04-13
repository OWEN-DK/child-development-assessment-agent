#!/bin/bash
echo "Testing markdown files..."
grep -A 5 "subgraph 数据层" AGENTS.md
grep -A 5 "subgraph 数据层" CLAUDE.md
grep "Redis 客户端" AGENTS.md
grep "Redis 客户端" CLAUDE.md
grep "SQLAlchemy" AGENTS.md
grep "SQLAlchemy" CLAUDE.md

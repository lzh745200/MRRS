---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W4-T4 Docker E2E 链路三层修复

**来源**: 检测（`docker-compose.e2e.yml:25-27` 依赖不存在的服务；external network 未声明；容器内缺 pytest-timeout；`Makefile:31` `|| true` 吞退出码）

## 验收标准
- [ ] Makefile e2e 目标补 `-f docker-compose.yml`
- [ ] compose 内声明所需网络或改用默认网络
- [ ] requirements/镜像内补 pytest-timeout（与 --timeout=60 匹配）
- [ ] 移除 `|| true`，Playwright 失败即失败
- [ ] `make test-e2e-docker` 本地完整跑通一次并记录结果

## 涉及文件
- `Makefile`、`docker/docker-compose.e2e.yml`、E2E 依赖清单

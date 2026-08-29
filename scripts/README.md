# 服务管理脚本

本目录包含用于管理开发服务的便捷脚本。

## Windows 脚本

### 🚀 start-all.bat - 一键启动所有服务

**功能**：
- 自动检测并清理端口冲突（8000, 5173）
- 启动后端服务（FastAPI）
- 启动前端服务（Vite）
- 等待服务就绪
- 自动打开浏览器

**使用方法**：
```bash
# 在项目根目录或 scripts 目录执行
scripts\start-all.bat
```

**注意事项**：
- 会打开两个新的命令行窗口（后端和前端）
- 关闭启动脚本窗口不会停止服务
- 需要在各服务窗口中按 Ctrl+C 停止服务

---

### 🛑 stop-all.bat - 停止所有服务

**功能**：
- 停止后端服务（端口 8000）
- 停止前端服务（端口 5173）
- 清理相关的命令行窗口

**使用方法**：
```bash
scripts\stop-all.bat
```

---

## 常见问题

### Q: 端口被占用怎么办？

**错误信息**：
```
[Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000):
通常每个套接字地址(协议/网络地址/端口)只允许使用一次。
```

**解决方案**：
1. 使用 `stop-all.bat` 清理（会终止后端进程）
2. 或使用 `start-all.bat`（会自动清理）
3. 手动清理：
   ```bash
   netstat -ano | findstr :8000
   taskkill //F //PID <进程ID>
   ```

### Q: 服务启动失败？

**检查清单**：
1. Python 虚拟环境是否已创建？
   ```bash
   cd backend
   python -m venv .venv
   ```

2. 依赖是否已安装？
   ```bash
   cd backend
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. 前端依赖是否已安装？
   ```bash
   cd frontend
   npm install
   ```

4. 数据库是否正常？
   - 检查 `backend/data/rural_revitalization.db` 是否存在
   - 查看 `backend/logs/app.log` 日志

### Q: 如何查看服务日志？

**后端日志**：
- 文件：`backend/logs/app.log`
- 实时查看：在后端服务窗口中查看输出

**前端日志**：
- 浏览器开发者工具（F12）→ Console
- 前端服务窗口中查看 Vite 输出

### Q: 如何完全重启服务？

```bash
# 1. 停止所有服务
scripts\stop-all.bat

# 2. 等待 2-3 秒

# 3. 重新启动
scripts\start-all.bat
```

---

## 开发建议

1. **日常开发**：使用 `start-all.bat` 一键启动
2. **调试后端**：单独运行 `cd backend && .venv\Scripts\python start.py`，前端手动启动
3. **遇到问题**：先用 `stop-all.bat` 停止，再重新启动
4. **端口冲突**：使用 `stop-all.bat` 清理后按 `netstat -ano | findstr :8000` 手动确认

---

## 技术说明

### 端口使用

- **8000**: 后端 FastAPI 服务
- **5173**: 前端 Vite 开发服务器
- **3000**: Electron 主进程（如果启动）

### 进程管理

脚本使用 Windows 的 `netstat` 和 `taskkill` 命令：
- `netstat -ano`: 查看端口占用
- `taskkill //F //PID`: 强制终止进程

### 虚拟环境

后端使用 Python 虚拟环境（`.venv`）：
- 自动激活：脚本会自动调用 `activate.bat`
- 手动激活：`.venv\Scripts\activate.bat`
- 退出：`deactivate`

---

## 贡献

如果你发现脚本有问题或有改进建议，请：
1. 查看 `CLAUDE.md` 了解项目结构
2. 提交 Issue 或 Pull Request
3. 联系项目维护者

---

**最后更新**: 2026-03-14

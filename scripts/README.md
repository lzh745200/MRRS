# 服务管理脚本

本目录包含用于管理开发服务的便捷脚本。

## Windows 脚本

> **Python 解析（W24）**：PATH 里的裸 `python` 可能指向已删除 / 32 位安装（本机实测
> 指向 `...\Python311-32`），裸调用不可复现甚至会直接失败。所有 .bat 统一通过
> `find-python.bat` 显式解析项目解释器，优先级
> `MRRS_PYTHON` → `backend\.venv\Scripts\python.exe` → `py -3.11`；
> 全部不可用时打印修复指引并 `exit /b 1`。Node 侧等价解析器为
> `scripts/run-python.js`（供 npm 脚本使用：`node scripts/run-python.js --print`）。

### 🐍 find-python.bat - 项目 Python 解析（被其它脚本复用）

- 以 `call "%~dp0find-python.bat"` 方式调用，成功时导出 `PYTHON_EXE`（绝对路径），
  失败时 errorlevel=1；`cleanup.bat` / `dev-setup.bat` / `run-backend.bat` 均复用它。
- 不得使用 `setlocal`（变量需泄漏给调用方）。

### ▶️ run-backend.bat / run-frontend.bat - 单服务启动器

- 由 `start-all.bat` 在独立窗口调用（窗口标题 `后端服务` / `前端服务`，
  `stop-all.bat` 按标题清理）；也可单独双击运行。
- 设置 `MRRS_DRY_RUN=1` 可只打印将要执行的命令（供 CI/自检）。

### 🚀 start-all.bat - 一键启动所有服务

**功能**：
- 自动检测并清理端口冲突（8000, 5173）
- 启动后端服务（FastAPI）
- 启动前端服务（Vite）
- 等待服务就绪
- 自动打开浏览器

> v1.15.5 修复：本脚本此前只等待端口、**从未真正启动后端/前端**（历史改动误删启动行）。
> 现改为调用 `run-backend.bat` / `run-frontend.bat` 各自开窗启动。

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

后端使用 Python 虚拟环境（`backend\.venv`）：
- 脚本调用：统一经 `find-python.bat` 解析出绝对路径后调用，**不需要**手动激活，
  也不依赖 PATH 里的裸 `python`
- 手动激活（可选）：`backend\.venv\Scripts\activate.bat`
- 退出：`deactivate`

---

## 贡献

如果你发现脚本有问题或有改进建议，请：
1. 查看 `CLAUDE.md` 了解项目结构
2. 提交 Issue 或 Pull Request
3. 联系项目维护者

---

**最后更新**: 2026-10-19（v1.15.5：W24 构建/启动脚本可复现性修复）

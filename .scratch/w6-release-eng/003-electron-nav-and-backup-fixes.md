---
labels: [ready-for-agent, severity-high]
blocks: []
blocked-by: []
---

# W6-T3 Electron 导航白名单 origin 精确匹配 + 备份清理凭证修复

**来源**: 检测 S3/S4/L5/L6（`main.js:561,575` startsWith 前缀绕过；`:851,863` list/delete 无 Authorization → 清理从不生效；`:394` shutdown 后仍强杀；`:246` 端口等待仅 2s）

## 验收标准
- [ ] 导航判定改 `new URL(url).origin === 'http://127.0.0.1:'+port` 精确匹配（main+setWindowOpenHandler 两处）
- [ ] backup list/delete 走 X-Internal-Backup 内部密钥头（与 create 同模式，后端补豁免通道）
- [ ] stopBackend：收到优雅关闭响应后取消强杀定时器；重启端口等待改为探测就绪
- [ ] 手动验证：7 天过期清理实际删除文件

## 涉及文件
- `electron/main.js`、`backend/app/api/v1/system/backup.py`

"""Unit test conftest —— 不再向 sys.modules 注入 Heavy-Dependency 替身。

历史（W4-T7 之前）：本文件用 ``'sklearn' not in sys.modules`` 判定，把 sklearn /
scipy 整体替换为 MagicMock。由于"已安装但尚未 import"同样满足该条件，真实实现
几乎永远走不到：表面断言通过、真实回归路径无人验证。

现状（W4-T7 完成）：
- ``scikit-learn`` 是 ``backend/requirements.txt`` 的运行时依赖（scipy 随其安装），
  CI 与本地 venv 都必然存在真实包；
- 因此这里**不再注入任何替身**，导入失败会立即暴露依赖缺失（而不是静默走 mock）；
- 需要特定预测/异常检测行为的用例，请在本用例内显式 patch 目标模块
  （例如 ``test_anomaly_detection_service_complete`` 直接 patch 服务模块内的
  ``SKLEARN_AVAILABLE`` / ``IsolationForest``）。

顺序独立性：全量自然顺序 + pytest-randomly 随机顺序两轮回归锁定（w4-007）。
"""

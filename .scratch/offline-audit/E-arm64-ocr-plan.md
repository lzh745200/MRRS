# E 区 · ARM64（麒麟 V10）离线 OCR 可行性结论与实现方案

> 任务：task-5（team board）｜执行：arm64-ocr｜日期：2026-10-21
> 目标产物：`MRRS-Setup-<ver>-arm64.deb`（Electron 桌面版）与
> `assistance-management-system_<ver>_arm64.deb`（standalone Web 版）**均内置离线 OCR**，
> 且构建流水线自身能证明这一点。
> 版本代号：v1.16.0（下一个发布版本；本方案不含版本号 bump，由发布流程统一处理）。

---

## 1. 结论

**可行（已实现，构建期可自证）。**

| 维度 | 结论 |
|------|------|
| 技术可行性 | ✅ ARM64（麒麟 V10，glibc 2.28）可离线跑 `rapidocr-onnxruntime==1.4.4`：cp311/aarch64 的 onnxruntime / opencv / pyclipper / shapely / PyYAML 轮子齐备，引擎模型随 wheel（15.4 MB） |
| 实现方式 | ✅ 取消 Dockerfile 对 OCR 三项的过滤；ARM64 改 `opencv-python-headless` + `pip install --no-deps rapidocr-onnxruntime==1.4.4`；spec 条件收集模型/动态库；构建期 OCR 冒烟门禁 |
| 安装代价 | ✅ **DEB `Depends` 仍为空**（headless cv2 不链接 libGL；onnxruntime 不需要 libgomp），`dpkg -i` 即装特性不变 |
| 体积代价 | ⚠️ ARM64 安装包 **+约 65–80 MB**（压缩后以实际产物为准）；standalone 由 ≈58 MB 预计升至 ≈125–140 MB |
| 硬前提 | ⚠️ 目标机 **glibc ≥ 2.28**（manylinux_2_28 轮子下限）；麒麟 V10 Server = 2.28、Desktop = 2.31，均满足 |
| 回退 | ✅ 完全保留既有降级链：引擎不可用时 `/funds/ocr-voucher` 返回 503 + 前端提示手工录入，不阻断业务 |

---

## 2. 现状与根因（改前）

1. `docker/Dockerfile.kylin-standalone:89`（改前）用一条 `grep -v -E` 把
   `rapidocr-onnxruntime|onnxruntime|opencv-python` 从 ARM64 requirements 中剔除。
2. `backend/requirements.txt:153-158`（改前）给出的理由是
   "onnxruntime/opencv 无 buster ARM64 wheel"，因此"Linux 端 OCR 降级为不可用提示"。
3. 该理由在 2026-10 已不成立（见 §3），结果是：Windows 安装包有 OCR，ARM64 安装包
   恒 503，而文档口径在"内置"与"降级"之间摇摆（README 两处、技术栈说明一处）。

---

## 3. 可行性证据

### 3.1 wheel 清单（PyPI JSON 实测，2026-10-21）

命令（脚本存于 `%TEMP%\pypi_arm64_probe.py`，逻辑＝抓 `https://pypi.org/pypi/<pkg>/<ver>/json`
并筛 aarch64 / 纯 Python 轮子）：

```
backend\.venv\Scripts\python.exe %TEMP%\pypi_arm64_probe.py
```

关键输出（原样摘录，仅列 cp311/aarch64 相关行）：

```
### rapidocr-onnxruntime == 1.4.4  (release files: 1)
    rapidocr_onnxruntime-1.4.4-py3-none-any.whl                               14.2 MB  py3
    Requires-Dist:
      - pyclipper>=1.2.0
      - opencv-python>=4.5.1.48
      - numpy<3.0.0,>=1.19.5
      - six>=1.15.0
      - Shapely!=2.0.4,>=1.7.1
      - PyYAML
      - Pillow
      - onnxruntime>=1.7.0
      - tqdm

### onnxruntime == 1.31.0  (release files: 24)
    onnxruntime-1.31.0-cp311-cp311-manylinux_2_28_aarch64.whl                 20.4 MB  py3
    Requires-Dist:
      - flatbuffers
      - numpy>=1.21.6
      - packaging
      - protobuf>=4.25.8
      - sympy; extra == "symbolic"
      - ml_dtypes; extra == "quantization"

### numpy == 2.4.6  (release files: 72)
    numpy-2.4.6-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl    15.2 MB  cp311

### pillow == 12.3.0  (release files: 87)
    pillow-12.3.0-cp311-cp311-manylinux_2_27_aarch64.manylinux_2_28_aarch64.whl     6.0 MB  cp311

### opencv-python == 4.12.0.88  (release files: 7)
    opencv_python-4.12.0.88-cp37-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl    43.8 MB  cp37

### opencv-python-headless == 4.12.0.88  (release files: 7)
    opencv_python_headless-4.12.0.88-cp37-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.whl    31.6 MB  cp37

### pyclipper == 1.4.0  (release files: 36)
    pyclipper-1.4.0-cp311-cp311-manylinux_2_24_aarch64.manylinux_2_28_aarch64.whl     0.9 MB  cp311

### shapely == 2.2.0  (release files: 64)
    shapely-2.2.0-cp311-cp311-manylinux_2_24_aarch64.manylinux_2_28_aarch64.whl     2.1 MB  cp311

### PyYAML == 6.0.3  (release files: 73)
    pyyaml-6.0.3-cp311-cp311-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl     0.7 MB  cp311

### tqdm == 4.70.1  (release files: 2)
    tqdm-4.70.1-py3-none-any.whl                                               0.1 MB  py3

### flatbuffers == 25.12.19  (release files: 1)
    flatbuffers-25.12.19-py2.py3-none-any.whl                                  0.0 MB  py2.py3

### protobuf == 7.36.2  (release files: 8)
    protobuf-7.36.2-cp310-abi3-manylinux2014_aarch64.whl                       0.3 MB  cp310
```

**推论**：
- 运行时依赖树上每个包都有 cp311/aarch64 轮子（无源码编译，QEMU 构建不会因编译超时/缺
  gcc 工具链失败）；
- `sympy` 只在 `extra == "symbolic"` 里，默认不装 → 不会把 6 MB 的 sympy 拖进来；
- `coloredlogs` 在 1.31.0 已不是必需依赖（老版本才有）；
- headless opencv 比非 headless **小 12.2 MB**（31.6 vs 43.8），且不带 libGL 依赖。

### 3.2 glibc 匹配推理（目标机 2.28 ↔ 构建基座 2.28 ↔ manylinux_2_28）

| 环节 | glibc | 依据 |
|------|-------|------|
| 麒麟 V10 Server | **2.28** | 仓库既有口径（`docker/Dockerfile.kylin-standalone:45-48`）；Desktop 为 2.31 |
| 构建基座 `python:3.11-slim-buster` | **2.28** | 同上；Dockerfile 里已有 `ldd --version` → `<= 2.28` 断言（改后仍在，行 77-83） |
| `onnxruntime-1.31.0-cp311-cp311-manylinux_2_28_aarch64.whl` | 要求 ≥ **2.28** | manylinux_2_28 政策定义 = glibc 2.28 符号基线 |
| 实测 `libonnxruntime.so.1.31.0` | 最高引用符号 **GLIBC_2.28**（集合 2.17/2.25/2.27/2.28） | Lead 下载该 wheel 后 `objdump -T` 扫描 |

→ **2.28 = 2.28 = 2.28**，不出现"构建基座 glibc 比目标机新"的经典陷阱；同时
`objdump` 实测的符号版本上限恰好等于 2.28，没有向上越界。

`numpy` / `pillow` 的轮子标签是 `manylinux_2_27_aarch64.manylinux_2_28_aarch64`（复合标签），
即最低 2.27 —— 也 ≤ 2.28，兼容。（这两包在改前就会被 ARM64 构建安装，不是新增风险。）

### 3.3 系统库依赖（决定 DEB `Depends` 是否要加东西）

Lead 实测 `libonnxruntime.so.1.31.0` 的 `DT_NEEDED`：

```
libc.so.6  libdl.so.2  libgcc_s.so.1  libm.so.6  libpthread.so.0  librt.so.1  libstdc++.so.6
+ libonnxruntime_providers_*.so（同 wheel 内自带）
```

**没有 libgomp / libGL / libcuda** → onnxruntime 不需要追加任何 apt 包。

`opencv` 侧：非 headless 轮子在 import 阶段 dlopen `libGL.so.1` / `libglib-2.0.so.0`，
这正是"很多离线机装完 import cv2 就崩"的根因。本方案改用
`opencv-python-headless`，从源头消除这两个依赖 → **DEB `Depends` 保持为空**，
`dpkg -i` 即装特性不变。

> 为什么不做 `pip install rapidocr-onnxruntime` 常规模安装：它的 `Requires-Dist` 写死
> `opencv-python`（非 headless），pip 无法用 headless 满足该名字，会额外拉 43.8 MB 非
> headless 轮子并顶掉 headless。因此 Dockerfile 用 `--no-deps` 安装引擎本体，
> 其依赖全部显式 pin 在 `backend/requirements-arm64-ocr.txt`。

### 3.4 pip 跨平台解析（实际执行记录与替代证据）

按任务要求执行了 `pip download --only-binary=:all: --platform ... --python-version 3.11`：

| 尝试 | 结果 |
|------|------|
| 全树解析 `rapidocr-onnxruntime==1.4.4`（2 个 platform 标签） | 40 分钟未完成（100% CPU）：`numpy` 的 `manylinux_2_27` 轮子不在给定 platform 列表内 → pip 反复 backtrack |
| 全树解析（12 个 platform 标签，含 2_17…2_28 + manylinux2014 + linux_aarch64） | 8 分钟仍在解析、dest 目录仍为空 |
| 逐包 `--no-deps` 下载 16 个包 | 20 分钟 0 文件落盘（PyPI `files.pythonhosted.org` 本机吞吐 ≈ 5–20 KB/s；实测 `pypi.org/pypi/.../json` 单次 75 KB 也要 15.5 s） |
| 极小轮子对照（tqdm 100 KB + flatbuffers 30 KB） | 240 秒超时未完成 |

**结论**：本机到 `files.pythonhosted.org` 的网络吞吐不足以完成 100 MB 级下载，
pip 全树解析这条证据链在本机不可得（不是解析失败，是下载带宽不足）。替代证据：

1. **PyPI JSON 元数据**（§3.1）：每个包的 aarch64 轮子文件名、平台标签、字节数 ——
   这等价于 pip 解析时用的候选集合，且是 pip 解析的唯一事实来源；
2. **Lead 实际下载并扫描**了 `onnxruntime-1.31.0-cp311-cp311-manylinux_2_28_aarch64.whl`
   （21.4 MB 落盘、`objdump -T` 得 GLIBC_2.28、`DT_NEEDED` 清单）；
3. **仓库本机 Windows venv 实跑**：`python docker/ocr_smoke_arm64.py`（非严格模式）→
   `RapidOCR()` 实例化成功、对合成图识别出 `'12345.67'`（见 §7.1），证明脚本断言链与
   rapidocr 1.4.4 的 API/模型用法正确；
4. **仓库本机 venv 实跑 PyInstaller 收集函数**（即 spec 新增代码，见 §7.1 第 6 条）：
   `collect_data_files('rapidocr_onnxruntime')` → 4 个文件（3 个 ONNX + config.yaml）、
   `collect_dynamic_libs('onnxruntime')` → 2 个动态库 —— 证明 spec 的收集逻辑能真正
   抓到模型与 onnxruntime 库（Windows 上验证，Linux 上等价，只是扩展名 `.so`）；
5. **最终验证在 CI**：`build-arm64.yml` 的构建阶段会真正在 aarch64 容器里
   `pip install` + PyInstaller + 冒烟，通过即证明解析与运行可行（§7.2）。

---

## 4. 精确改动

### 4.1 `docker/Dockerfile.kylin-standalone`

**① 过滤正则去掉 OCR 三项（行 99）**

```diff
-RUN grep -v -E '^(prophet|...|cssselect|rapidocr-onnxruntime|onnxruntime|opencv-python)' \
+RUN grep -v -E '^(prophet|...|cssselect)' \
     requirements.txt > requirements-arm64.txt && \
     echo "python-magic==0.4.27" >> requirements-arm64.txt && \
     echo "--- ARM64 requirements ---" && \
     wc -l requirements-arm64.txt
```

**② 新增 OCR 依赖清单 + 安装方式替换（行 88/98/112）**

```diff
 COPY backend/requirements.txt .
+COPY backend/requirements-arm64-ocr.txt .
 ...
+# OCR 的**安装方式替换**（不是能力降级）：rapidocr 的依赖名写死 opencv-python（非 headless，
+# import 时 dlopen libGL/libglib），离线麒麟机常无图形栈，也不该为 OCR 把"零外部依赖"的包
+# 变成"缺 libgl1 就装不上"。故从批量清单摘出 rapidocr，改由下方 --no-deps 单独安装。
+RUN grep -v -E '^rapidocr-onnxruntime' requirements-arm64.txt > requirements-arm64-base.txt && \
+    wc -l requirements-arm64-base.txt && cat requirements-arm64-ocr.txt
```

> ⚠️ 说明：这是本方案里**唯一仍出现 `rapidocr` 名字的 grep**，作用是"换安装方式"
> （base 清单不含引擎本体 → 由第 ③ 步 `--no-deps` 安装），与改前的"能力降级过滤"
> 语义完全相反。原"过滤正则"（大清单）已按要求不再包含三项。

**③ pip 安装拆三步（行 122/127/132）**

```diff
-RUN pip install --retries 3 --timeout 120 \
-    -r requirements-arm64.txt pyinstaller > /tmp/pip-install.log 2>&1; ...
+RUN pip install ... -r requirements-arm64-base.txt pyinstaller   # ① 主依赖
+RUN pip install ... -r requirements-arm64-ocr.txt                # ② headless cv2 + onnxruntime + pyclipper/shapely/tqdm
+RUN pip install --retries 3 --timeout 120 --no-deps \
+    rapidocr-onnxruntime==1.4.4 > /tmp/pip-install-rapidocr.log 2>&1; ...   # ③ 引擎本体
```

**④ 构建期 OCR 冒烟（行 145-149，脚本在仓库内，不用 heredoc）**

```diff
+COPY docker/ocr_smoke_arm64.py /tmp/ocr_smoke_arm64.py
+RUN python /tmp/ocr_smoke_arm64.py --require-headless > /tmp/ocr-smoke.log 2>&1; \
+    code=$?; tail -40 /tmp/ocr-smoke.log; \
+    if [ $code -ne 0 ]; then echo "ERROR: ARM64 OCR 冒烟失败（见上方日志）"; exit 1; fi
```

**⑤ 冻结产物载荷断言（行 185-195）**

```diff
+RUN MODELS=$(find dist/assistance-management-backend -path "*rapidocr_onnxruntime/models*" -name "*.onnx" | wc -l) && \
+    test "$MODELS" -ge 2 || (echo "ERROR: 冻结产物缺少 rapidocr ONNX 模型（datas 收集失效）" && exit 1) && \
+    ORT=$(find dist/assistance-management-backend -name "onnxruntime_pybind11_state*" | wc -l) && \
+    test "$ORT" -ge 1 || (echo "ERROR: 缺少 onnxruntime 绑定库（collect_dynamic_libs 失效）" && exit 1) && \
+    CV2=$(find dist/assistance-management-backend -name "cv2*.so" | wc -l) && \
+    test "$CV2" -ge 1 || (echo "ERROR: 缺少 cv2 扩展模块" && exit 1)
```

**⑥ DEB `Depends` 保持为空（行 283-306；第 300 行是 echo "Depends: "）**：只加了注释说明"为什么可以不依赖系统库"，
`echo "Depends: "` 一行未改；Description 补一句"Python 运行时/前端/离线 OCR 模型均已内置"。

### 4.2 `backend/backend_linux_arm64_standalone.spec`

| 行 | 改动 |
|----|------|
| 16-21 | 新增 `import importlib.util as _ilu`；`from PyInstaller.utils.hooks import (collect_data_files, collect_dynamic_libs, collect_submodules)` |
| 25 | 新增 `project_root = os.path.dirname(backend_dir)` |
| 41-43 | **map-tiles 收集（存在才加，与 Windows spec 完全一致的片段）** |
| 141-154 | OCR 条件收集（双 `find_spec` 守卫） |

**map-tiles 片段（与 Windows spec 同款，逐字一致）**

```python
_tiles_dir = os.path.join(project_root, 'resources', 'map-tiles')
if os.path.isdir(_tiles_dir):
    datas.append((_tiles_dir, os.path.join('resources', 'map-tiles')))
```

> 目标目录必须是 `resources/map-tiles`：`app/api/v1/map.py` 冻结态按
> `sys._MEIPASS/resources/map-tiles` 解析（onedir 下 `_MEIPASS` = `_internal/`）。
> 仓库当前**未生成** `resources/map-tiles`（离线地图未出图），故该分支现在是 no-op，
> 一旦出图即自动进包。

**OCR 收集片段**

```python
# 双 find_spec 守卫：任一包缺失时静默跳过，保持 503 降级链，绝不让 spec 崩
_rapidocr_spec = _ilu.find_spec('rapidocr_onnxruntime')
if _rapidocr_spec and _rapidocr_spec.submodule_search_locations:
    datas += collect_data_files('rapidocr_onnxruntime')          # *.onnx 模型 + 字典 + yaml
    hiddenimports += collect_submodules('rapidocr_onnxruntime')
    print("[SPEC] 已收集 rapidocr_onnxruntime 模型数据与子模块")
else:
    print("[SPEC] 未安装 rapidocr_onnxruntime，跳过 OCR 数据收集（OCR 将降级 503）")

_ort_spec = _ilu.find_spec('onnxruntime')
if _ort_spec and _ort_spec.submodule_search_locations:
    binaries += collect_dynamic_libs('onnxruntime')              # capi 下的 *_state.so / provider .so
    hiddenimports += collect_submodules('onnxruntime')
    print("[SPEC] 已收集 onnxruntime 动态库与子模块")
else:
    print("[SPEC] 未安装 onnxruntime，跳过 OCR 动态库收集（OCR 将降级 503）")
```

依据（本机 rapidocr 安装目录实测）：模型 3 个、共 **15.44 MB**
（`ch_PP-OCRv4_det_infer.onnx` 4.53 MB / `ch_PP-OCRv4_rec_infer.onnx` 10.35 MB /
`ch_ppocr_mobile_v2.0_cls_infer.onnx` 0.56 MB）；`cv2`、`pyclipper`、`shapely`、`yaml`、
`onnxruntime` 均为**顶层静态 import**（`main.py:8`、`utils.py:6-9`、`infer_engine.py:12` …），
因此 `collect_submodules('rapidocr_onnxruntime')` 之后 Analysis 能跟到这些依赖。

### 4.3 新增文件

| 文件 | 作用 |
|------|------|
| `backend/requirements-arm64-ocr.txt` | ARM64 OCR 依赖精确 pin（headless cv2 / onnxruntime / pyclipper / shapely / tqdm / flatbuffers / protobuf），带完整"为什么 headless"说明 |
| `docker/ocr_smoke_arm64.py` | 构建期 OCR 冒烟脚本（零新依赖、可本地复现、可被 CI 复用） |

### 4.4 `.github/workflows/build-arm64.yml`

| 行 | 改动 |
|----|------|
| 585-616 | 新增步骤 **`Verify OCR payload and zero-dep contract in DEB`**：断言 standalone DEB 载荷含 `rapidocr_onnxruntime/models/*.onnx`、`onnxruntime_pybind11_state`、`cv2*.so`；断言 `Depends` 不含 `libgl1`/`libgomp1`/`libglib2.0` |
| 433-444 | `Verify DEB package` 步骤追加 Electron DEB 的 OCR 载荷断言（复用同一 backend-builder 产物） |

### 4.5 文档同步

| 文件 | 改动 |
|------|------|
| `README.md:101` | "Windows 安装包内置模型，ARM64 构建过滤降级" → "Windows 与 ARM64 均内置模型；ARM64 用 headless + 构建期冒烟；体积 +65–80 MB；前提 glibc ≥ 2.28" |
| `README.md:242` | 自包含清单：删掉"ARM64 构建过滤降级为 503+手工录入"，改为两平台均内置、模型约 15 MB、glibc ≥ 2.28 |
| `docs/04-部署文档/02-Linux部署/麒麟V10离线部署完整方案.md:36-50` | 新增「ARM64 安装包的系统前提（v1.16.0：内置离线 OCR 后）」表：glibc / 系统库 / 体积 / 失败表现 |
| 同上 `:2000+` | 新增「D-1 离线 OCR（v1.16.0 起 ARM64 内置）」：前提、体积、目标机验证命令（含 `dpkg-deb -c` 与 `curl /funds/ocr-voucher`） |
| `docs/03-开发文档/06-运维文档/技术栈说明.md:18` | "ARM64 构建过滤降级" → "两平台均内置，ARM64 走 headless + 冒烟，glibc ≥ 2.28" |
| `backend/requirements.txt:154-164` | 删除过时理由（"onnxruntime/opencv 无 buster ARM64 wheel"），写明复核结论与 ARM64 安装方式 |

---

## 5. 体积与启动影响

### 5.1 体积（wheel 压缩态）

| 包 | aarch64 轮子 | 说明 |
|----|-------------|------|
| `onnxruntime==1.31.0` | 20.4 MB | 推理运行时 |
| `opencv-python-headless==4.12.0.88` | 31.6 MB | 比非 headless（43.8 MB）省 12.2 MB |
| `rapidocr-onnxruntime==1.4.4` | 14.2 MB | 其中 ONNX 模型 15.4 MB（**未压缩**，轮子是 zip 不含已压缩内容） |
| `pyclipper==1.4.0` + `shapely==2.2.0` + `tqdm` + `flatbuffers` + `protobuf` | ≈ 3.4 MB | |
| **合计新增下载/解包** | **≈ 69.6 MB** | `numpy`/`pillow`/`PyYAML`/`six` 改前已在装，不重复计 |

冻结后（PyInstaller `strip=True` + `upx=True`，DEB 用 xz 压缩）：

- **standalone DEB**：改前 ≈ 58 MB（`60,786,460 B`，v1.15.15）→ 预计 **≈ 125–140 MB**（+约 65–80 MB）；
- **Electron DEB**：改前 ≈ 196 MB → 预计 **≈ 260–280 MB**（同为 +65–80 MB）；
- 实际数值以 v1.16.0 构建产物为准（CI 产物 SHA256SUMS 与 `ls -lh` 会给出）；
- 若体积超预算，可裁剪顺序：① `upx` 已开；② `onnxruntime` 只保留 CPU provider（wheel 即如此）；
  ③ 模型量化版（`ch_PP-OCRv4_det/rec` 替换为 mobile 版可再省 ~10 MB，但精度下降 → 不作默认）。

### 5.2 启动影响

| 指标 | 影响 |
|------|------|
| 后端冷启动 | **几乎无变化**：`ocr_service` 懒加载，`RapidOCR()` 仅在第一次 OCR 请求时初始化（本机 Windows 实测模型加载 ≈1.1 s） |
| 内存 | OCR 请求时 +≈150–250 MB（onnxruntime + cv2 + 模型常驻）；常驻单例，后续请求复用 |
| 磁盘 | `_internal/` 体积 +≈70–140 MB（解包后） |
| 前端 | 无影响 |

---

## 6. 回退路径

设计上 **不需要改代码即可回退**，三条路径由轻到重：

1. **运行时自动降级（默认已具备）**：
   `app/services/ocr_service.py:59-85` 懒加载失败 → 缓存错误 → `available()` False →
   `POST /funds/ocr-voucher` 返回 503 → 前端提示"请手工录入金额与日期"，不阻断业务。
   触发场景：glibc < 2.28（onnxruntime 加载失败）、内存不足、模型文件损坏。
2. **构建期回退（改一行）**：在 `backend/requirements-arm64-ocr.txt` 里注释掉 OCR 段、
   并把 Dockerfile 第 112 行的摘行 grep 与第 132 行的 `--no-deps` 安装一并注释掉 →
   ARM64 包恢复"无 OCR"，spec 的 `find_spec` 守卫自动跳过收集，构建不会失败。
3. **完全回退（git revert）**：`git revert <本任务提交>` 即回到"过滤降级"状态；
   因所有改动都在构建/配置/文档层，无数据迁移、无 schema 变更、无业务代码改动。

**风险前提的兜底**：若某台麒麟机 glibc < 2.28（例如改装过的老系统），
`RapidOCR()` 初始化会失败并走路径 1（503 手工录入），**不会崩服务**；
如需彻底避免该机体积浪费，可发布"无 OCR 精简版 ARM64 包"（路径 2）。

---

## 7. 验证步骤

### 7.1 已完成的本地验证（本次）

```powershell
# 1) spec 语法（spec 是 Python 语法，用 compile() 校验，不在 PyInstaller 上下文执行）
backend\.venv\Scripts\python.exe -c "compile(open('backend/backend_linux_arm64_standalone.spec',encoding='utf-8').read(),'spec','exec')"
→ OK: arm64 spec 语法通过, lines = 224

# 2) 冒烟脚本语法
backend\.venv\Scripts\python.exe -c "import py_compile;py_compile.compile('docker/ocr_smoke_arm64.py', doraise=True)"
→ OK

# 3) workflow YAML 可解析（并确认新步骤已注册）
python -c "import yaml;d=yaml.safe_load(open('.github/workflows/build-arm64.yml'));print(len(d['jobs']['standalone-deb']['steps']))"
→ OK: steps = 17，含 "Verify OCR payload and zero-dep contract in DEB"

# 4) 过滤正则不含 OCR 三项
Select-String docker\Dockerfile.kylin-standalone -Pattern "grep -v -E '"
→ 正则含 rapidocr|onnxruntime|opencv ? -> False

# 5) 冒烟脚本实跑（本机 Windows venv，非严格模式；验证脚本逻辑与 rapidocr API 用法）
backend\.venv\Scripts\python.exe docker\ocr_smoke_arm64.py
→ WARN: 当前环境使用非 headless 的 opencv-python
  OK: import cv2 成功，版本 5.0.0
  OK: RapidOCR() 实例化成功，识别耗时 [1.0986037999991822, 0.0, 0.04687309265136719]
      识别文本: '12345.67'
  OK: 识别结果含数字，ocr_service.parse_amount 前提满足
  === OK: ARM64 离线 OCR 冒烟全部通过 ===
```

> 第 5 条同时说明：`--require-headless` 在 Windows 上会失败（本机是 WIN32UI 非 headless），
> 这是**预期行为**——严格模式只用于 ARM64 构建门禁。

```powershell
# 6) spec 新增的收集逻辑实跑（等价于 PyInstaller 在 Analysis 前做的收集）
backend\.venv\Scripts\python.exe -c "from PyInstaller.utils.hooks import *; \
  print(len(collect_data_files('rapidocr_onnxruntime')), len(collect_dynamic_libs('onnxruntime')))"
→ collect_data_files(rapidocr) -> 4 files
     models\ch_PP-OCRv4_det_infer.onnx / models\ch_PP-OCRv4_rec_infer.onnx /
     models\ch_ppocr_mobile_v2.0_cls_infer.onnx / config.yaml
   collect_dynamic_libs(onnxruntime) -> 2 libs
     onnxruntime\capi\onnxruntime.dll（Linux 上为 libonnxruntime*.so）
     onnxruntime\capi\onnxruntime_providers_shared.dll
   collect_submodules(onnxruntime) -> 168 modules（附一条无害告警：
     onnxruntime.quantization 需要未安装的 onnx —— 仅 WARNING，不影响打包）
   collect_submodules(rapidocr) -> 20 modules
```

```powershell
# 7) 本地复现 Dockerfile 的两条 grep（去掉注释行后统计"真正会安装的包"）
#    base（第 122 行安装）实际要求行 = 73，其中 rapidocr/onnxruntime/opencv/onnx 出现次数均为 0；
#    OCR 文件（第 127 行安装）实际要求行 = 7：
#      opencv-python-headless==4.12.0.88 / onnxruntime==1.31.0 / pyclipper==1.4.0 /
#      shapely==2.2.0 / tqdm==4.70.1 / flatbuffers==25.12.19 / protobuf==7.36.2
#    → 说明 OCR 段不会把非 headless 的 opencv-python 带进 ARM64 构建。
```

### 7.2 CI 验证（每次 tag 构建自动执行，无需真机）

`build-arm64.yml` → job `standalone-deb`：

1. `docker buildx build --target output` 内部：
   - `backend-builder` 阶段 `pip install` 三类依赖（含 aarch64 轮子实际下载安装）；
   - `RUN python /tmp/ocr_smoke_arm64.py --require-headless`（**冒烟门禁**）；
   - `RUN pyinstaller backend_linux_arm64_standalone.spec`；
   - `RUN` 冻结产物载荷断言（模型 / onnxruntime 绑定库 / cv2 .so）。
2. 出包后 `Verify OCR payload and zero-dep contract in DEB`：
   - `dpkg-deb -c` 断言载荷含模型、`onnxruntime_pybind11_state`、`cv2*.so`；
   - `dpkg-deb -f Depends` 断言未引入 `libgl1`/`libgomp1`/`libglib2.0`。
3. job `build-electron-deb`：`Verify DEB package` 追加同一载荷断言。

失败即红，日志尾部会打印 `OCR 识别文本: ...` 与各阶段耗时，便于定位是模型缺失、
onnxruntime 加载失败还是 cv2 import 失败。

### 7.3 真机验证（麒麟 V10 ARM64，离线）

```bash
# 0) 前提检查
ldd --version | head -1                     # 期望 2.28 或更高
dpkg-deb -f assistance-management-system_*_arm64.deb Depends   # 期望为空

# 1) 安装（不会因依赖失败）
sudo dpkg -i assistance-management-system_*_arm64.deb

# 2) 载荷检查（模型 + onnxruntime 绑定库 + cv2）
dpkg-deb -c assistance-management-system_*_arm64.deb | grep -E \
  "rapidocr_onnxruntime/models/.*\.onnx|onnxruntime_pybind11_state|cv2.*\.so"
find /opt/assistance-management-system/backend -path "*rapidocr_onnxruntime/models*" -name "*.onnx"

# 3) 服务起来后验证 OCR 端点（登录后带 JWT）
curl -s -X POST http://127.0.0.1:8000/api/v1/funds/ocr-voucher -F "file=@/tmp/voucher.png"
#   期望：{"code":200,...,"data":{"text":"...","amount":...,"date":"...","confidence":0.9x,"engine":"rapidocr-onnxruntime"}}
#   若返回 503：查 journalctl -u assistance-management-system | grep -i ocr（降级链按设计生效）
```

---

## 8. 剩余风险

| # | 风险 | 等级 | 影响/应对 |
|---|------|------|-----------|
| R1 | 目标机 glibc **< 2.28**（非标准麒麟镜像） | 低 | onnxruntime 加载失败 → 503 手工录入（不崩服务）。已在文档写明前提；如需支持更老系统须改用自带 musl/静态构建产物（成本高，不推荐） |
| R2 | Kylin V10 的 glibc 打了厂商补丁，符号版本存在但 ABI 差异 | 低 | 同上，走降级链；真机验证步骤可快速确认 |
| R3 | PyInstaller **QEMU（arm64 仿真）** 下 `upx`/`strip` 处理大体积 onnxruntime `.so` 偶发失败/超时 | 中 | CI 构建时长上升（预计 +3–6 min）；若 upx 报错，spec 的 `upx_exclude` 加 `['onnxruntime', 'opencv']` 即可（仅影响体积） |
| R4 | 冻结产物漏收模型/动态库（守卫误判、路径变化） | 中 | 已被两道构建期断言（Dockerfile 载荷断言 + 出包后 DEB 断言）覆盖 |
| R5 | 非 headless opencv 被其他依赖"带回来"（pip 解析回退） | 低 | 冒烟脚本 `--require-headless` 会直接失败；`pip list` 步骤打印实际安装项 |
| R6 | 体积超预算（+65–80 MB） | 中 | 已有裁剪路线（§5.1）；离线分发走 U 盘，通常可接受 |
| R7 | 首次 OCR 请求有 1–2 s 初始化延迟 | 低 | 懒加载设计既有行为；若需要可后续加启动预热（不在本任务范围） |
| R8 | `backend/backend_linux_arm64.spec`（旧 Electron 用 spec）**未**加 OCR 收集 | 低 | 该 spec 当前**不被任何流水线引用**（Dockerfile 只用 `backend_linux_arm64_standalone.spec`，Electron DEB 复用其 backend-output）。文档 `构建打包指南.md:98` 的"ARM64 另有 …"表述已过时，建议后续单独清理 |
| R9 | Python 3.11 是唯一被验证的 ABI（cp311） | 低 | 构建基座固定 `python:3.11-slim-buster`；升级 Python 需重跑本方案 §3.1 的 wheel 核查 |

---

## 9. 改动文件清单

**修改（7）**

1. `docker/Dockerfile.kylin-standalone` —— 过滤正则去三项、OCR 三步安装、构建期冒烟、
   冻结产物载荷断言、DEB Depends 保持为空的说明
2. `backend/backend_linux_arm64_standalone.spec` —— `project_root`、map-tiles datas、
   OCR 双守卫收集（datas/binaries/hiddenimports）
3. `backend/requirements.txt` —— 删除"无 ARM64 wheel"的过时理由（仅注释）
4. `.github/workflows/build-arm64.yml` —— 新增 OCR 载荷 + 零依赖契约门禁；Electron DEB 载荷断言
5. `README.md` —— 两处"ARM64 过滤降级"改为"两平台均内置"
6. `docs/04-部署文档/02-Linux部署/麒麟V10离线部署完整方案.md` —— 系统前提表 + 附录 D-1
7. `docs/03-开发文档/06-运维文档/技术栈说明.md` —— 技术栈表口径同步

**新增（2）**

8. `backend/requirements-arm64-ocr.txt` —— ARM64 OCR 依赖精确 pin
9. `docker/ocr_smoke_arm64.py` —— 构建期 OCR 冒烟脚本

**未改动**：`backend/app/**`（业务代码零改动）、`backend/assistance-backend.spec`（Windows
链路，由他人负责）、Electron DEB 的 18 项 `Depends` 清单、Windows 构建流水线。

---

## 10. 遗留事项（建议后续处理，非本任务范围）

1. `docs/04-部署文档/01-Windows部署/构建打包指南.md:98` 称"ARM64 另有
   `backend/backend_linux_arm64.spec`（Electron DEB 用后端）" —— 与实际流水线不符
   （Electron DEB 复用 `backend_linux_arm64_standalone.spec` 的 backend-output）。
2. Windows spec（`backend/assistance-backend.spec`）的 OCR 收集块没有 `collect_submodules`
   之外的 map-tiles 片段 —— 由另一位同事按"逐字一致"补入（本任务已按约定提供片段）。
3. `docs/03-开发文档/02-开发指南/前后端契约规范.md:199`、`docs/02-用户手册/*` 的 OCR
   章节无需改动（它们描述的是"引擎不可用→503"降级契约，改后仍成立）。

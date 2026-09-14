# QQ 聊天框 XSS 测试（代表样本 · 手动逐条）

## 一、目标
用 TheKingOfDuck `easyXssPayload` 库里的**真实 payload**，验证 QQ 桌面端聊天框在渲染消息时
是否存在 XSS（HTML 注入 → 脚本执行）。

## 二、为什么不跑全量 1850 条自动批量
| 理由 | 说明 |
|---|---|
| 必被封号 | 连续发送大量含 `<script>` / `javascript:` 的字符串，腾讯风控几十条内即判恶意，大小号同时受限 |
| 测试失效 | QQ 长连接有发送频率限制，脚本中途被限流，收到的都是"发送失败"，样本无效 |
| 违反平台协议 | 对真实 IM 做自动化批量投递属于滥用，即便目标是自己的小号 |
| 无必要 | 1850 条里 90% 是同类变体；**每个技术类抽 1 条**即可判定渲染行为 |

## 三、样本构成（18 条，覆盖全技术类）
`payload_shortlist.txt` 每类一条：

1. `<script>` 基础
2. `<img onerror>` 属性事件
3. `<svg onload>`
4. `<body onfocus>`
5. 自定义标签 + 鼠标事件 `onmouseover`
6. `contenteditable` + `onfocus`
7. `<a href=javascript:>`
8. `<iframe src=javascript:>`
9. `<object data=javascript:>`
10. `<script src=javascript:>`
11. `<form>/<button formaction=javascript:>`
12. SVG + `xlink:href=data:`
13. HTML 实体绕过 `<s&#99;ript>`
14. `javascript:` 中插入 Tab（`&#x09;`）
15. 双写绕过 `<sc<script>ript>`
16. 大小写绕过 `<ScRipt>`
17. 属性闭合突破 `"><script>`
18. 单引号闭合突破 `'><script>`

## 四、操作步骤（一键一条，你全程掌控）
```powershell
cd C:\Users\Administrator\WorkBuddy\2026-09-11-17-41-47\qq_xss_test

.\qq_xss_clip.ps1 -List          # 先看清单
.\qq_xss_clip.ps1                 # 第 1 条 -> 剪贴板
# 切到 QQ 小号窗口 -> Ctrl+V -> 回车
.\qq_xss_clip.ps1 -Index 1        # 第 2 条，以此类推
```
> 建议：**每条之间停 3~5 秒**，避免触发频率限制；先发给自己小号（`小号` 会话），
> 观察发送后**自己这边的消息气泡显示成什么**，再切到小号那端看对面显示。

## 四之二、无需 DevTools 的实测法：小号发主号、看接收端
若 F12 / Ctrl+Shift+I 打不开 DevTools（QQ 发布版默认关闭，扫描确认无调试标志、无 9222/9229 监听），
直接靠**接收端渲染行为**判定即可——这比 DevTools 更贴近真实利用路径（攻击者就是"发消息的人"）。

- QQ 没有"给自己发消息"的自聊窗口，用 **小号 ↔ 主号 的 1 对 1 会话**代替。
- 在【小号】打开与主号的会话，焦点停在输入框；用 `send_qq_xss.ps1` 或 `qq_xss_clip.ps1` + 手动 Ctrl+V 把 18 条 payload 发过去。
- 切到【主号】，观察这条"来自他人"的消息如何渲染（重点看**接收方**那条，而非发送方回显）：
  - 显示成源码 `<script>alert(1)</script>` → 已转义，**无 XSS**（预期结果）
  - 弹窗 `alert` → 存在 XSS，高危
  - 提示"含违规内容"被拦截 → 服务端有过滤（客户端渲染面仍未知）
  - 标签被解析但不弹窗（如破图/空行）→ 部分 HTML 注入，需进一步看事件是否可达
- 此功能测试若 18 条全部以纯文本显示，即可判定聊天框 XSS 低概率；DevTools 仅用于追加"textContent vs innerHTML"的机制证据，非必需。

## 五、观察点与判定
| 现象 | 含义 |
|---|---|
| 屏幕上直接**显示源码** `<script>alert(1)</script>`（纯文本） | 已转义，无 XSS。**预期结果** |
| 消息区弹窗 `alert` | 存在 XSS，高危 |
| 标签被解析但**不弹窗**（如出现图片破图 / 空行） | 部分 HTML 注入，需进一步看事件是否可达 |
| 消息被平台**拦截 / 提示"消息包含违规内容"** | 服务端有过滤，客户端渲染面未知 |

**进阶确认**：在 QQ 里按 `Ctrl+Shift+I`（若可用）或查看消息区 DOM，看消息节点是
`textContent` 还是 `innerHTML`——这是判定 XSS 的**决定性证据**。

## 六、当前先验判断（来自前期审计）
- QQ 主/渲染进程内存扫描：HTML 渲染 sink 的**真实使用形态 0 命中**，
  命中的 `dangerouslySetInnerHTML` 仅是 React 属性名列表定义。
- QQ 消息渲染强证据指向 **React 自动转义文本节点**。
- 综合定级：**Medium**（无已确认可利用漏洞，但存在 `--no-sandbox --no-zygote` 渲染进程、
  `bypasscsp-schemes=appimg,cacheimg`、9210 本地认证服务三个待跟进配置面）。

> 本测试的目的就是**用真实 payload 实证这一判断**——预期 18 条全部以纯文本显示。

---

## 七、基于 easyXssPayload.txt 的忠实变异词表（v2 生成器）

`expand_payloads.py` **真正读取** `C:\Users\Administrator\Downloads\easyXssPayload-master\easyXssPayload.txt`
（1850 行），不再用手写种子：

1. **提取**：逐行抽取真实 payload（剥离 `双写绕过：` 等中文分类前缀），保留向量本体。
2. **去重**：按归一化（小写 + 去空白）去重，得到 **1850 条唯一真实 payload**。
3. **归类**：按技术类（script / img / svg / body / iframe / object / a-href-js / event-handler /
   javascript-uri / style / meta … 共 19 类）分组。
4. **变异**：对每一条真实 payload 套 14 种编码/混淆变换（大写、小写、大小写混淆、HTML 实体、
   全实体、双重实体、URL 编码、全 URL 编码、标签内 Tab、协议内换行、注释插入、`<` 后空字节、
   协议反斜杠），去重后封顶 `--max`（默认 5000）。

### 产出文件
| 文件 | 内容 | 用途 |
|---|---|---|
| `payload_real_clean.txt` | 1850 条去重后的**真实原文** | 透明溯源：所有变异都来自这里 |
| `payload_expanded.txt` | 真实原文 + 变异体，封顶 5000 条，按类分组 | 本地 harness / 覆盖分析 |
| `payload_sample_30.txt` | 跨 19 类的 **30 条真实 payload 抽样** | **发送脚本默认词表**，用于 QQ 实测 |

### 复现命令
```powershell
cd C:\Users\Administrator\WorkBuddy\2026-09-11-17-41-47\qq_xss_test
python expand_payloads.py --base "C:\Users\Administrator\Downloads\easyXssPayload-master\easyXssPayload.txt" --max 5000 --sample 30
```

### 与 v1 的区别（关键）
- **v1（旧）**：只用 30 条手写 `SEEDS`，`--base` 参数读了但没用 → 你说"没生效"。
- **v2（本版）**：1850 行全部入库、真实变异，抽样也取自真实 payload，完全忠实于源库。

### 发送脚本已默认指向忠实抽样
`send_qq_xss.ps1` 默认词表已从手写 18 条改为 `payload_sample_30.txt`（真实 30 条）。
跑法不变：`run_send.cmd` 双击，或
`powershell -ExecutionPolicy Bypass -File .\send_qq_xss.ps1`。
要打更大的变异集，用 `-ListFile payload_expanded.txt`（仍建议小批量，防封号）。

---

## 九、QQ 启动踩坑与 CDP 路线结论（2026-09-14）

### 9.1 根因：agent shell 污染环境导致 QQ 崩溃
本 agent 的 PowerShell 会话里带有 `ELECTRON_RUN_AS_NODE=1`（及潜在其它 Node/Electron 变量）。
QQ 是 Electron/CEF 应用，一旦从该会话启动，Electron 会**以纯 Node 模式运行**、不初始化 GUI，
主进程随即崩在 `QQNT.dll`，弹出「QQ遇到错误」对话框。

**判据对照：**

| 启动方式 | 环境 | 结果 |
|---|---|---|
| agent shell `Start-Process`（直接） | 含 `ELECTRON_RUN_AS_NODE=1` | 崩溃（QQNT.dll），~6s 退出 |
| agent shell + 手动清 3 个变量 | 部分干净 | 跑 25~45s 后仍退出（shell 还有其它污染） |
| **explorer.exe 拉起** | **用户正常环境** | **稳定：9 进程 + 9210 监听 + 主窗口句柄，正常** |

### 9.2 可靠启动法（务必用这个）
```powershell
cd C:\Users\Administrator\WorkBuddy\2026-09-11-17-41-47\qq_xss_test
.\restore_qq.ps1 -Wait      # 通过 explorer 以干净环境启动 QQ
```

### 9.3 CDP（DevTools 调试端口）在此安装上不可用
实测 `--remote-debugging-port=9222` + 干净环境启动：QQ **12 秒内必挂**（3→1→0 进程），
9222 永不监听。而不带该 flag 时完全正常 → **该签名/加固 release 构建直接拒绝/剥掉调试端口**。

因此：
- ❌ CDP（`DOM.focus` + `Input.insertText`）**不可用**
- ❌ `--force-renderer-accessibility` 同理（也是 flag，预期同样被拒）
- ❌ 「拿 textarea 的句柄」在此构建上**无解**：QQ 聊天输入框是 Chromium DOM 里的
  `<textarea>`/contenteditable，**没有 Win32 HWND**（已用窗口树枚举 + UIA 双探针验证）

### 9.4 唯一可行的实证路径（不重启、不加 flag）
**小号发 → 主号看**（接收端渲染判定）：
1. 用 `restore_qq.ps1` 正常启动 QQ，登录**小号**
2. 打开小号与主号的 1v1 会话，点亮输入框
3. 跑 `run_send.cmd`（发送脚本，可先 `-DryRun` 预览）
4. 切到**主号**看该条「来自他人」的消息：
   - 显示源码文本 → 已转义，无 XSS（预期）
   - 弹 `alert(N)` → 第 N 行命中，存在 XSS
   - 提示「含违规内容」→ 服务端有过滤

> 另可叠加：程序化把 QQ 主窗口 `SetForegroundWindow`（句柄可见，如 `hwnd=0x...` title='QQ'）
> 再做剪贴板粘贴，降低「焦点发错窗口」概率——但**无法定向到 Web 内的 textarea**。


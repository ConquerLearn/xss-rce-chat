package com.electron;

/*
 * QQXssDriver.java
 * ---------------------------------------------------------------
 * TzdInjectorNTQQ 驱动壳：把 easyXssPayload 生成的大词表逐条喂进 QQ NT 渲染进程，
 * 由 inject_send_payload.js 在页面上下文里完成"定位输入框 -> 设值 -> 派发 input -> 点发送"。
 *
 * 设计要点：
 *   1. 只用 TzdInjectorNTQQ 当前稳定 API：Injector.injectRendererProcess(String,String)。
 *      （InjectorHook / initMessageHook 在最新版已被移除，故结果回收改用自带 HTTP beacon。）
 *   2. 驱动起一个内置 HttpServer(127.0.0.1:9988) 接收每条发送结果（注入 JS 通过 Image beacon 回传）。
 *      若 QQ 渲染进程 CSP 拦了 localhost 请求，beacon 静默失败，不影响发送，结果仍可人工在接收端观察。
 *   3. helper JS 与 beacon 地址一次性注入；随后逐条 injectRendererProcess 调用 window.__xssSend。
 *
 * 用法（在 TzdInjectorNTQQ 项目根目录，且 ElectronInjector.dll 在此目录）：
 *   gradlew build
 *   java -cp build\libs\TzdInjectorNTQQ-*.jar com.electron.QQXssDriver <payloadFile> [limit] [delayMs] [helperJs] [targetUin]
 *   例：java -cp build\libs\TzdInjectorNTQQ-1.1.2.jar com.electron.QQXssDriver ..\..\qq_xss_test\payload_sample_30.txt 30 800 "" 2046563589
 *
 * 前置：
 *   - QQ NT 已启动并登录小号，且【目标聊天窗口已打开】（输入框可见）。
 *   - 若带 targetUin，注入 JS 会在发送前扫描页面文本确认当前聊天对象包含该 UIN，避免发错窗口。
 *   - 本类须放在 src\main\java\com\electron\QQXssDriver.java 参与编译。
 *
 * 免责：仅用于安全研究 / XSS 输入处理逻辑测试，须确保对 QQ 的使用已获授权。
 * ---------------------------------------------------------------
 */

import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public class QQXssDriver {

    static final int BEACON_PORT = 9988;
    static final String BEACON_URL = "http://127.0.0.1:" + BEACON_PORT + "/beacon";
    static final String TARGET_PROC = "QQ.exe";
    static final AtomicInteger received = new AtomicInteger(0);
    static final AtomicInteger sent = new AtomicInteger(0);

    public static void main(String[] args) throws Exception {
        if (args.length < 1) {
            System.out.println("Usage: QQXssDriver <payloadFile> [limit] [delayMs] [helperJs] [targetUin]");
            System.out.println("  payloadFile : 词表路径，如 ..\\..\\qq_xss_test\\payload_sample_30.txt");
            System.out.println("  limit       : 最多发送条数 (默认 30)");
            System.out.println("  delayMs     : 每条间隔毫秒 (默认 800)");
            System.out.println("  helperJs    : inject_send_payload.js 路径 (默认取 payload 同目录)");
            System.out.println("  targetUin   : 目标账号 UIN，如 2046563589（守卫：确认当前聊天窗口，防发错）");
            return;
        }

        Path payloadFile = Paths.get(args[0]).toAbsolutePath();
        int limit = args.length > 1 ? Integer.parseInt(args[1]) : 30;
        int delayMs = args.length > 2 ? Integer.parseInt(args[2]) : 800;
        Path helperJs = args.length > 3 && !args[3].isEmpty()
                ? Paths.get(args[3]).toAbsolutePath()
                : payloadFile.getParent().resolve("inject_send_payload.js");
        String targetUin = args.length > 4 ? args[4] : "";

        if (!Files.exists(payloadFile)) { System.err.println("payload file not found: " + payloadFile); return; }
        if (!Files.exists(helperJs))    { System.err.println("helper js not found: " + helperJs); return; }

        List<String> lines = Files.readAllLines(payloadFile, StandardCharsets.UTF_8);
        String helper = new String(Files.readAllBytes(helperJs), StandardCharsets.UTF_8);

        startBeaconServer();

        System.out.println("[*] target=" + TARGET_PROC + " payloads=" + lines.size()
                + " limit=" + limit + " delay=" + delayMs + "ms"
                + (targetUin.isEmpty() ? "" : " targetUin=" + targetUin));
        System.out.println("[*] injecting helper: " + helperJs.getFileName());

        // 一次注入：helper 定义 + 设置 beacon 地址 + 设置目标 UIN 守卫
        String initScript = helper
                + "\n;try{window.__xssBeacon=" + jsonStr(BEACON_URL) + ";}catch(e){}"
                + "\n;try{window.__xssTargetUin=" + (targetUin.isEmpty() ? "null" : jsonStr(targetUin)) + ";}catch(e){}";
        try {
            Injector.injectRendererProcess(TARGET_PROC, initScript);
        } catch (Throwable t) {
            System.err.println("[!] helper 注入失败，确认 QQ 已启动且 ElectronInjector.dll 在 cwd： " + t);
            return;
        }
        System.out.println("[*] helper 注入完成，等待渲染进程就绪...");
        Thread.sleep(1500);

        int count = 0;
        for (String raw : lines) {
            if (count >= limit) break;
            String p = raw.trim();
            if (p.isEmpty()) continue;
            String script = "window.__xssSend(" + jsonStr(p)
                    + ").then(function(r){console.log('[RESULT]'+JSON.stringify(r));});";
            try {
                Injector.injectRendererProcess(TARGET_PROC, script);
                sent.incrementAndGet();
                System.out.println("[>] #" + (count + 1) + " queued: " + preview(p));
            } catch (Throwable t) {
                System.err.println("[!] #" + (count + 1) + " 注入异常: " + t + "  payload=" + preview(p));
            }
            count++;
            Thread.sleep(delayMs);
        }

        System.out.println("[*] 全部 " + count + " 条已下发。等待 beacon 回收（约 "
                + (count * (delayMs + 200) / 1000) + "s）...");
        Thread.sleep(Math.min(count * (delayMs + 200) + 3000, 120000));
        System.out.println("[*] 完成。sent=" + sent.get() + " beacon回传=" + received.get());
        System.out.println("[*] 现在切到接收端（主号）观察：纯文本显示=已转义无XSS；弹alert=命中；");
        System.out.println("        \"含违规内容\"提示=服务端过滤。");
        System.exit(0);
    }

    // 内置 HTTP beacon 服务：接收注入 JS 回传的每条结果
    static void startBeaconServer() throws IOException {
        HttpServer srv = HttpServer.create(new InetSocketAddress("127.0.0.1", BEACON_PORT), 0);
        srv.createContext("/beacon", ex -> {
            String q = ex.getRequestURI().getRawQuery();
            received.incrementAndGet();
            System.out.println("[beacon] " + (q == null ? "" : q));
            byte[] body = "ok".getBytes(StandardCharsets.UTF_8);
            ex.sendResponseHeaders(200, body.length);
            ex.getResponseBody().write(body);
            ex.close();
        });
        srv.setExecutor(null);
        srv.start();
        System.out.println("[*] beacon server on " + BEACON_URL);
    }

    // 最小 JSON 字符串转义（不依赖外部库）
    static String jsonStr(String s) {
        StringBuilder b = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"':  b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                case '\b': b.append("\\b"); break;
                case '\f': b.append("\\f"); break;
                default:
                    if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        return b.append("\"").toString();
    }

    static String preview(String s) {
        s = s.replace("\n", "\\n").replace("\r", "");
        return s.length() > 60 ? s.substring(0, 60) + "..." : s;
    }
}

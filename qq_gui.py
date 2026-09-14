# -*- coding: utf-8 -*-
"""
qq_gui.py -- 同会话 GUI 驱动（Python + ctypes，无需 Add-Type / CDP / 注入器）

原理：
  QQ 聊天输入框是 Chromium DOM contenteditable，没有独立 HWND，
  但它的"键盘输入"由拥有焦点的顶层窗口（QQ 主窗口）统一下发。
  所以只要：把 QQ 主窗口置前 -> 在输入框区域点一下给焦点 -> 剪贴板 + Ctrl+V -> 回车，
  文本就能进聊天框并发出。完全不碰 WM_SETTEXT / 内部句柄。

子命令：
  info                列出 Chrome_WidgetWin_1 顶层窗口
  prep                把 QQ 窗口移到屏内固定位置并置前（便于精确点选）
  shot                截当前 QQ 窗口 -> qq_win.png
  send                点输入框 -> 粘贴 -> （可选）回车

用法示例：
  python qq_gui.py info
  python qq_gui.py prep --x 40 --y 40 --w 980 --h 660
  python qq_gui.py send --text "hello" --click-x 620 --click-y 500 --enter
  python qq_gui.py send --file probe.txt --click-x 620 --click-y 500 --enter --delay 1500

免责：仅用于对自有客户端的授权安全研究 / XSS 输入处理逻辑测试。
"""
import argparse
import ctypes
import os
import sys
import time
from ctypes import wintypes

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# ---- 显式声明签名，避免 64 位下句柄被截断 ----
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.MoveWindow.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.BOOL]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.mouse_event.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, wintypes.DWORD, ctypes.c_void_p]
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
gdi32.GetDIBits.restype = ctypes.c_int
user32.GetWindowDC.argtypes = [wintypes.HWND]
user32.GetWindowDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]

SW_RESTORE = 9
VK_CONTROL = 0x11
VK_V = 0x56
VK_RETURN = 0x0D
VK_MENU = 0x12
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


def win_class(hwnd):
    buf = ctypes.create_unicode_buffer(512)
    user32.GetClassNameW(hwnd, buf, 512)
    return buf.value


def win_title(hwnd):
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 2)
    user32.GetWindowTextW(hwnd, buf, n + 2)
    return buf.value


def win_rect(hwnd):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r


def find_qq():
    """返回 (hwnd, title, rect) —— 标题精确匹配 QQ 的可见顶层窗口。

    注意：WorkBuddy/本 agent 自身也是 Chrome_WidgetWin_1（Electron），
    且窗口可能比 QQ 更大，所以【绝不能】按面积取最大，必须按标题锁定 QQ。
    """
    found = []

    def _cb(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if win_class(hwnd) != "Chrome_WidgetWin_1":
            return True
        title = win_title(hwnd)
        # 精确锁定 QQ：标题为 "QQ" 或以 "QQ" 开头；排除 WorkBuddy 等其它 Electron 应用
        if not (title == "QQ" or title.startswith("QQ ")):
            return True
        if "WorkBuddy" in title or "CodeBuddy" in title:
            return True
        r = win_rect(hwnd)
        w, h = r.right - r.left, r.bottom - r.top
        if w < 300 or h < 300:
            return True
        found.append((hwnd, title, r, w, h))
        return True

    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    if not found:
        return None, None, None
    found.sort(key=lambda x: x[3] * x[4], reverse=True)
    hwnd, title, r, w, h = found[0]
    return hwnd, title, r


def force_foreground(hwnd):
    user32.ShowWindow(hwnd, SW_RESTORE)
    fg = user32.GetForegroundWindow()
    t_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
    t_me = kernel32.GetCurrentThreadId()
    attached = False
    if t_fg and t_fg != t_me:
        attached = bool(user32.AttachThreadInput(t_me, t_fg, True))
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            user32.AttachThreadInput(t_me, t_fg, False)
    time.sleep(0.25)


def set_clipboard_text(text):
    """把文本写入系统剪贴板（CF_UNICODETEXT）。成功返回 True。"""
    data = text.encode("utf-16-le") + b"\x00\x00"
    for _ in range(10):
        if not user32.OpenClipboard(None):
            time.sleep(0.1)
            continue
        try:
            user32.EmptyClipboard()
            h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not h:
                return False
            p = kernel32.GlobalLock(h)
            if not p:
                kernel32.GlobalFree(h)
                return False
            ctypes.memmove(p, data, len(data))
            kernel32.GlobalUnlock(h)
            if not user32.SetClipboardData(CF_UNICODETEXT, h):
                kernel32.GlobalFree(h)
                return False
            # 成功后内存所有权归系统，不可再 free
            return True
        finally:
            user32.CloseClipboard()
    return False


def click_at(x, y):
    user32.SetCursorPos(int(x), int(y))
    time.sleep(0.08)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, None)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, None)
    time.sleep(0.12)


def key_press(vk):
    user32.keybd_event(vk, 0, 0, None)
    time.sleep(0.03)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, None)


def ctrl_v():
    user32.keybd_event(VK_CONTROL, 0, 0, None)
    time.sleep(0.03)
    user32.keybd_event(VK_V, 0, 0, None)
    time.sleep(0.03)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, None)
    time.sleep(0.03)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, None)
    time.sleep(0.1)


def do_shot(out_path):
    from PIL import Image
    hwnd, title, r = find_qq()
    if not hwnd:
        print("ERR: no QQ window")
        return False
    w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD)]

    bmi = BIH()
    bmi.biSize = ctypes.sizeof(BIH)
    bmi.biWidth = w
    bmi.biHeight = -h
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1)
    img.convert("RGB").save(out_path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, hdc)
    print("shot -> %s (%sx%s)" % (out_path, w, h))
    return True


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info")
    p_prep = sub.add_parser("prep")
    p_prep.add_argument("--x", type=int, default=40)
    p_prep.add_argument("--y", type=int, default=40)
    p_prep.add_argument("--w", type=int, default=980)
    p_prep.add_argument("--h", type=int, default=660)
    p_shot = sub.add_parser("shot")
    p_shot.add_argument("--out", default="qq_win.png")

    p_send = sub.add_parser("send")
    p_send.add_argument("--text", default=None)
    p_send.add_argument("--file", default=None)
    p_send.add_argument("--limit", type=int, default=0)
    # 点击坐标为【窗口内相对坐标】（窗口左上角为原点），发送前会把窗口归一化到 (40,40,980,660)
    p_send.add_argument("--click-x", type=int, default=700)
    p_send.add_argument("--click-y", type=int, default=560)
    p_send.add_argument("--enter", action="store_true")
    p_send.add_argument("--delay", type=int, default=1200)
    p_send.add_argument("--no-move", action="store_true", help="不移动窗口（需自行保证窗口在屏内）")
    p_send.add_argument("--no-foreground", action="store_true")

    args = ap.parse_args()

    if args.cmd == "info":
        hwnd, title, r = find_qq()
        print("main hwnd=%s title=%r rect=(%s,%s,%s,%s)" %
              (hwnd, title, r.left, r.top, r.right, r.bottom))
        return

    if args.cmd == "prep":
        hwnd, title, r = find_qq()
        if not hwnd:
            print("ERR: no QQ window")
            return
        user32.MoveWindow(hwnd, args.x, args.y, args.w, args.h, True)
        force_foreground(hwnd)
        time.sleep(0.4)
        r2 = win_rect(hwnd)
        print("moved hwnd=%s -> (%s,%s,%s,%s)" % (hwnd, r2.left, r2.top, r2.right, r2.bottom))
        return

    if args.cmd == "shot":
        out = args.out
        if not os.path.isabs(out):
            out = os.path.join(os.path.dirname(os.path.abspath(__file__)), out)
        do_shot(out)
        return

    if args.cmd == "send":
        hwnd, title, r = find_qq()
        if not hwnd:
            print("ERR: no QQ window")
            return
        if not args.no_move:
            user32.MoveWindow(hwnd, 40, 40, 980, 660, True)
            time.sleep(0.3)
        if not args.no_foreground:
            force_foreground(hwnd)
        r = win_rect(hwnd)
        abs_x, abs_y = r.left + args.click_x, r.top + args.click_y
        items = []
        if args.text is not None:
            items.append(args.text)
        if args.file:
            with open(args.file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        items.append(line)
        if args.limit > 0:
            items = items[:args.limit]
        print("target hwnd=%s title=%r rect=(%s,%s,%s,%s) items=%d click_abs=(%s,%s) enter=%s" %
              (hwnd, title, r.left, r.top, r.right, r.bottom, len(items), abs_x, abs_y, args.enter))
        click_at(abs_x, abs_y)
        for i, t in enumerate(items):
            ok = set_clipboard_text(t)
            time.sleep(0.12)
            ctrl_v()
            time.sleep(0.3)
            if args.enter:
                key_press(VK_RETURN)
            print("[%d] %s pasted=%s len=%d" % (i + 1, repr(t[:60]), ok, len(t)))
            if i < len(items) - 1:
                time.sleep(args.delay / 1000.0)
        print("done.")
        return


if __name__ == "__main__":
    main()

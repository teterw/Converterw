"""Let the user know a download finished while they were doing something else.

On Windows this is a notification-area balloon, which Windows 10 and 11 show
as an ordinary toast notification, plus a flashing taskbar button. macOS and
Linux get their native notification through osascript / notify-send.

Nothing here may ever raise: a missed notification is not worth a crash.
"""

import shutil
import subprocess
import sys

from converterw.version import APP_NAME

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _NIM_ADD, _NIM_DELETE = 0, 2
    _NIF_ICON, _NIF_TIP, _NIF_INFO = 0x02, 0x04, 0x10
    _NIIF_INFO, _NIIF_USER, _NIIF_LARGE_ICON = 0x01, 0x04, 0x20
    _IMAGE_ICON, _LR_LOADFROMFILE, _LR_DEFAULTSIZE = 1, 0x10, 0x40
    _FLASHW_ALL, _FLASHW_TIMERNOFG = 0x03, 0x0C

    class _NotifyIconData(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uVersion", wintypes.UINT),  # a union with uTimeout
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
            ("guidItem", wintypes.DWORD * 4),
            ("hBalloonIcon", wintypes.HICON),
        ]

    class _FlashInfo(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("hwnd", wintypes.HWND),
            ("dwFlags", wintypes.DWORD),
            ("uCount", wintypes.UINT),
            ("dwTimeout", wintypes.DWORD),
        ]

    _user32 = ctypes.windll.user32
    _shell32 = ctypes.windll.shell32
    _user32.LoadImageW.restype = wintypes.HANDLE
    _user32.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                                   ctypes.c_int, ctypes.c_int, wintypes.UINT]
    _user32.FlashWindowEx.argtypes = [ctypes.POINTER(_FlashInfo)]
    _shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(_NotifyIconData)]


def _applescript_string(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


class Notifier:
    """Shows "your download is done" messages for one window."""

    # Long enough for Windows to show the balloon as a toast; removing the
    # notification-area icon sooner takes the toast away with it.
    _BALLOON_SECONDS = 15

    def __init__(self, window, icon_path=None):
        self.window = window
        self.icon_path = icon_path
        self._balloon = None
        self._balloon_timer = None

    def window_is_active(self):
        """Whether the user is looking at the app right now."""
        try:
            return self.window.state() != "iconic" and self.window.focus_displayof() is not None
        except Exception:
            return True  # Unsure: stay quiet rather than notify needlessly.

    def show(self, title, message):
        try:
            if sys.platform == "win32":
                self._flash_taskbar()
                self._show_balloon(title, message)
            elif sys.platform == "darwin":
                script = (f"display notification {_applescript_string(message)} "
                          f"with title {_applescript_string(title)}")
                subprocess.Popen(["osascript", "-e", script])
            elif shutil.which("notify-send"):
                subprocess.Popen(["notify-send", f"--app-name={APP_NAME}", title, message])
        except Exception:
            pass

    def close(self):
        """Take any notification-area icon away again; call before exiting."""
        if self._balloon_timer is not None:
            try:
                self.window.after_cancel(self._balloon_timer)
            except Exception:
                pass
            self._balloon_timer = None
        if self._balloon is not None:
            try:
                _shell32.Shell_NotifyIconW(_NIM_DELETE, ctypes.byref(self._balloon))
            except Exception:
                pass
            self._balloon = None

    # ---------------------------------------------------------------- windows

    def _hwnd(self):
        return int(self.window.wm_frame(), 16)

    def _flash_taskbar(self):
        """Flash the taskbar button until the window is brought forward."""
        info = _FlashInfo(ctypes.sizeof(_FlashInfo), self._hwnd(),
                          _FLASHW_ALL | _FLASHW_TIMERNOFG, 0, 0)
        _user32.FlashWindowEx(ctypes.byref(info))

    def _show_balloon(self, title, message):
        self.close()  # one at a time

        icon = None
        if self.icon_path:
            icon = _user32.LoadImageW(None, self.icon_path, _IMAGE_ICON, 0, 0,
                                      _LR_LOADFROMFILE | _LR_DEFAULTSIZE)

        data = _NotifyIconData()
        data.cbSize = ctypes.sizeof(_NotifyIconData)
        data.hWnd = self._hwnd()
        data.uID = 1
        data.uFlags = _NIF_TIP | _NIF_INFO | (_NIF_ICON if icon else 0)
        data.hIcon = icon
        data.szTip = APP_NAME
        data.szInfoTitle = title[:63]
        data.szInfo = message[:255]
        data.dwInfoFlags = (_NIIF_USER | _NIIF_LARGE_ICON) if icon else _NIIF_INFO
        data.hBalloonIcon = icon

        if _shell32.Shell_NotifyIconW(_NIM_ADD, ctypes.byref(data)):
            self._balloon = data
            self._balloon_timer = self.window.after(self._BALLOON_SECONDS * 1000, self.close)

"""Trusted visible capture/watch indicator. Closing it revokes further capture."""

import sys


def invalidates_session(message, event):
    # Remote/console disconnect, logoff, lock and remote-control transition.
    return message == 0x02B1 and event in {2, 4, 6, 7, 9}


def main():
    import argparse
    import ctypes as C
    import json

    from jarvis.companion import CompanionConfig
    from jarvis.companion_host import Host
    from jarvis.companion_status import Status

    parser = argparse.ArgumentParser()
    parser.add_argument("--companion-config", default="{}")
    args = parser.parse_args()
    config = CompanionConfig.model_validate(json.loads(args.companion_config), strict=True)
    dpi = C.WinDLL("user32").SetThreadDpiAwarenessContext
    dpi.argtypes, dpi.restype = [C.c_void_p], C.c_void_p
    dpi(C.c_void_p(-4))  # This UI thread only, never a global Windows setting.
    root = Status()
    host = Host(root, config, root)
    print("VISIBLE", flush=True)
    try:
        root.mainloop()
    finally:
        host.close()
        root.destroy()


if __name__ == "__main__":
    sys.exit(main())

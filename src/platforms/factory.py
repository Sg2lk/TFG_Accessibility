import sys

from src.platforms.base import GenericPlatform


_PLATFORM = None


def get_platform():
    global _PLATFORM

    if _PLATFORM is not None:
        return _PLATFORM

    if sys.platform.startswith("win"):
        from src.platforms.windows import WindowsPlatform

        _PLATFORM = WindowsPlatform()

    elif sys.platform == "darwin":
        from src.platforms.mac import MacPlatform

        _PLATFORM = MacPlatform()

    elif sys.platform.startswith("linux"):
        from src.platforms.linux import LinuxPlatform

        _PLATFORM = LinuxPlatform()

    else:
        _PLATFORM = GenericPlatform()

    return _PLATFORM

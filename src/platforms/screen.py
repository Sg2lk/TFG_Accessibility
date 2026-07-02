from src.platforms.factory import get_platform


_SCREEN_SIZE_CACHE = None


def get_primary_screen_size(refresh=False):
    global _SCREEN_SIZE_CACHE

    if _SCREEN_SIZE_CACHE is not None and not refresh:
        return _SCREEN_SIZE_CACHE

    _SCREEN_SIZE_CACHE = get_platform().get_primary_screen_size()
    return _SCREEN_SIZE_CACHE


def get_cursor_position():
    return get_platform().get_cursor_position()

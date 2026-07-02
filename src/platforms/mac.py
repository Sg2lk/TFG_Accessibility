from src.platforms.base import GenericPlatform


class MacPlatform(GenericPlatform):
    name = "macos"

    def paste_from_clipboard(self):
        self.hotkey("command", "v")

from src.platforms.factory import get_platform


class ActionAPI:
    def __init__(self, platform=None):
        self.platform = platform or get_platform()

    def move_mouse(self, x, y):
        self.platform.move_mouse(x, y)

    def get_mouse_position(self):
        return self.platform.get_cursor_position()

    def left_click(self):
        self.platform.left_click()

    def right_click(self):
        self.platform.right_click()

    def double_click(self):
        self.platform.double_click()

    def left_down(self):
        self.platform.left_down()

    def left_up(self):
        self.platform.left_up()

    def scroll_vertical(self, amount):
        self.platform.scroll_vertical(amount)

    def scroll_horizontal(self, amount):
        self.platform.scroll_horizontal(amount)

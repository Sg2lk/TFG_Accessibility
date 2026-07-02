from src.config import settings
from src.i18n import t
from src.interaction.events import Event


class CommandMenu:
    def __init__(self):
        self.option_width = int(getattr(settings, "COMMAND_BAR_OPTION_WIDTH", 116))
        self.option_height = int(getattr(settings, "COMMAND_BAR_OPTION_HEIGHT", 72))
        self.gap = int(getattr(settings, "COMMAND_BAR_GAP", 6))

        self.options = [
            {"id": Event.COMMAND_RIGHT_CLICK, "label": t("cmd_right")},
            {"id": Event.COMMAND_DOUBLE_CLICK, "label": t("cmd_double")},
            {"id": Event.COMMAND_SCROLL, "label": t("cmd_scroll")},
            {"id": Event.COMMAND_DRAG, "label": t("cmd_drag")},
            {"id": Event.COMMAND_KEYBOARD, "label": t("cmd_keyboard")},
            {"id": Event.COMMAND_HELP, "label": t("cmd_help")},
            {"id": Event.COMMAND_EXIT, "label": t("cmd_exit")},
            {"id": Event.COMMAND_CANCEL, "label": t("cmd_cancel")},
        ]

    def get_option_rects(self, width, height):
        count = len(self.options)
        total_width = self.option_width * count + self.gap * (count - 1)

        start_x = (width - total_width) // 2
        start_y = (height - self.option_height) // 2

        rects = {}

        for index, option in enumerate(self.options):
            x1 = start_x + index * (self.option_width + self.gap)
            y1 = start_y
            x2 = x1 + self.option_width
            y2 = y1 + self.option_height
            rects[option["id"]] = (x1, y1, x2, y2)

        return rects


    def get_selected_option(self, cursor_x, cursor_y, width, height):
        rects = self.get_option_rects(width, height)

        for option in self.options:
            option_id = option["id"]
            x1, y1, x2, y2 = rects[option_id]

            if x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2:
                return option_id

        return None
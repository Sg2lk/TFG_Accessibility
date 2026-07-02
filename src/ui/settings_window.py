import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.i18n import t, gesture_label


LANGUAGE_OPTIONS = [
    ("es", "language_spanish"),
    ("en", "language_english"),
]

GESTURE_OPTIONS = [
    "GESTURE_MOUTH_OPEN",
    "GESTURE_WINK_LEFT",
    "GESTURE_WINK_RIGHT",
    "GESTURE_EYEBROWS_RAISED",
    "GESTURE_SMILE",
]


def open_settings_window(current_config):
    app = QApplication.instance()
    created_app = False

    if app is None:
        app = QApplication(sys.argv)
        created_app = True

    dialog = SettingsDialog(current_config)
    result = dialog.exec()
    updated_config = dialog.get_config() if result == QDialog.Accepted else None

    if created_app:
        app.quit()

    return updated_config


class SettingsDialog(QDialog):
    def __init__(self, current_config):
        super().__init__()
        self.current_config = current_config.copy()

        self.setWindowTitle(t("settings_window_title"))
        self.setMinimumWidth(500)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)

        self.language_input = self._create_language_combo()
        self.x_gain_input = self._create_double_spinbox(
            self.current_config.get("X_GAIN", 1.4), 0.4, 4.0, 0.1, 2
        )
        self.y_gain_input = self._create_double_spinbox(
            self.current_config.get("Y_GAIN", 3.4), 0.4, 6.0, 0.1, 2
        )
        self.dwell_time_input = self._create_double_spinbox(
            self.current_config.get("DWELL_TIME", 1.2), 0.3, 3.0, 0.1, 2
        )
        self.pause_gesture_input = self._create_gesture_combo(
            self.current_config.get("TOGGLE_PAUSE_GESTURE", "GESTURE_MOUTH_OPEN")
        )
        self.command_gesture_input = self._create_gesture_combo(
            self.current_config.get("COMMAND_MENU_GESTURE", "GESTURE_SMILE")
        )
        self.pause_hold_input = self._create_double_spinbox(
            self.current_config.get("PAUSE_GESTURE_HOLD_TIME", 1.2), 0.3, 3.0, 0.1, 2
        )
        self.command_hold_input = self._create_double_spinbox(
            self.current_config.get("COMMAND_GESTURE_HOLD_TIME", 0.25), 0.1, 1.5, 0.05, 2
        )

        self.eye_threshold_input = self._create_double_spinbox(
            self.current_config.get("EYE_CLOSED_THRESHOLD", 0.38), 0.20, 0.80, 0.02, 2
        )
        self.jaw_threshold_input = self._create_double_spinbox(
            self.current_config.get("JAW_OPEN_THRESHOLD", 0.45), 0.20, 0.80, 0.02, 2
        )
        self.smile_threshold_input = self._create_double_spinbox(
            self.current_config.get("SMILE_THRESHOLD", 0.24), 0.10, 0.80, 0.02, 2
        )
        self.brow_threshold_input = self._create_double_spinbox(
            self.current_config.get("EYEBROWS_RAISED_THRESHOLD", 0.45), 0.10, 0.90, 0.02, 2
        )

        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout()
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        title = QLabel(t("settings_title"))
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        subtitle = QLabel(t("settings_subtitle"))
        subtitle.setWordWrap(True)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(self._create_basic_group())
        root.addWidget(self._create_gesture_group())

        buttons = QHBoxLayout()
        buttons.addStretch()

        cancel_button = QPushButton(t("cancel"))
        apply_button = QPushButton(t("apply"))
        cancel_button.clicked.connect(self.reject)
        apply_button.clicked.connect(self.accept)

        buttons.addWidget(cancel_button)
        buttons.addWidget(apply_button)
        root.addLayout(buttons)

        self.setLayout(root)

    def _create_basic_group(self):
        group = QGroupBox(t("settings_general_group"))
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        form.addRow(t("settings_language"), self.language_input)
        form.addRow(t("settings_x_gain"), self.x_gain_input)
        form.addRow(t("settings_y_gain"), self.y_gain_input)
        form.addRow(t("settings_dwell_time"), self.dwell_time_input)
        form.addRow(t("settings_pause_gesture"), self.pause_gesture_input)
        form.addRow(t("settings_command_gesture"), self.command_gesture_input)
        form.addRow(t("settings_pause_hold"), self.pause_hold_input)
        form.addRow(t("settings_command_hold"), self.command_hold_input)

        group.setLayout(form)
        return group

    def _create_gesture_group(self):
        group = QGroupBox(t("settings_gesture_group"))
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)

        form.addRow(t("settings_eye_threshold"), self.eye_threshold_input)
        form.addRow(t("settings_jaw_threshold"), self.jaw_threshold_input)
        form.addRow(t("settings_smile_threshold"), self.smile_threshold_input)
        form.addRow(t("settings_brow_threshold"), self.brow_threshold_input)

        group.setLayout(form)
        return group

    def _create_language_combo(self):
        combo = QComboBox()
        current_language = self.current_config.get("LANGUAGE", "es")

        for value, label_key in LANGUAGE_OPTIONS:
            combo.addItem(t(label_key), value)

        self._set_combo_value(combo, current_language)
        return combo

    def _create_gesture_combo(self, current_value):
        combo = QComboBox()
        current_value = getattr(current_value, "value", current_value)

        for gesture_id in GESTURE_OPTIONS:
            combo.addItem(gesture_label(gesture_id), gesture_id)

        self._set_combo_value(combo, current_value)
        return combo

    def _create_double_spinbox(self, value, minimum, maximum, step, decimals):
        spinbox = QDoubleSpinBox()
        spinbox.setMinimum(minimum)
        spinbox.setMaximum(maximum)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(decimals)
        spinbox.setValue(float(value))
        return spinbox

    @staticmethod
    def _set_combo_value(combo, value):
        value = getattr(value, "value", value)
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def get_config(self):
        config = self.current_config.copy()
        config["LANGUAGE"] = self.language_input.currentData()
        config["X_GAIN"] = self.x_gain_input.value()
        config["Y_GAIN"] = self.y_gain_input.value()
        config["DWELL_TIME"] = self.dwell_time_input.value()
        config["TOGGLE_PAUSE_GESTURE"] = self.pause_gesture_input.currentData()
        config["COMMAND_MENU_GESTURE"] = self.command_gesture_input.currentData()
        config["PAUSE_GESTURE_HOLD_TIME"] = self.pause_hold_input.value()
        config["COMMAND_GESTURE_HOLD_TIME"] = self.command_hold_input.value()
        config["EYE_CLOSED_THRESHOLD"] = self.eye_threshold_input.value()
        config["JAW_OPEN_THRESHOLD"] = self.jaw_threshold_input.value()
        config["SMILE_THRESHOLD"] = self.smile_threshold_input.value()
        config["EYEBROWS_RAISED_THRESHOLD"] = self.brow_threshold_input.value()
        return config

import json
import os
import time

from src.app_paths import get_user_config_path


USER_CONFIG_KEYS = [
    "LANGUAGE",
    "CAMERA_DIGITAL_ZOOM",
    "X_GAIN",
    "Y_GAIN",
    "DWELL_TIME",
    "TOGGLE_PAUSE_GESTURE",
    "COMMAND_MENU_GESTURE",
    "PAUSE_GESTURE_HOLD_TIME",
    "COMMAND_GESTURE_HOLD_TIME",
    "EYE_CLOSED_THRESHOLD",
    "JAW_OPEN_THRESHOLD",
    "SMILE_THRESHOLD",
    "EYEBROWS_RAISED_THRESHOLD",
]


USER_CONFIG_PATH = get_user_config_path()


def build_default_user_config(settings_module=None):
    if settings_module is None:
        from src.config import settings as settings_module

    return {
        key: _json_safe_value(getattr(settings_module, key))
        for key in USER_CONFIG_KEYS
        if hasattr(settings_module, key)
    }


def load_user_config(settings_module=None):
    default_config = build_default_user_config(settings_module)

    if not USER_CONFIG_PATH.exists():
        _save_user_config_if_possible(default_config)
        return default_config.copy()

    try:
        with open(USER_CONFIG_PATH, "r", encoding="utf-8") as file:
            loaded_config = json.load(file)

    except (json.JSONDecodeError, OSError):
        _save_user_config_if_possible(default_config)
        return default_config.copy()

    config = default_config.copy()

    for key in USER_CONFIG_KEYS:
        if key in loaded_config:
            config[key] = loaded_config[key]

    if _needs_save(loaded_config, config):
        _save_user_config_if_possible(config)

    return config


def save_user_config(config):
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    clean_config = {
        key: _json_safe_value(config[key])
        for key in USER_CONFIG_KEYS
        if key in config
    }

    temporary_path = USER_CONFIG_PATH.with_name(
        f"{USER_CONFIG_PATH.stem}.{os.getpid()}.tmp"
    )

    try:
        with open(temporary_path, "w", encoding="utf-8") as file:
            json.dump(
                clean_config,
                file,
                indent=4,
                ensure_ascii=False,
            )

        last_error = None

        for attempt in range(5):
            try:
                os.replace(temporary_path, USER_CONFIG_PATH)
                return

            except PermissionError as error:
                last_error = error
                time.sleep(0.05 * (attempt + 1))

        if last_error is not None:
            raise last_error

    finally:
        try:
            if temporary_path.exists():
                temporary_path.unlink()
        except OSError:
            pass


def apply_user_config_to_settings(settings_module, config):
    for key, value in config.items():
        if key in USER_CONFIG_KEYS:
            setattr(settings_module, key, value)


def load_and_apply_user_config(settings_module):
    config = load_user_config(settings_module)
    apply_user_config_to_settings(settings_module, config)
    return config


def _needs_save(loaded_config, config):
    loaded_keys = set(loaded_config.keys())
    expected_keys = set(config.keys())

    if loaded_keys != expected_keys:
        return True

    for key in expected_keys:
        if _json_safe_value(loaded_config.get(key)) != _json_safe_value(config[key]):
            return True

    return False


def _save_user_config_if_possible(config):
    try:
        save_user_config(config)
    except OSError:
        pass


def _json_safe_value(value):
    return getattr(value, "value", value)

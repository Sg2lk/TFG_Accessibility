from src.platforms.factory import get_platform


APP_DIR_NAME = "TFGAccessibility"


def get_app_data_dir():
    return get_platform().get_app_data_dir(APP_DIR_NAME)


def get_user_config_path():
    return get_app_data_dir() / "user_config.json"


def get_log_file_path():
    return get_app_data_dir() / "logs" / "app.log"

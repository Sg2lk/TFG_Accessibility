from multiprocessing import freeze_support
import logging
import sys

from src.app_logging import setup_logging
from src.platforms.factory import get_platform


_SINGLE_INSTANCE_GUARD = None


def main():
    platform = get_platform()
    platform.enable_dpi_awareness()

    setup_logging()
    logging.getLogger(__name__).info("Application starting")

    from src.app import Application

    app = Application()
    app.run()

    logging.getLogger(__name__).info("Application closed")


def run_with_crash_report():
    try:
        main()

    except Exception as error:
        log_file_path = setup_logging()
        logger = logging.getLogger(__name__)
        logger.exception("Unhandled application error")

        message = (
            "Ha ocurrido un error inesperado y la aplicación debe cerrarse.\n\n"
            f"Detalles: {type(error).__name__}: {error}\n\n"
            "Se ha guardado un informe completo en:\n"
            f"{log_file_path}"
        )

        get_platform().show_error_dialog(
            "TFG Accessibility - Error",
            message,
        )

        sys.exit(1)


if __name__ == "__main__":
    freeze_support()
    setup_logging()
    _SINGLE_INSTANCE_GUARD = get_platform().ensure_single_instance()
    run_with_crash_report()

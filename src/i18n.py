from src.config import settings


TRANSLATIONS = {'en': {'apply': 'Apply',
        'calibrate': 'Calibrate',
        'calibration_face_detected': 'Face detected',
        'calibration_face_missing': 'No face detected',
        'calibration_how_title': 'How to calibrate',
        'calibration_shortcuts': 'Keyboard shortcuts: SPACE = Calibrate   |   ESC = Exit',
        'calibration_status_default': 'Place your face inside the guide',
        'calibration_step_1': '1. Sit comfortably.',
        'calibration_step_2': '2. Keep your head neutral.',
        'calibration_step_3': '3. Place the pointer on the tip of your nose.',
        'calibration_step_4': '4. Press Calibrate.',
        'calibration_title': 'Initial calibration',
        'calibration_window_title': 'Calibration',
        'calibration_zoom_adjusted': 'Camera zoom adjusted',
        'cancel': 'Cancel',
        'close': 'Close',
        'cmd_cancel': 'Cancel',
        'cmd_center_subtitle': 'select with dwell',
        'cmd_center_title': 'COMMAND',
        'cmd_double': 'Double',
        'cmd_drag': 'Drag',
        'cmd_exit': 'Exit',
        'cmd_help': 'Help',
        'cmd_keyboard': 'Keyboard',
        'cmd_right': 'Right',
        'cmd_scroll': 'Scroll',
        'drag_active_subtitle': 'Move cursor, then dwell to release',
        'drag_active_title': 'DRAG ACTIVE',
        'drag_released_subtitle': 'Left button released',
        'drag_released_title': 'DRAG RELEASED',
        'exit': 'Exit',
        'face_missing_subtitle': 'System paused for safety\n'
                                 'Look at the camera again and use {pause_gesture} to resume',
        'face_missing_title': 'FACE NOT DETECTED',
        'gesture_eyebrows': 'Eyebrows raised',
        'gesture_mouth_open': 'Mouth open',
        'gesture_smile': 'Smile',
        'gesture_wink_left': 'Left wink',
        'gesture_wink_right': 'Right wink',
        'keyboard_backspace': 'Backspace',
        'keyboard_enter': 'Enter',
        'keyboard_opened': 'Virtual keyboard opened',
        'keyboard_space': 'Space',
        'keyboard_title': 'Virtual Keyboard',
        'keyboard_title_status': 'KEYBOARD',
        'quick_guide_subtitle': '- Move your head to control the cursor\n'
                                '- Keep the cursor still to left click\n'
                                '- Assigned gesture for command menu: {command_gesture}\n'
                                '- Opening commands locks a target at the last stable position\n'
                                '- Right, Double and Drag act on that target\n'
                                '- {pause_gesture}: start / pause / resume\n'
                                '- Right: right click on the target\n'
                                '- Double: double click on the target\n'
                                '- Scroll: vertical or horizontal scrolling\n'
                                '- Drag: hold left click and release with dwell\n'
                                '- Keyboard: open the virtual keyboard\n'
                                '- Help: show this guide\n'
                                '- Exit: close the application safely\n'
                                '- Cancel: close the command menu',
        'quick_guide_title': 'QUICK GUIDE',
        'scroll_help': 'Move your head up/down to scroll vertically\n'
                       'Move your head left/right to scroll horizontally\n'
                       'Use {command_gesture} to open the command menu and leave scroll mode',
        'settings': 'Settings',
        'settings_brow_threshold': 'Eyebrows threshold',
        'settings_command_gesture': 'Command menu gesture',
        'settings_command_hold': 'Command gesture hold time',
        'settings_dwell_time': 'Dwell click time',
        'settings_eye_threshold': 'Wink threshold',
        'settings_general_group': 'General',
        'settings_gesture_group': 'Gestures',
        'settings_jaw_threshold': 'Mouth open threshold',
        'settings_language': 'Interface language',
        'language_spanish': 'Spanish',
        'language_english': 'English',
        'settings_pause_gesture': 'Pause/resume gesture',
        'settings_pause_hold': 'Pause gesture hold time',
        'settings_smile_threshold': 'Smile threshold',
        'settings_subtitle': 'Adjust the main interaction parameters. Changes are saved for this user.',
        'settings_title': 'User Settings',
        'settings_window_title': 'Accessibility Control Settings',
        'settings_x_gain': 'Horizontal sensitivity',
        'settings_y_gain': 'Vertical sensitivity',
        'state_active_subtitle': 'Control resumed',
        'state_active_title': 'ACTIVE',
        'state_paused_subtitle': '{pause_gesture} to resume',
        'state_paused_title': 'PAUSED',
        'state_scroll_subtitle': 'Move head to scroll. {command_gesture} to open commands and exit.',
        'state_scroll_title': 'SCROLL MODE',
        'zoom_minus': '-',
        'zoom_plus': '+'},
 'es': {'apply': 'Aplicar',
        'calibrate': 'Calibrar',
        'calibration_face_detected': 'Rostro detectado',
        'calibration_face_missing': 'No se detecta rostro',
        'calibration_how_title': 'Como calibrar',
        'calibration_shortcuts': 'Atajos: ESPACIO = Calibrar   |   ESC = Salir',
        'calibration_status_default': 'Coloca tu rostro dentro de la guia',
        'calibration_step_1': '1. Sientate comodamente.',
        'calibration_step_2': '2. Manten la cabeza neutra.',
        'calibration_step_3': '3. Coloca el puntero en la punta de la nariz.',
        'calibration_step_4': '4. Pulsa Calibrar.',
        'calibration_title': 'Calibracion inicial',
        'calibration_window_title': 'Calibracion',
        'calibration_zoom_adjusted': 'Zoom de camara ajustado',
        'cancel': 'Cancelar',
        'close': 'Cerrar',
        'cmd_cancel': 'Cancelar',
        'cmd_center_subtitle': 'elige con permanencia',
        'cmd_center_title': 'COMANDO',
        'cmd_double': 'Doble',
        'cmd_drag': 'Arrastrar',
        'cmd_exit': 'Salir',
        'cmd_help': 'Ayuda',
        'cmd_keyboard': 'Teclado',
        'cmd_right': 'Derecho',
        'cmd_scroll': 'Scroll',
        'drag_active_subtitle': 'Mueve el cursor y mantente quieto para soltar',
        'drag_active_title': 'ARRASTRE ACTIVO',
        'drag_released_subtitle': 'Boton izquierdo liberado',
        'drag_released_title': 'ARRASTRE SOLTADO',
        'exit': 'Salir',
        'face_missing_subtitle': 'Sistema pausado por seguridad\n'
                                 'Mira de nuevo a la camara y usa {pause_gesture} para reanudar',
        'face_missing_title': 'ROSTRO NO DETECTADO',
        'gesture_eyebrows': 'Cejas levantadas',
        'gesture_mouth_open': 'Boca abierta',
        'gesture_smile': 'Sonrisa',
        'gesture_wink_left': 'Guiño izquierdo',
        'gesture_wink_right': 'Guiño derecho',
        'keyboard_backspace': 'Borrar',
        'keyboard_enter': 'Intro',
        'keyboard_opened': 'Teclado virtual abierto',
        'keyboard_space': 'Espacio',
        'keyboard_title': 'Teclado virtual',
        'keyboard_title_status': 'TECLADO',
        'quick_guide_subtitle': '- Mueve la cabeza para controlar el cursor\n'
                                '- Manten el cursor quieto para hacer click izquierdo\n'
                                '- Gesto asignado para abrir el menu de comandos: {command_gesture}\n'
                                '- Al abrir comandos se fija un objetivo en la posicion estable\n'
                                '  Derecho, Doble y Arrastrar actuan sobre ese objetivo\n'
                                '- {pause_gesture}: iniciar / pausar / reanudar\n'
                                '- Derecho: click derecho sobre el objetivo\n'
                                '- Doble: doble click sobre el objetivo\n'
                                '- Scroll: desplazamiento vertical u horizontal\n'
                                '- Arrastrar: mantiene click izquierdo y se suelta por permanencia\n'
                                '- Teclado: abre el teclado virtual\n'
                                '- Ayuda: muestra esta guia\n'
                                '- Salir: cierra la aplicacion de forma segura\n'
                                '- Cancelar: cierra el menu de comandos',
        'quick_guide_title': 'GUIA RAPIDA',
        'scroll_help': 'Mueve la cabeza arriba/abajo para scroll vertical\n'
                       'Mueve la cabeza izquierda/derecha para scroll horizontal\n'
                       'Usa {command_gesture} para abrir el menu de comandos y salir del scroll',
        'settings': 'Configuracion',
        'settings_brow_threshold': 'Umbral de cejas levantadas',
        'settings_command_gesture': 'Gesto para menu de comandos',
        'settings_command_hold': 'Tiempo de mantenimiento del gesto',
        'settings_dwell_time': 'Tiempo para hacer click',
        'settings_eye_threshold': 'Umbral de guiño',
        'settings_general_group': 'General',
        'settings_gesture_group': 'Gestos',
        'settings_jaw_threshold': 'Umbral de boca abierta',
        'settings_language': 'Idioma de la interfaz',
        'language_spanish': 'Español',
        'language_english': 'Inglés',
        'settings_pause_gesture': 'Gesto para pausar/reanudar',
        'settings_pause_hold': 'Tiempo de mantenimiento para pausa',
        'settings_smile_threshold': 'Umbral de sonrisa',
        'settings_subtitle': 'Ajusta los parametros principales de interaccion. Los cambios se guardan para '
                             'este usuario.',
        'settings_title': 'Configuracion de usuario',
        'settings_window_title': 'Configuracion del sistema accesible',
        'settings_x_gain': 'Sensibilidad horizontal',
        'settings_y_gain': 'Sensibilidad vertical',
        'state_active_subtitle': 'Control reanudado',
        'state_active_title': 'ACTIVO',
        'state_paused_subtitle': '{pause_gesture} para reanudar',
        'state_paused_title': 'PAUSADO',
        'state_scroll_subtitle': 'Mueve la cabeza para desplazarte. {command_gesture} para abrir comandos y '
                                 'salir.',
        'state_scroll_title': 'MODO SCROLL',
        'zoom_minus': '-',
        'zoom_plus': '+'}}


GESTURE_TRANSLATION_KEYS = {
    "GESTURE_MOUTH_OPEN": "gesture_mouth_open",
    "GESTURE_WINK_LEFT": "gesture_wink_left",
    "GESTURE_WINK_RIGHT": "gesture_wink_right",
    "GESTURE_EYEBROWS_RAISED": "gesture_eyebrows",
    "GESTURE_SMILE": "gesture_smile",
}


def get_language():
    language = getattr(settings, "LANGUAGE", "en")

    if language not in TRANSLATIONS:
        return "en"

    return language


def t(key, **kwargs):
    language = get_language()
    text = TRANSLATIONS.get(language, {}).get(key)

    if text is None:
        text = TRANSLATIONS["en"].get(key, key)

    if kwargs:
        return text.format(**kwargs)

    return text


def gesture_label(gesture_id):
    value = getattr(gesture_id, "value", gesture_id)
    key = GESTURE_TRANSLATION_KEYS.get(value)

    if key is None:
        return str(value)

    return t(key)

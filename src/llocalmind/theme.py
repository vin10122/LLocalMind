from PySide6.QtGui import QFont, QFontDatabase
from .widgets import ASSETS

STYLE = '''
QMainWindow, QDialog { background: #edf4f8; color: #122c40; }
QWidget { color: #122c40; font-family: 'Manrope'; font-size: 15px; font-weight: 400; }
QFrame#sidebar { background: #122c40; border-radius: 24px; }
QFrame#sidebar QLabel { color: #f5f2eb; background: transparent; }
QLabel#brand { font-family: 'Sora'; font-size: 23px; font-weight: 650; }
QLabel#section { color: #a8c5d9; font-size: 11px; font-weight: 700; letter-spacing: 2px; }
QPushButton { border: 1px solid #becfda; border-radius: 12px; background: #ffffff; padding: 10px 16px; }
QPushButton:hover { background: #dfeaf1; }
QPushButton:disabled { color: #8193a0; }
QPushButton#newChat { background: #f5f2eb; border: none; border-radius: 17px; font-family: 'Sora'; font-weight: 600; font-size: 17px; padding: 16px; }
QPushButton#newChat:hover { background: #e0eaf0; }
QPushButton#sidebarAction { color: #f5f2eb; background: transparent; border: none; text-align: left; padding: 14px 8px; }
QPushButton#sidebarAction:hover { background: #29465c; }
QListWidget#chatList { background: transparent; border: none; outline: none; }
QListWidget#chatList::item { color: #f3f6f8; border-radius: 12px; padding: 14px 10px; margin-bottom: 5px; }
QListWidget#chatList::item:selected { background: #49667d; }
QListWidget#chatList::item:hover:!selected { background: #244257; }
QFrame#localPill { background: #29465c; border-radius: 18px; }
QLabel#heading { font-family: 'Sora'; font-size: 29px; font-weight: 650; }
QLabel#subtitle, QLabel#muted { color: #506d85; }
QFrame#line { background: #b9cfde; border: none; max-height: 1px; }
QFrame#statusPill { background: #ffffff; border-radius: 20px; }
QScrollArea { background: transparent; border: none; }
QWidget#conversation { background: transparent; }
QLabel#userBubble { background: #acc8dc; border-radius: 20px; padding: 18px 22px; font-size: 16px; }
QLabel#assistantName { font-family: 'Sora'; font-size: 18px; font-weight: 600; }
QTextBrowser#markdown { background: transparent; border: none; font-size: 16px; selection-background-color: #b5d6e9; }
QFrame#scheduleCard { background: #ffffff; border-radius: 20px; }
QFrame#cardAccent { background: #7ab8db; border-radius: 2px; }
QLabel#cardTime { font-family: 'Sora'; font-size: 22px; font-weight: 650; }
QPushButton#action { background: transparent; border: none; padding: 8px 2px; color: #375870; }
QPushButton#action:hover { color: #122c40; background: #dce9f1; }
QFrame#composer { background: #ffffff; border: 1px solid #bfd1df; border-radius: 24px; }
QPlainTextEdit#composerInput { background: transparent; border: none; font-size: 17px; padding: 12px 0; }
QToolButton { background: transparent; border: none; border-radius: 14px; padding: 8px; }
QToolButton:hover { background: #e4edf4; }
QToolButton#send { background: #122c40; border-radius: 24px; }
QToolButton#send:hover { background: #294a63; }
QToolButton#send:disabled { background: #71899b; }
QLabel#footer { color: #506d85; font-size: 12px; }
QLabel#responseStats { color: #506d85; font-size: 12px; }
QLabel#notice { background: #e0ebf3; color: #25485f; padding: 12px 16px; border-radius: 12px; }
QLabel#dialogTitle { font-family: 'Sora'; font-size: 20px; font-weight: 600; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #ffffff; border: 1px solid #becfda; border-radius: 9px; padding: 8px; }
QGroupBox { border: 1px solid #becfda; border-radius: 12px; margin-top: 12px; padding-top: 18px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #b6cbd9; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
'''


def apply_theme(application):
    for name in ('Sora-600.ttf','Manrope-400.ttf','Manrope-600.ttf'):
        QFontDatabase.addApplicationFont(str(ASSETS/'fonts'/name))
    application.setFont(QFont('Manrope',11))
    application.setStyleSheet(STYLE)

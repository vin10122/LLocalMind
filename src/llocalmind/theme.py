from PySide6.QtGui import QFont, QFontDatabase
from .widgets import ASSETS

STYLE = '''
QMainWindow, QDialog { background: #edf4f8; color: #122c40; }
QWidget#settingsBody { background: #edf4f8; }
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
QPushButton#sidebarAction, QPushButton#languageButton { color: #f5f2eb; background: transparent; border: none; text-align: left; padding: 14px 8px; }
QPushButton#sidebarAction:hover, QPushButton#languageButton:hover { background: #29465c; }
QPushButton#webSearch { padding: 10px 12px; }
QPushButton#webSearch:checked { background: #d3e6f2; border-color: #6d9bb6; }
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
QFrame#responseWidget { background: #ffffff; border: 1px solid #bfd1df; border-radius: 18px; }
QFrame#widgetTable { background: transparent; }
QLabel#widgetHeading { font-family: 'Sora'; font-weight: 600; }
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


ITALIAN_STYLE = """
QMainWindow, QDialog { background: #e1f0ff; }
QWidget#settingsBody { background: #e1f0ff; }
QFrame#sidebar { background: #175b96; }
QFrame#localPill { background: #2871ad; }
QPushButton#sidebarAction:hover, QPushButton#languageButton:hover { background: #2871ad; }
QListWidget#chatList::item:selected { background: #3680ba; }
QListWidget#chatList::item:hover:!selected { background: #286da5; }
QPushButton#newChat { background: #ffffff; color: #175b96; }
QLabel#heading, QLabel#assistantName { color: #124e82; }
QLabel#userBubble { background: #e4f2ff; color: #123b60; border-radius: 16px; }
QFrame#composer { background: #f8fcff; border-color: #9bc7eb; }
QFrame#line { background: #abd0ef; }
QFrame#statusPill, QFrame#scheduleCard { background: #f8fcff; }
QFrame#cardAccent { background: #64ace0; }
QPushButton#webSearch { background: #edf7ff; border-color: #a2c9e6; }
QPushButton#webSearch:checked { background: #badcfa; }
QToolButton#send { background: #198455; color: #ffffff; border-radius: 18px; font-weight: 600; font-size: 15px; padding: 8px 12px; }
QToolButton#send:hover { background: #126b44; }
QToolButton#send[stopping="true"] { background: #c93848; }
QToolButton#send[stopping="true"]:hover { background: #ac2839; }
QToolButton#send:disabled { background: #7395b2; color: #f6faff; }
QFrame#tricolorBar { border: none; border-radius: 3px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #16955a,stop:0.3333 #16955a,stop:0.3334 #ffffff,stop:0.6666 #ffffff,stop:0.6667 #d83b48,stop:1 #d83b48); }
"""


DARK_STYLE = """
QMainWindow, QDialog { background: #000000; color: #e7f3eb; }
QWidget#settingsBody { background: #000000; }
QWidget { color: #e7f3eb; }
QFrame#sidebar { background: #103b29; }
QFrame#sidebar QLabel { color: #e7f3eb; }
QLabel#section, QLabel#subtitle, QLabel#muted, QLabel#footer, QLabel#responseStats { color: #a7c5b2; }
QLabel#heading, QLabel#assistantName { color: #f0f8f3; }
QPushButton { background: #13251b; border-color: #345b43; color: #e7f3eb; }
QPushButton:hover { background: #214b34; }
QPushButton:disabled { color: #789785; border-color: #263d2f; }
QPushButton#newChat { background: #1c5638; color: #f0f8f3; }
QPushButton#newChat:hover { background: #286d48; }
QPushButton#webSearch { background: #13251b; border-color: #345b43; color: #e7f3eb; }
QPushButton#webSearch:checked { background: #286044; border-color: #79ba91; }
QPushButton#webSearch:disabled { color: #789785; }
QPushButton#sidebarAction:hover, QPushButton#languageButton:hover { background: #20533a; }
QListWidget#chatList::item:selected { background: #286044; }
QListWidget#chatList { background: transparent; border: none; outline: none; }
QPushButton#sidebarAction, QPushButton#languageButton { background: transparent; border: none; color: #e7f3eb; }
QListWidget#chatList::item:hover:!selected { background: #1b4b33; }
QFrame#localPill { background: #1b4b33; }
QFrame#line { background: #294b36; }
QFrame#statusPill, QFrame#scheduleCard { background: #102017; }
QFrame#responseWidget { background: #102017; border-color: #345b43; }
QLabel#userBubble { background: #153d2b; color: #eff8f2; }
QTextEdit, QPlainTextEdit, QTextBrowser { background: #101e16; color: #e7f3eb; border: 1px solid #345b43; selection-background-color: #315f43; }
QTextBrowser#markdown { background: transparent; border: none; color: #e7f3eb; selection-background-color: #315f43; }
QFrame#cardAccent { background: #78c99b; }
QPushButton#action { color: #a7d8ba; background: transparent; }
QPushButton#action:hover { color: #ffffff; background: #163624; }
QFrame#composer { background: #0c1710; border-color: #31583f; }
QPlainTextEdit#composerInput { background: transparent; border: none; color: #edf7f0; selection-background-color: #315f43; }
QToolButton:hover { background: #214b34; }
QToolButton#send { background: #22613f; color: #ffffff; }
QToolButton#send:hover { background: #2c8052; }
QToolButton#send:disabled { background: #264b35; }
QLabel#notice { background: #152e20; color: #d0e7d8; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #101e16; color: #e7f3eb; border-color: #345b43; selection-background-color: #315f43; }
QAbstractItemView, QMenu { background: #101e16; color: #e7f3eb; border: 1px solid #345b43; selection-background-color: #286044; }
QComboBox::drop-down { background: transparent; border: none; }
QMenu::item:selected { background: #286044; }
QGroupBox { border-color: #345b43; }
QProgressBar { background: #101e16; color: #e7f3eb; border: 1px solid #345b43; border-radius: 6px; text-align: center; }
QProgressBar::chunk { background: #43855b; border-radius: 5px; }
QScrollBar::handle:vertical { background: #3d6c4e; }
QToolTip { background: #14291c; color: #e7f3eb; border: 1px solid #416c50; padding: 5px; }
"""

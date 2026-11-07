"""Reusable Qt widgets matching the approved LLocalMind design."""
from pathlib import Path
import re
from PySide6.QtCore import Qt, QSize, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontMetrics, QIcon, QPainter, QPixmap, QTextDocument
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QSizePolicy, QTextBrowser, QToolButton, QVBoxLayout)
from .metrics import clean_stats, response_summary
from .images import image_path

ASSETS = Path(__file__).with_name('assets')
NAVY = '#122c40'
PATHS = {
    'plus':'<path d="M12 5v14M5 12h14"/>',
    'chat':'<path d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-5 4v-4a2 2 0 0 1-2-2V6a2 2 0 0 1 3-2Z"/>',
    'send':'<path d="m5 11 7-7 7 7M12 4v16"/>',
    'stop':'<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor"/>',
    'copy':'<rect x="8" y="7" width="12" height="14" rx="2"/><path d="M16 7V3H4v14h4"/>',
    'reload':'<path d="M20 8a8 8 0 1 0 0 8M20 3v5h-5"/>',
    'clip':'<path d="m8 13 7-7a3 3 0 0 1 4 4L9 20a5 5 0 0 1-7-7L13 2M6 15l9-9"/>',
    'settings':'<path d="m10 2-1 3-3 1-3-1-2 4 2 2v3l-2 2 2 4 3-1 3 1 1 3h4l1-3 3-1 3 1 2-4-2-2v-3l2-2-2-4-3 1-3-1-1-3Z"/><circle cx="12" cy="12" r="3"/>',
}


def icon(name, color=NAVY, size=24):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" color="{color}" stroke-width="1.7" stroke-linecap="round" '
           f'stroke-linejoin="round">{PATHS[name]}</svg>').encode()
    image = QPixmap(size*2, size*2)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    QSvgRenderer(svg).render(painter)
    painter.end()
    image.setDevicePixelRatio(2)
    return QIcon(image)


def logo_label(size):
    label = QLabel()
    label.setFixedSize(size,size)
    label.setPixmap(QPixmap(str(ASSETS/'logo.png')).scaled(size,size,Qt.AspectRatioMode.KeepAspectRatio,
                                                        Qt.TransformationMode.SmoothTransformation))
    return label


def action(text, image, *, color=NAVY, name='action'):
    button = QPushButton(text)
    button.setObjectName(name)
    button.setIcon(icon(image,color))
    button.setIconSize(QSize(21,21))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def schedule_parts(text):
    """Only turn a simple complete time list into cards, preserving its text."""
    if '```' in text:
        return None
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    start = next((i for i,line in enumerate(lines) if re.match(r'^(?:[-*]\s*)?\d{1,2}:\d{2}\s*[—–-]',line)),None)
    if start is None:
        return None
    entries=[]
    for line in lines[start:]:
        match=re.fullmatch(r'(?:[-*]\s*)?(\d{1,2}:\d{2})\s*[—–-]\s*(.+)',line)
        if not match:
            return None
        hour,minute=map(int,match[1].split(':'))
        if hour>23 or minute>59:
            return None
        entries.append((match[1],match[2]))
    return ('\n\n'.join(lines[:start]),entries) if 2<=len(entries)<=4 else None


class TextDocument(QTextDocument):
    def loadResource(self,kind,name):
        # Model output cannot load remote or local images into the chat.
        return None


class Markdown(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setDocument(TextDocument(self))
        self.setObjectName('markdown')
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.open_link)
        self.document().setDocumentMargin(0)
        self.document().contentsChanged.connect(self.fit)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)

    def setMarkdown(self,text):
        self.document().setMarkdown(text, QTextDocument.MarkdownFeature.MarkdownDialectGitHub
                                    | QTextDocument.MarkdownFeature.MarkdownNoHTML)

    @staticmethod
    def open_link(url):
        if url.scheme() in ('https','http'):
            QDesktopServices.openUrl(url)

    def fit(self):
        self.document().setTextWidth(max(80,self.viewport().width()))
        self.setFixedHeight(max(32,int(self.document().size().height())+8))

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.fit()


class Message(QFrame):
    copy_requested=Signal(str)
    regenerate_requested=Signal()

    def __init__(self,role,text='',pending=False,stats=None,*,images=None,directory=None):
        super().__init__()
        self.role=role
        self.text=text
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,12,0,12)
        if role=='user':
            row=QHBoxLayout()
            row.addStretch()
            self.bubble=QLabel()
            self.bubble.setObjectName('userBubble')
            self.bubble.setWordWrap(True)
            self.bubble.setTextFormat(Qt.TextFormat.PlainText)
            self.bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.bubble.setMaximumWidth(720)
            row.addWidget(self.bubble)
            layout.addLayout(row)
            for item in images or []:
                image_row=QHBoxLayout()
                image_row.addStretch()
                preview=QLabel()
                preview.setTextFormat(Qt.TextFormat.PlainText)
                pixmap=QPixmap(str(image_path(directory,item)))
                if pixmap.isNull():preview.setText('Immagine non disponibile: '+item['name'])
                else:preview.setPixmap(pixmap.scaled(200,140,Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
                preview.setToolTip(item['name'])
                image_row.addWidget(preview)
                layout.addLayout(image_row)
        else:
            heading=QHBoxLayout()
            heading.setSpacing(10)
            heading.addWidget(logo_label(38))
            label=QLabel('LLocalMind')
            label.setObjectName('assistantName')
            heading.addWidget(label)
            heading.addStretch()
            layout.addLayout(heading)
            content=QFrame()
            column=QVBoxLayout(content)
            column.setContentsMargins(49,3,0,0)
            column.setSpacing(14)
            self.body=Markdown()
            column.addWidget(self.body)
            self.cards=QFrame()
            self.cards_layout=QHBoxLayout(self.cards)
            self.cards_layout.setContentsMargins(0,0,0,0)
            self.cards_layout.setSpacing(14)
            column.addWidget(self.cards)
            row=QHBoxLayout()
            row.setSpacing(14)
            self.copy_button=action('Copia','copy')
            self.regenerate_button=action('Rigenera','reload')
            self.copy_button.clicked.connect(lambda:self.copy_requested.emit(self.text))
            self.regenerate_button.clicked.connect(self.regenerate_requested)
            row.addWidget(self.copy_button)
            row.addWidget(self.regenerate_button)
            row.addStretch()
            self.metrics_label=QLabel()
            self.metrics_label.setObjectName('responseStats')
            self.metrics_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(self.metrics_label)
            column.addLayout(row)
            layout.addWidget(content)
        self.update_text(text,pending=pending)
        self.set_stats(stats)

    def set_stats(self,value):
        if self.role!='assistant':
            return
        stats=clean_stats(value)
        text=response_summary(stats)
        self.metrics_label.setText(text)
        self.metrics_label.setVisible(bool(text))
        tooltip='Media della generazione dopo il primo token; elaborazione del prompt esclusa.'
        if stats and stats['rate'] is None:
            tooltip='Servono almeno due token e un tempo di generazione valido per misurare i tok/s.'
        if stats and stats['interrupted']:
            tooltip+=' Generazione interrotta.'
        self.metrics_label.setToolTip(tooltip)

    def update_text(self,text,pending=False):
        self.text=text
        if self.role=='user':
            self.bubble.setText(text)
            widest=max(text.splitlines() or [''],key=len)
            self.bubble.setMinimumWidth(min(580,max(480,QFontMetrics(self.bubble.font()).horizontalAdvance(widest)+44)))
            return
        self.copy_button.setEnabled(bool(text) and not pending)
        self.regenerate_button.setEnabled(not pending)
        while self.cards_layout.count():
            self.cards_layout.takeAt(0).widget().deleteLater()
        parsed=schedule_parts(text) if not pending else None
        self.cards.setVisible(parsed is not None)
        if parsed:
            intro,entries=parsed
            self.body.setMarkdown(intro)
            self.body.setVisible(bool(intro))
            for at,title in entries:
                card=QFrame()
                card.setObjectName('scheduleCard')
                row=QHBoxLayout(card)
                row.setContentsMargins(18,18,16,18)
                stripe=QFrame()
                stripe.setObjectName('cardAccent')
                stripe.setFixedWidth(5)
                row.addWidget(stripe)
                col=QVBoxLayout()
                time_label=QLabel(at)
                time_label.setObjectName('cardTime')
                col.addWidget(time_label)
                title_label=QLabel(title)
                title_label.setTextFormat(Qt.TextFormat.PlainText)
                title_label.setWordWrap(True)
                col.addWidget(title_label)
                row.addLayout(col,1)
                self.cards_layout.addWidget(card,1)
        else:
            self.body.setVisible(True)
            # Model text is markdown; disable raw HTML and file URLs in Qt.
            self.body.setMarkdown(text or ('Elaborazione del prompt…' if pending else 'Risposta non completata.'))
        self.body.fit()


class Composer(QPlainTextEdit):
    submitted=Signal()

    def __init__(self):
        super().__init__()
        self.setPlaceholderText('Da dove iniziamo?')
        self.setObjectName('composerInput')
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(54)
        self.blockCountChanged.connect(lambda count:self.setFixedHeight(min(120,max(54,count*24+16))))
        self.setTabChangesFocus(True)

    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.submitted.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

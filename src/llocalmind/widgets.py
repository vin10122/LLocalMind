"""Reusable Qt widgets matching the approved LLocalMind design."""
from .i18n import tr
from pathlib import Path
import re
from PySide6.QtCore import Qt, QSize, QUrl, Signal, QRectF
from PySide6.QtGui import QDesktopServices, QFontMetrics, QIcon, QPainter, QPixmap, QTextDocument, QColor, QLinearGradient, QPainterPath, QPen
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QSizePolicy, QTextBrowser, QToolButton, QVBoxLayout)
from .metrics import clean_stats, response_summary
from .images import image_path

ASSETS = Path(__file__).with_name('assets')
NAVY = '#122c40'
PATHS = {
    'globe':'<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
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


class ThemeSwitch(QCheckBox):
    """Keyboard-accessible native checkbox, painted as a sliding switch."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setObjectName('italianInterfaceSwitch')
        self.setFixedSize(52,30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Italian Interface 🇮🇹')

    def hitButton(self,position):
        return self.rect().contains(position)

    def paintEvent(self,event):
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#278a61' if self.isChecked() else '#698497'))
        painter.drawRoundedRect(QRectF(2,3,48,24),12,12)
        painter.setBrush(QColor('#ffffff'))
        painter.drawEllipse(QRectF(28 if self.isChecked() else 5,6,18,18))
        if self.hasFocus():
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor('#9bd7ff'),1.5))
            painter.drawRoundedRect(QRectF(1,1,50,28),14,14)


class PromptFrame(QFrame):
    """Paint a six-pixel tricolour border, leaving the interior solid blue."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.italian_interface=False
        self.setObjectName('promptFrame')
        self.setMaximumWidth(732)
        self.content=QVBoxLayout(self)
        self.content.setSpacing(0)
        self.content.setContentsMargins(0,0,0,0)

    def set_italian_interface(self,enabled):
        self.italian_interface=bool(enabled)
        self.setMaximumWidth(732 if enabled else 720)
        border=6 if enabled else 0
        self.content.setContentsMargins(border,border,border,border)
        self.updateGeometry()
        self.update()

    def paintEvent(self,event):
        if not self.italian_interface:
            return super().paintEvent(event)
        painter=QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient=QLinearGradient(0,0,self.width(),0)
        for position,color in ((0,'#16955a'),(.3333,'#16955a'),(.3334,'#ffffff'),
                               (.6666,'#ffffff'),(.6667,'#d83b48'),(1,'#d83b48')):
            gradient.setColorAt(position,QColor(color))
        outer=QPainterPath();outer.addRoundedRect(QRectF(self.rect()),22,22)
        painter.fillPath(outer,gradient)
        inner=QPainterPath();inner.addRoundedRect(QRectF(self.rect()).adjusted(6,6,-6,-6),16,16)
        painter.fillPath(inner,QColor('#e4f2ff'))


class Message(QFrame):
    copy_requested=Signal(str)
    regenerate_requested=Signal()

    def __init__(self,role,text='',pending=False,stats=None,*,images=None,directory=None,
                 web_search=False,italian_interface=False):
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
            self.prompt_frame=PromptFrame()
            self.prompt_frame.content.addWidget(self.bubble)
            self.prompt_frame.set_italian_interface(italian_interface)
            row.addWidget(self.prompt_frame)
            layout.addLayout(row)
            for item in images or []:
                image_row=QHBoxLayout()
                image_row.addStretch()
                preview=QLabel()
                preview.setTextFormat(Qt.TextFormat.PlainText)
                pixmap=QPixmap(str(image_path(directory,item)))
                if pixmap.isNull():preview.setText(tr('Immagine non disponibile: ')+item['name'])
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
            self.copy_button=action(tr('Copia'),'copy')
            self.regenerate_button=action(tr('Rigenera'),'reload')
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
        if role=='user' and web_search:
            self.bubble.setText(tr('Ricerca web · DuckDuckGo\n\n')+text)
        self.set_stats(stats)

    def set_stats(self,value):
        if self.role!='assistant':
            return
        stats=clean_stats(value)
        text=response_summary(stats)
        self.metrics_label.setText(text)
        self.metrics_label.setVisible(bool(text))
        tooltip=tr('Media della generazione dopo il primo token; elaborazione del prompt esclusa.')
        if stats and stats['rate'] is None:
            tooltip=tr('Servono almeno due token e un tempo di generazione valido per misurare i tok/s.')
        if stats and stats['interrupted']:
            tooltip+=tr(' Generazione interrotta.')
        if stats and stats.get('prefill') is not None:
            tooltip+=tr('\nElaborazione prompt: {seconds:.2f} s.',seconds=stats['prefill'])
        if stats and stats.get('prompt_tokens') is not None:
            tooltip+=tr('\nPrompt: {count} token; cache: {cached}.',count=stats['prompt_tokens'],cached=stats.get('cached_tokens','n/a'))
        if stats and stats.get('encoder_device'):
            tooltip+=tr('\nEncoder immagini: ')+stats['encoder_device']+tr('; modello linguistico: CPU.')
        if stats and stats.get('image_max_tokens') is not None:
            tooltip+=tr('\nLimite per immagine: {count} token visivi.',count=stats['image_max_tokens'])
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
            self.body.setMarkdown(text or (tr('Elaborazione del prompt…') if pending else tr('Risposta non completata.')))
        self.body.fit()


class Composer(QPlainTextEdit):
    submitted=Signal()

    def __init__(self):
        super().__init__()
        self.setPlaceholderText(tr('Da dove iniziamo?'))
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

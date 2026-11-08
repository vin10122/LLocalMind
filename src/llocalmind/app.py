"""LLocalMind desktop chat, based on the approved rounded blue mockup."""
from __future__ import annotations
from .i18n import tr, set_language, language

import argparse
import copy
from pathlib import Path
import sys
import tempfile
import threading

from PySide6.QtCore import Qt, QSize, QThread, QTimer, Signal, Slot, QUrl
from PySide6.QtGui import QIcon, QDesktopServices
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

from .inference import ModelWorker
from .images import MAX_IMAGES,import_image
from .metrics import clean_stats, response_summary
from .settings_dialog import SettingsDialog
from .state import LocalState, new_chat, engine_signature
from .theme import apply_theme, ITALIAN_STYLE, DARK_STYLE
from .update_worker import UpdateTask
from .updater import UpdateManager
from .widgets import ASSETS, Composer, Message, ThemeSwitch, action, icon, logo_label


def number(value,places=1):
    text=f'{value:.{places}f}'
    return text if language()=='en' else text.replace('.',',')


class UpdateProgress(QDialog):
    def __init__(self,kind,cancel,parent):
        super().__init__(parent)
        self.cancel=cancel
        self.setWindowTitle(tr('Motore llama.cpp') if kind=='runtime' else tr('Aggiornamenti LLocalMind'))
        self.setMinimumWidth(380)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(24,24,24,24)
        layout.setSpacing(16)
        self.label=QLabel(tr('Installazione motore vision…') if kind=='runtime' else
                         tr('Controllo aggiornamenti…') if kind=='check' else tr('Download aggiornamento…'))
        layout.addWidget(self.label)
        self.bar=QProgressBar()
        self.bar.setRange(0,0 if kind=='check' else 100)
        layout.addWidget(self.bar)
        button=QPushButton(tr('Annulla'))
        button.clicked.connect(self.reject)
        layout.addWidget(button)

    def reject(self):
        self.cancel.set()
        super().reject()


class MainWindow(QMainWindow):
    load_requested=Signal(str,dict)
    generate_requested=Signal(list,dict)
    shutdown_requested=Signal()

    def __init__(self,*,state=None,demo=False,worker_factory=ModelWorker):
        super().__init__()
        self.demo=demo
        self.state=state or LocalState()
        set_language(self.state.settings['language'])
        self.current_id=self.state.chats[0]['id']
        self.busy=False
        self.ready=False
        self.loading=False
        self._closing=False
        self._allow_close=False
        self._model_thread_done=False
        self._pending_update=None
        self._update_jobs=[]
        self._vision_install_draft=None
        self._loaded_options=None
        self._message_widgets=[]
        self._active_reply=None
        self._pending_images=[]
        self._stop=threading.Event()
        self.setWindowTitle('LLocalMind' + (tr(' · Anteprima') if demo else ''))
        self.setWindowIcon(QIcon(str(ASSETS/'logo.png')))
        self.resize(1400,900)
        self.setMinimumSize(1024,700)
        self._build()
        self._thread=QThread(self)
        self._worker=worker_factory(self._stop)
        self._worker.moveToThread(self._thread)
        self.load_requested.connect(self._worker.load)
        self.generate_requested.connect(self._worker.generate)
        self.shutdown_requested.connect(self._worker.shutdown)
        self._worker.progress.connect(self._progress,Qt.ConnectionType.QueuedConnection)
        self._worker.loaded.connect(self._loaded,Qt.ConnectionType.QueuedConnection)
        self._worker.token.connect(self._token,Qt.ConnectionType.QueuedConnection)
        self._worker.stats.connect(self._stats,Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self._error,Qt.ConnectionType.QueuedConnection)
        self._worker.search_status.connect(self._search_progress,Qt.ConnectionType.QueuedConnection)
        self._worker.reply_finished.connect(self._reply_finished,Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._worker_finished)
        self._thread.start()
        self._timer=QTimer(self)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._animate)
        self._render_timer=QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(40)
        self._render_timer.timeout.connect(self._flush_reply)
        self._dot=0
        self._phase=''
        if demo:
            self._seed_demo()
        self._refresh_list()
        self._render()
        self._buttons()
        if self.state.warning:
            self._notice(self.state.warning)
        if not demo and self.state.settings['model_path']:
            QTimer.singleShot(100,self.load_model)

    @property
    def current(self):
        return next(c for c in self.state.chats if c['id']==self.current_id)

    def _build(self):
        root=QWidget()
        self.setCentralWidget(root)
        row=QHBoxLayout(root)
        row.setContentsMargins(16,16,20,16)
        row.setSpacing(26)
        sidebar=QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(278)
        side=QVBoxLayout(sidebar)
        side.setContentsMargins(20,22,20,18)
        side.setSpacing(18)
        brand=QHBoxLayout()
        brand.setSpacing(8)
        brand.addWidget(logo_label(58))
        label=QLabel('LLocalMind')
        label.setObjectName('brand')
        brand.addWidget(label)
        brand.addStretch()
        side.addLayout(brand)
        side.addSpacing(12)
        self.new_button=action(tr('Nuova chat'),'plus',name='newChat')
        self.new_button.clicked.connect(self.new_conversation)
        side.addWidget(self.new_button)
        side.addSpacing(4)
        section=QLabel(tr('LE TUE CHAT'))
        section.setObjectName('section')
        side.addWidget(section)
        self.chat_list=QListWidget()
        self.chat_list.setObjectName('chatList')
        self.chat_list.setIconSize(QSize(22,22))
        self.chat_list.currentRowChanged.connect(self._select)
        self.chat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self._chat_menu)
        side.addWidget(self.chat_list,1)
        pill=QFrame()
        pill.setObjectName('localPill')
        pill_row=QHBoxLayout(pill)
        pill_row.setContentsMargins(16,12,12,12)
        dot=QLabel('●')
        dot.setStyleSheet('color: #51b86b;')
        pill_row.addWidget(dot)
        pill_row.addWidget(QLabel(tr('Tutto sul tuo PC')))
        pill_row.addStretch()
        side.addWidget(pill)
        theme_row=QHBoxLayout()
        theme_label=QLabel('Italian Interface 🇮🇹')
        self.theme_switch=ThemeSwitch()
        theme_label.setBuddy(self.theme_switch)
        self.theme_switch.setChecked(self.state.settings['italian_interface'])
        self.theme_switch.toggled.connect(self.set_italian_interface)
        theme_row.addWidget(theme_label)
        theme_row.addStretch()
        theme_row.addWidget(self.theme_switch)
        side.addLayout(theme_row)
        self.language_button=action(tr('Lingua / Language'),'globe',color='#f5f2eb',name='sidebarAction')
        self.language_button.setObjectName('languageButton')
        self.language_button.clicked.connect(self.choose_language)
        side.addWidget(self.language_button)
        settings=action(tr('Impostazioni'),'settings',color='#f5f2eb',name='sidebarAction')
        settings.clicked.connect(self.settings)
        side.addWidget(settings)
        row.addWidget(sidebar)
        main=QVBoxLayout()
        main.setContentsMargins(0,8,0,4)
        main.setSpacing(14)
        self.tricolor_bar=QFrame()
        self.tricolor_bar.setObjectName('tricolorBar')
        self.tricolor_bar.setFixedHeight(6)
        main.addWidget(self.tricolor_bar)
        heading=QHBoxLayout()
        title_col=QVBoxLayout()
        title=QLabel(tr('Il tuo spazio per pensare'))
        title.setObjectName('heading')
        title_col.addWidget(title)
        self.subtitle=QLabel(tr('Scegli un modello GGUF nelle impostazioni'))
        self.subtitle.setObjectName('subtitle')
        self.subtitle.setWordWrap(True)
        title_col.addWidget(self.subtitle)
        heading.addLayout(title_col,1)
        status=QFrame()
        status.setObjectName('statusPill')
        status_row=QHBoxLayout(status)
        status_row.setContentsMargins(16,10,16,10)
        self.status_dot=QLabel('●')
        self.status_label=QLabel()
        status_row.addWidget(self.status_dot)
        status_row.addWidget(self.status_label)
        heading.addWidget(status,0,Qt.AlignmentFlag.AlignTop)
        main.addLayout(heading)
        self._set_status(tr('Non caricato'),'idle')
        main.addWidget(self._line())
        self.notice=QLabel()
        self.notice.setTextFormat(Qt.TextFormat.PlainText)
        self.notice.setWordWrap(True)
        self.notice.setObjectName('notice')
        self.notice.hide()
        main.addWidget(self.notice)
        self.scroll=QScrollArea()
        self.scroll.setWidgetResizable(True)
        content=QWidget()
        content.setObjectName('conversation')
        self.messages=QVBoxLayout(content)
        self.messages.setContentsMargins(0,0,4,8)
        self.messages.setSpacing(8)
        self.messages.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(content)
        main.addWidget(self.scroll,1)
        self.scroll.verticalScrollBar().rangeChanged.connect(self._scroll_to_bottom)
        self.vision_controls=QWidget()
        vision_row=QHBoxLayout(self.vision_controls)
        vision_row.setContentsMargins(0,0,0,0)
        vision_row.addWidget(QLabel(tr('Immagini')))
        self.vision_quality=QComboBox()
        self.vision_quality.setObjectName('visionQuality')
        self.vision_quality.addItem(tr('Dettagliata · testo piccolo'),'detail')
        self.vision_quality.addItem(tr('Rapida · panoramica'),'fast')
        self.vision_quality.setCurrentIndex(self.vision_quality.findData(self.state.settings['vision_image_profile']))
        self.vision_quality.setToolTip(tr('Rapida riduce i dettagli per elaborare meno pixel. Usa Dettagliata per scritte piccole, grafici e documenti. Gli originali sono conservati.'))
        self.vision_quality.currentIndexChanged.connect(self._image_profile_changed)
        vision_row.addWidget(self.vision_quality)
        vision_row.addStretch()
        main.addWidget(self.vision_controls)
        composer=QFrame()
        composer.setObjectName('composer')
        compose=QHBoxLayout(composer)
        compose.setContentsMargins(14,12,14,12)
        compose.setSpacing(12)
        self.attach=QToolButton()
        self.attach.setIcon(icon('clip'))
        self.attach.setIconSize(QSize(26,26))
        self.attach.setToolTip(tr('Allega testo o immagini locali'))
        self.attach.clicked.connect(self.attach_text)
        compose.addWidget(self.attach)
        self.web_search_button=QPushButton(tr('Ricerca web'))
        self.web_search_button.setObjectName('webSearch')
        self.web_search_button.setCheckable(True)
        self.web_search_button.setToolTip(
            tr('Facoltativa e disattivata di default. Invia solo la domanda a Tavily, '
               'usando la chiave nel tuo file .env. La ricerca usa crediti Tavily; la risposta viene generata sul PC.'))
        compose.addWidget(self.web_search_button)
        self.input=Composer()
        self.input.submitted.connect(self.send)
        compose.addWidget(self.input,1)
        self.send_button=QToolButton()
        self.send_button.setObjectName('send')
        self.send_button.setFixedSize(48,48)
        self.send_button.setIconSize(QSize(26,26))
        self.send_button.clicked.connect(self.send_or_stop)
        compose.addWidget(self.send_button)
        self.attachments=QWidget()
        attachment_row=QHBoxLayout(self.attachments)
        attachment_row.setContentsMargins(0,0,0,0)
        self.attachment_names=QLabel()
        self.attachment_names.setTextFormat(Qt.TextFormat.PlainText)
        self.attachment_names.setWordWrap(True)
        attachment_row.addWidget(self.attachment_names,1)
        clear=QPushButton(tr('Rimuovi immagini'))
        clear.clicked.connect(self._clear_images)
        attachment_row.addWidget(clear)
        self.attachments.hide()
        main.addWidget(self.attachments)
        main.addWidget(composer)
        main.addWidget(self._line())
        footer=QHBoxLayout()
        label=QLabel(tr('Elaborazione locale'))
        label.setObjectName('footer')
        footer.addWidget(label)
        footer.addStretch()
        self.stats_label=QLabel('')
        self.stats_label.setObjectName('footer')
        footer.addWidget(self.stats_label)
        main.addLayout(footer)
        row.addLayout(main,1)
        self._apply_interface_style()

    def _apply_interface_style(self):
        enabled=self.state.settings['italian_interface']
        dark=self.state.settings['dark_mode']
        self.setStyleSheet((ITALIAN_STYLE if enabled else '')+(DARK_STYLE if dark else ''))
        foreground='#d3eddc' if dark else '#122c40'
        self.new_button.setIcon(icon('plus',foreground))
        self.attach.setIcon(icon('clip',foreground))
        self.tricolor_bar.setVisible(enabled)

    def set_italian_interface(self,enabled):
        if self._closing:return
        try:self.state.save_settings(dict(self.state.settings,italian_interface=bool(enabled)))
        except (OSError,ValueError) as error:
            self.theme_switch.blockSignals(True)
            self.theme_switch.setChecked(self.state.settings['italian_interface'])
            self.theme_switch.blockSignals(False)
            self._notice(str(error))
            return
        self._apply_interface_style()
        for widget in self._message_widgets:
            if widget.role=='user':widget.prompt_frame.set_italian_interface(enabled)
        self._buttons()

    @staticmethod
    def _line():
        line=QFrame()
        line.setObjectName('line')
        line.setFixedHeight(1)
        return line

    def _set_status(self,text,kind='ready'):
        self.status_label.setText(text)
        colors={'ready':'#50b76b','busy':'#76afd0','idle':'#a7b5bf','error':'#c88550'}
        self.status_dot.setStyleSheet('color: '+colors[kind]+';')

    def _image_profile_changed(self):
        if self.busy or self.loading or self._closing:return
        previous=self.state.settings['vision_image_profile']
        try:self.state.save_settings(dict(self.state.settings,vision_image_profile=self.vision_quality.currentData()))
        except (OSError,ValueError) as error:
            self.vision_quality.blockSignals(True)
            self.vision_quality.setCurrentIndex(self.vision_quality.findData(previous))
            self.vision_quality.blockSignals(False)
            self._notice(str(error))

    def _buttons(self):
        blocked=self.busy or self.loading or self._closing
        self.vision_controls.setVisible(self.state.settings['engine']=='vision')
        self.vision_quality.setEnabled(not blocked)
        self.web_search_button.setVisible(True)
        self.language_button.setEnabled(not blocked)
        self.new_button.setEnabled(not blocked)
        self.chat_list.setEnabled(not blocked)
        self.attach.setEnabled(not blocked)
        self.web_search_button.setEnabled(
            not blocked and not self.demo)
        self.attachments.setEnabled(not blocked)
        self.input.setReadOnly(blocked)
        self.send_button.setEnabled(self.demo or self.busy or (self.ready and not blocked))
        self.theme_switch.setEnabled(not self._closing)
        self.send_button.setProperty('stopping',self.busy)
        if self.state.settings['italian_interface']:
            self.send_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            self.send_button.setFixedSize(236,54)
            self.send_button.setText('Fratello, fermati 🍝' if self.busy else 'Dottore, parti 🍕')
        else:
            self.send_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            self.send_button.setFixedSize(48,48)
            self.send_button.setText('')
            self.send_button.setIcon(icon('stop' if self.busy else 'send','#f5f2eb'))
        self.send_button.style().unpolish(self.send_button)
        self.send_button.style().polish(self.send_button)
        self.send_button.setToolTip(tr('Interrompi') if self.busy else tr('Invia · Maiusc+Invio per andare a capo'))
        assistants=[w for w in self._message_widgets if w.role=='assistant']
        for widget in assistants:
            widget.regenerate_button.setEnabled(not blocked and self.ready and widget is assistants[-1])

    def _refresh_list(self):
        self.chat_list.blockSignals(True)
        self.chat_list.clear()
        for index,chat in enumerate(self.state.chats):
            title=tr('Nuova conversazione') if not chat['messages'] and chat['title'] in ('Nuova conversazione','New conversation') else chat['title']
            item=QListWidgetItem(icon('chat','#eaf1f6'),title)
            item.setToolTip(chat['title'])
            self.chat_list.addItem(item)
            if chat['id']==self.current_id:
                self.chat_list.setCurrentRow(index)
        self.chat_list.blockSignals(False)

    def _render(self):
        self._message_widgets.clear()
        while self.messages.count():
            self.messages.takeAt(0).widget().deleteLater()
        for message in self.current['messages']:
            self._add_message(message['role'],message['content'] or message.get('error',''),stats=message.get('stats'),
                              images=message.get('images'),web_search=message.get('web_search',False),
                              web_provider=message.get('web_provider','duckduckgo'))
        if not self.current['messages']:
            welcome=QLabel(tr('Uno spazio tranquillo per le tue idee.\nScrivi una domanda per iniziare.'))
            welcome.setObjectName('muted')
            welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
            welcome.setMinimumHeight(200)
            self.messages.addWidget(welcome)
        self.stats_label.clear()
        if self.current['messages']:
            self._show_footer(self.current['messages'][-1].get('stats'))
        self._buttons()

    def _add_message(self,role,text,pending=False,stats=None,images=None,web_search=False,web_provider='duckduckgo'):
        widget=Message(role,text,pending,stats,images=images,directory=self.state.directory,
                       web_search=web_search,web_provider=web_provider,italian_interface=self.state.settings['italian_interface'],
                       dark_mode=self.state.settings['dark_mode'])
        widget.copy_requested.connect(lambda text:QApplication.clipboard().setText(text))
        widget.regenerate_requested.connect(self.regenerate)
        self._message_widgets.append(widget)
        self.messages.addWidget(widget)
        return widget

    def _scroll_to_bottom(self,*_):
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _select(self,index):
        if index>=0 and not self.busy and not self.loading:
            self._clear_images()
            self.current_id=self.state.chats[index]['id']
            self._render()

    def new_conversation(self):
        if self.busy or self.loading:
            return
        chat=new_chat()
        self._clear_images()
        self.state.chats.insert(0,chat)
        self.current_id=chat['id']
        self._refresh_list()
        self._render()
        self._save()
        self._notice('')
        self.input.setFocus()

    def _chat_menu(self,position):
        if self.busy or self.loading:
            return
        item=self.chat_list.itemAt(position)
        if item is None:
            return
        index=self.chat_list.row(item)
        menu=QMenu(self)
        remove=menu.addAction(tr('Elimina conversazione'))
        if menu.exec(self.chat_list.mapToGlobal(position)) is not remove:
            return
        if QMessageBox.question(self,tr('Elimina conversazione'),tr('Eliminare questa conversazione salvata?'))!=QMessageBox.StandardButton.Yes:
            return
        removed=self.state.chats.pop(index)
        if not self.state.chats:
            self.state.chats=[new_chat()]
        if self.current_id==removed['id']:
            self.current_id=self.state.chats[0]['id']
            self._clear_images()
        self._refresh_list()
        self._render()
        self._save()

    def _save(self):
        try:
            self.state.save_chats()
        except (OSError,ValueError) as error:
            self._notice(tr('Salvataggio non riuscito: ')+str(error))

    def _notice(self,text):
        self.notice.setText(text)
        self.notice.setVisible(bool(text))

    def choose_language(self):
        if self.busy or self.loading or self._closing:return
        menu=QMenu(self)
        for code,title in (('it','Italiano'),('en','English')):
            entry=menu.addAction(title)
            entry.setCheckable(True)
            entry.setChecked(code==self.state.settings['language'])
            entry.triggered.connect(lambda checked=False,value=code:self.change_language(value))
        menu.exec(self.language_button.mapToGlobal(self.language_button.rect().bottomLeft()))

    def change_language(self,code,*,save=True):
        if self.busy or self.loading or self._closing:return
        if save:
            try:self.state.save_settings(dict(self.state.settings,language=code))
            except (OSError,ValueError) as error:
                self._notice(str(error));return
        draft=self.input.toPlainText()
        research=self.web_search_button.isChecked()
        subtitle=self.subtitle.text() if self.ready else None
        set_language(code)
        self.setWindowTitle('LLocalMind'+(tr(' · Anteprima') if self.demo else ''))
        self._build()
        self.input.setPlainText(draft)
        self.web_search_button.setChecked(research)
        self._refresh_list()
        self._render()
        if subtitle:self.subtitle.setText(subtitle)
        self._set_status(tr('Pronto') if self.ready else tr('Non caricato'),'ready' if self.ready else 'idle')
        if self._pending_images:
            self.attachment_names.setText(' · '.join(item['name'] for item in self._pending_images))
            self.attachments.show()
        self._buttons()

    def settings(self,*,draft=None):
        from .vision_runtime import supported_platform
        dialog=SettingsDialog(draft or self.state.settings,self.check_updates,
            self.busy or self.loading or self.demo,self,
            can_install_vision=supported_platform() and not self._update_jobs and not self.state.read_only)
        result=dialog.exec()
        if result==SettingsDialog.InstallVision:
            self._vision_install_draft=dialog.values.copy()
            self._start_update('runtime')
            return
        if result!=QDialog.DialogCode.Accepted:
            return
        previous=self.state.settings.copy()
        # Live appearance/image controls must survive older runtime-install drafts.
        dialog.values['italian_interface']=previous['italian_interface']
        dialog.values['vision_image_profile']=previous['vision_image_profile']
        try:
            self.state.save_settings(dialog.values)
        except (OSError,ValueError) as error:
            self._notice(str(error))
            return
        if previous['language']!=dialog.values['language']:
            self.change_language(dialog.values['language'],save=False)
        elif previous['dark_mode']!=dialog.values['dark_mode']:
            self._apply_interface_style()
            self._render()
        active=self._loaded_options or previous
        changed=engine_signature(active)!=engine_signature(dialog.values)
        if not self.demo and dialog.values['model_path'] and (changed or not self.ready) and not self.busy and not self.loading:
            self.load_model()

    def load_model(self):
        if self.loading or self.busy or self._closing:
            return
        self.ready=False
        self.loading=True
        self._stop.clear()
        self._phase=tr('Caricamento del modello')
        self._timer.start()
        self._notice('')
        self._buttons()
        self._loaded_options=self.state.settings.copy()
        self.load_requested.emit(self.state.settings['model_path'],self._options())

    def _options(self):
        return dict(self.state.settings,_attachment_directory=str(self.state.directory))

    @Slot(int,str)
    def _progress(self,percent,label):
        if not self._closing:
            self._phase=tr('Caricamento {percent}%',percent=percent)
            self.subtitle.setText(tr(label))
            self._animate()

    @Slot(str)
    def _loaded(self,name):
        if self._closing:
            return
        self.loading=False
        self.ready=True
        self._timer.stop()
        self._set_status(tr('Pronto'))
        if name.lower().startswith('hermes3.6-35b'):
            name='Hermes 3.6 · 35B A3B'+(name[name.index(' · Vision'):] if ' · Vision' in name else '')
        self.subtitle.setText(name)
        self._buttons()

    def send_or_stop(self):
        if self.busy:
            self._stop.set()
            self._phase=tr('Interruzione')
        else:
            self.send()

    def send(self):
        if self.demo:
            self._notice(tr('Anteprima grafica: avvia la GUI senza --demo e seleziona un GGUF per chattare.'))
            return
        text=self.input.toPlainText().strip()
        if not (text or self._pending_images) or not self.ready or self.busy or self.loading or self._closing:
            return
        if self.state.settings['engine']!='vision' and (self._pending_images or any(m.get('images') for m in self.current['messages'])):
            self._notice(tr('Questa chat contiene immagini: seleziona Vision locale o apri una nuova chat di testo.'))
            return
        web_search=self.web_search_button.isChecked()
        text=text or tr('Descrivi questa immagine.')
        self.input.clear()
        chat=self.current
        if not chat['messages']:
            chat['title']=' '.join(text.split())[:45]
        message=dict(role='user',content=text)
        if self._pending_images:message['images']=copy.deepcopy(self._pending_images)
        if web_search:message.update(web_search=True,web_provider='tavily')
        chat['messages'].append(message)
        self._clear_images()
        self._render()
        self._start_reply(web_search=web_search)
        self._refresh_list()

    def regenerate(self):
        if not self.ready or self.busy or self.loading or self._closing:
            return
        messages=self.current['messages']
        if self.state.settings['engine']!='vision' and any(m.get('images') for m in messages):
            self._notice(tr('Seleziona Vision locale per rigenerare questa risposta con immagini.'))
            return
        if messages and messages[-1]['role']=='assistant':
            web_search=bool(len(messages)>1 and messages[-2].get('web_search',False))
            if web_search:messages[-2]['web_provider']='tavily'
            messages.pop()
            self._render()
            self._start_reply(web_search=web_search)

    def _start_reply(self,*,web_search=False):
        messages=self.current['messages']
        history=copy.deepcopy(messages)
        messages.append(dict(role='assistant',content=''))
        self._active_reply=self._add_message('assistant','',pending=True)
        self.stats_label.clear()
        self.busy=True
        self._stop.clear()
        self._phase=tr('Ricerca web') if web_search else tr('Elaborazione del prompt')
        self._timer.start()
        self._animate()
        self._notice('')
        self._buttons()
        self._save()
        options=self._options()
        options['_web_search']=web_search
        self.generate_requested.emit(history,options)

    @Slot(str)
    def _search_progress(self,text):
        if not self._closing:
            self._phase=text

    @Slot(str)
    def _token(self,text):
        if self._active_reply is not None:
            message=self.current['messages'][-1]
            first=not message['content']
            message['content']+=text
            if first:self._active_reply.update_text(message['content'],pending=True)
            elif not self._render_timer.isActive():self._render_timer.start()
            self._phase=tr('Generazione')

    @Slot()
    def _flush_reply(self):
        if self._active_reply is not None:
            self._active_reply.update_text(self.current['messages'][-1]['content'],pending=True)

    @Slot(dict)
    def _stats(self,stats):
        stats=clean_stats(stats)
        if stats is None or self._active_reply is None:
            return
        self.current['messages'][-1]['stats']=stats
        self._active_reply.set_stats(stats)
        self._show_footer(stats)

    def _show_footer(self,stats):
        stats=clean_stats(stats)
        if stats is None:
            self.stats_label.clear()
            return
        first=stats.get('first_token')
        text=response_summary(stats)
        if first is not None:
            text+=tr(' · {seconds} s al primo token',seconds=number(first,0))
        self.stats_label.setText(text)

    @Slot(str)
    def _reply_finished(self,status):
        self._render_timer.stop()
        self.busy=False
        self._timer.stop()
        if self._active_reply is not None:
            message=self.current['messages'][-1]
            self._active_reply.update_text(message['content'] or message.get('error',''))
            if 'stats' in message:
                message['stats']['interrupted']=status=='stopped'
                self._active_reply.set_stats(message['stats'])
        self._active_reply=None
        self._save()
        if not self._closing:
            self._set_status(tr('Pronto') if self.ready else tr('Non caricato'),'ready' if self.ready else 'idle')
            self._buttons()
            if status=='stopped':
                self._notice(tr('Generazione interrotta.'))
            self.input.setFocus()

    @Slot(str)
    def _error(self,error):
        if self._closing:
            return
        if self.busy and self._active_reply is not None:
            self.current['messages'][-1]['error']=tr(
                'Operazione non riuscita: {error}\n\nPuoi riprovare con Rigenera.',error=str(error)[:1500])
        if self.loading:
            self.loading=False
            self.ready=False
            self._timer.stop()
            self.subtitle.setText(tr('Seleziona un modello GGUF nelle impostazioni'))
            self._set_status(tr('Non caricato'),'error')
        self._notice(error)
        self._buttons()

    def _animate(self):
        self._dot=(self._dot+1)%4
        self._set_status(self._phase+'.'*self._dot,'busy')

    def attach_text(self):
        path,_=QFileDialog.getOpenFileName(self,tr('Allega file locale'),str(Path.home()),
            tr('Testo e immagini (*.txt *.md *.png *.jpg *.jpeg *.webp)'))
        if not path:
            return
        try:
            filename=Path(path)
            if filename.suffix.lower() in ('.png','.jpg','.jpeg','.webp'):
                self.add_image(filename)
                return
            if filename.stat().st_size>1024**2:
                raise ValueError(tr('Il file supera 1 MiB; seleziona un estratto piu\' breve.'))
            text=filename.read_text(encoding='utf-8-sig')
            self.input.insertPlainText(f'\n[{filename.name}]\n{text}\n')
        except (OSError,UnicodeError,ValueError) as error:
            self._notice(str(error))

    def add_image(self,path):
        if self.busy or self.loading or self._closing:return
        if self.state.settings['engine']!='vision':
            self._notice(tr('Per le immagini seleziona Vision locale nelle impostazioni e indica llama-server e mmproj.'))
            return
        try:
            if self.state.read_only:raise ValueError(self.state.warning)
            if len(self._pending_images)>=MAX_IMAGES:raise ValueError(tr('Massimo quattro immagini per messaggio'))
            self._pending_images.append(import_image(path,self.state.directory))
            self.attachment_names.setText(' · '.join(item['name'] for item in self._pending_images))
            self.attachments.show()
            self._notice('')
        except (OSError,ValueError) as error:self._notice(str(error))

    def _clear_images(self):
        self._pending_images.clear()
        self.attachments.hide()
        self.attachment_names.clear()

    def check_updates(self):
        self._start_update('check')

    def _start_update(self,kind,release=None):
        if self._update_jobs or self._closing:
            return
        cancel=threading.Event()
        thread=QThread(self)
        task=UpdateTask(kind,cancel,release)
        task.moveToThread(thread)
        progress=UpdateProgress(kind,cancel,self)
        task.progress.connect(progress.bar.setValue)
        thread.started.connect(task.run,Qt.ConnectionType.QueuedConnection)
        task.finished.connect(thread.quit,Qt.ConnectionType.DirectConnection)
        thread.finished.connect(task.deleteLater)
        job=dict(thread=thread,task=task,cancel=cancel,progress=progress)
        self._update_jobs.append(job)
        thread.finished.connect(self._update_thread_finished,Qt.ConnectionType.QueuedConnection)
        progress.show()
        thread.start()

    @Slot()
    def _update_thread_finished(self):
        thread=self.sender()
        # finished precedes final thread-local cleanup; wait releases the GIL
        # before Qt may destroy the thread object on the GUI event loop.
        thread.wait()
        job=next(job for job in self._update_jobs if job['thread'] is thread)
        self._update_finished(job)

    def _update_finished(self,job):
        self._update_jobs.remove(job)
        # accept() completes the dialog; reject() represents user cancellation.
        job['progress'].accept()
        job['progress'].deleteLater()
        task=job['task']
        job['thread'].deleteLater()
        if self._closing:
            self._finish_close()
            return
        if job['cancel'].is_set():
            return
        if task.error:
            if task.action=='check':
                box=QMessageBox(QMessageBox.Icon.Warning,tr('Aggiornamenti'),task.error,
                               QMessageBox.StandardButton.Ok,self)
                manual=box.addButton(tr('Apri GitHub Releases'),QMessageBox.ButtonRole.ActionRole)
                box.exec()
                if box.clickedButton() is manual:
                    QDesktopServices.openUrl(QUrl('https://github.com/vin10122/LLocalMind/releases'))
            else:
                QMessageBox.warning(self,tr('Motore llama.cpp') if task.action=='runtime' else tr('Aggiornamenti'),task.error)
            return
        if task.action=='runtime':
            path=str(task.result)
            values=dict(self.state.settings,vision_executable=path)
            try:self.state.save_settings(values)
            except (OSError,ValueError) as error:
                self._notice(tr('Motore installato, ma configurazione non salvata: ')+str(error))
                return
            draft=dict(self._vision_install_draft or values,vision_executable=path)
            self._vision_install_draft=None
            QMessageBox.information(self,tr('Motore llama.cpp pronto'),
                tr('Il motore llama.cpp è pronto. Seleziona il GGUF; aggiungi il mmproj solo se vuoi usare immagini.'))
            self.settings(draft=draft)
        elif task.action=='check':
            release=task.result
            if release is None:
                QMessageBox.information(self,tr('Aggiornamenti'),tr('Nessun aggiornamento disponibile (incluse le anteprime).'))
            else:
                box=QMessageBox(self)
                box.setWindowTitle(tr('Aggiornamento disponibile'))
                box.setTextFormat(Qt.TextFormat.PlainText)
                channel=tr(' · anteprima') if release.prerelease else ''
                box.setText(tr('LLocalMind {version}{channel} è disponibile.',version=release.version,channel=channel))
                box.setDetailedText(release.notes)
                download=box.addButton(tr('Scarica aggiornamento'),QMessageBox.ButtonRole.AcceptRole)
                box.addButton(tr('Non ora'),QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() is download:
                    self._start_update('download',release)
        elif not getattr(sys,'frozen',False):
            QMessageBox.information(self,tr('Download completato'),
                tr('Installer verificato:\n{path}\n\nDai sorgenti continua a usare git pull.',path=task.result.path))
        else:
            choice=QMessageBox.question(self,tr('Installa aggiornamento'),
                tr('Salvare la conversazione e chiudere il modello per installare l\'aggiornamento?'))
            if choice==QMessageBox.StandardButton.Yes:
                self._pending_update=task.result
                self.close()

    def closeEvent(self,event):
        if self._allow_close:
            event.accept()
            return
        event.ignore()
        if not self._closing:
            self._closing=True
            self._stop.set()
            self._timer.stop()
            self._set_status(tr('Chiusura del modello…'),'busy')
            self._buttons()
            self._save()
            for job in self._update_jobs:
                job['cancel'].set()
            self.shutdown_requested.emit()
        self._finish_close()

    @Slot()
    def _worker_finished(self):
        self._thread.wait()
        self._model_thread_done=True
        self._finish_close()

    def _finish_close(self):
        if self._closing and self._model_thread_done and not self._update_jobs:
            if self._pending_update is not None:
                try:
                    UpdateManager().launch_installer(self._pending_update)
                except Exception as error:
                    QMessageBox.warning(self,tr('Installazione aggiornamento'),str(error))
                self._pending_update=None
            self._allow_close=True
            self.close()

    def _seed_demo(self):
        chat=new_chat()
        chat['title']=tr('Una giornata di studio')
        chat['messages']=[
            dict(role='user',content=tr('Aiutami a organizzare una giornata di studio.')),
            dict(role='assistant',content=tr('Ecco un programma semplice, con il giusto spazio per le pause.\n\n'
                 '09:00 — Ripasso\n10:30 — Pausa\n11:00 — Esercizi'))]
        others=[new_chat(),new_chat()]
        others[0]['title']=tr('Idee per un progetto')
        others[1]['title']=tr('Spiegare un concetto')
        self.state.chats=[chat,*others]
        self.current_id=chat['id']
        self.subtitle.setText('Hermes 3.6 · 35B A3B')
        self._set_status(tr('Anteprima'),'ready')
        QTimer.singleShot(0,lambda:self.stats_label.setText(tr('Anteprima · statistiche non misurate')))


def main(argv=None):
    parser=argparse.ArgumentParser(description=tr('LLocalMind · chat locale'))
    parser.add_argument('--language',choices=('it','en'),help='Italiano / English')
    parser.add_argument('--italian-interface',action=argparse.BooleanOptionalAction,default=None,help='Italian Interface appearance only')
    parser.add_argument('--demo',action='store_true',help=tr('Anteprima della GUI senza caricare il modello'))
    parser.add_argument('--smoke-test',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--smoke-report',help=argparse.SUPPRESS)
    parser.add_argument('--smoke-screenshot',help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    if (args.smoke_report or args.smoke_screenshot) and not args.smoke_test:
        parser.error('--smoke-report e --smoke-screenshot richiedono --smoke-test')
    application=QApplication.instance() or QApplication(sys.argv[:1])
    application.setApplicationName('LLocalMind')
    application.setOrganizationName('LLocalMind')
    apply_theme(application)
    preview=args.demo or args.smoke_test
    temporary=tempfile.TemporaryDirectory(prefix='llocalmind-preview-') if preview else None
    state=LocalState(temporary.name) if temporary else LocalState()
    overrides={}
    if args.language:overrides['language']=args.language
    if args.italian_interface is not None:overrides['italian_interface']=args.italian_interface
    if overrides:
        if state.read_only:state.settings.update(overrides)
        else:state.save_settings(dict(state.settings,**overrides))
    window=MainWindow(state=state,demo=preview)
    window.show()
    smoke_result=[]
    if args.smoke_test:
        def run_smoke():
            from .smoke import probe,write_report
            try:
                details=probe()
                expected='New chat' if state.settings['language']=='en' else 'Nuova chat'
                if window.new_button.text()!=expected:raise RuntimeError('GUI language smoke check failed')
                details['language']=state.settings['language']
                details['italian_interface']=state.settings['italian_interface']
                if state.settings['italian_interface'] and window.send_button.text()!='Dottore, parti 🍕':
                    raise RuntimeError('Italian Interface smoke check failed')
                if args.smoke_screenshot:
                    path=Path(args.smoke_screenshot)
                    path.parent.mkdir(parents=True,exist_ok=True)
                    if not window.grab().save(str(path)):
                        raise RuntimeError('GUI screenshot failed')
                write_report(args.smoke_report,dict(ok=True,gui=True,**details))
                smoke_result.append(0)
            except Exception as error:
                write_report(args.smoke_report,dict(ok=False,error=str(error)))
                smoke_result.append(1)
            finally:
                window.close()
        QTimer.singleShot(200,run_smoke)
    result=application.exec()
    if temporary:
        temporary.cleanup()
    return smoke_result[0] if smoke_result else result

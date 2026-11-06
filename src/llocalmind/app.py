"""LLocalMind desktop chat, based on the approved rounded blue mockup."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import sys
import tempfile
import threading

from PySide6.QtCore import Qt, QSize, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox,
    QProgressBar, QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

from .inference import ModelWorker
from .settings_dialog import SettingsDialog
from .state import LocalState, new_chat
from .theme import apply_theme
from .update_worker import UpdateTask
from .updater import UpdateManager
from .widgets import ASSETS, Composer, Message, action, icon, logo_label


def number(value,places=1):
    return f'{value:.{places}f}'.replace('.',',')


class UpdateProgress(QDialog):
    def __init__(self,kind,cancel,parent):
        super().__init__(parent)
        self.cancel=cancel
        self.setWindowTitle('Aggiornamenti LLocalMind')
        self.setMinimumWidth(380)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(24,24,24,24)
        layout.setSpacing(16)
        self.label=QLabel('Controllo aggiornamenti…' if kind=='check' else 'Download aggiornamento…')
        layout.addWidget(self.label)
        self.bar=QProgressBar()
        self.bar.setRange(0,0 if kind=='check' else 100)
        layout.addWidget(self.bar)
        button=QPushButton('Annulla')
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
        self.current_id=self.state.chats[0]['id']
        self.busy=False
        self.ready=False
        self.loading=False
        self._closing=False
        self._allow_close=False
        self._model_thread_done=False
        self._pending_update=None
        self._update_jobs=[]
        self._message_widgets=[]
        self._active_reply=None
        self._stop=threading.Event()
        self.setWindowTitle('LLocalMind' + (' · Anteprima' if demo else ''))
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
        self._worker.progress.connect(self._progress)
        self._worker.loaded.connect(self._loaded)
        self._worker.token.connect(self._token)
        self._worker.stats.connect(self._stats)
        self._worker.error.connect(self._error)
        self._worker.reply_finished.connect(self._reply_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._worker_finished)
        self._thread.start()
        self._timer=QTimer(self)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._animate)
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
        self.new_button=action('Nuova chat','plus',name='newChat')
        self.new_button.clicked.connect(self.new_conversation)
        side.addWidget(self.new_button)
        side.addSpacing(4)
        section=QLabel('LE TUE CHAT')
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
        pill_row.addWidget(QLabel('Tutto sul tuo PC'))
        pill_row.addStretch()
        side.addWidget(pill)
        settings=action('Impostazioni','settings',color='#f5f2eb',name='sidebarAction')
        settings.clicked.connect(self.settings)
        side.addWidget(settings)
        row.addWidget(sidebar)
        main=QVBoxLayout()
        main.setContentsMargins(0,8,0,4)
        main.setSpacing(14)
        heading=QHBoxLayout()
        title_col=QVBoxLayout()
        title=QLabel('Il tuo spazio per pensare')
        title.setObjectName('heading')
        title_col.addWidget(title)
        self.subtitle=QLabel('Scegli un modello GGUF nelle impostazioni')
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
        self._set_status('Non caricato','idle')
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
        composer=QFrame()
        composer.setObjectName('composer')
        compose=QHBoxLayout(composer)
        compose.setContentsMargins(14,12,14,12)
        compose.setSpacing(12)
        self.attach=QToolButton()
        self.attach.setIcon(icon('clip'))
        self.attach.setIconSize(QSize(26,26))
        self.attach.setToolTip('Allega un file di testo locale')
        self.attach.clicked.connect(self.attach_text)
        compose.addWidget(self.attach)
        self.input=Composer()
        self.input.submitted.connect(self.send)
        compose.addWidget(self.input,1)
        self.send_button=QToolButton()
        self.send_button.setObjectName('send')
        self.send_button.setFixedSize(48,48)
        self.send_button.setIconSize(QSize(26,26))
        self.send_button.clicked.connect(self.send_or_stop)
        compose.addWidget(self.send_button)
        main.addWidget(composer)
        main.addWidget(self._line())
        footer=QHBoxLayout()
        label=QLabel('Elaborazione locale')
        label.setObjectName('footer')
        footer.addWidget(label)
        footer.addStretch()
        self.stats_label=QLabel('')
        self.stats_label.setObjectName('footer')
        footer.addWidget(self.stats_label)
        main.addLayout(footer)
        row.addLayout(main,1)

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

    def _buttons(self):
        blocked=self.busy or self.loading or self._closing
        self.new_button.setEnabled(not blocked)
        self.chat_list.setEnabled(not blocked)
        self.attach.setEnabled(not blocked)
        self.input.setReadOnly(blocked)
        self.send_button.setEnabled(self.demo or self.busy or (self.ready and not blocked))
        self.send_button.setIcon(icon('stop' if self.busy else 'send','#f5f2eb'))
        self.send_button.setToolTip('Interrompi' if self.busy else 'Invia · Maiusc+Invio per andare a capo')
        assistants=[w for w in self._message_widgets if w.role=='assistant']
        for widget in assistants:
            widget.regenerate_button.setEnabled(not blocked and self.ready and widget is assistants[-1])

    def _refresh_list(self):
        self.chat_list.blockSignals(True)
        self.chat_list.clear()
        for index,chat in enumerate(self.state.chats):
            item=QListWidgetItem(icon('chat','#eaf1f6'),chat['title'])
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
            self._add_message(message['role'],message['content'])
        if not self.current['messages']:
            welcome=QLabel('Uno spazio tranquillo per le tue idee.\nScrivi una domanda per iniziare.')
            welcome.setObjectName('muted')
            welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
            welcome.setMinimumHeight(200)
            self.messages.addWidget(welcome)
        self.stats_label.clear()
        self._buttons()

    def _add_message(self,role,text,pending=False):
        widget=Message(role,text,pending)
        widget.copy_requested.connect(lambda text:QApplication.clipboard().setText(text))
        widget.regenerate_requested.connect(self.regenerate)
        self._message_widgets.append(widget)
        self.messages.addWidget(widget)
        return widget

    def _scroll_to_bottom(self,*_):
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _select(self,index):
        if index>=0 and not self.busy and not self.loading:
            self.current_id=self.state.chats[index]['id']
            self._render()

    def new_conversation(self):
        if self.busy or self.loading:
            return
        chat=new_chat()
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
        remove=menu.addAction('Elimina conversazione')
        if menu.exec(self.chat_list.mapToGlobal(position)) is not remove:
            return
        if QMessageBox.question(self,'Elimina conversazione','Eliminare questa conversazione salvata?')!=QMessageBox.StandardButton.Yes:
            return
        removed=self.state.chats.pop(index)
        if not self.state.chats:
            self.state.chats=[new_chat()]
        if self.current_id==removed['id']:
            self.current_id=self.state.chats[0]['id']
        self._refresh_list()
        self._render()
        self._save()

    def _save(self):
        try:
            self.state.save_chats()
        except (OSError,ValueError) as error:
            self._notice('Salvataggio non riuscito: '+str(error))

    def _notice(self,text):
        self.notice.setText(text)
        self.notice.setVisible(bool(text))

    def settings(self):
        dialog=SettingsDialog(self.state.settings,self.check_updates,
                              self.busy or self.loading or self.demo,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:
            return
        previous=self.state.settings.copy()
        try:
            self.state.save_settings(dialog.values)
        except (OSError,ValueError) as error:
            self._notice(str(error))
            return
        engine_keys=set(previous)-{'max_tokens','temperature'}
        changed=any(previous[key]!=dialog.values[key] for key in engine_keys)
        if not self.demo and dialog.values['model_path'] and (changed or not self.ready) and not self.busy and not self.loading:
            self.load_model()

    def load_model(self):
        if self.loading or self.busy or self._closing:
            return
        self.ready=False
        self.loading=True
        self._stop.clear()
        self._phase='Caricamento del modello'
        self._timer.start()
        self._notice('')
        self._buttons()
        self.load_requested.emit(self.state.settings['model_path'],self.state.settings.copy())

    def _progress(self,percent,label):
        if not self._closing:
            self._phase=f'Caricamento {percent}%'
            self.subtitle.setText(label)
            self._animate()

    def _loaded(self,name):
        if self._closing:
            return
        self.loading=False
        self.ready=True
        self._timer.stop()
        self._set_status('Pronto')
        self.subtitle.setText('Hermes 3.6 · 35B A3B' if name.lower().startswith('hermes3.6-35b') else name)
        self._buttons()

    def send_or_stop(self):
        if self.busy:
            self._stop.set()
            self._phase='Interruzione'
        else:
            self.send()

    def send(self):
        if self.demo:
            self._notice('Anteprima grafica: avvia la GUI senza --demo e seleziona un GGUF per chattare.')
            return
        text=self.input.toPlainText().strip()
        if not text or not self.ready or self.busy or self.loading or self._closing:
            return
        self.input.clear()
        chat=self.current
        if not chat['messages']:
            chat['title']=' '.join(text.split())[:45]
        chat['messages'].append(dict(role='user',content=text))
        self._render()
        self._start_reply()
        self._refresh_list()

    def regenerate(self):
        if not self.ready or self.busy or self.loading or self._closing:
            return
        messages=self.current['messages']
        if messages and messages[-1]['role']=='assistant':
            messages.pop()
            self._render()
            self._start_reply()

    def _start_reply(self):
        messages=self.current['messages']
        history=copy.deepcopy(messages)
        messages.append(dict(role='assistant',content=''))
        self._active_reply=self._add_message('assistant','',pending=True)
        self.busy=True
        self._stop.clear()
        self._phase='Elaborazione del prompt'
        self._timer.start()
        self._animate()
        self._notice('')
        self._buttons()
        self._save()
        self.generate_requested.emit(history,self.state.settings.copy())

    def _token(self,text):
        if self._active_reply is not None:
            message=self.current['messages'][-1]
            message['content']+=text
            self._active_reply.update_text(message['content'],pending=True)
            self._phase='Generazione'

    def _stats(self,stats):
        rate=stats.get('rate')
        first=stats.get('first_token')
        text=f'{number(rate)} tok/s' if rate is not None else f"{stats['tokens']} token"
        if first is not None:
            text+=f' · {number(first,0)} s al primo token'
        self.stats_label.setText(text)

    def _reply_finished(self,status):
        self.busy=False
        self._timer.stop()
        if self._active_reply is not None:
            self._active_reply.update_text(self.current['messages'][-1]['content'])
        self._active_reply=None
        self._save()
        if not self._closing:
            self._set_status('Pronto' if self.ready else 'Non caricato','ready' if self.ready else 'idle')
            self._buttons()
            if status=='stopped':
                self._notice('Generazione interrotta.')
            self.input.setFocus()

    def _error(self,error):
        if self._closing:
            return
        if self.loading:
            self.loading=False
            self.ready=False
            self._timer.stop()
            self.subtitle.setText('Seleziona un modello GGUF nelle impostazioni')
            self._set_status('Non caricato','error')
        self._notice(error)
        self._buttons()

    def _animate(self):
        self._dot=(self._dot+1)%4
        self._set_status(self._phase+'.'*self._dot,'busy')

    def attach_text(self):
        path,_=QFileDialog.getOpenFileName(self,'Allega testo locale',str(Path.home()),'Testo (*.txt *.md)')
        if not path:
            return
        try:
            filename=Path(path)
            if filename.stat().st_size>1024**2:
                raise ValueError('Il file supera 1 MiB; seleziona un estratto piu\' breve.')
            text=filename.read_text(encoding='utf-8-sig')
            self.input.insertPlainText(f'\n[{filename.name}]\n{text}\n')
        except (OSError,UnicodeError,ValueError) as error:
            self._notice(str(error))

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
            QMessageBox.warning(self,'Aggiornamenti',task.error)
            return
        if task.action=='check':
            release=task.result
            if release is None:
                QMessageBox.information(self,'Aggiornamenti','Nessun aggiornamento stabile disponibile.')
            else:
                box=QMessageBox(self)
                box.setWindowTitle('Aggiornamento disponibile')
                box.setTextFormat(Qt.TextFormat.PlainText)
                box.setText(f'LLocalMind {release.version} è disponibile.')
                box.setDetailedText(release.notes)
                download=box.addButton('Scarica aggiornamento',QMessageBox.ButtonRole.AcceptRole)
                box.addButton('Non ora',QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() is download:
                    self._start_update('download',release)
        elif not getattr(sys,'frozen',False):
            QMessageBox.information(self,'Download completato',
                f'Installer verificato:\n{task.result.path}\n\nDai sorgenti continua a usare git pull.')
        else:
            choice=QMessageBox.question(self,'Installa aggiornamento',
                'Salvare la conversazione e chiudere il modello per installare l\'aggiornamento?')
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
            self._set_status('Chiusura del modello…','busy')
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
                    QMessageBox.warning(self,'Installazione aggiornamento',str(error))
                self._pending_update=None
            self._allow_close=True
            self.close()

    def _seed_demo(self):
        chat=new_chat()
        chat['title']='Una giornata di studio'
        chat['messages']=[
            dict(role='user',content='Aiutami a organizzare una giornata di studio.'),
            dict(role='assistant',content='Ecco un programma semplice, con il giusto spazio per le pause.\n\n'
                 '09:00 — Ripasso\n10:30 — Pausa\n11:00 — Esercizi')]
        others=[new_chat(),new_chat()]
        others[0]['title']='Idee per un progetto'
        others[1]['title']='Spiegare un concetto'
        self.state.chats=[chat,*others]
        self.current_id=chat['id']
        self.subtitle.setText('Hermes 3.6 · 35B A3B')
        self._set_status('Anteprima','ready')
        QTimer.singleShot(0,lambda:self.stats_label.setText('Anteprima · statistiche non misurate'))


def main(argv=None):
    parser=argparse.ArgumentParser(description='LLocalMind · chat locale')
    parser.add_argument('--demo',action='store_true',help='Anteprima della GUI senza caricare il modello')
    args=parser.parse_args(argv)
    application=QApplication.instance() or QApplication(sys.argv[:1])
    application.setApplicationName('LLocalMind')
    application.setOrganizationName('LLocalMind')
    apply_theme(application)
    temporary=tempfile.TemporaryDirectory(prefix='llocalmind-preview-') if args.demo else None
    state=LocalState(temporary.name) if temporary else LocalState()
    window=MainWindow(state=state,demo=args.demo)
    window.show()
    result=application.exec()
    if temporary:
        temporary.cleanup()
    return result

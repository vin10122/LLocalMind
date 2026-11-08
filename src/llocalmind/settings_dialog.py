from .i18n import tr
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QScrollArea, QSpinBox, QVBoxLayout, QWidget)
from . import __version__
from .state import validate_settings


class SettingsDialog(QDialog):
    InstallVision=42

    def __init__(self,values,check_updates,busy=False,parent=None,*,can_install_vision=True):
        super().__init__(parent)
        self.setWindowTitle(tr('Impostazioni · LLocalMind'))
        self.setMinimumWidth(560)
        self.values=values.copy()
        self.controls={}
        outer=QVBoxLayout(self)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        body=QWidget()
        body.setObjectName('settingsBody')
        scroll.setWidget(body)
        outer.addWidget(scroll,1)
        layout=QVBoxLayout(body)
        layout.setContentsMargins(24,24,24,24)
        layout.setSpacing(18)
        title=QLabel(tr('Il tuo modello, sul tuo PC'))
        title.setObjectName('dialogTitle')
        layout.addWidget(title)
        model_row=QHBoxLayout()
        self.path=QLineEdit(values['model_path'])
        self.path.setPlaceholderText(tr('Seleziona il file GGUF…'))
        self.path.setEnabled(not busy)
        browse=QPushButton(tr('Sfoglia…'))
        browse.setEnabled(not busy)
        browse.clicked.connect(self.browse)
        model_row.addWidget(self.path,1)
        model_row.addWidget(browse)
        layout.addLayout(model_row)
        hint=QLabel(tr('Il modello resta nella posizione scelta e non viene incluso negli aggiornamenti.'))
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        layout.addWidget(hint)
        vision_form=QFormLayout()
        self.engine=QComboBox()
        self.engine.addItem(tr('llama.cpp · consigliato · testo e immagini'),'vision')
        self.engine.addItem(tr('Motore nativo Intel · sperimentale'),'optimized')
        self.engine.setCurrentIndex(self.engine.findData(values['engine']))
        self.engine.setEnabled(not busy)
        vision_form.addRow(tr('Motore'),self.engine)
        self.language=QComboBox()
        self.language.addItem('Italiano','it')
        self.language.addItem('English','en')
        self.language.setCurrentIndex(self.language.findData(values['language']))
        self.language.setEnabled(not busy)
        vision_form.addRow(tr('Lingua dell’interfaccia'),self.language)
        self.dark_mode=QCheckBox(tr('Modalità scura · nero e verde'))
        self.dark_mode.setChecked(values['dark_mode'])
        self.dark_mode.setEnabled(not busy)
        vision_form.addRow(tr('Aspetto'),self.dark_mode)
        self.web_profile=QComboBox()
        self.web_profile.addItem(tr('Rapida · 2 fonti, estratti brevi'),'fast')
        self.web_profile.addItem(tr('Completa · 3 fonti, più dettagli'),'detail')
        self.web_profile.setCurrentIndex(self.web_profile.findData(values['web_profile']))
        self.web_profile.setEnabled(not busy)
        self.web_profile.setToolTip(tr('Rapida riduce il testo da elaborare ma può omettere dettagli. Completa mantiene gli estratti più lunghi.'))
        vision_form.addRow(tr('Ricerca web'),self.web_profile)
        language_note=QLabel(tr('La modalità inglese usa l’interfaccia e le nuove risposte in inglese. Le conversazioni salvate restano invariate.'))
        language_note.setWordWrap(True)
        vision_form.addRow(language_note)

        self.vision_fields=QWidget()
        fields=QFormLayout(self.vision_fields)
        fields.setContentsMargins(0,0,0,0)
        self.vision_paths={}
        for key,label,file_filter in (
            ('vision_executable','llama-server',tr('Eseguibile (llama-server.exe llama-server)')),
            ('vision_projector',tr('mmproj · facoltativo per il testo'),'GGUF (*.gguf)')):
            row=QHBoxLayout()
            edit=QLineEdit(values[key])
            edit.setEnabled(not busy)
            self.vision_paths[key]=edit
            button=QPushButton(tr('Sfoglia…'))
            button.setEnabled(not busy)
            def choose(_=False,control=edit,title=label,filter_=file_filter):
                filename,_=QFileDialog.getOpenFileName(self,title,str(Path.home()),filter_)
                if filename:control.setText(filename)
            button.clicked.connect(choose)
            row.addWidget(edit,1)
            row.addWidget(button)
            fields.addRow(label,row)
        self.install_vision=QPushButton(tr('Installa / aggiorna motore llama.cpp CPU'))
        self.install_vision.setEnabled(not busy and can_install_vision)
        self.install_vision.clicked.connect(self.request_vision_install)
        fields.addRow(self.install_vision)
        note=QLabel(tr('Per il testo bastano il GGUF e llama-server. Il mmproj compatibile serve solo per le immagini. '
                   'Modello ed eventuale encoder immagini usano la CPU.'))
        note.setWordWrap(True)
        fields.addRow(note)
        vision_form.addRow(self.vision_fields)
        self.vision_fields.setVisible(self.engine.currentData()=='vision')
        self.engine.currentIndexChanged.connect(lambda:self.vision_fields.setVisible(self.engine.currentData()=='vision'))
        layout.addLayout(vision_form)
        advanced=QGroupBox(tr('Parametri avanzati · configurazione consigliata preimpostata'))
        advanced.setCheckable(True)
        advanced.setChecked(False)
        inner=QWidget()
        form=QFormLayout(inner)
        for name,title,low,high in (
            ('max_tokens',tr('Token massimi di risposta'),1,4096),
            ('max_seq',tr('Contesto massimo'),256,16384),
            ('cache',tr('Cache esperti'),1,2048),
            ('weight_cache',tr('Cache pesi convertiti'),1,2048),
            ('expert_workers',tr('Worker esperti CPU'),1,16),
            ('prefill_threads',tr('Thread prefill CPU'),1,16),
            ('vision_image_tokens',tr('Token visivi massimi'),64,8192),
            ('vision_threads',tr('Thread Vision CPU'),1,16),
            ('vision_batch',tr('Batch vision'),32,2048),
            ('vision_ubatch',tr('Microbatch vision'),32,2048),
            ('vision_cache_mib',tr('Cache prompt vision (MiB)'),0,1024),
        ):
            control=QSpinBox()
            control.setRange(low,high)
            control.setValue(values[name])
            control.setEnabled(not busy)
            self.controls[name]=control
            form.addRow(title,control)
        warmup=QCheckBox(tr('Prepara il motore prima di «Pronto»'))
        warmup.setChecked(values['vision_warmup'])
        warmup.setEnabled(not busy)
        self.controls['vision_warmup']=warmup
        form.addRow('Vision',warmup)
        detail=QLabel(tr('Meno token visivi riducono il lavoro ma possono perdere dettagli e scritte piccole. '
            'Disattivare la preparazione iniziale accelera l’avvio ma può rallentare la prima risposta.'))
        detail.setWordWrap(True)
        form.addRow(detail)
        for name,title in (('ssm_device','DeltaNet'),('attention_device','Full attention')):
            control=QComboBox()
            control.addItems(['GPU','CPU','NPU'])
            control.setCurrentText(values[name])
            control.setEnabled(not busy)
            self.controls[name]=control
            form.addRow(title,control)
        temperature=QDoubleSpinBox()
        temperature.setRange(0,2)
        temperature.setSingleStep(.1)
        temperature.setValue(values['temperature'])
        temperature.setEnabled(not busy)
        self.controls['temperature']=temperature
        form.addRow(tr('Temperatura'),temperature)
        group_layout=QVBoxLayout(advanced)
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(240)
        scroll.setWidget(inner)
        group_layout.addWidget(scroll)
        scroll.setVisible(False)
        advanced.toggled.connect(scroll.setVisible)
        layout.addWidget(advanced)
        about=QHBoxLayout()
        about.addWidget(QLabel(f'LLocalMind {__version__}'))
        about.addStretch()
        updates=QPushButton(tr('Controlla aggiornamenti'))
        def check_clicked():
            self.reject()
            check_updates()
        updates.clicked.connect(check_clicked)
        about.addWidget(updates)
        outer.addLayout(about)
        if busy:
            note=QLabel(tr('Interrompi la risposta prima di cambiare modello o configurazione.'))
            note.setWordWrap(True)
            layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(tr('Salva'))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr('Annulla'))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.resize(620,min(840,max(350,self.screen().availableGeometry().height()-80)))

    def browse(self):
        filename,_=QFileDialog.getOpenFileName(self,tr('Seleziona modello GGUF'),str(Path.home()),tr('Modelli GGUF (*.gguf)'))
        if filename:
            self.path.setText(filename)

    def collected_values(self):
        values=self.values.copy()
        values['model_path']=self.path.text().strip()
        values['engine']=self.engine.currentData()
        values['language']=self.language.currentData()
        values['dark_mode']=self.dark_mode.isChecked()
        values['web_profile']=self.web_profile.currentData()
        for key,edit in self.vision_paths.items():values[key]=edit.text().strip()
        for name,control in self.controls.items():
            values[name]=(control.currentText() if isinstance(control,QComboBox) else
                          control.isChecked() if isinstance(control,QCheckBox) else control.value())
        return validate_settings(values)

    def request_vision_install(self):
        try:self.values=self.collected_values()
        except ValueError as error:
            QMessageBox.warning(self,tr('Impostazioni'),str(error))
            return
        self.done(self.InstallVision)

    def accept(self):
        try:
            values=self.collected_values()
            if values['model_path'] and not Path(values['model_path']).is_file():
                raise ValueError(tr('Il file del modello selezionato non esiste'))
            if values['engine']=='vision':
                for key in ('vision_executable',):
                    if not values[key] or not Path(values[key]).is_file():
                        raise ValueError(tr('Installa o seleziona llama-server.'))
                if values['vision_projector'] and not Path(values['vision_projector']).is_file():
                    raise ValueError(tr('Seleziona un mmproj esistente oppure lascia il campo vuoto per il solo testo.'))
                if values['vision_projector'] and Path(values['vision_projector']).suffix.lower()!='.gguf':
                    raise ValueError(tr('Il mmproj deve essere un file GGUF'))
        except ValueError as error:
            QMessageBox.warning(self,tr('Impostazioni'),str(error))
            return
        self.values=values
        super().accept()

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
        self.setWindowTitle('Impostazioni · LLocalMind')
        self.setMinimumWidth(560)
        self.values=values.copy()
        self.controls={}
        layout=QVBoxLayout(self)
        layout.setContentsMargins(24,24,24,24)
        layout.setSpacing(18)
        title=QLabel('Il tuo modello, sul tuo PC')
        title.setObjectName('dialogTitle')
        layout.addWidget(title)
        model_row=QHBoxLayout()
        self.path=QLineEdit(values['model_path'])
        self.path.setPlaceholderText('Seleziona il file GGUF…')
        self.path.setEnabled(not busy)
        browse=QPushButton('Sfoglia…')
        browse.setEnabled(not busy)
        browse.clicked.connect(self.browse)
        model_row.addWidget(self.path,1)
        model_row.addWidget(browse)
        layout.addLayout(model_row)
        hint=QLabel('Il modello resta nella posizione scelta e non viene incluso negli aggiornamenti.')
        hint.setWordWrap(True)
        hint.setObjectName('muted')
        layout.addWidget(hint)
        vision_form=QFormLayout()
        self.engine=QComboBox()
        self.engine.addItem('Testo · Intel ottimizzato','optimized')
        self.engine.addItem('Testo e immagini · llama.cpp locale','vision')
        self.engine.setCurrentIndex(self.engine.findData(values['engine']))
        self.engine.setEnabled(not busy)
        vision_form.addRow('Motore',self.engine)
        self.vision_fields=QWidget()
        fields=QFormLayout(self.vision_fields)
        fields.setContentsMargins(0,0,0,0)
        self.vision_paths={}
        for key,label,file_filter in (
            ('vision_executable','llama-server','Eseguibile (llama-server.exe llama-server)'),
            ('vision_projector','mmproj compatibile','GGUF (*.gguf)')):
            row=QHBoxLayout()
            edit=QLineEdit(values[key])
            edit.setEnabled(not busy)
            self.vision_paths[key]=edit
            button=QPushButton('Sfoglia…')
            button.setEnabled(not busy)
            def choose(_=False,control=edit,title=label,filter_=file_filter):
                filename,_=QFileDialog.getOpenFileName(self,title,str(Path.home()),filter_)
                if filename:control.setText(filename)
            button.clicked.connect(choose)
            row.addWidget(edit,1)
            row.addWidget(button)
            fields.addRow(label,row)
        self.vision_encoder=QComboBox()
        self.vision_encoder.addItem('Automatico · GPU Vulkan se disponibile','auto')
        self.vision_encoder.addItem('CPU','cpu')
        self.vision_encoder.setCurrentIndex(self.vision_encoder.findData(values['vision_encoder']))
        self.vision_encoder.setEnabled(not busy)
        fields.addRow('Encoder immagini',self.vision_encoder)
        self.install_vision=QPushButton('Installa / aggiorna motore vision Vulkan')
        self.install_vision.setEnabled(not busy and can_install_vision)
        self.install_vision.clicked.connect(self.request_vision_install)
        fields.addRow(self.install_vision)
        note=QLabel('Serve una versione di llama.cpp che supporti il modello e il suo mmproj. '
                   'Il nuovo runtime usa la GPU per l’encoder immagini quando disponibile; il modello resta su CPU. '
                   'Il pulsante scarica e configura il motore; modello e mmproj restano da selezionare.')
        note.setWordWrap(True)
        fields.addRow(note)
        vision_form.addRow(self.vision_fields)
        self.vision_fields.setVisible(self.engine.currentData()=='vision')
        self.engine.currentIndexChanged.connect(lambda:self.vision_fields.setVisible(self.engine.currentData()=='vision'))
        layout.addLayout(vision_form)
        advanced=QGroupBox('Parametri avanzati · configurazione consigliata preimpostata')
        advanced.setCheckable(True)
        advanced.setChecked(False)
        inner=QWidget()
        form=QFormLayout(inner)
        for name,title,low,high in (
            ('max_tokens','Token massimi di risposta',1,4096),
            ('max_seq','Contesto massimo',256,16384),
            ('cache','Cache esperti',1,2048),
            ('weight_cache','Cache pesi convertiti',1,2048),
            ('expert_workers','Worker esperti CPU',1,16),
            ('prefill_threads','Thread prefill CPU',1,16),
            ('vision_image_tokens','Token visivi massimi',64,8192),
            ('vision_batch','Batch vision',32,2048),
            ('vision_ubatch','Microbatch vision',32,2048),
            ('vision_cache_mib','Cache prompt vision (MiB)',0,1024),
        ):
            control=QSpinBox()
            control.setRange(low,high)
            control.setValue(values[name])
            control.setEnabled(not busy)
            self.controls[name]=control
            form.addRow(title,control)
        warmup=QCheckBox('Prepara il motore prima di «Pronto»')
        warmup.setChecked(values['vision_warmup'])
        warmup.setEnabled(not busy)
        self.controls['vision_warmup']=warmup
        form.addRow('Vision',warmup)
        detail=QLabel('Meno token visivi riducono il lavoro ma possono perdere dettagli e scritte piccole. '
            'Disattivare la preparazione iniziale accelera l’avvio ma può rallentare la prima risposta.')
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
        form.addRow('Temperatura',temperature)
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
        updates=QPushButton('Controlla aggiornamenti')
        def check_clicked():
            self.reject()
            check_updates()
        updates.clicked.connect(check_clicked)
        about.addWidget(updates)
        layout.addLayout(about)
        if busy:
            note=QLabel('Interrompi la risposta prima di cambiare modello o configurazione.')
            note.setWordWrap(True)
            layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText('Salva')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Annulla')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse(self):
        filename,_=QFileDialog.getOpenFileName(self,'Seleziona modello GGUF',str(Path.home()),'Modelli GGUF (*.gguf)')
        if filename:
            self.path.setText(filename)

    def collected_values(self):
        values=self.values.copy()
        values['model_path']=self.path.text().strip()
        values['engine']=self.engine.currentData()
        values['vision_encoder']=self.vision_encoder.currentData()
        for key,edit in self.vision_paths.items():values[key]=edit.text().strip()
        for name,control in self.controls.items():
            values[name]=(control.currentText() if isinstance(control,QComboBox) else
                          control.isChecked() if isinstance(control,QCheckBox) else control.value())
        return validate_settings(values)

    def request_vision_install(self):
        try:self.values=self.collected_values()
        except ValueError as error:
            QMessageBox.warning(self,'Impostazioni',str(error))
            return
        self.done(self.InstallVision)

    def accept(self):
        try:
            values=self.collected_values()
            if values['model_path'] and not Path(values['model_path']).is_file():
                raise ValueError('Il file del modello selezionato non esiste')
            if values['engine']=='vision':
                for key in ('vision_executable','vision_projector'):
                    if not values[key] or not Path(values[key]).is_file():
                        raise ValueError('Seleziona llama-server e il mmproj compatibile')
                if Path(values['vision_projector']).suffix.lower()!='.gguf':
                    raise ValueError('Il mmproj deve essere un file GGUF')
        except ValueError as error:
            QMessageBox.warning(self,'Impostazioni',str(error))
            return
        self.values=values
        super().accept()

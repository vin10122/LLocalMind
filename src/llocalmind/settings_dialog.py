from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QLineEdit, QMessageBox, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)
from . import __version__
from .state import validate_settings


class SettingsDialog(QDialog):
    def __init__(self,values,check_updates,busy=False,parent=None):
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
        ):
            control=QSpinBox()
            control.setRange(low,high)
            control.setValue(values[name])
            control.setEnabled(not busy)
            self.controls[name]=control
            form.addRow(title,control)
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
        group_layout.addWidget(inner)
        inner.setVisible(False)
        advanced.toggled.connect(inner.setVisible)
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

    def accept(self):
        values=self.values.copy()
        values['model_path']=self.path.text().strip()
        for name,control in self.controls.items():
            values[name]=control.currentText() if isinstance(control,QComboBox) else control.value()
        try:
            self.values=validate_settings(values)
            if values['model_path'] and not Path(values['model_path']).is_file():
                raise ValueError('Il file del modello selezionato non esiste')
        except ValueError as error:
            QMessageBox.warning(self,'Impostazioni',str(error))
            return
        super().accept()

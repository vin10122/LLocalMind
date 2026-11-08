from PySide6.QtCore import QObject, Signal, Slot
from .updater import UpdateManager


class UpdateTask(QObject):
    progress=Signal(int)
    finished=Signal()

    def __init__(self,action,cancel,release=None):
        super().__init__()
        self.action=action
        self.cancel=cancel
        self.release=release
        self.result=None
        self.error=''

    @Slot()
    def run(self):
        try:
            if self.action=='runtime':
                from .vision_runtime import RuntimeInstaller
                self.result=RuntimeInstaller().install(cancel=self.cancel,progress=self.progress.emit)
            else:
                manager=UpdateManager()
                if self.action=='check':
                    self.result=manager.check(cancel=self.cancel)
                else:
                    self.result=manager.download(self.release,cancel=self.cancel,
                        progress=lambda received,total:self.progress.emit(int(received*100/total)))
        except Exception as error:
            self.error=str(error)
        finally:
            self.finished.emit()

"""Offscreen GUI/session checks. No real GGUF or inference required."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from PySide6.QtCore import QThread,Slot
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from llocalmind.app import MainWindow
from llocalmind.inference import ModelWorker
from llocalmind.metrics import clean_stats, response_summary
from llocalmind.prompts import format_conversation
from llocalmind.state import LocalState,validate_settings
from llocalmind.theme import apply_theme
from llocalmind.widgets import Message,schedule_parts


class FakeWorker(ModelWorker):
    @Slot(str,dict)
    def load(self,path,options):
        self.loaded.emit('Test model')

    @Slot(list,dict)
    def generate(self,messages,options):
        self.history=copy.deepcopy(messages)
        count=0
        for _ in range(50):
            if self.stop.is_set():break
            count+=1
            self.token.emit('test ')
            QThread.msleep(3)
        self.stats.emit(dict(tokens=count,first_token=.01 if count else None,rate=2.5 if count>1 else None))
        self.reply_finished.emit('stopped' if self.stop.is_set() else 'complete')


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.state=LocalState(self.temp.name)
        self.windows=[]

    def wait(self,predicate):
        deadline=time.monotonic()+4
        while not predicate() and time.monotonic()<deadline:
            QTest.qWait(10)
        self.assertTrue(predicate())

    def tearDown(self):
        for window in self.windows:
            window.close()
            # Also drain the GUI's queued completion callback before the next
            # test releases the window/archive, not just the native thread.
            self.wait(lambda:window._allow_close and not window._thread.isRunning())
        self.temp.cleanup()

    def window(self,**kwargs):
        window=MainWindow(state=self.state,worker_factory=FakeWorker,**kwargs)
        self.windows.append(window)
        window.show()
        QTest.qWait(30)
        return window

    def test_layout_logo_fonts_and_preview_without_inference(self):
        window=self.window(demo=True)
        self.assertEqual(window.chat_list.count(),3)
        self.assertEqual(window.status_label.text(),'Anteprima')
        self.assertEqual(window.new_button.text(),'Nuova chat')
        self.assertFalse(window.windowIcon().isNull())
        self.assertTrue(window._message_widgets[-1].cards.isVisible())
        window.resize(1024,700)
        QTest.qWait(30)
        self.assertLess(window.input.geometry().right(),window.width())
        target=ROOT/'build/gui-preview.png'
        target.parent.mkdir(parents=True,exist_ok=True)
        window.resize(1400,900)
        QTest.qWait(50)
        self.assertTrue(window.grab().save(str(target)))
        result=subprocess.run([sys.executable,'-c',
            "import sys;sys.path.insert(0,'src');from PySide6.QtWidgets import QApplication;"
            "from llocalmind.app import MainWindow;from llocalmind.state import LocalState;"
            "import tempfile;from PySide6.QtCore import QTimer;"
            "a=QApplication([]);w=MainWindow(state=LocalState(tempfile.mkdtemp()),demo=True);"
            "w.show();QTimer.singleShot(10,w.close);a.exec();"
            "assert not {'numpy','gguf','openvino'} & set(sys.modules)"],
            cwd=ROOT,env=os.environ,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_stream_stop_history_save_and_regenerate(self):
        window=self.window()
        window.load_model()
        self.wait(lambda:window.ready)
        window.input.setPlainText('Prima domanda')
        window.send()
        self.wait(lambda:bool(window.current['messages'][-1]['content']))
        window.send_or_stop()
        self.wait(lambda:not window.busy)
        self.assertEqual([m['role'] for m in window.current['messages']],['user','assistant'])
        self.assertEqual(window._worker.history,[dict(role='user',content='Prima domanda')])
        restored=LocalState(self.temp.name)
        self.assertEqual(restored.chats[0]['messages'],window.current['messages'])
        window.input.setPlainText('Seconda domanda')
        window.send()
        self.wait(lambda:not window.busy)
        self.assertEqual(len(window._worker.history),3)
        previous=copy.deepcopy(window.current['messages'])
        window.regenerate()
        self.wait(lambda:not window.busy)
        self.assertEqual(len(window.current['messages']),4)
        self.assertEqual(window._worker.history,previous[:-1])
        window._message_widgets[-1].copy_button.click()
        self.assertEqual(QApplication.clipboard().text(),window.current['messages'][-1]['content'])

    def test_close_during_generation_drains_thread(self):
        window=self.window()
        window.load_model()
        self.wait(lambda:window.ready)
        window.input.setPlainText('Domanda')
        window.send()
        window.close()
        self.wait(lambda:window._allow_close)
        self.assertFalse(window._thread.isRunning())
        self.assertEqual(len(LocalState(self.temp.name).chats[0]['messages']),2)

    def test_per_response_metrics_survive_reload_and_regeneration(self):
        window=self.window()
        window.load_model()
        self.wait(lambda:window.ready)
        for question in ('Prima domanda','Seconda domanda'):
            window.input.setPlainText(question)
            window.send()
            self.assertIsNotNone(window._active_reply, f'{question}: ready={window.ready} busy={window.busy} loading={window.loading} closing={window._closing} messages={len(window.current["messages"])}')
            self.assertTrue(window._active_reply.metrics_label.isHidden())
            self.wait(lambda:not window.busy)
            self.assertEqual(window._message_widgets[-1].metrics_label.text(),'2,50 tok/s · 50 token')
        restored=LocalState(self.temp.name)
        replies=[m for m in restored.chats[0]['messages'] if m['role']=='assistant']
        self.assertEqual(len(replies),2)
        self.assertTrue(all(m['stats']['rate']==2.5 for m in replies))
        window.state=restored
        window._render()
        labels=[w.metrics_label.text() for w in window._message_widgets if w.role=='assistant']
        self.assertEqual(labels,['2,50 tok/s · 50 token']*2)
        window.regenerate()
        self.assertTrue(window._active_reply.metrics_label.isHidden())
        self.wait(lambda:not window.busy)
        self.assertEqual(len(window.current['messages']),4)
        self.assertEqual(window.current['messages'][-1]['stats']['tokens'],50)

    def test_old_chats_and_unmeasurable_response_metrics(self):
        widget=Message('assistant','Una vecchia risposta')
        self.assertTrue(widget.metrics_label.isHidden())
        widget.set_stats(dict(tokens=1,rate=100.0))
        self.assertNotIn('100',widget.metrics_label.text())
        self.assertIn('non misurabili',widget.metrics_label.text())
        self.assertEqual(response_summary(dict(tokens=0,rate=None)),'')
        self.assertIsNone(clean_stats(dict(tokens=True,rate=2)))
        for invalid in (float('nan'),float('inf'),-1,10**1000):
            self.assertIsNone(clean_stats(dict(tokens=3,rate=invalid))['rate'])
        self.state.chats[0]['messages']=[dict(role='assistant',content='Testo',stats=dict(tokens=3,rate=float('nan')))]
        path=Path(self.temp.name)/'conversations.json'
        path.write_text(json.dumps(self.state.chats),encoding='utf-8')
        restored=LocalState(self.temp.name)
        self.assertFalse(restored.read_only)
        self.assertIsNone(restored.chats[0]['messages'][0]['stats']['rate'])
        restored.save_chats()
        widget.deleteLater()

    def test_atomic_storage_and_corrupt_archive_preserved(self):
        self.state.chats[0]['messages']=[dict(role='user',content='Caffè e tè')]
        self.state.save_chats()
        self.assertEqual(LocalState(self.temp.name).chats,self.state.chats)
        path=Path(self.temp.name)/'conversations.json'
        path.write_text('corrupt original')
        broken=LocalState(self.temp.name)
        with self.assertRaises(ValueError):broken.save_chats()
        self.assertEqual(path.read_text(),'corrupt original')
        self.assertEqual(list(Path(self.temp.name).glob('*.tmp')),[])
        with self.assertRaises(ValueError):validate_settings([])
        with self.assertRaises(ValueError):validate_settings(dict(temperature=float('nan')))

    def test_template_and_schedule_format(self):
        history=[dict(role='user',content='Uno'),dict(role='assistant',content='Due'),dict(role='user',content='Tre')]
        text=format_conversation(history)
        self.assertIn('<|im_start|>assistant\nDue<|im_end|>',text)
        self.assertTrue(text.endswith('<|im_start|>assistant\n<think>\n\n</think>\n\n'))
        for invalid in ([],history[:-1],[dict(role='assistant',content='No')],[None]):
            with self.assertRaises(ValueError):format_conversation(invalid)
        self.assertIsNotNone(schedule_parts('Piano\n09:00 — Studio\n10:00 — Pausa'))
        self.assertIsNone(schedule_parts('09:00 — Studio\n10:00 — Pausa\nConclusione'))
        self.assertIsNone(schedule_parts('99:00 — Studio\n10:00 — Pausa'))

    def test_settings_update_check_runs_without_model(self):
        window=self.window()
        with patch('llocalmind.update_worker.UpdateManager') as manager, \
                patch('llocalmind.app.QMessageBox.information') as notice, \
                patch('llocalmind.app.QMessageBox.warning') as warning:
            manager.return_value.check.return_value=None
            window.check_updates()
            self.wait(lambda:not window._update_jobs)
            self.assertFalse(warning.called, warning.call_args)
            notice.assert_called_once()
            self.assertFalse(window.ready)
            self.assertTrue(window._thread.isRunning())

    def test_real_stream_adapter_budget_cancellation_and_cleanup(self):
        # Exercise the real detokenizer with a tiny fake token vocabulary.
        class Tokenizer:
            tokens=['Ciao','!']
            token_types=[1,1]
            _byte_decoder={c:ord(c) for c in 'Ciao!'}
            def encode(self,text,add_bos=False):return [0,1]
        class Model:
            max_seq_len=256
            last_stream_timings=dict(generation_seconds=1,prefill_seconds=.5)
            def stream(self,*args,**kwargs):
                try:
                    self.last_stream_timings=dict(generation_seconds=.1,prefill_seconds=.5)
                    yield 1,0
                    self.last_stream_timings=dict(generation_seconds=1.1,prefill_seconds=.5)
                    yield 2,1
                finally:self.drained=True
        worker=ModelWorker()
        worker.model=Model()
        worker.tokenizer=Tokenizer()
        output=[];stats=[];done=[];errors=[]
        worker.token.connect(output.append)
        worker.stats.connect(stats.append)
        worker.reply_finished.connect(done.append)
        worker.error.connect(errors.append)
        worker.generate([dict(role='user',content='Domanda')],self.state.settings)
        self.assertEqual(''.join(output),'Ciao!')
        self.assertEqual(stats[-1]['rate'],1)
        self.assertEqual(done[-1],'complete')
        self.assertTrue(worker.model.drained)
        self.assertFalse(errors)
        worker.model.max_seq_len=2
        worker.generate([dict(role='user',content='Domanda')],self.state.settings)
        self.assertEqual(done[-1],'error')
        self.assertIn('contesto',errors[-1])
        worker.model.max_seq_len=256
        worker.token.connect(lambda text:worker.stop.set())
        worker.generate([dict(role='user',content='Domanda')],self.state.settings)
        self.assertEqual(done[-1],'stopped')
        self.assertEqual(stats[-1]['tokens'],1)
        self.assertIsNone(stats[-1]['rate'])
        self.assertTrue(worker.model.drained)


if __name__=='__main__':unittest.main()

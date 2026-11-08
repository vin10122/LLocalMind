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
from PySide6.QtWidgets import QApplication,QDialog
from llocalmind.app import MainWindow
from llocalmind.inference import ModelWorker
from llocalmind.metrics import clean_stats, response_summary
from llocalmind.prompts import format_conversation
from llocalmind.state import LocalState,validate_settings
from llocalmind.theme import apply_theme
from llocalmind.widgets import Message,schedule_parts
from llocalmind.settings_dialog import SettingsDialog
from PIL import Image


class FakeWorker(ModelWorker):
    @Slot(str,dict)
    def load(self,path,options):
        self.loaded.emit('Test model')

    @Slot(list,dict)
    def generate(self,messages,options):
        self.history=copy.deepcopy(messages)
        self.options=copy.deepcopy(options)
        count=0
        for _ in range(50):
            if self.stop.is_set():break
            count+=1
            self.token.emit('test ')
            QThread.msleep(3)
        self.stats.emit(dict(tokens=count,first_token=.01 if count else None,rate=2.5 if count>1 else None))
        self.reply_finished.emit('stopped' if self.stop.is_set() else 'complete')


class SearchFailureWorker(FakeWorker):
    fail=True

    @Slot(list,dict)
    def generate(self,messages,options):
        if self.fail:
            self.error.emit('DuckDuckGo richiede una verifica anti-bot.')
            self.reply_finished.emit('error')
        else:super().generate(messages,options)


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.state=LocalState(self.temp.name)
        self.state.settings['engine']='optimized'  # Legacy-controller fixtures remain explicit.
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

    def test_web_timing_includes_search_in_first_token_and_persists_phase_metrics(self):
        from unittest.mock import Mock
        from llocalmind.web_search import WebResult
        worker=ModelWorker();worker.vision=Mock();worker.vision.projector=None
        worker.vision.generate.return_value=dict(tokens=2,rate=2,first_token=.5,prefill=.2)
        clock=[10.0];stats=[];errors=[]
        worker.stats.connect(stats.append);worker.error.connect(errors.append)
        def search(*args,**kwargs):
            clock[0]+=2
            return [WebResult('Source','https://example.com','','Evidence',provider='tavily')]
        options=dict(self.state.settings,engine='vision',_web_search=True,web_profile='detail',
                     _attachment_directory=str(self.state.directory))
        with patch('llocalmind.web_search.search_and_fetch',side_effect=search) as api, \
                patch('llocalmind.inference.time.perf_counter',side_effect=lambda:clock[0]), \
                patch('llocalmind.performance.record'),patch('llocalmind.performance.memory_snapshot',return_value={}):
            worker.generate([dict(role='user',content='Question')],options)
        self.assertFalse(errors,errors)
        self.assertEqual(api.call_args.kwargs['profile'],'detail')
        cleaned=clean_stats(stats[0])
        self.assertEqual(cleaned['web_seconds'],2)
        self.assertEqual(cleaned['first_token'],2.5)
        self.assertEqual(cleaned['prefill'],.2)
        self.assertEqual(cleaned['web_sources'],1)
        self.assertEqual(cleaned['web_profile'],'detail')

    def test_llama_default_and_one_time_migration_preserve_explicit_legacy_choice(self):
        root=Path(self.temp.name)/'migration'
        root.mkdir()
        self.assertEqual(LocalState(root).settings['engine'],'vision')
        config=root/'settings.json'
        config.write_text(json.dumps(dict(engine='optimized',vision_executable=sys.executable)))
        migrated=LocalState(root)
        self.assertEqual(migrated.settings['engine'],'vision')
        migrated.save_settings(dict(migrated.settings,engine='optimized'))
        self.assertEqual(LocalState(root).settings['engine'],'optimized')
        config.write_text(json.dumps(dict(engine='optimized',vision_executable='')))
        self.assertEqual(LocalState(root).settings['engine'],'optimized')

    def test_llama_settings_accept_text_without_projector(self):
        model=Path(self.temp.name)/'text.gguf';model.touch()
        values=dict(self.state.settings,engine='vision',model_path=str(model),
                    vision_executable=sys.executable,vision_projector='')
        dialog=SettingsDialog(values,lambda:None)
        dialog.web_profile.setCurrentIndex(dialog.web_profile.findData('detail'))
        with patch('llocalmind.settings_dialog.QMessageBox.warning') as warning:
            dialog.accept()
        warning.assert_not_called()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.values['vision_projector'],'')
        self.assertEqual(dialog.values['web_profile'],'detail')
        self.assertEqual(dialog.engine.itemData(0),'vision')

    def test_llama_web_research_preserves_pixels_and_keeps_images_off_search_api(self):
        from unittest.mock import Mock
        from llocalmind.images import import_image
        from llocalmind.web_search import WebResult
        source=Path(self.temp.name)/'research.png'
        Image.new('RGB',(32,32),'blue').save(source)
        image=import_image(source,self.state.directory)
        history=[dict(role='user',content='Che cosa significa?',images=[image])]
        original=copy.deepcopy(history)
        worker=ModelWorker();worker.vision=Mock()
        worker.vision.projector=Path(self.temp.name)/'mmproj.gguf'
        worker.vision.generate.return_value=dict(tokens=2,rate=2)
        options=dict(self.state.settings,engine='vision',_web_search=True,
                     _attachment_directory=str(self.state.directory))
        errors=[];worker.error.connect(errors.append)
        with patch('llocalmind.web_search.search_and_fetch',return_value=[WebResult('Source','https://example.com','','Evidence',provider='tavily')]) as search, \
                patch('llocalmind.performance.record'),patch('llocalmind.performance.memory_snapshot',return_value={}):
            worker.generate(history,options)
        self.assertFalse(errors,errors)
        self.assertEqual(search.call_args.args[0],'Che cosa significa?')
        request=worker.vision.generate.call_args.args[0]
        self.assertIn('non attendibili',request[0]['content'])
        self.assertIn('Evidence',request[-1]['content'][0]['text'])
        self.assertIn('data:image/png;base64,',request[-1]['content'][1]['image_url']['url'])
        self.assertEqual(history,original)
        worker.vision.generate.reset_mock();worker.vision.projector=None
        with patch('llocalmind.web_search.search_and_fetch') as search:
            worker.generate(history,options)
        search.assert_not_called();worker.vision.generate.assert_not_called()
        self.assertIn('mmproj',errors[-1])

    def test_dark_settings_persist_preserve_session_and_keep_links_readable(self):
        model=Path(self.temp.name)/'model.gguf';model.touch()
        self.state.settings['model_path']=str(model)
        window=self.window();window.load_model();self.wait(lambda:window.ready)
        window.current['messages']=[dict(role='user',content='Question'),
            dict(role='assistant',content='[Source](https://example.com)')]
        window._render();window.input.setPlainText('Keep this draft')
        thread=window._thread;loads=[]
        window.load_requested.connect(lambda *args:loads.append(args))
        def dark(dialog):
            dialog.dark_mode.setChecked(True);dialog.accept();return dialog.result()
        with patch('llocalmind.settings_dialog.SettingsDialog.exec',dark):window.settings()
        self.assertTrue(window.state.settings['dark_mode'])
        self.assertTrue(LocalState(self.temp.name).settings['dark_mode'])
        self.assertIn('#000000',window.styleSheet())
        self.assertEqual(window.input.toPlainText(),'Keep this draft')
        self.assertIs(window._thread,thread);self.assertFalse(loads)
        body=window._message_widgets[-1].body
        iterator=body.document().begin().begin();colors=[]
        while not iterator.atEnd():
            fragment=iterator.fragment()
            if fragment.isValid() and fragment.charFormat().isAnchor():
                colors.append(fragment.charFormat().foreground().color().name())
            iterator+=1
        self.assertEqual(colors,['#8be0ae'])
        # QTextBlock iterators must not outlive their document when the UI is
        # rebuilt below for a language/theme change.
        del iterator,fragment,body
        window.set_italian_interface(True)
        self.assertTrue(window._message_widgets[0].prompt_frame.dark_mode)
        self.assertIn('#000000',window.styleSheet())
        window.change_language('en')
        self.assertTrue(window.state.settings['dark_mode'])
        def light(dialog):
            dialog.dark_mode.setChecked(False);dialog.accept();return dialog.result()
        with patch('llocalmind.settings_dialog.SettingsDialog.exec',light):window.settings()
        self.assertFalse(window.state.settings['dark_mode'])
        self.assertNotIn('#000000',window.styleSheet())
        self.assertTrue(window.state.settings['italian_interface'])
        self.assertFalse(loads)

    def test_language_switch_preserves_draft_history_model_and_pending_images(self):
        window=self.window()
        window.ready=True
        window.current['messages']=[dict(role='user',content='Copia'),dict(role='assistant',content='Pronto')]
        window.current['title']='Impostazioni'
        window.input.setPlainText('Bozza italiana ancora qui')
        window._pending_images=[dict(id='a'*64+'.png',name='foto.png')]
        loaded=[]
        window.load_requested.connect(lambda *args:loaded.append(args))
        original_thread=window._thread
        window.change_language('en')
        self.assertEqual(window.new_button.text(),'New chat')
        self.assertEqual(window.language_button.text(),'Language')
        self.assertEqual(window.input.placeholderText(),'Where shall we start?')
        self.assertEqual(window.input.toPlainText(),'Bozza italiana ancora qui')
        self.assertEqual(window.current['title'],'Impostazioni')
        self.assertEqual(window.current['messages'][-1]['content'],'Pronto')
        self.assertEqual(window._message_widgets[0].bubble.text(),'Copia')
        self.wait(lambda:window.attachments.isVisible())
        self.assertEqual(window._pending_images[0]['name'],'foto.png')
        self.assertIs(window._thread,original_thread)
        self.assertFalse(loaded)
        self.assertEqual(LocalState(self.temp.name).settings['language'],'en')
        dialog=SettingsDialog(window.state.settings,lambda:None)
        self.assertEqual(dialog.windowTitle(),'Settings · LLocalMind')
        self.assertEqual(dialog.language.currentData(),'en')
        self.assertEqual(dialog.collected_values()['language'],'en')
        dialog.deleteLater()
        window.change_language('it')
        self.assertEqual(window.new_button.text(),'Nuova chat')
        self.assertEqual(window.input.toPlainText(),'Bozza italiana ancora qui')

    def test_italian_appearance_is_persistent_and_does_not_change_language_or_inference(self):
        from PySide6.QtCore import Qt
        from llocalmind.state import engine_signature
        window=self.window()
        window.change_language('en')
        before=engine_signature(window.state.settings)
        window.current['messages']=[dict(role='user',content='Original text')]
        window._render()
        window.input.setPlainText('Keep this draft')
        calls=[]
        window.load_requested.connect(lambda *args:calls.append(args))
        window.generate_requested.connect(lambda *args:calls.append(args))
        window.busy=True
        window._buttons()
        QTest.mouseClick(window.theme_switch,Qt.MouseButton.LeftButton)
        self.assertTrue(window.state.settings['italian_interface'])
        self.assertTrue(window.busy)
        self.assertFalse(window._stop.is_set())
        self.assertEqual(window.state.settings['language'],'en')
        self.assertEqual(window.new_button.text(),'New chat')
        self.assertEqual(window.send_button.text(),'Fratello, fermati 🍝')
        self.assertEqual(window.input.toPlainText(),'Keep this draft')
        self.assertEqual(window.current['messages'][0]['content'],'Original text')
        self.assertTrue(window._message_widgets[0].prompt_frame.italian_interface)
        self.assertEqual(engine_signature(window.state.settings),before)
        self.assertFalse(calls)
        window.send_button.click()
        self.assertTrue(window._stop.is_set())
        window._stop.clear()
        window.busy=False
        window._buttons()
        self.assertEqual(window.send_button.text(),'Dottore, parti 🍕')
        QTest.keyClick(window.theme_switch,Qt.Key.Key_Space)
        self.assertFalse(window.state.settings['italian_interface'])
        self.assertEqual(window.send_button.width(),48)
        self.assertFalse(window._message_widgets[0].prompt_frame.italian_interface)
        QTest.keyClick(window.theme_switch,Qt.Key.Key_Space)
        self.assertTrue(LocalState(self.temp.name).settings['italian_interface'])
        self.assertEqual(LocalState(self.temp.name).settings['language'],'en')
        window.change_language('it')
        self.assertTrue(window.theme_switch.isChecked())
        self.assertEqual(window.send_button.text(),'Dottore, parti 🍕')

    def test_image_profile_changes_next_request_without_reloading_or_rewriting_chat(self):
        from llocalmind.state import engine_signature
        self.state.settings['engine']='vision'
        window=self.window()
        window.current['messages']=[dict(role='user',content='Keep this history')]
        window.input.setPlainText('Keep this draft')
        before=engine_signature(window.state.settings)
        calls=[]
        window.load_requested.connect(lambda *args:calls.append(args))
        window.generate_requested.connect(lambda *args:calls.append(args))
        window.vision_quality.setCurrentIndex(window.vision_quality.findData('fast'))
        self.assertEqual(window._options()['vision_image_profile'],'fast')
        self.assertEqual(LocalState(self.temp.name).settings['vision_image_profile'],'fast')
        self.assertEqual(engine_signature(window.state.settings),before)
        self.assertEqual(window.current['messages'][0]['content'],'Keep this history')
        self.assertEqual(window.input.toPlainText(),'Keep this draft')
        self.assertFalse(calls)
        window.busy=True;window._buttons()
        self.assertFalse(window.vision_quality.isEnabled())
        window.busy=False
        window.change_language('en')
        self.assertEqual(window.vision_quality.currentData(),'fast')
        self.assertIn('Fast',window.vision_quality.currentText())
        window.change_language('it')

    def test_language_cannot_change_during_generation(self):
        window=self.window()
        window.busy=True
        window._buttons()
        self.assertFalse(window.language_button.isEnabled())
        window.change_language('en')
        self.assertEqual(window.state.settings['language'],'it')
        self.assertEqual(window.new_button.text(),'Nuova chat')
        window.busy=False

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

    def test_failed_web_search_is_visible_persisted_and_retryable(self):
        window=MainWindow(state=self.state,worker_factory=SearchFailureWorker)
        self.windows.append(window)
        window.show()
        window.load_model()
        self.wait(lambda:window.ready)
        window.web_search_button.setChecked(True)
        window.input.setPlainText('Quando gioca la squadra?')
        window.send()
        self.wait(lambda:not window.busy)
        message=window.current['messages'][-1]
        self.assertEqual(message['content'],'')
        self.assertIn('anti-bot',message['error'])
        self.assertIn('Rigenera',window._message_widgets[-1].body.toPlainText())
        self.assertNotIn('Risposta non completata',window._message_widgets[-1].body.toPlainText())
        self.assertEqual(LocalState(self.temp.name).chats[0]['messages'][-1]['error'],message['error'])
        window._render()
        self.assertIn('anti-bot',window._message_widgets[-1].body.toPlainText())
        window._worker.fail=False
        window.regenerate()
        self.wait(lambda:not window.busy)
        self.assertNotIn('error',window.current['messages'][-1])
        self.assertTrue(window.current['messages'][-1]['content'])
        self.assertTrue(window._worker.options['_web_search'])

    def test_web_search_is_opt_in_persisted_and_used_again_on_regenerate(self):
        window=self.window()
        window.load_model()
        self.wait(lambda:window.ready)
        self.assertFalse(window.web_search_button.isChecked())
        self.assertIn('Tavily',window.web_search_button.toolTip())
        window.web_search_button.setChecked(True)
        window.input.setPlainText('Domanda recente')
        window.send()
        self.wait(lambda:not window.busy)
        self.assertTrue(window._worker.options['_web_search'])
        self.assertTrue(window.current['messages'][0]['web_search'])
        self.assertEqual(window.current['messages'][0]['web_provider'],'tavily')
        self.assertIn('Ricerca web · Tavily',window._message_widgets[0].bubble.text())
        self.assertTrue(LocalState(self.temp.name).chats[0]['messages'][0]['web_search'])
        # Existing conversations keep their original provider attribution until
        # the user requests another search with the new transport.
        window.current['messages'][0].pop('web_provider')
        window._render()
        self.assertIn('DuckDuckGo',window._message_widgets[0].bubble.text())
        window.regenerate()
        self.wait(lambda:not window.busy)
        self.assertTrue(window._worker.options['_web_search'])
        self.assertEqual(window.current['messages'][0]['web_provider'],'tavily')
        self.assertIn('Tavily',window._message_widgets[0].bubble.text())

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

    def test_stream_bursts_are_coalesced_without_losing_final_text(self):
        window=self.window()
        window.current['messages']=[dict(role='assistant',content='')]
        widget=window._active_reply=window._add_message('assistant','',pending=True)
        with patch.object(widget,'update_text',wraps=widget.update_text) as render:
            for _ in range(100):window._token('x')
            self.assertEqual(render.call_count,1)
            self.wait(lambda:render.call_count==2)
            window._reply_finished('complete')
            self.assertEqual(widget.text,'x'*100)
            self.assertEqual(render.call_count,3)

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
        invalid=self.state.chats[0].copy()
        invalid['messages']=[dict(role='user',content='Question',web_search='yes')]
        path.write_text(json.dumps([invalid]),encoding='utf-8')
        self.assertTrue(LocalState(self.temp.name).read_only)

    def test_image_only_send_persistence_and_text_mode_guard(self):
        self.state.settings['engine']='vision'
        window=self.window()
        self.assertTrue(window.web_search_button.isEnabled())
        window.load_model()
        self.wait(lambda:window.ready)
        source=Path(self.temp.name)/'red.png'
        Image.new('RGB',(32,32),'red').save(source)
        window.add_image(source)
        self.assertEqual(len(window._pending_images),1)
        self.assertFalse(window.attachments.isHidden())
        window._clear_images()
        self.assertTrue(window.attachments.isHidden())
        window.add_image(source)
        window.send()
        self.wait(lambda:not window.busy)
        sent=window._worker.history[0]
        self.assertEqual(sent['content'],'Descrivi questa immagine.')
        self.assertEqual(sent['images'][0]['name'],'red.png')
        self.assertFalse(window._pending_images)
        source.unlink()
        restored=LocalState(self.temp.name)
        self.assertEqual(restored.chats[0]['messages'][0],sent)
        window.state=restored
        window._render()
        window.state.settings['engine']='optimized'
        window.input.setPlainText('Ancora?')
        window.send()
        self.assertFalse(window.busy)
        self.assertIn('immagini',window.notice.text())
        self.assertEqual(window.input.toPlainText(),'Ancora?')

    def test_vision_worker_closes_native_and_preserves_cancel_status(self):
        from unittest.mock import Mock
        from flash_moe.multimodal import VisionCancelled
        worker=ModelWorker()
        native=worker.model=Mock()
        worker.tokenizer=Mock()
        model=Path(self.temp.name)/'model.gguf'
        model.touch()
        options=dict(self.state.settings,engine='vision',_attachment_directory=self.temp.name)
        done=[];errors=[]
        worker.reply_finished.connect(done.append)
        worker.error.connect(errors.append)
        with patch('flash_moe.multimodal.LocalVisionModel') as factory:
            engine=factory.return_value
            engine.encoder_device='CPU'
            engine.generate.return_value=dict(tokens=2,rate=2)
            worker.load(str(model),options)
            native.backend.close.assert_called_once()
            native.store.close.assert_called_once()
            self.assertIsNone(worker.model)
            worker.generate([dict(role='user',content='Domanda')],options)
            engine.generate.side_effect=VisionCancelled()
            worker.generate([dict(role='user',content='Domanda')],options)
            self.assertEqual(done,['complete','stopped'])
            self.assertFalse(errors)
            worker.shutdown()
            engine.close.assert_called_once()

    def test_template_and_schedule_format(self):
        history=[dict(role='user',content='Uno'),dict(role='assistant',content='Due'),dict(role='user',content='Tre')]
        text=format_conversation(history)
        self.assertIn("Rispondi nella lingua dell'utente",text)
        self.assertIn('dai una risposta chiara e completa',text.casefold())
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

    def test_runtime_button_preserves_unfinished_settings(self):
        values=dict(self.state.settings,engine='vision')
        dialog=SettingsDialog(values,lambda:None,can_install_vision=True)
        dialog.vision_paths['vision_projector'].setText('D:/models/my-mmproj.gguf')
        self.assertTrue(dialog.install_vision.isEnabled())
        self.assertNotIn('vision_encoder',dialog.collected_values())
        dialog.request_vision_install()
        self.assertEqual(dialog.result(),SettingsDialog.InstallVision)
        self.assertEqual(dialog.values['vision_projector'],'D:/models/my-mmproj.gguf')
        dialog.deleteLater()

    def test_runtime_install_saves_executable_and_restores_settings_draft(self):
        window=self.window()
        target=Path(self.temp.name)/'llama-server.exe'
        target.touch()
        window._vision_install_draft=dict(self.state.settings,engine='vision',vision_projector='D:/mmproj.gguf')
        with patch('llocalmind.vision_runtime.RuntimeInstaller') as installer, \
                patch('llocalmind.app.QMessageBox.information'), \
                patch('llocalmind.app.QMessageBox.warning') as warning,patch.object(window,'settings') as settings:
            installer.return_value.install.return_value=target
            window._start_update('runtime')
            self.wait(lambda:not window._update_jobs)
            self.assertFalse(warning.called,warning.call_args)
            self.assertEqual(self.state.settings['vision_executable'],str(target))
            restored=settings.call_args.kwargs['draft']
            self.assertEqual(restored['vision_projector'],'D:/mmproj.gguf')
            self.assertEqual(restored['vision_executable'],str(target))
            self.assertEqual(restored['engine'],'vision')
            self.assertEqual(LocalState(self.temp.name).settings['vision_executable'],str(target))

    def test_runtime_cancellation_does_not_change_previous_settings(self):
        from llocalmind.vision_runtime import RuntimeInstallCancelled
        window=self.window()
        previous=self.state.settings.copy()
        def install(*,cancel,progress):
            progress(10);cancel.set()
            raise RuntimeInstallCancelled('cancelled')
        with patch('llocalmind.vision_runtime.RuntimeInstaller') as installer, \
                patch('llocalmind.app.QMessageBox.warning') as warning,patch.object(window,'settings') as settings:
            installer.return_value.install.side_effect=install
            window._start_update('runtime')
            self.wait(lambda:not window._update_jobs)
            self.assertEqual(self.state.settings,previous)
            warning.assert_not_called();settings.assert_not_called()

    def test_replacing_runtime_reloads_engine_even_if_path_was_already_saved(self):
        self.state.settings.update(model_path='model.gguf',engine='vision',vision_executable='old.exe')
        window=self.window()
        window.load_model()
        self.wait(lambda:window.ready)
        self.state.save_settings(dict(self.state.settings,vision_executable='new.exe'))
        with patch('llocalmind.app.SettingsDialog') as factory,patch.object(window,'load_model') as reload:
            factory.InstallVision=SettingsDialog.InstallVision
            factory.return_value.exec.return_value=QDialog.DialogCode.Accepted
            factory.return_value.values=self.state.settings.copy()
            window.settings()
            reload.assert_called_once()

    def test_close_during_runtime_install_drains_download_thread(self):
        import threading
        from llocalmind.vision_runtime import RuntimeInstallCancelled
        window=self.window()
        started=threading.Event()
        def install(*,cancel,progress):
            started.set();cancel.wait(2)
            raise RuntimeInstallCancelled('cancelled')
        with patch('llocalmind.vision_runtime.RuntimeInstaller') as installer:
            installer.return_value.install.side_effect=install
            window._start_update('runtime')
            self.wait(started.is_set)
            window.close()
            self.wait(lambda:window._allow_close)
            self.assertFalse(window._update_jobs)

    def test_real_stream_adapter_budget_cancellation_and_cleanup(self):
        # Exercise the real detokenizer with a tiny fake token vocabulary.
        class Tokenizer:
            tokens=['Ciao','!']
            token_types=[1,1]
            _byte_decoder={c:ord(c) for c in 'Ciao!'}
            def encode(self,text,add_bos=False):
                self.last_text=text
                return [0,1]
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
        options=dict(self.state.settings,max_tokens=128)
        with patch('llocalmind.web_search.search_and_fetch') as search:
            worker.generate([dict(role='user',content='Domanda')],options)
            search.assert_not_called()
        self.assertEqual(''.join(output),'Ciao!')
        self.assertEqual(stats[-1]['rate'],1)
        self.assertEqual(done[-1],'complete')
        self.assertTrue(worker.model.drained)
        self.assertFalse(errors)
        from llocalmind.web_search import WebResult
        worker.stop.clear()
        options['_web_search']=True
        with patch('llocalmind.web_search.search_and_fetch',
                   return_value=[WebResult('Fonte','https://example.com','',
                                           'Estratto verificato.')]) as search:
            worker.generate([dict(role='user',content='Domanda recente',web_search=True)],options)
        search.assert_called_once()
        self.assertIn('Domanda recente',worker.tokenizer.last_text)
        self.assertIn('Estratto verificato.',worker.tokenizer.last_text)
        self.assertIn('https://example.com',worker.tokenizer.last_text)
        self.assertIn('fonti esterne non attendibili',worker.tokenizer.last_text)
        self.assertEqual(done[-1],'complete')
        from llocalmind.web_search import WebSearchError
        before=(len(output),len(stats),worker.tokenizer.last_text)
        worker.model.drained=False
        with patch('llocalmind.web_search.search_and_fetch',side_effect=WebSearchError('Search blocked')):
            worker.generate([dict(role='user',content='Domanda recente',web_search=True)],options)
        self.assertEqual(done[-1],'error')
        self.assertEqual((len(output),len(stats),worker.tokenizer.last_text),before)
        self.assertFalse(worker.model.drained)
        options['_web_search']=False
        worker.model.max_seq_len=2
        worker.generate([dict(role='user',content='Domanda')],options)
        self.assertEqual(done[-1],'error')
        self.assertIn('contesto',errors[-1])
        worker.model.max_seq_len=256
        worker.token.connect(lambda text:worker.stop.set())
        worker.generate([dict(role='user',content='Domanda')],options)
        self.assertEqual(done[-1],'stopped')
        self.assertEqual(stats[-1]['tokens'],1)
        self.assertIsNone(stats[-1]['rate'])
        self.assertTrue(worker.model.drained)


if __name__=='__main__':unittest.main()

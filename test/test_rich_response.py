"""Protocol and real Qt rendering checks, without a model or network."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from llocalmind.rich_response import parse_response
from llocalmind.prompts import system_prompt,format_conversation
from llocalmind.state import validate_settings,DEFAULTS,LocalState


def answer(widgets=None,**overrides):
    data=dict(version=1,fallback='Readable summary',widgets=widgets or [
        dict(type='card',title='Summary',text='<script>literal text</script>'),
        dict(type='table',title='Comparison',columns=['A','B'],rows=[['one','two']]),
        dict(type='checklist',title='Steps',items=['First step','Second step'])])
    data.update(overrides)
    return 'Introduction\n\n```llocalmind-ui\n'+json.dumps(data)+'\n```'


class ProtocolTests(unittest.TestCase):
    def test_complete_response_and_copy(self):
        prose,widgets,copy=parse_response(answer())
        self.assertEqual(prose,'Introduction')
        self.assertEqual(len(widgets),3)
        self.assertEqual(copy,'Introduction\n\nReadable summary')

    def test_stream_hides_protocol_and_final_truncation_is_visible(self):
        partial=answer()[:-10]
        self.assertEqual(parse_response(partial,pending=True)[:2],('Introduction',[]))
        self.assertEqual(parse_response(partial),(partial,[],partial))

    def test_invalid_and_oversized_widgets_remain_text(self):
        cases=[answer(version=True),answer(version=2),answer(fallback=''),
               answer(widgets=[dict(type='execute',title='Oops',text='run')]),
               answer(widgets=[dict(type='table',title='Bad',columns=['A'],rows=[['x','y']])]),
               answer(widgets=[dict(type='checklist',title='Too many',items=['x']*17)]),
               answer(widgets=[dict(type='card',title='Huge',text='x'*24001)]),
               answer(widgets=[dict(type='card',title='Object',text={'html':'oops'})]),
               answer()+'\nAdditional unparsed content',
               '```llocalmind-ui\nnot JSON\n```']
        for text in cases:
            with self.subTest(text=text[:80]):
                self.assertEqual(parse_response(text),(text,[],text))

    def test_plain_markdown_is_unchanged(self):
        for text in ('Hello','```python\nprint(1)\n```','Inline ```llocalmind-ui example'):
            self.assertEqual(parse_response(text),(text,[],text))

    def test_prompt_opt_in_and_history_fallback(self):
        from llocalmind.images import chat_messages
        self.assertNotIn('llocalmind-ui',system_prompt())
        for language in ('it','en'):
            self.assertIn('llocalmind-ui',system_prompt(language,intelligent_ui=True))
        history=[dict(role='user',content='one'),dict(role='assistant',content=answer()),dict(role='user',content='two')]
        rendered=format_conversation(history)
        self.assertIn('Readable summary',rendered)
        self.assertNotIn('llocalmind-ui',rendered)
        vision=chat_messages(history,'.',intelligent_ui=True)
        self.assertIn('llocalmind-ui',vision[0]['content'])
        self.assertEqual(vision[2]['content'],'Introduction\n\nReadable summary')

    def test_setting_validation_and_persistence(self):
        import tempfile
        from llocalmind.state import engine_signature
        self.assertFalse(DEFAULTS['intelligent_ui'])
        with self.assertRaises(ValueError):validate_settings(dict(DEFAULTS,intelligent_ui='yes'))
        with tempfile.TemporaryDirectory() as directory:
            state=LocalState(directory)
            state.save_settings(dict(state.settings,intelligent_ui=True))
            self.assertTrue(LocalState(directory).settings['intelligent_ui'])
            self.assertEqual(engine_signature(state.settings),engine_signature(dict(state.settings,intelligent_ui=False)))


class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        from llocalmind.theme import apply_theme
        cls.app=QApplication.instance() or QApplication([])
        apply_theme(cls.app)

    def test_widgets_controls_copy_and_literal_text_in_both_themes(self):
        from PySide6.QtWidgets import QCheckBox,QLabel,QScrollArea
        from PySide6.QtCore import Qt
        from llocalmind.widgets import Message
        from llocalmind.theme import DARK_STYLE
        for dark in (False,True):
            widget=Message('assistant',answer(),dark_mode=dark)
            if dark:widget.setStyleSheet(DARK_STYLE)
            widget.resize(760,800);widget.show();self.app.processEvents()
            self.assertFalse(widget.rich_panel.isHidden())
            self.assertEqual(len(widget.rich_panel.findChildren(QCheckBox)),2)
            check=widget.rich_panel.findChild(QCheckBox)
            check.click();self.assertTrue(check.isChecked())
            literal=next(x for x in widget.rich_panel.findChildren(QLabel) if '<script>' in x.text())
            self.assertEqual(literal.textFormat(),Qt.TextFormat.PlainText)
            self.assertEqual(len(widget.rich_panel.findChildren(QScrollArea)),1)
            copied=[];widget.copy_requested.connect(copied.append)
            widget.copy_button.click()
            self.assertEqual(copied,['Introduction\n\nReadable summary'])
            widget.close();widget.deleteLater();self.app.processEvents()

    def test_pending_and_invalid_do_not_build_widgets(self):
        from llocalmind.widgets import Message
        widget=Message('assistant',answer(),pending=True)
        self.assertTrue(widget.rich_panel.isHidden())
        self.assertNotIn('llocalmind-ui',widget.body.toPlainText())
        self.assertFalse(widget.copy_button.isEnabled())
        widget.update_text(answer())
        self.assertFalse(widget.rich_panel.isHidden())
        malformed=answer()[:-5]
        widget.update_text(malformed)
        self.assertTrue(widget.rich_panel.isHidden())
        self.assertIn('"version": 1',widget.body.toPlainText())
        widget.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()

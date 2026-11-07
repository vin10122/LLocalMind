"""Real HTTP transport and attachment tests; no trained GGUF is downloaded."""
import base64
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from PIL import Image,PngImagePlugin
from flash_moe.multimodal import LocalVisionModel,MultiModalProjector,VisionCancelled
from flash_moe.model import Qwen3MoEModel
from llocalmind.images import chat_messages,import_image,validate_images
from llocalmind.prompts import format_conversation
from llocalmind.state import LocalState


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def do_POST(self):
        self.server.payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.auth=self.headers.get('Authorization')
        self.server.received.set()
        if self.server.reject:
            data=b'{"error":"context limit exceeded"}'
            self.send_response(400)
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_response(200)
        self.send_header('Content-Type','text/event-stream')
        self.send_header('Connection','close')
        self.end_headers()
        self.close_connection=True
        if self.server.stall:
            self.server.release.wait(4)
            return
        events=[dict(choices=[dict(delta=dict(content='Un quadrato '))]),
                dict(choices=[dict(delta=dict(content='rosso.'))]),
                dict(choices=[],usage=dict(completion_tokens=5),timings=dict(predicted_ms=2000,prompt_ms=1250))]
        if self.server.no_timings:events[-1].pop('timings')
        for event in events:
            self.wfile.write(b'data: '+json.dumps(event).encode()+b'\n\n')
        if not self.server.truncate:self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()


class MultimodalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.source=self.root/'image.png'
        metadata=PngImagePlugin.PngInfo();metadata.add_text('private','must be removed')
        Image.new('RGB',(64,32),'red').save(self.source,pnginfo=metadata)
        self.item=import_image(self.source,self.root/'data')
        self.server=None
        self.model=self.root/'model.gguf';self.model.touch()
        self.projector=self.root/'mmproj.gguf';self.projector.touch()

    def tearDown(self):
        if self.server:
            self.server.release.set();self.server.shutdown();self.server.server_close()
        self.temp.cleanup()

    def engine(self):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.received=threading.Event();self.server.release=threading.Event()
        self.server.reject=self.server.stall=self.server.truncate=self.server.no_timings=False
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        engine=LocalVisionModel(self.model,self.projector,sys.executable,log_path=self.root/'vision.log',encoder='cpu')
        engine.port=self.server.server_port
        engine.process=Mock();engine.process.poll.return_value=None
        return engine

    def history(self):return [dict(role='user',content='Cosa vedi?',images=[self.item])]

    def test_owned_pixels_persist_without_source_or_metadata(self):
        state=LocalState(self.root/'data')
        state.chats[0]['messages']=self.history();state.save_chats()
        self.source.unlink()
        restored=LocalState(self.root/'data')
        self.assertFalse(restored.read_only)
        self.assertEqual(restored.chats[0]['messages'],self.history())
        payload=chat_messages(self.history(),state.directory)
        data=base64.b64decode(payload[1]['content'][1]['image_url']['url'].split(',')[1])
        import io
        image=Image.open(io.BytesIO(data))
        self.assertEqual(image.size,(64,32))
        self.assertEqual(image.info,{})
        self.assertEqual(image.getpixel((0,0)),(255,0,0))
        with self.assertRaisesRegex(ValueError,'immagini'):format_conversation(self.history())

    def test_spatial_information_is_preserved_in_transmitted_pixels(self):
        image=Image.new('RGB',(56,28),'blue');image.paste('red',(0,0,28,28))
        image.save(self.source);left=import_image(self.source,self.root/'data')
        image.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(self.source)
        right=import_image(self.source,self.root/'data')
        a=chat_messages([dict(role='user',content='Dove si trova il rosso?',images=[left])],self.root/'data')
        b=chat_messages([dict(role='user',content='Dove si trova il rosso?',images=[right])],self.root/'data')
        self.assertNotEqual(a[1]['content'][1],b[1]['content'][1])

    def test_resize_transparency_validation_and_corruption(self):
        Image.new('RGBA',(4096,512),(0,0,0,0)).save(self.source)
        item=import_image(self.source,self.root/'data')
        image=Image.open(self.root/'data/images'/item['id'])
        self.assertEqual(image.size,(2048,256));self.assertEqual(image.getpixel((0,0)),(255,255,255));image.close()
        for invalid in ([dict(id='../secret',name='x')],[self.item]*5,'x'):
            with self.assertRaises(ValueError):validate_images(invalid)
        (self.root/'data/images'/self.item['id']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'danneggiata'):chat_messages(self.history(),self.root/'data')

    def test_full_http_request_includes_image_history_and_token_metrics(self):
        engine=self.engine();text=[]
        history=self.history()+[dict(role='assistant',content='Rosso.'),dict(role='user',content='Quale forma?')]
        stats=engine.generate(chat_messages(history,self.root/'data'),on_text=text.append)
        payload=self.server.payload
        self.assertEqual(self.server.auth,'Bearer '+engine.key)
        self.assertTrue(payload['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertEqual(payload['messages'][2]['content'],'Rosso.')
        self.assertEqual(''.join(text),'Un quadrato rosso.')
        self.assertEqual(stats['tokens'],5) # Not the number of network chunks.
        self.assertEqual(stats['rate'],2.5);self.assertEqual(stats['prefill'],1.25)
        self.server.no_timings=True
        self.assertIsNone(engine.generate(chat_messages(self.history(),self.root/'data'))['rate'])

    def test_stop_interrupts_request_even_before_first_token(self):
        engine=self.engine();self.server.stall=True
        stop=threading.Event();errors=[]
        def run():
            try:engine.generate(chat_messages(self.history(),self.root/'data'),stop=stop)
            except Exception as error:errors.append(error)
        thread=threading.Thread(target=run);thread.start()
        self.assertTrue(self.server.received.wait(2));stop.set();thread.join(timeout=2)
        self.assertFalse(thread.is_alive());self.assertIsInstance(errors[0],VisionCancelled)

    def test_context_errors_and_incomplete_streams_are_errors(self):
        engine=self.engine()
        for reject,truncate,expected in ((True,False,'contesto'),(False,True,'interrotta')):
            self.server.reject=reject;self.server.truncate=truncate
            with self.assertRaisesRegex((ValueError,RuntimeError),expected):
                engine.generate(chat_messages(self.history(),self.root/'data'))

    def test_no_fake_native_vision_or_quantized_float_reshape(self):
        for filename in ('F16.gguf','Q8_0.gguf'):
            with self.assertRaisesRegex(NotImplementedError,'vision'):
                MultiModalProjector(self.root/filename,hidden_size=2048)
        with self.assertRaisesRegex(NotImplementedError,'Vision|Vision|vision'):
            Qwen3MoEModel(self.root/'missing.gguf',mmproj_path=self.projector)

    def test_start_validates_identity_and_closes_owned_process(self):
        engine=LocalVisionModel(self.model,self.projector,sys.executable,log_path=self.root/'vision.log',encoder='cpu')
        response=Mock(status=200)
        response.read.return_value=json.dumps(dict(data=[dict(id=engine.alias)])).encode()
        conn=Mock();conn.getresponse.return_value=response
        with patch('flash_moe.multimodal.subprocess.Popen') as popen,patch.object(engine,'_connection',return_value=conn):
            popen.return_value.poll.return_value=None
            engine.start()
            command=popen.call_args.args[0]
            self.assertEqual(command[command.index('--host')+1],'127.0.0.1')
            self.assertEqual(command[command.index('-ngl')+1],'0')
            self.assertIn('--no-mmproj-offload',command)
            self.assertIn('--no-context-shift',command)
            engine.close();popen.return_value.terminate.assert_called_once()
            self.assertTrue(engine.log is None)

    def test_failed_start_cleans_process_and_log(self):
        engine=LocalVisionModel(self.model,self.projector,sys.executable,log_path=self.root/'vision.log',encoder='cpu')
        with patch('flash_moe.multimodal.subprocess.Popen') as popen:
            popen.return_value.poll.return_value=1
            with self.assertRaisesRegex(RuntimeError,'Avvio'):engine.start()
            self.assertIsNone(engine.process);self.assertIsNone(engine.log)

    def test_gpu_encoder_does_not_offload_language_model(self):
        engine=LocalVisionModel(self.model,self.projector,sys.executable,log_path=self.root/'vision.log')
        response=Mock(status=200)
        response.read.return_value=json.dumps(dict(data=[dict(id=engine.alias)])).encode()
        conn=Mock();conn.getresponse.return_value=response
        with patch('flash_moe.multimodal.detect_vulkan_device',return_value='Vulkan1'), \
                patch('flash_moe.multimodal.subprocess.Popen') as popen,patch.object(engine,'_connection',return_value=conn):
            popen.return_value.poll.return_value=None
            engine.start()
            command=popen.call_args.args[0]
            self.assertEqual(command[command.index('-ngl')+1],'0')
            self.assertEqual(command[command.index('--device')+1],'none')
            self.assertEqual(command[command.index('--mmproj-device')+1],'Vulkan1')
            self.assertIn('--mmproj-offload',command)
            self.assertNotIn('--no-mmproj-offload',command)
            self.assertEqual(engine.encoder_device,'Vulkan1')
            engine.close()

    def test_device_probe_handles_missing_gpu_failure_timeout_and_cancel(self):
        from flash_moe.multimodal import detect_vulkan_device
        with patch('flash_moe.multimodal.subprocess.Popen') as popen:
            process=popen.return_value.__enter__.return_value
            process.returncode=0
            process.communicate.return_value=(b'Available devices:\n  Vulkan0: NVIDIA adapter\n  Vulkan1: Intel Arc 130V\n',None)
            self.assertEqual(detect_vulkan_device(sys.executable),'Vulkan1')
            process.communicate.return_value=(b'Available devices:\n',None)
            self.assertIsNone(detect_vulkan_device(sys.executable))
            process.returncode=1
            self.assertIsNone(detect_vulkan_device(sys.executable))
            process.returncode=0
            process.communicate.side_effect=[subprocess.TimeoutExpired('probe',.2),(b'',None)]
            with patch('flash_moe.multimodal.time.monotonic',side_effect=[0,11]):
                self.assertIsNone(detect_vulkan_device(sys.executable))
            process.kill.assert_called_once()
        stop=threading.Event();stop.set()
        with self.assertRaises(VisionCancelled):detect_vulkan_device(sys.executable,stop)

    def test_auto_mode_falls_back_to_cpu_when_runtime_has_no_gpu(self):
        engine=LocalVisionModel(self.model,self.projector,sys.executable,log_path=self.root/'vision.log')
        response=Mock(status=200)
        response.read.return_value=json.dumps(dict(data=[dict(id=engine.alias)])).encode()
        conn=Mock();conn.getresponse.return_value=response
        with patch('flash_moe.multimodal.detect_vulkan_device',return_value=None), \
                patch('flash_moe.multimodal.subprocess.Popen') as popen,patch.object(engine,'_connection',return_value=conn):
            popen.return_value.poll.return_value=None
            engine.start()
            self.assertIn('--no-mmproj-offload',popen.call_args.args[0])
            self.assertEqual(engine.encoder_device,'CPU')
            engine.close()

    def test_cli_vision_bypasses_native_model_and_sends_pixels(self):
        import chat
        engine=Mock();engine.generate.return_value=dict(tokens=2,rate=2)
        with patch('chat.model_path',return_value=self.model),patch('chat._load_text_model') as native, \
                patch('llocalmind.vision_cli.LocalVisionModel',return_value=engine):
            self.assertEqual(chat.main(['--mmproj',str(self.projector),'--llama-server',sys.executable,
                '--image',str(self.source),'Cosa vedi?']),0)
            native.assert_not_called();engine.start.assert_called_once();engine.close.assert_called_once()
            sent=engine.generate.call_args.args[0]
            self.assertEqual(sent[1]['content'][0]['text'],'Cosa vedi?')
            self.assertIn('data:image/png;base64,',sent[1]['content'][1]['image_url']['url'])

    def test_cli_missing_mmproj_is_rejected_before_native_load(self):
        import chat
        with patch('chat.model_path',return_value=self.model),patch('chat._load_text_model') as native:
            self.assertEqual(chat.main(['--image',str(self.source),'Domanda']),1)
            native.assert_not_called()


if __name__=='__main__':unittest.main()

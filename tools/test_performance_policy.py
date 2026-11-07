"""Behavioral guards for bounded memory, lazy imports and reusable work."""
import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from llocalmind.state import DEFAULTS,engine_signature,validate_settings
from llocalmind.images import ImagePayloadCache,chat_messages,import_image
from llocalmind.prompts import SYSTEM
from PIL import Image


class PerformancePolicyTests(unittest.TestCase):
    def test_memory_snapshot_is_read_only_and_reports_valid_counters(self):
        import os
        from llocalmind.performance import memory_snapshot
        values=memory_snapshot(os.getpid())
        self.assertGreater(values['total_ram_bytes'],0)
        self.assertLessEqual(values['available_ram_bytes'],values['total_ram_bytes'])
        if 'process_rss_bytes' in values:self.assertGreater(values['process_rss_bytes'],0)

    def test_vision_and_cli_help_do_not_load_native_dependencies(self):
        for code in ('from flash_moe.multimodal import LocalVisionModel',
                     'import chat;chat.build_parser()'):
            result=subprocess.run([sys.executable,'-c',
                "import sys;sys.path[:0]=['src','.'];"+code+";assert not {'numpy','gguf','openvino'} & set(sys.modules)"],
                cwd=ROOT,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)

    def test_lazy_public_exports_keep_identity_and_unknown_attributes(self):
        import flash_moe
        from flash_moe.key import ExpertKey
        from flash_moe import ExpertKey as public
        self.assertIs(public,ExpertKey)
        self.assertIs(flash_moe.ExpertKey,public)
        with self.assertRaises(AttributeError):getattr(flash_moe,'not_an_export')

    def test_only_relevant_settings_change_engine_identity(self):
        native=dict(DEFAULTS)
        self.assertEqual(engine_signature(native),engine_signature(dict(native,vision_image_tokens=256)))
        vision=dict(DEFAULTS,engine='vision')
        self.assertEqual(engine_signature(vision),engine_signature(dict(vision,cache=1000,
            ssm_device='CPU',max_tokens=200,prefill_threads=12)))
        self.assertNotEqual(engine_signature(vision),engine_signature(dict(vision,vision_image_tokens=256)))
        self.assertNotEqual(engine_signature(vision),engine_signature(dict(vision,vision_threads=4)))
        self.assertNotEqual(engine_signature(vision),engine_signature(dict(vision,max_seq=4096)))
        for change in (dict(vision_image_tokens=1),dict(vision_ubatch=2048,vision_batch=128),
                       dict(vision_threads=0),dict(vision_cache_mib=8192),dict(vision_warmup='false')):
            with self.assertRaises(ValueError):validate_settings(dict(DEFAULTS,**change))

    def test_existing_default_vision_profile_migrates_to_measured_preset(self):
        old={key:value for key,value in DEFAULTS.items() if key!='vision_threads'}
        old.update(vision_batch=512,vision_ubatch=256)
        values=validate_settings(old)
        self.assertEqual(values['vision_threads'],8)
        self.assertEqual(values['vision_batch'],2048)
        self.assertEqual(values['vision_ubatch'],1024)
        custom=validate_settings(dict(old,vision_batch=1024,vision_ubatch=512))
        self.assertEqual((custom['vision_batch'],custom['vision_ubatch']),(1024,512))

    def test_vision_cli_defaults_match_the_measured_preset(self):
        import chat
        args=chat.build_parser().parse_args([])
        self.assertEqual((args.vision_threads,args.vision_batch,args.vision_ubatch),(8,2048,1024))

    def test_longer_answer_defaults_and_legacy_settings_migration(self):
        self.assertEqual(DEFAULTS['max_tokens'],512)
        legacy=validate_settings({'max_tokens':128})
        self.assertEqual(legacy['max_tokens'],512)
        small_context=validate_settings({'max_tokens':128,'max_seq':256})
        self.assertEqual(small_context['max_tokens'],255)
        custom=validate_settings({'max_tokens':256})
        self.assertEqual(custom['max_tokens'],256)
        import chat
        args=chat.build_parser().parse_args([])
        self.assertEqual(args.max_tokens,512)
        self.assertEqual(args.max_seq,2048)
        self.assertIn('dai una risposta chiara e completa',SYSTEM.casefold())
        self.assertIn('non sacrificare informazioni utili',SYSTEM.casefold())

    def test_image_payload_is_reused_but_changed_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.png'
            Image.new('RGB',(32,32),'red').save(source)
            item=import_image(source,directory)
            history=[dict(role='user',content='Cosa vedi?',images=[item])]
            cache=ImagePayloadCache()
            with patch.object(Path,'read_bytes',autospec=True,side_effect=Path.read_bytes) as read:
                first=chat_messages(history,directory,cache=cache)
                second=chat_messages(history,directory,cache=cache)
                self.assertEqual(read.call_count,1)
            a=first[1]['content'][1]['image_url']['url']
            b=second[1]['content'][1]['image_url']['url']
            self.assertIs(a,b)
            self.assertEqual(Image.open(io.BytesIO(base64.b64decode(a.split(',')[1]))).getpixel((0,0)),(255,0,0))
            (Path(directory)/'images'/item['id']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'danneggiata'):chat_messages(history,directory,cache=cache)

    def test_encoded_image_cache_respects_byte_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            cache=ImagePayloadCache(max_bytes=200)
            for color in ('red','green','blue','yellow'):
                source=Path(directory)/'source.png'
                Image.new('RGB',(32,32),color).save(source)
                item=import_image(source,directory)
                chat_messages([dict(role='user',content='x',images=[item])],directory,cache=cache)
                self.assertLessEqual(cache.bytes,cache.max_bytes)
            self.assertLess(len(cache.entries),4)

    def test_kv_reset_reuses_storage_without_exposing_previous_tokens(self):
        import numpy as np
        from flash_moe.attention import KVCache
        cache=KVCache(2,4,max_seq_len=64)
        old=cache._key_storage
        cache.append(np.ones((8,2,4)),np.ones((8,2,4)))
        cache.reset()
        self.assertIs(cache._key_storage,old)
        self.assertEqual(cache.length,0)
        self.assertEqual(len(cache.keys),0)
        cache.append(np.full((1,2,4),3),np.full((1,2,4),4))
        np.testing.assert_array_equal(cache.keys,np.full((1,2,4),3))
        cache.max_seq_len=128
        cache.reset()
        self.assertIsNot(cache._key_storage,old)

    def test_vision_start_caps_compute_memory_and_keeps_warmup_explicit(self):
        from flash_moe.multimodal import LocalVisionModel
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            model=root/'m.gguf';model.touch()
            projector=root/'v.gguf';projector.touch()
            engine=LocalVisionModel(model,projector,sys.executable,log_path=root/'vision.log')
            conn=Mock();response=Mock(status=200)
            response.read.return_value=json.dumps(dict(data=[dict(id=engine.alias)])).encode()
            conn.getresponse.return_value=response
            with patch('flash_moe.multimodal.subprocess.Popen') as popen,patch.object(engine,'_connection',return_value=conn):
                popen.return_value.poll.return_value=None
                engine.start()
                args=popen.call_args.args[0]
                self.assertEqual(args[args.index('--image-max-tokens')+1],'768')
                self.assertEqual(args[args.index('--cache-ram')+1],'128')
                self.assertEqual(args[args.index('-ub')+1],'256')
                self.assertNotIn('--no-warmup',args)
                self.assertIn('--no-cache-idle-slots',args)
                engine.close()

    def test_f16_embedding_keeps_existing_storage(self):
        import numpy as np
        from types import SimpleNamespace
        from flash_moe.embedding import EmbeddingLookup
        source=np.arange(32,dtype=np.float16).reshape(8,4)
        tensor=SimpleNamespace(data=source,shape=np.array([4,8]),tensor_type=1)
        embedding=EmbeddingLookup.from_gguf_tensor(tensor)
        self.assertTrue(np.shares_memory(source,embedding.weight))
        np.testing.assert_array_equal(embedding.forward(np.array([2,5])),source[[2,5]])

    def test_target_benchmark_writes_timings_and_closes_server_on_failure(self):
        from llocalmind.vision_benchmark import main
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            model=root/'m.gguf';model.touch()
            projector=root/'v.gguf';projector.touch()
            image=root/'image.png';Image.new('RGB',(32,32),'red').save(image)
            config=root/'settings.json'
            config.write_text(json.dumps(dict(DEFAULTS,model_path=str(model),vision_projector=str(projector),vision_executable=sys.executable)))
            report=root/'report.json'
            engine=Mock(startup_seconds=2)
            engine.generate.return_value=dict(tokens=4,rate=2,first_token=3,prefill=2,image_max_tokens=768)
            with patch('llocalmind.vision_benchmark.LocalVisionModel',return_value=engine):
                self.assertEqual(main(['--image',str(image),'--settings',str(config),'--output',str(report)]),0)
                engine.close.assert_called_once()
                saved=json.loads(report.read_text())
                self.assertEqual(len(saved['samples']),2)
                self.assertEqual(saved['startup_seconds'],2)
                engine.close.reset_mock()
                engine.generate.side_effect=RuntimeError('failed')
                self.assertEqual(main(['--image',str(image),'--settings',str(config),'--output',str(report)]),1)
                engine.close.assert_called_once()
                self.assertEqual(json.loads(report.read_text())['error'],'failed')


if __name__=='__main__':unittest.main()

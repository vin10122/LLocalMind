"""Offline runtime installer tests; no real EXE is executed here."""
import hashlib
import io
from pathlib import Path
import stat
import struct
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock,patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from llocalmind.vision_runtime import (HTTPSOnly,RuntimeInstaller,RuntimePackage,
    RuntimeInstallError,RuntimeInstallCancelled)
from llocalmind.app_paths import child_environment


def pe():
    data=bytearray(70);data[:2]=b'MZ';struct.pack_into('<I',data,60,64)
    data[64:]=b'PE\0\0\x64\x86'
    return bytes(data)


def archive(extra=None,server=True,dll=True):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        if server:z.writestr('llama-server.exe',pe())
        if dll:z.writestr('ggml.dll',b'fake DLL fixture')
        for name,data in extra or []:z.writestr(name,data)
    return out.getvalue()


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)/'runtimes'
        self.platform=patch('llocalmind.vision_runtime.supported_platform',return_value=True)
        self.platform.start();self.calls=[];self.probe=Mock()
    def tearDown(self):self.platform.stop();self.temp.cleanup()
    def installer(self,data=None,**kwargs):
        data=archive() if data is None else data
        self.body=data
        package=RuntimePackage('b1',
            'https://github.com/ggml-org/llama.cpp/releases/download/b1/llama-b1-bin-win-cpu-x64.zip',
            hashlib.sha256(data).hexdigest(),len(data))
        def open_(request,timeout):
            self.calls.append(request.full_url)
            return io.BytesIO(self.body)
        return RuntimeInstaller(self.root,package=package,opener=open_,probe=self.probe,**kwargs)
    def empty(self):self.assertFalse(self.root.exists() and list(self.root.iterdir()))

    def test_complete_install_probe_and_offline_reuse(self):
        installer=self.installer();progress=[]
        executable=installer.install(progress=progress.append)
        self.assertEqual(executable.name,'llama-server.exe');self.assertEqual(executable.read_bytes(),pe())
        self.assertTrue(executable.with_name('ggml.dll').is_file())
        self.assertEqual(progress[-1],100);self.assertEqual(progress,sorted(progress))
        self.assertEqual(installer.install(),executable)
        self.assertEqual(len(self.calls),1);self.assertEqual(self.probe.call_count,2)
        self.assertFalse(list(self.root.glob('.install-*')))

    def test_hash_mismatch_and_wrong_size_leave_no_installation(self):
        for replacement in (b'broken',archive()+b'extra'):
            installer=self.installer();self.body=replacement
            with self.assertRaises(RuntimeInstallError):installer.install()
            self.empty();self.probe.assert_not_called()

    def test_cancel_before_and_during_download(self):
        installer=self.installer();cancel=threading.Event();cancel.set()
        with self.assertRaises(RuntimeInstallCancelled):installer.install(cancel=cancel)
        self.assertFalse(self.calls);self.empty()
        cancel.clear()
        with self.assertRaises(RuntimeInstallCancelled):
            installer.install(cancel=cancel,progress=lambda n:cancel.set() if n>0 else None)
        self.empty();self.probe.assert_not_called()

    def test_cancel_during_extraction(self):
        installer=self.installer();cancel=threading.Event()
        with self.assertRaises(RuntimeInstallCancelled):
            installer.install(cancel=cancel,progress=lambda n:cancel.set() if n>75 else None)
        self.empty();self.probe.assert_not_called()

    def test_unsafe_paths_links_and_case_collisions(self):
        names=['../escape.dll','/absolute.dll','C:/drive.dll','folder\\file.dll',
               'CON.dll','trailing .','LLAMA-SERVER.EXE']
        for name in names:
            with self.subTest(name=name):
                installer=self.installer(archive([(name,b'x')]))
                with self.assertRaises(RuntimeInstallError):installer.install()
                self.empty()
        link=zipfile.ZipInfo('symlink.dll');link.create_system=3
        link.external_attr=(stat.S_IFLNK|0o777)<<16
        installer=self.installer(archive([(link,b'../outside')]))
        with self.assertRaises(RuntimeInstallError):installer.install()
        self.empty();self.probe.assert_not_called()

    def test_missing_executable_dll_invalid_pe_and_expansion_limit(self):
        for data in (archive(server=False),archive(dll=False),b'not a zip',archive([('llama-server.exe.bad',b'x')],server=False)):
            with self.subTest(data=data[:10]):
                with self.assertRaises(RuntimeInstallError):self.installer(data).install()
                self.empty()
        installer=self.installer(archive([('llama-server.exe',b'not PE')],server=False))
        with self.assertRaisesRegex(RuntimeInstallError,'x64'):installer.install()
        self.empty()
        with patch('llocalmind.vision_runtime.MAX_UNPACKED',1):
            with self.assertRaisesRegex(RuntimeInstallError,'grande'):self.installer().install()
        self.empty();self.probe.assert_not_called()

    def test_probe_failure_preserves_old_runtime(self):
        old=self.root/'old'/'llama-server.exe';old.parent.mkdir(parents=True);old.write_bytes(b'old')
        self.probe.side_effect=RuntimeInstallError('DLL load failure')
        with self.assertRaisesRegex(RuntimeInstallError,'DLL'):self.installer().install()
        self.assertEqual(old.read_bytes(),b'old')
        self.assertEqual(list(self.root.iterdir()),[old.parent])

    def test_tampered_cache_installs_beside_old_without_overwrite(self):
        installer=self.installer();first=installer.install()
        first.with_name('ggml.dll').write_bytes(b'corrupt')
        second=installer.install()
        self.assertNotEqual(first,second);self.assertEqual(len(self.calls),2)
        self.assertEqual(first.with_name('ggml.dll').read_bytes(),b'corrupt')
        self.assertEqual(second.with_name('ggml.dll').read_bytes(),b'fake DLL fixture')

    def test_download_exception_cleans_staging(self):
        installer=self.installer();installer.open=Mock(side_effect=OSError('network failed'))
        with self.assertRaisesRegex(RuntimeInstallError,'network'):installer.install()
        self.empty()

    def test_reject_untrusted_manifest_platform_and_http_redirect(self):
        with self.assertRaises(RuntimeInstallError):
            RuntimeInstaller(package=RuntimePackage('b1','https://example.com/engine.zip','0'*64,1))
        with patch('llocalmind.vision_runtime.supported_platform',return_value=False):
            with self.assertRaisesRegex(RuntimeInstallError,'Windows'):self.installer().install()
        self.assertFalse(self.calls)
        with self.assertRaises(RuntimeInstallError):
            HTTPSOnly().redirect_request(None,None,302,'',{},'http://example.com/engine')

    def test_child_process_environment_finds_bundled_vc_runtime(self):
        with patch.object(sys,'frozen',True,create=True),patch.object(sys,'_MEIPASS','C:/LLocalMind/_internal',create=True):
            self.assertTrue(child_environment()['PATH'].startswith('C:/LLocalMind/_internal'))


if __name__=='__main__':unittest.main()

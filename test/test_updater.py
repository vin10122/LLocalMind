"""Offline updater checks: no GitHub calls, model loads or real installers."""
import hashlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from llocalmind.updater import (API_URL, FEED_URL, REPOSITORY, DownloadCancelled,
                                DownloadedUpdate, UpdateError, UpdateManager,
                                _HTTPSRedirects, version_tuple)


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        pause=patch('llocalmind.updater.time.sleep')
        pause.start();self.addCleanup(pause.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = b'MZ fake offline installer\x00\xff'
        self.name = 'LLocalMind-Setup-0.2.0-windows-x64.exe'
        self.url = f'https://github.com/{REPOSITORY}/releases/download/v0.2.0/{self.name}'
        self.digest = hashlib.sha256(self.payload).hexdigest()
        self.metadata = dict(tag_name='v0.2.0', draft=False, prerelease=False,
                             name='Release 0.2.0', body='Release notes', assets=[
            dict(name=self.name, browser_download_url=self.url,
                 size=len(self.payload), digest='sha256:' + self.digest)])
        self.responses = {self.url: self.payload}
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request.full_url)
        self.assertEqual(timeout,10 if request.full_url in (API_URL,FEED_URL) else 30)
        value = json.dumps([self.metadata]).encode() if request.full_url == API_URL else self.responses[request.full_url]
        if isinstance(value, Exception):
            raise value
        return io.BytesIO(value)

    def manager(self, version='0.1.0'):
        return UpdateManager(version, directory=self.root / 'updates', opener=self.open)

    def test_semantic_versions_and_no_downgrades(self):
        self.assertGreater(version_tuple('v0.10.0'), version_tuple('0.9.0'))
        for value in ('1.2', '01.2.3', '../1.2.3', '1.2.3-beta', None):
            with self.assertRaises(UpdateError):
                version_tuple(value)
        self.assertIsNone(self.manager('0.2.0').check())
        self.assertIsNone(self.manager('1.0.0').check())

    def test_previews_included_drafts_excluded_and_no_executable_download_on_check(self):
        release = self.manager().check()
        self.assertEqual(release.version, '0.2.0')
        self.assertEqual(release.notes, 'Release notes')
        self.assertEqual(self.requests, [API_URL])
        self.metadata['prerelease']=True
        self.assertTrue(self.manager().check().prerelease)
        self.metadata['draft']=True
        self.assertIsNone(self.manager().check())

    def test_offline_and_no_releases(self):
        for code in (404, 403, 500):
            def fail(request, timeout):
                raise HTTPError(API_URL, code, 'error', {}, None)
            manager = UpdateManager(opener=fail)
            if code == 404:
                self.assertIsNone(manager.check())
            else:
                with self.assertRaises(UpdateError): manager.check()
        def offline(request, timeout): raise URLError('offline')
        with self.assertRaises(UpdateError): UpdateManager(opener=offline).check()

    def test_temporary_504_retries_then_recovers_without_fallback(self):
        calls=[]
        def open_(request,timeout):
            calls.append(request.full_url)
            if len(calls)==1:raise HTTPError(API_URL,504,'timeout',{},None)
            return io.BytesIO(json.dumps([self.metadata]).encode())
        self.assertEqual(UpdateManager('0.1.0',opener=open_).check().version,'0.2.0')
        self.assertEqual(calls,[API_URL,API_URL])

    def test_official_feed_after_api_timeout_preserves_validation(self):
        calls=[]
        def open_(request,timeout):
            calls.append(request.full_url)
            if request.full_url==API_URL:raise HTTPError(API_URL,504,'timeout',{},None)
            self.assertEqual(request.full_url,FEED_URL)
            return io.BytesIO(json.dumps(dict(schema=1,releases=[self.metadata])).encode())
        manager=UpdateManager('0.1.0',directory=self.root/'updates',opener=open_)
        self.assertEqual(manager.check().sha256,self.digest)
        self.assertEqual(calls,[API_URL,API_URL,FEED_URL])
        self.assertFalse(manager.directory.exists())
        self.metadata['assets'][0]['browser_download_url']='https://example.com/untrusted.exe'
        with self.assertRaises(UpdateError):manager.check()

    def test_long_retry_after_uses_feed_without_hammering_api(self):
        calls=[]
        def open_(request,timeout):
            calls.append(request.full_url)
            if request.full_url==API_URL:raise HTTPError(API_URL,429,'limit',{'Retry-After':'120'},None)
            return io.BytesIO(json.dumps(dict(schema=1,releases=[self.metadata])).encode())
        self.assertEqual(UpdateManager('0.1.0',opener=open_).check().version,'0.2.0')
        self.assertEqual(calls,[API_URL,FEED_URL])

    def test_broken_feed_or_all_hosts_offline_does_not_claim_no_updates(self):
        for data in (b'not JSON',b'[]',b'{"schema":true,"releases":[]}',b'{"schema":2,"releases":[]}'):
            def open_(request,timeout):
                if request.full_url==API_URL:raise URLError('offline')
                return io.BytesIO(data)
            with self.assertRaises(UpdateError):UpdateManager(opener=open_).check()
        def offline(*args,**kwargs):raise URLError('offline')
        with self.assertRaisesRegex(UpdateError,'temporaneamente'):
            UpdateManager(opener=offline).check()

    def test_cancel_during_download_retry_backoff(self):
        manager=self.manager();release=manager.check();stop=threading.Event()
        calls=[]
        def open_(request,timeout):
            calls.append(request.full_url)
            raise HTTPError(request.full_url,504,'timeout',{},None)
        manager._open=open_
        with patch.object(stop,'wait',side_effect=lambda delay:stop.set()):
            with self.assertRaises(DownloadCancelled):manager.download(release,cancel=stop)
        self.assertEqual(calls,[release.download_url])
        self.assertEqual(list(manager.directory.glob('*.part')),[])

    def test_cancel_check_stops_before_another_request_or_feed(self):
        stop=threading.Event();calls=[]
        def open_(request,timeout):
            calls.append(request.full_url)
            raise HTTPError(API_URL,504,'timeout',{},None)
        with patch.object(stop,'wait',side_effect=lambda delay:stop.set()):
            with self.assertRaises(DownloadCancelled):UpdateManager(opener=open_).check(cancel=stop)
        self.assertEqual(calls,[API_URL])

    def test_feed_generator_skips_drafts_and_requires_complete_release(self):
        spec=importlib.util.spec_from_file_location('update_feed_builder',Path(__file__).resolve().parents[1]/'.github/scripts/publish_update_feed.py')
        builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
        draft=dict(self.metadata,draft=True,tag_name='v9.0.0')
        incomplete=dict(self.metadata,tag_name='v8.0.0',assets=[])
        feed=builder.build_feed([draft,incomplete,self.metadata],'v0.2.0')
        self.assertEqual([r['tag_name'] for r in feed['releases']],['v0.2.0'])
        with self.assertRaises(RuntimeError):builder.build_feed([incomplete],'v8.0.0')

    def test_invalid_release_metadata(self):
        for value in (b'not JSON', b'{}', b'[null]'):
            with self.assertRaises(UpdateError):
                UpdateManager(opener=lambda *a, **kw: io.BytesIO(value)).check()
        self.assertIsNone(UpdateManager(opener=lambda *a,**kw:io.BytesIO(b'[]')).check())
        for assets in ({}, ['invalid'], [], [dict(name=self.name)]):
            self.metadata['assets'] = assets
            with self.assertRaises(UpdateError): self.manager().check()

    def test_untrusted_asset_or_missing_hash_rejected(self):
        asset = self.metadata['assets'][0]
        asset['browser_download_url'] = 'https://example.org/update.exe'
        with self.assertRaises(UpdateError): self.manager().check()
        asset['browser_download_url'] = self.url
        asset['digest'] = None
        with self.assertRaises(UpdateError): self.manager().check()

    def test_highest_version_wins_even_if_stable_is_listed_first(self):
        older=copy.deepcopy(self.metadata)
        older['tag_name']='v0.1.9'
        newest=copy.deepcopy(self.metadata)
        newest['prerelease']=True
        draft=copy.deepcopy(self.metadata)
        draft['tag_name']='v9.0.0';draft['draft']=True
        unknown=dict(tag_name='nightly',draft=False)
        data=json.dumps([older,draft,unknown,newest]).encode()
        manager=UpdateManager('0.1.9',opener=lambda *a,**kw:io.BytesIO(data))
        self.assertEqual(manager.check().version,'0.2.0')
        self.assertTrue(manager.check().prerelease)
        manager.current_version='0.2.0'
        self.assertIsNone(manager.check())

    def test_verified_download_and_user_data_preserved(self):
        self.metadata['prerelease']=True
        data = self.root / 'data/chat.json'
        data.parent.mkdir()
        data.write_text('my conversation')
        manager = self.manager()
        release = manager.check()
        progress = []
        update = manager.download(release, progress=lambda n, total: progress.append((n, total)))
        self.assertEqual(update.path.read_bytes(), self.payload)
        self.assertEqual(update.sha256, self.digest)
        self.assertEqual(progress[-1], (len(self.payload), len(self.payload)))
        self.assertEqual(data.read_text(), 'my conversation')
        self.assertEqual(list(manager.directory.glob('*.part')), [])

    def test_truncated_oversized_and_corrupt_downloads_do_not_replace_existing(self):
        manager = self.manager()
        release = manager.check()
        manager.directory.mkdir()
        target = manager.directory / self.name
        target.write_bytes(b'previous verified installer')
        for bad in (b'', self.payload[:-1], self.payload + b'X', b'X' * len(self.payload)):
            self.responses[self.url] = bad
            with self.assertRaises(UpdateError): manager.download(release)
            self.assertEqual(target.read_bytes(), b'previous verified installer')
            self.assertEqual(list(manager.directory.glob('*.part')), [])

    def test_download_cancellation_cleans_up(self):
        manager = self.manager()
        release = manager.check()
        cancel = threading.Event()
        def progress(received, total):
            if received: cancel.set()
        with self.assertRaises(DownloadCancelled):
            manager.download(release, cancel=cancel, progress=progress)
        self.assertEqual(list(manager.directory.iterdir()), [])

    def test_checksum_sidecar_matches_exact_filename(self):
        self.metadata['assets'][0]['digest'] = None
        url = self.url + '.sha256'
        self.metadata['assets'].append(dict(name=self.name + '.sha256', browser_download_url=url))
        self.responses[url] = f'{self.digest}  {self.name}\n'.encode()
        manager = self.manager()
        self.assertEqual(manager.download(manager.check()).path.read_bytes(), self.payload)
        self.responses[url] = f'{self.digest}  other.exe'.encode()
        with self.assertRaises(UpdateError): manager.download(manager.check())

    def test_path_traversal_and_invalid_release_objects(self):
        manager = self.manager()
        release = manager.check()
        for bad in (replace(release, asset_name='../outside.exe'),
                    replace(release, size=0), replace(release, sha256='bad'),
                    replace(release, tag='v9.0.0')):
            with self.assertRaises(UpdateError): manager.download(bad)
        self.assertFalse(manager.directory.exists())

    def test_install_explicit_platform_guard_and_revalidation(self):
        manager = self.manager()
        update = manager.download(manager.check())
        with patch.object(sys, 'frozen', False, create=True):
            with self.assertRaises(UpdateError): manager.launch_installer(update)
        with patch.object(sys, 'platform', 'win32'), patch.object(sys, 'frozen', True, create=True), \
                patch('llocalmind.updater.subprocess.Popen') as launch:
            manager.launch_installer(update)
            command = launch.call_args.args[0]
            self.assertEqual(command[0], str(update.path.resolve()))
            self.assertIn('/RELAUNCH=1', command)
            launch.reset_mock()
            with self.assertRaises(UpdateError):
                manager.launch_installer(replace(update, path=self.root/'outside.exe'))
            update.path.write_bytes(b'tampered')
            with self.assertRaises(UpdateError): manager.launch_installer(update)
            launch.assert_not_called()

    def test_https_redirects_only(self):
        with self.assertRaises(UpdateError):
            _HTTPSRedirects().redirect_request(None, None, 302, '', {}, 'http://example.org/update.exe')

    @staticmethod
    def load_module(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_source_commands_check_without_download_and_refuse_install(self):
        cli = self.load_module(Path(__file__).resolve().parents[1] / 'update.py', 'update_cli_test')
        with patch.object(cli, 'UpdateManager') as manager, patch('sys.stdout', new_callable=io.StringIO), \
                patch('sys.stderr', new_callable=io.StringIO), patch.object(sys, 'frozen', False, create=True):
            manager.return_value.check.return_value = self.manager().check()
            self.assertEqual(cli.main(['check']), 0)
            manager.return_value.download.assert_not_called()
            manager.return_value.check.reset_mock()
            self.assertEqual(cli.main(['install']), 1)
            manager.return_value.check.assert_not_called()
            manager.return_value.launch_installer.assert_not_called()

    def test_installer_builder_emits_matching_checksum(self):
        root = Path(__file__).resolve().parents[1]
        builder = self.load_module(root / 'tools/build_windows_installer.py', 'installer_builder_test')
        app = self.root / 'app'
        app.mkdir()
        (app / 'LLocalMind.exe').write_bytes(b'MZ application placeholder')
        out = self.root / 'release'
        name = f'LLocalMind-Setup-{builder.__version__}-windows-x64.exe'
        def compile_installer(command, check):
            self.assertTrue(check)
            self.assertIn(f'/DAppVersion={builder.__version__}', command)
            (out / name).write_bytes(self.payload)
        with patch.object(sys, 'platform', 'win32'), \
                patch.object(builder.subprocess, 'run', side_effect=compile_installer), \
                patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(builder.main(['--app-dir', str(app), '--output-dir', str(out),
                                           '--iscc', str(self.root/'ISCC.exe')]), 0)
        self.assertEqual((out / (name + '.sha256')).read_text(), f'{self.digest}  {name}\n')
        recipe = (root / 'packaging/windows/LLocalMind.iss').read_text()
        self.assertIn('PrivilegesRequired=lowest', recipe)
        self.assertIn(r'DefaultDirName={localappdata}\Programs\LLocalMind', recipe)
        self.assertIn('AppId={{B644D036-5385-40F5-9D76-B6A08E0527EC}', recipe)
        self.assertNotIn('\n[UninstallDelete]', recipe)
        # [Code] is Pascal Script, where semicolons are not comment markers.
        code = recipe.split('[Code]', 1)[1]
        self.assertFalse(any(line.lstrip().startswith(';') for line in code.splitlines()))

    def test_no_inference_imports(self):
        self.assertTrue({'numpy', 'gguf', 'openvino'}.isdisjoint(sys.modules))


if __name__ == '__main__':
    unittest.main()

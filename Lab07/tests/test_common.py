"""Testes de contratos/erros do lifecycle sem containers nem instalações Fabric."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

# Isola apenas a dependência de criação Fogbed. Não emula sucesso da rede Fabric.
class Container:
    """Guarda argumentos dos construtores para verificar caminhos sem criar nós."""
    def __init__(self, name, **kwargs):
        self.name = name
        self.__dict__.update(kwargs)

fake_fogbed = types.ModuleType('fogbed')
fake_fogbed.Container = Container
spec = importlib.util.spec_from_file_location('lab07_under_test', Path(__file__).parents[1] / 'common.py')
common = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'fogbed': fake_fogbed}):
    spec.loader.exec_module(common)


def completed(stdout='', stderr='', code=0):
    """Cria evidência CLI controlada para exercitar somente a interpretação."""
    return subprocess.CompletedProcess(['peer'], code, stdout, stderr)


class LifecycleTests(unittest.TestCase):
    """Verifica identificação inequívoca e interrupção em falhas reais do CLI."""
    def test_paths_are_lab07_and_lab05_remains_read_only(self):
        self.assertEqual(Path(common.infra.ROOT_DIR), common.ROOT_DIR)
        self.assertEqual(Path(common.infra.CHANNEL_BLOCK).parent, common.ROOT_DIR / 'channel-artifacts')
        self.assertEqual(Path(common.infra.lab05_common.ROOT_DIR).name, 'Lab05')
        self.assertTrue(common.select_chaincode('basic')['path'].is_relative_to(common.ROOT_DIR))

    def test_command_failure_preserves_streams_and_exit(self):
        with patch.object(common.subprocess, 'run', return_value=completed('partial', 'build failed', 9)):
            with self.assertRaisesRegex(RuntimeError, 'exit code: 9') as caught:
                common.run_command(['peer', 'lifecycle'])
            self.assertIn('build failed', str(caught.exception))
            self.assertIn('partial', str(caught.exception))

    def test_package_uses_local_source_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            def package_command(args, **kwargs):
                Path(args[4]).write_bytes(b'actual package bytes')
                self.assertEqual(args[6], common.CHAINCODES['basic']['path'])
                return completed()
            with patch.object(common, 'run_command', side_effect=package_command):
                package = common.package_chaincode(common.select_chaincode('basic'), tmp, {})
            self.assertEqual(package['package_id'], 'basic_1.0:' + hashlib.sha256(b'actual package bytes').hexdigest())
            self.assertTrue(package['path'].is_file())

    def test_failed_package_does_not_replace_previous_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'basic.tar.gz'
            path.write_bytes(b'previous')
            with patch.object(common, 'run_command', side_effect=RuntimeError('compile error')):
                with self.assertRaises(RuntimeError):
                    common.package_chaincode(common.select_chaincode('basic'), tmp, {})
            self.assertEqual(path.read_bytes(), b'previous')

    def test_query_keeps_stderr_out_of_json(self):
        response = completed(json.dumps({'installed_chaincodes': [{'label':'basic_1.0', 'package_id':'basic_1.0:abc'}]}), 'INFO log')
        with patch.object(common, 'peer_lifecycle', return_value=response):
            entries, evidence = common.query_installed_chaincodes(None, '192.0.2.2')
        self.assertEqual(entries[0]['package_id'], 'basic_1.0:abc')
        self.assertEqual(evidence.stderr, 'INFO log')

    def test_malformed_query_is_not_success(self):
        for body in ('not JSON', '{}', '{"installed_chaincodes":[{}]}'):
            with self.subTest(body=body), patch.object(common, 'peer_lifecycle', return_value=completed(body)):
                with self.assertRaises(RuntimeError):
                    common.query_installed_chaincodes(None, '192.0.2.2')

    def test_same_label_wrong_hash_is_rejected(self):
        package = {'label':'basic_1.0', 'package_id':'basic_1.0:expected'}
        with self.assertRaises(RuntimeError):
            common.identify_installed_package(package, [{'label':'basic_1.0','package_id':'basic_1.0:other'}])
        self.assertEqual(common.identify_installed_package(package, [dict(package)]), package['package_id'])

    def test_future_operations_are_rejected(self):
        with self.assertRaises(ValueError):
            common.peer_lifecycle(None, '192.0.2.2', ['commit'])

    def test_lifecycle_uses_non_tty_exec_and_admin_context(self):
        peer = types.SimpleNamespace(environment={
            'CORE_PEER_MSPCONFIGPATH':'/node-msp', 'CORE_PEER_LOCALMSPID':'Org1MSP',
            'CORE_PEER_ID':'peer0.org1.example.com', 'CORE_PEER_LISTENADDRESS':'0.0.0.0:7051',
            'CORE_PEER_TLS_ENABLED':'true', 'CORE_PEER_TLS_ROOTCERT_FILE':'/tls/ca.crt'},
            _service=types.SimpleNamespace(docker=types.SimpleNamespace(did='actual-container-id')))
        with patch.object(common, 'run_command', return_value=completed()) as run:
            common.peer_lifecycle(peer, '192.0.2.2', ['queryinstalled', '--output','json'])
        args = run.call_args.args[0]
        self.assertNotIn('-t', args)
        self.assertIn('CORE_PEER_MSPCONFIGPATH=' + common.infra.PEER_ADMIN_MSP, args)
        self.assertIn('CORE_PEER_ADDRESS=192.0.2.2:7051', args)
        self.assertIn('actual-container-id', args)
        self.assertEqual(peer.environment['CORE_PEER_MSPCONFIGPATH'], '/node-msp')

    def test_changed_package_is_not_installed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(common, 'PACKAGE_DIR', Path(tmp)):
            path = Path(tmp) / 'basic.tar.gz'
            path.write_bytes(b'changed')
            with patch.object(common, 'peer_lifecycle') as execute:
                with self.assertRaises(RuntimeError):
                    common.install_chaincode(None, '', {'path':path,'label':'basic_1.0','package_id':'basic_1.0:old'})
                execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()

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
            common.peer_lifecycle(None, '192.0.2.2', ['invoke'])

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


class ApprovalTests(unittest.TestCase):
    """Valida argumentos reais da aprovação sem enviar transações Fabric."""
    def setUp(self):
        self.peer = types.SimpleNamespace(volumes=['/local/ca.crt:' + common.ORDERER_CLI_CA + ':ro'])
        self.orderer = types.SimpleNamespace(
            volumes=['/crypto/orderers/orderer0.example.com/tls:/etc/hyperledger/fabric/tls'],
            environment={'ORDERER_GENERAL_LISTENPORT':'7050'})
        self.definition = {'channel':'mychannel','name':'assets','version':'1.0','sequence':1}

    def test_approval_uses_supplied_id_definition_and_orderer_tls(self):
        evidence = completed('accepted', 'event received')
        with patch.object(common, 'peer_lifecycle', return_value=evidence) as execute:
            result = common.approve_chaincode_for_org(
                self.peer, '192.0.2.2', self.orderer, self.definition, 'assets_1.0:dynamic-hash')
        args = execute.call_args.args[2]
        self.assertEqual(args[0], 'approveformyorg')
        for flag, value in [('--name','assets'),('--package-id','assets_1.0:dynamic-hash'),
                            ('--sequence','1'),('--channelID','mychannel'),
                            ('-o','orderer0.example.com:7050'),
                            ('--cafile',common.ORDERER_CLI_CA),
                            ('--ordererTLSHostnameOverride','orderer0.example.com')]:
            self.assertEqual(args[args.index(flag)+1], value)
        self.assertIn('--tls', args)
        self.assertIn('--waitForEvent', args)
        self.assertIs(result, evidence)
        self.assertEqual(execute.call_count, 1)

    def test_approval_rejects_missing_package_or_ca(self):
        with patch.object(common, 'peer_lifecycle') as execute:
            with self.assertRaises(ValueError):
                common.approve_chaincode_for_org(self.peer, '', self.orderer, self.definition, '')
            self.peer.volumes = []
            with self.assertRaises(ValueError):
                common.approve_chaincode_for_org(self.peer, '', self.orderer, self.definition, 'id')
            execute.assert_not_called()

    def test_approval_preserves_failure_without_retry(self):
        with patch.object(common, 'peer_lifecycle', side_effect=RuntimeError('exit code: 1; TLS failure')) as execute:
            with self.assertRaisesRegex(RuntimeError, 'TLS failure'):
                common.approve_chaincode_for_org(self.peer, '', self.orderer, self.definition, 'id')
            self.assertEqual(execute.call_count, 1)


class CommitTests(ApprovalTests):
    """Exercita critérios semânticos do incremento sem executar Fabric."""
    def test_readiness_requires_boolean_approval(self):
        self.peer.environment = {'CORE_PEER_LOCALMSPID': 'Org1MSP'}
        for approvals in ({}, {'Org1MSP': False}, {'Org1MSP': 'true'}, {'Org1MSP': 1}):
            with self.subTest(approvals=approvals), patch.object(
                    common, 'peer_lifecycle', return_value=completed(json.dumps({'approvals': approvals}))):
                with self.assertRaises(RuntimeError):
                    common.check_commit_readiness(self.peer, '', self.definition)
        for field in ('approvals', 'Approvals'):
            response = completed(json.dumps({field: {'Org1MSP': True}}), 'INFO')
            with patch.object(common, 'peer_lifecycle', return_value=response):
                approvals, evidence = common.check_commit_readiness(self.peer, '', self.definition)
            self.assertIs(approvals['Org1MSP'], True)
            self.assertEqual(evidence.stderr, 'INFO')

    def test_commit_waits_and_rejects_invalid_event_even_exit_zero(self):
        for stream in ('stdout', 'stderr'):
            response = completed(**{stream: 'txid [abc] committed with status (MVCC_READ_CONFLICT)'})
            with patch.object(common, 'peer_lifecycle', return_value=response) as execute:
                with self.assertRaisesRegex(RuntimeError, 'transação inválida'):
                    common.commit_chaincode_definition(self.peer, '', self.orderer, self.definition)
                self.assertEqual(execute.call_count, 1)
        response = completed(stderr='txid [abc] committed with status (VALID)')
        with patch.object(common, 'peer_lifecycle', return_value=response) as execute:
            self.assertIs(common.commit_chaincode_definition(
                self.peer, '', self.orderer, self.definition), response)
        args = execute.call_args.args[2]
        self.assertIn('--waitForEvent', args)
        self.assertIn('orderer0.example.com:7050', args)
        self.assertNotIn('--package-id', args)
        self.assertEqual(args[args.index('--name') + 1], 'assets')

    def test_querycommitted_checks_full_definition(self):
        found = {k: self.definition[k] for k in ('name', 'version', 'sequence')}
        invalid = [[], [dict(found, version='2.0')], [dict(found, sequence=2)],
                   [dict(found, name='other')], [dict(found, sequence=True)], [found, found]]
        for entries in invalid:
            with self.subTest(entries=entries), patch.object(common, 'peer_lifecycle', return_value=
                    completed(json.dumps({'chaincode_definitions': entries}))):
                with self.assertRaises(RuntimeError):
                    common.query_committed_chaincode(self.peer, '', self.definition)
        response = completed(json.dumps({'chaincode_definitions': [found]}), 'INFO')
        with patch.object(common, 'peer_lifecycle', return_value=response):
            actual, evidence = common.query_committed_chaincode(self.peer, '', self.definition)
        self.assertEqual(actual, found)
        self.assertIs(evidence, response)

    def test_queries_reject_malformed_json(self):
        self.peer.environment = {'CORE_PEER_LOCALMSPID': 'Org1MSP'}
        for body in ('not JSON', '{}', 'null', '[]'):
            for query in (common.check_commit_readiness, common.query_committed_chaincode):
                with self.subTest(body=body, query=query.__name__), patch.object(
                        common, 'peer_lifecycle', return_value=completed(body, 'diagnostic')):
                    with self.assertRaisesRegex(RuntimeError, 'diagnostic'):
                        query(self.peer, '', self.definition)


if __name__ == '__main__':
    unittest.main()

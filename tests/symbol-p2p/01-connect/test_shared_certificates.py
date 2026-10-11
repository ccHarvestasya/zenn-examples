import hashlib
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[3]
COMMON = REPO / 'symbol-p2p/common'


class SharedCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.common = cls.root / 'shared certificate directory'
        cls.common.mkdir()
        cls.script = cls.common / 'generate_certificates.sh'
        shutil.copyfile(COMMON / 'generate_certificates.sh', cls.script)
        subprocess.run(['bash', str(cls.script)], cwd=cls.root,
                       check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_default_location_validity_and_private_key_permissions(self):
        for name, days in [('ca', 3650), ('node', 365)]:
            certificate = self.common / 'cert' / f'{name}.crt.pem'
            dates = subprocess.check_output([
                'openssl', 'x509', '-in', str(certificate), '-noout', '-dates',
            ], text=True).splitlines()
            values = dict(line.split('=', 1) for line in dates)
            self.assertEqual(ssl.cert_time_to_seconds(values['notAfter']) -
                             ssl.cert_time_to_seconds(values['notBefore']),
                             days * 86400)
            self.assertEqual((self.common / 'cert' / f'{name}.key.pem').stat().st_mode & 0o777,
                             0o600)
        self.assertFalse((self.root / 'cert').exists())

    def test_existing_identity_is_not_overwritten(self):
        directory = self.common / 'cert'
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in directory.iterdir()}
        result = subprocess.run(['bash', str(self.script)], cwd=self.root,
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in directory.iterdir()}
        self.assertEqual(before, after)

    def test_all_clients_resolve_the_same_directory_from_another_cwd(self):
        expected = str(COMMON / 'cert')
        files = [p for p in (REPO / 'symbol-p2p').glob('*/*.py')
                 if 'CERT_DIRECTORY =' in p.read_text()]
        self.assertGreater(len(files), 1)
        for script in files:
            with self.subTest(script=str(script.relative_to(REPO))):
                code = ('import importlib,sys; sys.path.insert(0,sys.argv[1]); '
                        'print(importlib.import_module(sys.argv[2]).CERT_DIRECTORY)')
                directory = subprocess.check_output([
                    sys.executable, '-c', code, str(script.parent), script.stem,
                ], cwd=self.root, text=True).strip()
                self.assertEqual(directory, expected)

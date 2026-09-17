import json
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


class SetupConfigTest(unittest.TestCase):
    def test_api_key_update_preserves_other_settings_and_escapes_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'config.json'
            original = {'api_key': 'old-key', 'desktop_1_only': True, 'future_setting': {'keep': True}}
            path.write_text(json.dumps(original))
            source = (Path(__file__).parent / 'setup.sh').read_text()
            prefix = source.split('echo "Step 2: Test the script"', 1)[0]
            prefix = prefix.replace('WALLPAPER_DIR="$HOME/.nasa_apod_wallpapers"',
                                    'WALLPAPER_DIR=' + shlex.quote(str(root)))
            key = 'test-"quoted"-\\key'
            subprocess.run(['/bin/bash', '-c', prefix], input='y' + key + '\n',
                           text=True, capture_output=True, check=True)
            original['api_key'] = key
            self.assertEqual(original, json.loads(path.read_text()))
            self.assertEqual(0o600, path.stat().st_mode & 0o777)


if __name__ == '__main__':
    unittest.main()

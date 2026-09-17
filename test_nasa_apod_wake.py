import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == 'darwin' and shutil.which('swiftc'), 'Requires macOS and swiftc')
class WakeListenerTest(unittest.TestCase):
    def test_delivers_events_after_an_active_updater_exits(self):
        domain = f'gui/{os.getuid()}'
        if subprocess.run(['launchctl', 'print', domain], capture_output=True).returncode:
            self.skipTest('Requires a macOS GUI session')
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            label = f'com.nasa.apod.wallpaper.test.{os.getpid()}'
            target = f'{domain}/{label}'
            event = label + '.screen'
            unlock = label + '.unlock'
            starts_path = directory / 'starts.log'
            log_path = directory / 'listener.log'
            source = (Path(__file__).parent / 'nasa_apod_wake.swift').read_text()
            source = source.replace('com.nasa.apod.wallpaper"', label + '"')
            source = source.replace('com.apple.screenIsUnlocked', unlock)
            source = source.replace('app.run()', f'''
let testObserver = DistributedNotificationCenter.default().addObserver(
    forName: Notification.Name("{event}"), object: nil, queue: .main
) {{ _ in
    NotificationCenter.default.post(name: NSApplication.didChangeScreenParametersNotification, object: app)
}}
app.run()
''')
            (directory / 'listener.swift').write_text(source)
            (directory / 'post.swift').write_text('''import Foundation
DistributedNotificationCenter.default().postNotificationName(
    Notification.Name(CommandLine.arguments[1]), object: nil, userInfo: nil, deliverImmediately: true
)
''')
            for name in ('listener', 'post'):
                subprocess.run(['swiftc', '-O', '-warnings-as-errors', str(directory / f'{name}.swift'),
                                '-o', str(directory / name)], check=True, capture_output=True)
            (directory / 'updater.py').write_text('''import os
import sys
import time
from pathlib import Path
directory = Path(sys.argv[1])
with (directory / 'starts.log').open('a') as output:
    output.write(str(os.getpid()) + '\\n')
count = len((directory / 'starts.log').read_text().splitlines())
deadline = time.monotonic() + 50
while not (directory / f'release-{count}').exists() and time.monotonic() < deadline:
    time.sleep(0.05)
''')
            plist = directory / 'updater.plist'
            plist.write_bytes(plistlib.dumps({
                'Label': label,
                'ProgramArguments': ['/usr/bin/python3', str(directory / 'updater.py'), str(directory)],
                'StandardOutPath': str(directory / 'updater.log'),
                'StandardErrorPath': str(directory / 'updater.log'),
            }))

            def wait_for(predicate):
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if predicate():
                        return
                    time.sleep(0.05)
                self.fail(log_path.read_text())

            def starts():
                return starts_path.read_text().splitlines() if starts_path.exists() else []

            def state():
                return subprocess.check_output(['launchctl', 'print', target], text=True)

            def post(name):
                subprocess.run([str(directory / 'post'), name], check=True)

            self.assertNotEqual(0, subprocess.run(['launchctl', 'print', target], capture_output=True).returncode)
            subprocess.run(['launchctl', 'bootstrap', domain, str(plist)], check=True)
            listener = None
            try:
                with log_path.open('w') as log:
                    listener = subprocess.Popen([str(directory / 'listener')], stdout=log, stderr=log)
                    wait_for(lambda: 'listener is ready' in log_path.read_text())
                    subprocess.run(['launchctl', 'kickstart', target], check=True)
                    wait_for(lambda: len(starts()) == 1)
                    first_pid = starts()[0]
                    post(event)
                    post(unlock)
                    wait_for(lambda: 'refresh is pending' in log_path.read_text())
                    self.assertEqual([first_pid], starts())
                    self.assertIn(f'pid = {first_pid}', state())
                    (directory / 'release-1').touch()
                    wait_for(lambda: len(starts()) == 2)
                    self.assertNotEqual(first_pid, starts()[1])
                    post(event)
                    wait_for(lambda: log_path.read_text().count('refresh is pending') >= 2)
                    self.assertEqual(2, len(starts()))
                    (directory / 'release-2').touch()
                    wait_for(lambda: len(starts()) == 3)
                    (directory / 'release-3').touch()
                    wait_for(lambda: 'state = not running' in state())
                    time.sleep(6)
                    self.assertEqual(3, len(starts()))
                    self.assertIn('last exit code = 0', state())
            finally:
                if listener is not None:
                    listener.terminate()
                    listener.wait(timeout=5)
                subprocess.run(['launchctl', 'bootout', target], check=True)


if __name__ == '__main__':
    unittest.main()

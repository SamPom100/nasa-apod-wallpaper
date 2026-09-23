import json
import os
import plistlib
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.parse import unquote, urlparse

os.environ.setdefault('NASA_API_KEY', 'test-key')
import nasa_apod_wallpaper as apod
from test_nasa_apod_wallpaper import JPEG_IMAGE
from test_wallpaper_store import desktop


class WallpaperRotationTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = self.root / 'Index.plist'
        self.contexts = [
            {'display_uuid': 'primary', 'space_uuid': space, 'current_space_uuid': 'space-2'}
            for space in ('space-1', 'space-2')
        ]
        self.external = {'display_uuid': 'external', 'space_uuid': 'space-3',
                         'current_space_uuid': 'space-3'}
        self.store.write_bytes(plistlib.dumps({'Spaces': {
            space: {'Default': {'Desktop': desktop('/old.jpg')}}
            for space in ('space-1', 'space-2', 'space-3')
        }}))
        for day in range(1, 6):
            self.cache(f'2000-01-{day:02d}')
        self.shuffle_count = 0
        for name, value in [
            ('WALLPAPER_DIR', self.root),
            ('CONFIG_FILE', self.root / 'config.json'),
            ('WALLPAPER_STORE_INDEX', self.store),
            ('get_desktop_contexts', mock.Mock(return_value=self.contexts)),
            ('is_valid_image', mock.Mock(side_effect=lambda path: Path(path).is_file())),
            ('load_config', mock.Mock(return_value={})),
            ('send_notification', mock.Mock()),
        ]:
            patch = mock.patch.object(apod, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        for patch in [mock.patch.object(apod.subprocess, 'run'),
                      mock.patch.object(apod.time, 'sleep'),
                      mock.patch.object(apod.random, 'shuffle', side_effect=self.shuffle),
                      mock.patch.object(apod.random, 'choice', side_effect=lambda paths: paths[0])]:
            patch.start()
            self.addCleanup(patch.stop)

    def cache(self, date):
        path = self.root / f'apod_{date}.jpg'
        path.write_bytes(JPEG_IMAGE)
        return path

    def shuffle(self, paths):
        if paths:
            paths.sort()
            offset = self.shuffle_count % len(paths)
            paths[:] = paths[offset:] + paths[:offset]
            self.shuffle_count += 1

    def refresh(self, date='2026-09-23', media_type='image', args=(), metadata_date=None,
                download_available=True):
        data = {'date': metadata_date or date, 'media_type': media_type,
                'title': 'APOD', 'explanation': 'An astronomy image.'} if media_type else None
        with mock.patch.object(apod, 'datetime', wraps=datetime) as clock, \
                mock.patch.object(apod, 'fetch_apod_with_fallback', return_value=data), \
                mock.patch.object(apod, 'download_apod_image',
                                  side_effect=lambda data, date, **kwargs:
                                  self.cache(date) if download_available else None), \
                mock.patch('sys.argv', ['nasa_apod_wallpaper.py', *args]):
            clock.now.return_value = datetime.strptime(date, '%Y-%m-%d')
            apod.main()
        return self.assignments()

    def assignments(self):
        data = plistlib.loads(self.store.read_bytes())
        result = {}
        for context in self.contexts:
            choice = data['Spaces'][context['space_uuid']]['Displays'][context['display_uuid']]['Desktop']['Content']['Choices'][0]
            url = plistlib.loads(choice['Configuration'])['url']['relative']
            result[context['space_uuid']] = Path(unquote(urlparse(url).path))
        return result

    def test_refresh_and_cache_addition_keep_the_same_random_image(self):
        first = self.refresh()
        self.cache('1999-12-31')
        self.assertEqual(first, self.refresh())
        self.assertEqual(first, self.refresh())

    def test_next_apod_changes_the_random_image(self):
        first = self.refresh()
        second = self.refresh('2026-09-24')
        self.assertEqual('apod_2026-09-24.jpg', second['space-1'].name)
        self.assertNotEqual(first['space-2'], second['space-2'])
        self.assertEqual(second, self.refresh('2026-09-24'))

    def test_video_keeps_both_random_images_until_the_next_apod(self):
        first = self.refresh(media_type='video')
        self.assertEqual(2, len(set(first.values())))
        self.assertEqual(first, self.refresh(media_type='video'))
        self.assertEqual(first, self.refresh(media_type=None))
        self.assertEqual(1, apod.send_notification.call_count)
        second = self.refresh('2026-09-24')
        self.assertEqual('apod_2026-09-24.jpg', second['space-1'].name)
        self.assertNotEqual(first['space-2'], second['space-2'])

    def test_failed_request_preserves_choices_until_the_next_apod_arrives(self):
        first = self.refresh()
        self.assertEqual(first, self.refresh('2026-09-24', media_type=None))
        self.assertEqual(first, self.refresh('2026-09-24', metadata_date='2026-09-23'))
        second = self.refresh('2026-09-24')
        self.assertNotEqual(first['space-2'], second['space-2'])

    def test_older_metadata_after_a_video_does_not_rotate_backwards(self):
        first = self.refresh(media_type='video')
        self.assertEqual(first, self.refresh(metadata_date='2026-09-22'))

    def test_image_recovery_on_the_same_apod_date_keeps_the_secondary_choice(self):
        first = self.refresh(download_available=False)
        self.assertEqual(first, self.refresh(download_available=False))
        recovered = self.refresh()
        self.assertEqual('apod_2026-09-23.jpg', recovered['space-1'].name)
        self.assertEqual(first['space-2'], recovered['space-2'])

    def test_first_run_without_nasa_keeps_random_choices_until_an_apod_arrives(self):
        first = self.refresh(media_type=None)
        self.assertEqual(first, self.refresh(media_type=None))
        recovered = self.refresh()
        self.assertNotEqual(first['space-2'], recovered['space-2'])

    def test_reconnect_and_new_display_keep_existing_choices(self):
        first = self.refresh()
        self.contexts.append(self.external)
        expanded = self.refresh()
        self.assertEqual(first['space-2'], expanded['space-2'])
        self.assertEqual(3, len(set(expanded.values())))
        self.contexts.pop()
        self.assertEqual(first, self.refresh())
        self.contexts.insert(1, self.external)
        self.assertEqual(expanded, self.refresh())

    def test_missing_image_replaces_only_that_desktop(self):
        self.contexts.append(self.external)
        first = self.refresh()
        first['space-2'].unlink()
        second = self.refresh()
        self.assertNotEqual(first['space-2'], second['space-2'])
        self.assertEqual(first['space-1'], second['space-1'])
        self.assertEqual(first['space-3'], second['space-3'])

    def test_disconnected_display_rotates_when_it_returns_after_a_new_apod(self):
        self.contexts.append(self.external)
        first = self.refresh()
        self.contexts.pop()
        current = self.refresh('2026-09-24')
        self.contexts.append(self.external)
        reconnected = self.refresh('2026-09-24')
        self.assertEqual(current['space-2'], reconnected['space-2'])
        self.assertNotEqual(first['space-3'], reconnected['space-3'])

    def test_primary_only_update_does_not_consume_the_secondary_rotation(self):
        first = self.refresh()
        primary_only = self.refresh('2026-09-24', args=['--desktop-1-only'])
        self.assertEqual(first['space-2'], primary_only['space-2'])
        second = self.refresh('2026-09-24')
        self.assertNotEqual(first['space-2'], second['space-2'])

    def test_shuffle_changes_the_random_image_and_refresh_retains_it(self):
        first = self.refresh()
        shuffled = self.refresh(args=['--shuffle'])
        self.assertNotEqual(first['space-2'], shuffled['space-2'])
        refreshed = self.refresh()
        self.assertEqual(first['space-1'], refreshed['space-1'])
        self.assertEqual(shuffled['space-2'], refreshed['space-2'])

    def test_force_refetch_keeps_the_random_image(self):
        first = self.refresh()
        self.assertEqual(first, self.refresh(args=['--force']))

    def test_failed_store_write_preserves_the_saved_choices(self):
        first = self.refresh()
        before = (self.root / 'wallpaper_state.json').read_bytes()
        with mock.patch.object(apod, 'set_wallpapers_in_store', return_value=False):
            with self.assertRaises(SystemExit):
                self.refresh('2026-09-24')
        self.assertEqual(before, (self.root / 'wallpaper_state.json').read_bytes())
        self.assertEqual(first, self.assignments())

    def test_corrupt_state_recovers_with_valid_assignments(self):
        for contents in ['{', '[]', json.dumps({'desktops': {'bad': []}})]:
            with self.subTest(contents=contents):
                (self.root / 'wallpaper_state.json').write_text(contents)
                first = self.refresh()
                self.assertTrue(all(path.is_file() for path in first.values()))
                self.assertEqual(first, self.refresh())


if __name__ == '__main__':
    unittest.main()

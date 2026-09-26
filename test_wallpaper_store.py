import copy
import json
import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault('NASA_API_KEY', 'test-key')
import nasa_apod_wallpaper as apod


def desktop(image):
    return {
        'Content': {
            'Choices': [{
                'Provider': 'com.apple.wallpaper.choice.image',
                'Files': [{'relative': Path(image).as_uri()}],
                'Configuration': plistlib.dumps({
                    'type': 'imageFile', 'url': {'relative': Path(image).as_uri()},
                }, fmt=plistlib.FMT_BINARY),
            }],
            'EncodedOptionValues': b'keep-options',
        },
        'LastSet': 'keep-timestamp',
    }


class DesktopContextTest(unittest.TestCase):
    def test_prefers_the_physical_display_and_first_normal_space(self):
        data = {'display_uuids': ['primary'], 'monitors': [
            {'Display Identifier': 'Main', 'Spaces': [{'uuid': 'other'}],
             'Current Space': {'uuid': 'other'}},
            {'Display Identifier': 'primary', 'Spaces': [
                {'uuid': 'fullscreen', 'type': 4}, {'uuid': 'space-1', 'type': 0},
            ], 'Current Space': {'uuid': 'space-2'}},
        ]}
        with mock.patch.object(apod.subprocess, 'run', return_value=mock.Mock(stdout=json.dumps(data))):
            result = apod.get_desktop_contexts()
        self.assertEqual([{'display_uuid': 'primary', 'space_uuid': 'space-1',
                          'current_space_uuid': 'space-2'}], result)

    def test_uses_main_when_the_display_has_no_separate_spaces(self):
        data = {'display_uuids': ['primary'], 'monitors': [
            {'Display Identifier': 'primary', 'Spaces': []},
            {'Display Identifier': 'Main', 'Spaces': [{'uuid': ''}],
             'Current Space': {'uuid': ''}},
        ]}
        with mock.patch.object(apod.subprocess, 'run', return_value=mock.Mock(stdout=json.dumps(data))):
            self.assertEqual('', apod.get_desktop_contexts()[0]['space_uuid'])

    def test_unknown_context_does_not_read_the_active_wallpaper(self):
        with mock.patch.object(apod, 'get_desktop_contexts', return_value=[]):
            self.assertIsNone(apod.get_current_desktop_1_wallpaper())

    def test_lists_all_normal_spaces_on_connected_displays(self):
        data = {'display_uuids': ['primary', 'external'], 'monitors': [
            {'Display Identifier': 'external', 'Spaces': [{'uuid': 'space-3'}],
             'Current Space': {'uuid': 'space-3'}},
            {'Display Identifier': 'primary', 'Spaces': [
                {'uuid': '', 'type': 0}, {'uuid': 'fullscreen', 'type': 4},
                {'uuid': 'space-2', 'type': 0},
            ], 'Current Space': {'uuid': 'space-2'}},
            {'Display Identifier': 'disconnected', 'Spaces': [{'uuid': 'old-space'}]},
        ]}
        with mock.patch.object(apod.subprocess, 'run', return_value=mock.Mock(stdout=json.dumps(data))):
            result = apod.get_desktop_contexts()
        self.assertEqual([('primary', ''), ('primary', 'space-2'), ('external', 'space-3')],
                         [(item['display_uuid'], item['space_uuid']) for item in result])


class WallpaperStoreTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / 'Index.plist'
        self.context = {'display_uuid': 'primary', 'space_uuid': 'space-1',
                        'current_space_uuid': 'space-2'}
        self.contexts = [self.context]
        self.data = {'Spaces': {
            'space-0': {'Default': {'Desktop': desktop('/other-space.jpg')}},
            'space-1': {
                'Default': {'Desktop': desktop('/default.jpg')},
                'Displays': {
                    'primary': {'Desktop': desktop('/primary.jpg'), 'Idle': {'keep': True}},
                    'external': {'Desktop': desktop('/external.jpg')},
                },
            },
        }, 'SystemDefault': {'keep': True}}
        self.save()
        for name, value in [('WALLPAPER_DIR', self.root),
                            ('WALLPAPER_STORE_INDEX', self.path),
                            ('get_desktop_contexts', mock.Mock(return_value=self.contexts))]:
            patch = mock.patch.object(apod, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def save(self):
        self.path.write_bytes(plistlib.dumps(self.data, fmt=plistlib.FMT_BINARY))

    def test_updates_only_the_primary_configuration_and_round_trips_the_path(self):
        image = Path('/wallpapers/new image.jpg')
        with mock.patch.object(apod.subprocess, 'run') as run:
            self.assertTrue(apod.set_wallpapers_in_store([(self.context, image)]))
            self.assertEqual(image, apod.get_current_desktop_1_wallpaper())
        self.assertEqual(1, run.call_count)
        updated = plistlib.loads(self.path.read_bytes())
        choices = updated['Spaces']['space-1']['Displays']['primary']['Desktop']['Content']['Choices']
        self.assertEqual([{'relative': image.as_uri()}], choices[0]['Files'])
        self.assertEqual(image.as_uri(), plistlib.loads(choices[0]['Configuration'])['url']['relative'])
        expected = copy.deepcopy(self.data)
        expected['Spaces']['space-1']['Displays']['primary']['Desktop']['Content']['Choices'] = choices
        self.assertEqual(expected, updated)
        self.assertTrue(self.path.read_bytes().startswith(b'bplist00'))
        self.assertEqual([self.path], list(self.root.iterdir()))

    def test_creates_a_primary_override_without_changing_shared_defaults(self):
        del self.data['Spaces']['space-1']['Displays']['primary']['Desktop']
        self.save()
        with mock.patch.object(apod.subprocess, 'run'):
            self.assertTrue(apod.set_wallpapers_in_store([(self.context, Path('/new.jpg'))]))
        updated = plistlib.loads(self.path.read_bytes())
        primary = updated['Spaces']['space-1']['Displays']['primary']
        self.assertEqual({'keep': True}, primary['Idle'])
        del primary['Desktop']
        self.assertEqual(self.data, updated)

    def test_unknown_space_does_not_change_a_different_space(self):
        self.context['space_uuid'] = 'missing'
        before = self.path.read_bytes()
        with mock.patch.object(apod.subprocess, 'run') as run:
            self.assertFalse(apod.set_wallpapers_in_store([(self.context, Path('/new.jpg'))]))
        self.assertEqual(before, self.path.read_bytes())
        run.assert_not_called()

    def test_empty_choices_do_not_report_success(self):
        self.data['Spaces']['space-1']['Displays']['primary']['Desktop']['Content']['Choices'] = []
        self.save()
        before = self.path.read_bytes()
        with mock.patch.object(apod.subprocess, 'run') as run:
            self.assertFalse(apod.set_wallpapers_in_store([(self.context, Path('/new.jpg'))]))
        self.assertEqual(before, self.path.read_bytes())
        run.assert_not_called()

    def test_failed_replace_preserves_the_store_and_removes_the_temporary_file(self):
        before = self.path.read_bytes()
        with mock.patch.object(Path, 'replace', side_effect=OSError('replace failed')), \
                mock.patch.object(apod.subprocess, 'run') as run:
            self.assertFalse(apod.set_wallpapers_in_store([(self.context, Path('/new.jpg'))]))
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([self.path], list(self.root.iterdir()))
        run.assert_not_called()

    def test_reader_prefers_configuration_to_stale_files(self):
        choice = self.data['Spaces']['space-1']['Displays']['primary']['Desktop']['Content']['Choices'][0]
        choice['Files'] = [{'relative': 'file:///stale.jpg'}]
        self.save()
        with mock.patch.object(apod.subprocess, 'run') as run:
            self.assertEqual(Path('/primary.jpg'), apod.get_current_desktop_1_wallpaper())
        run.assert_not_called()

    def test_reader_uses_inherited_defaults(self):
        del self.data['Spaces']['space-1']['Displays']['primary']
        self.save()
        self.assertEqual(Path('/default.jpg'), apod.get_current_desktop_1_wallpaper())

    def test_inactive_space_with_missing_store_does_not_read_the_active_wallpaper(self):
        self.path.unlink()
        with mock.patch.object(apod.subprocess, 'run') as run:
            self.assertIsNone(apod.get_current_desktop_1_wallpaper())
        run.assert_not_called()

    def test_failed_inactive_update_never_sets_the_active_space(self):
        self.path.unlink()
        with mock.patch.object(apod.subprocess, 'run', return_value=mock.Mock(stdout='2\n')) as run, \
                mock.patch.object(apod.time, 'sleep'):
            with self.assertRaises(SystemExit):
                apod.set_macos_wallpaper(Path('/new.jpg'), desktop_1_only=True)
        run.assert_not_called()

    def test_default_refresh_repairs_desktop_2_while_it_is_active(self):
        today = apod.datetime.now().strftime('%Y-%m-%d')
        image = Path(f'/wallpapers/apod_{today}.jpg')
        other = Path('/wallpapers/apod_2000-01-01.jpg')
        self.contexts.append(dict(self.context, space_uuid='space-2'))
        self.data['Spaces']['space-2'] = {'Default': {'Desktop': desktop(str(image))}}
        self.save()
        with mock.patch.object(apod, 'cached_image_files', return_value=[image, other]), \
                mock.patch.object(apod, 'load_config', return_value={}), \
                mock.patch.object(apod, 'fetch_apod_with_fallback') as fetch, \
                mock.patch.object(apod, 'send_notification') as notify, \
                mock.patch.object(apod.subprocess, 'run') as run, \
                mock.patch('sys.argv', ['nasa_apod_wallpaper.py']):
            apod.main()
        result = plistlib.loads(self.path.read_bytes())
        assigned = []
        for context in self.contexts:
            choice = result['Spaces'][context['space_uuid']]['Displays']['primary']['Desktop']['Content']['Choices'][0]
            assigned.append(plistlib.loads(choice['Configuration'])['url']['relative'])
        self.assertEqual([image.as_uri(), other.as_uri()], assigned)
        self.assertEqual(self.data['Spaces']['space-0'], result['Spaces']['space-0'])
        self.assertEqual(self.data['Spaces']['space-1']['Displays']['external'],
                         result['Spaces']['space-1']['Displays']['external'])
        fetch.assert_not_called()
        notify.assert_not_called()
        run.assert_called_once_with(['/usr/bin/killall', 'WallpaperAgent'], check=False, timeout=10)

    def test_cache_shortage_reuses_old_images_instead_of_apod(self):
        image, other = Path('/today.jpg'), Path('/older.jpg')
        self.contexts.extend([
            dict(self.context, display_uuid='external'),
            dict(self.context, space_uuid='space-0'),
        ])
        with mock.patch.object(apod, 'cached_image_files', return_value=[image, other]), \
                mock.patch.object(apod.subprocess, 'run'):
            apod.set_macos_wallpaper(image)
        result = plistlib.loads(self.path.read_bytes())
        assigned = []
        for context in self.contexts:
            choice = result['Spaces'][context['space_uuid']]['Displays'][context['display_uuid']]['Desktop']['Content']['Choices'][0]
            assigned.append(plistlib.loads(choice['Configuration'])['url']['relative'])
        self.assertEqual([image.as_uri(), other.as_uri(), other.as_uri()], assigned)

    def test_no_alternative_keeps_secondary_desktops_unchanged(self):
        image = Path('/today.jpg')
        self.contexts.append(dict(self.context, display_uuid='external'))
        with mock.patch.object(apod, 'cached_image_files', return_value=[image]), \
                mock.patch.object(apod.subprocess, 'run'):
            apod.set_macos_wallpaper(image)
        result = plistlib.loads(self.path.read_bytes())
        self.assertEqual(self.data['Spaces']['space-1']['Displays']['external'],
                         result['Spaces']['space-1']['Displays']['external'])

    def test_secondary_selection_excludes_today_when_primary_is_a_historical_image(self):
        today = Path(f'/wallpapers/apod_{apod.datetime.now():%Y-%m-%d}.jpg')
        primary = Path('/wallpapers/apod_2000-01-01.jpg')
        other = Path('/wallpapers/apod_2000-01-02.jpg')
        with mock.patch.object(apod, 'cached_image_files', return_value=[today, primary, other]):
            self.assertEqual([other], apod.pick_cache_images(primary, 3))

    def test_invalid_secondary_target_cannot_partially_change_desktop_1(self):
        before = self.path.read_bytes()
        assignments = [(self.context, Path('/today.jpg')),
                       (dict(self.context, space_uuid='missing'), Path('/other.jpg'))]
        with mock.patch.object(apod.subprocess, 'run') as run:
            self.assertFalse(apod.set_wallpapers_in_store(assignments))
        self.assertEqual(before, self.path.read_bytes())
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()

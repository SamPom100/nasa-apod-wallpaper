import base64
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("NASA_API_KEY", "test-key")

import nasa_apod_wallpaper as apod


JPEG_IMAGE = base64.b64decode(
    '/9j/wAALCAABAAEBAREA/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgED'
    'AwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcY'
    'GRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJ'
    'ipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo'
    '6erx8vP09fb3+Pn6/9sAQwACAgICAgIDAgIDBQMDAwUGBQUFBQYIBgYGBgYICggICAgICAoKCgoK'
    'CgoKDAwMDAwMDg4ODg4PDw8PDw8PDw8P/90ABAAB/9oACAEBAAA/APwDr//Z'
)
GIF_IMAGE = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')


class DownloadApodImageTest(unittest.TestCase):
    def test_uses_website_full_image_when_hd_url_fails(self):
        expected_path = Path("/tmp/apod_2026-08-20.jpeg")
        data = {
            "hdurl": "https://example.com/missing.jpeg",
            "url": "https://example.com/standard.jpeg",
        }

        with mock.patch.object(
            apod,
            "fetch_apod_page_image_url",
            return_value="https://example.com/full.jpeg",
        ):
            with mock.patch.object(
                apod,
                "download_image",
                side_effect=[None, expected_path],
            ) as download_image:
                result = apod.download_apod_image(data, "2026-08-20")

        self.assertEqual(expected_path, result)
        self.assertEqual(
            [
                mock.call(
                    "https://example.com/missing.jpeg",
                    "apod_2026-08-20.jpeg",
                    exit_on_error=False,
                ),
                mock.call(
                    "https://example.com/full.jpeg",
                    "apod_2026-08-20.jpeg",
                    exit_on_error=False,
                ),
            ],
            download_image.call_args_list,
        )

    def test_does_not_use_the_api_display_image(self):
        data = {
            "hdurl": "https://example.com/missing-hd.jpeg",
            "url": "https://example.com/standard.jpeg",
        }

        with mock.patch.object(
            apod,
            "fetch_apod_page_image_url",
            return_value=None,
        ):
            with mock.patch.object(
                apod,
                "download_image",
                return_value=None,
            ) as download_image:
                result = apod.download_apod_image(
                    data,
                    "2026-08-20",
                    exit_on_error=False,
                )

        self.assertIsNone(result)
        download_image.assert_called_once_with(
            "https://example.com/missing-hd.jpeg",
            "apod_2026-08-20.jpeg",
            exit_on_error=False,
        )

    def test_accepts_an_image_smaller_than_500_kb(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with mock.patch.object(
                apod,
                "WALLPAPER_DIR",
                Path(temporary_directory),
            ):
                with mock.patch.object(
                    apod.urllib.request,
                    "urlopen",
                    return_value=io.BytesIO(JPEG_IMAGE),
                ):
                    result = apod.download_image(
                        "https://example.com/image.jpeg",
                        "apod_2026-08-20.jpeg",
                    )

            self.assertEqual(JPEG_IMAGE, result.read_bytes())

    def test_rejects_invalid_downloads_without_replacing_cached_image(self):
        for content in (b'<html>Service unavailable</html>', b'', JPEG_IMAGE[:20]):
            with self.subTest(content=content):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    directory = Path(temporary_directory)
                    image = directory / 'apod_2026-09-14.jpg'
                    image.write_bytes(JPEG_IMAGE)
                    with mock.patch.object(apod, 'WALLPAPER_DIR', directory), \
                            mock.patch.object(apod.urllib.request, 'urlopen', return_value=io.BytesIO(content)):
                        result = apod.download_image(
                            'https://example.com/image.jpg', image.name, exit_on_error=False,
                        )

                    self.assertIsNone(result)
                    self.assertEqual(JPEG_IMAGE, image.read_bytes())
                    self.assertFalse(image.with_suffix('.jpg.download').exists())

    def test_uses_website_when_hd_response_is_not_an_image(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            with mock.patch.object(apod, 'WALLPAPER_DIR', directory), \
                    mock.patch.object(apod, 'fetch_apod_page_image_url', return_value='https://example.com/full.jpg'), \
                    mock.patch.object(apod.urllib.request, 'urlopen', side_effect=[
                        io.BytesIO(b'<html>Service unavailable</html>'), io.BytesIO(JPEG_IMAGE),
                    ]):
                result = apod.download_apod_image(
                    {'hdurl': 'https://example.com/broken.jpg'}, '2026-09-14',
                )

            self.assertEqual(JPEG_IMAGE, result.read_bytes())

    def test_returns_none_when_all_urls_fail(self):
        data = {
            "hdurl": "https://example.com/missing-hd.jpeg",
            "url": "https://example.com/missing-standard.jpeg",
        }

        with mock.patch.object(
            apod,
            "fetch_apod_page_image_url",
            return_value="https://example.com/missing-page.jpeg",
        ):
            with mock.patch.object(
                apod,
                "download_image",
                return_value=None,
            ):
                result = apod.download_apod_image(
                    data,
                    "2026-08-20",
                    exit_on_error=False,
                )

        self.assertIsNone(result)


class ApodPageParserTest(unittest.TestCase):
    def test_finds_the_link_around_the_display_image(self):
        parser = apod.ApodPageParser()
        parser.feed(
            '<a href="image/2608/IMG_5201.jpeg">'
            '<IMG SRC="image/2608/IMG_5201_sgarbossa1024.jpeg">'
            '</a>'
        )

        self.assertEqual(
            "image/2608/IMG_5201.jpeg",
            parser.full_image_path,
        )


class CachedImageFilesTest(unittest.TestCase):
    def test_includes_jpeg_and_gif_images(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            wallpaper_directory = Path(temporary_directory)
            jpeg_path = wallpaper_directory / "apod_2026-08-14.jpeg"
            gif_path = wallpaper_directory / "apod_2026-08-05.gif"
            ignored_path = wallpaper_directory / "apod.log"
            jpeg_path.write_bytes(JPEG_IMAGE)
            gif_path.write_bytes(GIF_IMAGE)
            ignored_path.touch()

            with mock.patch.object(
                apod,
                "WALLPAPER_DIR",
                wallpaper_directory,
            ):
                result = apod.cached_image_files()

        self.assertCountEqual([jpeg_path, gif_path], result)

    def test_cleanup_counts_invalid_files_toward_cache_limit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            invalid = directory / 'apod_2000-01-01.jpg'
            valid = directory / 'apod_2000-01-02.jpg'
            incomplete = directory / 'apod_2000-01-03.jpg.download'
            invalid.write_text('<html>Error</html>')
            valid.write_bytes(JPEG_IMAGE)
            incomplete.write_bytes(b'incomplete')
            os.utime(invalid, (1, 1))
            os.utime(valid, (2, 2))

            with mock.patch.object(apod, 'WALLPAPER_DIR', directory):
                apod.cleanup_old_images(keep_count=1)

            self.assertFalse(invalid.exists())
            self.assertEqual(JPEG_IMAGE, valid.read_bytes())
            self.assertTrue(incomplete.exists())


class SetMacOsWallpaperTest(unittest.TestCase):
    @mock.patch("subprocess.run")
    def test_sets_wallpaper_on_desktop_1_only(self, mock_run):
        mock_run.side_effect = [
            mock.Mock(stdout="2\n"),  # 2 desktops connected
            mock.Mock(returncode=0),   # osascript wallpaper setting call
        ]

        test_image = Path("/tmp/apod_today.jpg")
        apod.set_macos_wallpaper(test_image, desktop_1_only=True)

        self.assertEqual(mock_run.call_count, 2)
        call_args = mock_run.call_args_list[1]
        cmd = call_args[0][0]
        self.assertEqual(cmd[0], "osascript")
        self.assertEqual(cmd[1], "-e")
        self.assertIn("set picture of desktop 1 to imagePath", cmd[2])
        self.assertNotIn("desktopIndex", cmd[2])
        self.assertEqual(cmd[3], str(test_image))

    @mock.patch.object(apod, "pick_cache_images")
    @mock.patch("subprocess.run")
    def test_sets_wallpaper_on_all_desktops_by_default(self, mock_run, mock_pick):
        mock_run.side_effect = [
            mock.Mock(stdout="2\n"),  # 2 desktops connected
            mock.Mock(returncode=0),   # osascript wallpaper setting call
        ]
        cached_fallback = Path("/tmp/cached_photo.jpg")
        mock_pick.return_value = [cached_fallback]

        test_image = Path("/tmp/apod_today.jpg")
        apod.set_macos_wallpaper(test_image, desktop_1_only=False)

        self.assertEqual(mock_run.call_count, 2)
        call_args = mock_run.call_args_list[1]
        cmd = call_args[0][0]
        self.assertEqual(cmd[0], "osascript")
        self.assertEqual(cmd[1], "-e")
        self.assertIn("desktopIndex", cmd[2])
        self.assertEqual(cmd[3], str(test_image))
        self.assertEqual(cmd[4], str(cached_fallback))

    @mock.patch.object(apod, "is_desktop_1_active", return_value=False)
    @mock.patch.object(apod, "set_desktop_1_in_store", return_value=True)
    @mock.patch("subprocess.run")
    def test_sets_wallpaper_in_store_when_desktop_1_inactive(self, mock_run, mock_set_store, _mock_active):
        mock_run.return_value = mock.Mock(stdout="2\n")
        test_image = Path("/tmp/apod_today.jpg")
        apod.set_macos_wallpaper(test_image, desktop_1_only=True)

        mock_set_store.assert_called_once_with(test_image)
        # Should only call count of desktops, not set picture of desktop 1
        self.assertEqual(mock_run.call_count, 1)


class GetCurrentDesktopWallpaperTest(unittest.TestCase):
    def test_reads_from_wallpaper_store(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store_file = Path(temp_dir) / "Index.plist"
            data = {
                "Spaces": {
                    "": {
                        "Default": {
                            "Desktop": {
                                "Content": {
                                    "Choices": [
                                        {"Files": [{"relative": "file:///path/to/store_apod.jpg"}]}
                                    ]
                                }
                            }
                        }
                    }
                }
            }
            with open(store_file, "wb") as f:
                apod.plistlib.dump(data, f)

            with mock.patch.object(apod, "WALLPAPER_STORE_INDEX", store_file):
                wallpaper = apod.get_current_desktop_1_wallpaper()
                self.assertEqual(Path("/path/to/store_apod.jpg"), wallpaper)

    @mock.patch.object(apod, "WALLPAPER_STORE_INDEX", Path("/nonexistent/Index.plist"))
    @mock.patch("subprocess.run")
    def test_returns_current_wallpaper_path(self, mock_run):
        mock_run.return_value = mock.Mock(stdout="/path/to/apod.jpg\n", returncode=0)
        wallpaper = apod.get_current_desktop_1_wallpaper()
        self.assertEqual(Path("/path/to/apod.jpg"), wallpaper)

    @mock.patch.object(apod, "WALLPAPER_STORE_INDEX", Path("/nonexistent/Index.plist"))
    @mock.patch("subprocess.run", side_effect=Exception("AppleScript error"))
    def test_returns_none_on_error(self, _mock_run):
        self.assertIsNone(apod.get_current_desktop_1_wallpaper())


class MainAlreadyUpToDateTest(unittest.TestCase):
    @mock.patch.object(apod, "load_config", return_value={})
    @mock.patch.object(apod, "set_macos_wallpaper")
    @mock.patch.object(apod, "fetch_apod_with_fallback")
    @mock.patch.object(apod, "cached_image_files")
    def test_skips_fetch_when_already_set(self, mock_cached, mock_fetch, mock_set, _mock_config):
        today = apod.datetime.now().strftime("%Y-%m-%d")
        today_image = Path(f"/tmp/apod_{today}.jpg")
        mock_cached.return_value = [today_image]

        with mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
            apod.main()

        mock_fetch.assert_not_called()
        mock_set.assert_called_once_with(today_image, desktop_1_only=False)


class PickRandomCachedWallpaperTest(unittest.TestCase):
    def test_returns_none_when_cache_is_empty(self):
        with mock.patch.object(apod, "cached_image_files", return_value=[]):
            result = apod.pick_random_cached_wallpaper()
            self.assertIsNone(result)

    def test_picks_older_candidates_excluding_today(self):
        today_file = Path("/tmp/apod_2026-09-09.jpg")
        older_file = Path("/tmp/apod_2026-09-07.jpg")
        with mock.patch.object(
            apod,
            "cached_image_files",
            return_value=[today_file, older_file],
        ):
            result = apod.pick_random_cached_wallpaper(exclude_date="2026-09-09")
            self.assertEqual(older_file, result)

    def test_excludes_currently_set_wallpaper(self):
        file1 = Path("/tmp/apod_2026-09-07.jpg")
        file2 = Path("/tmp/apod_2026-09-08.jpg")
        with mock.patch.object(
            apod,
            "cached_image_files",
            return_value=[file1, file2],
        ):
            result = apod.pick_random_cached_wallpaper(
                exclude_paths=[file2],
                exclude_date="2026-09-09",
            )
            self.assertEqual(file1, result)

    def test_returns_current_wallpaper_if_only_candidate(self):
        file1 = Path("/tmp/apod_2026-09-08.jpg")
        with mock.patch.object(
            apod,
            "cached_image_files",
            return_value=[file1],
        ):
            result = apod.pick_random_cached_wallpaper(
                exclude_paths=[file1],
                exclude_date="2026-09-09",
            )
            self.assertEqual(file1, result)


class MainFallbackTest(unittest.TestCase):
    @mock.patch.object(apod, "send_notification")
    @mock.patch.object(apod, "set_macos_wallpaper")
    @mock.patch.object(apod, "pick_random_cached_wallpaper")
    @mock.patch.object(apod, "fetch_apod_with_fallback")
    @mock.patch.object(apod, "get_current_desktop_1_wallpaper", return_value=None)
    @mock.patch.object(apod, "cached_image_files", return_value=[])
    def test_falls_back_to_cache_when_media_type_is_video(
        self,
        _mock_cached,
        _mock_current,
        mock_fetch,
        mock_pick_random,
        mock_set_wallpaper,
        mock_notify,
    ):
        video_data = {
            "title": "Witness XZ Andromedae Wink",
            "date": "2026-09-09",
            "media_type": "video",
            "url": "https://apod.nasa.gov/apod/image/2609/xz_and.mp4",
            "explanation": "Do stars wink?",
        }
        mock_fetch.return_value = video_data
        fallback_path = Path("/tmp/apod_2026-09-07.jpg")
        mock_pick_random.return_value = fallback_path

        with mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
            apod.main()

        mock_pick_random.assert_called_once()
        mock_set_wallpaper.assert_called_once_with(fallback_path, desktop_1_only=mock.ANY)
        mock_notify.assert_called_once()
        self.assertIn("Witness XZ Andromedae Wink", mock_notify.call_args[0][0])
        self.assertIn("Cached", mock_notify.call_args[0][0])

    @mock.patch.object(apod, "send_notification")
    @mock.patch.object(apod, "set_macos_wallpaper")
    @mock.patch.object(apod, "pick_random_cached_wallpaper")
    @mock.patch.object(apod, "download_apod_image", return_value=None)
    @mock.patch.object(apod, "fetch_apod_with_fallback")
    @mock.patch.object(apod, "get_current_desktop_1_wallpaper", return_value=None)
    @mock.patch.object(apod, "cached_image_files", return_value=[])
    def test_falls_back_to_cache_when_download_fails(
        self,
        _mock_cached,
        _mock_current,
        mock_fetch,
        _mock_download,
        mock_pick_random,
        mock_set_wallpaper,
        mock_notify,
    ):
        image_data = {
            "title": "Cosmic Cloud",
            "date": "2026-09-09",
            "media_type": "image",
            "hdurl": "https://example.com/hd.jpg",
            "explanation": "A vast nebula.",
        }
        mock_fetch.return_value = image_data
        fallback_path = Path("/tmp/apod_2026-09-07.jpg")
        mock_pick_random.return_value = fallback_path

        with mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
            apod.main()

        mock_pick_random.assert_called_once()
        mock_set_wallpaper.assert_called_once_with(fallback_path, desktop_1_only=mock.ANY)
        mock_notify.assert_called_once()
        self.assertIn("Cosmic Cloud", mock_notify.call_args[0][0])
        self.assertIn("Cached", mock_notify.call_args[0][0])

    @mock.patch.object(apod, "send_notification")
    @mock.patch.object(apod, "set_macos_wallpaper")
    @mock.patch.object(apod, "pick_random_cached_wallpaper")
    @mock.patch.object(apod, "fetch_apod_with_fallback", return_value=None)
    @mock.patch.object(apod, "get_current_desktop_1_wallpaper", return_value=None)
    @mock.patch.object(apod, "cached_image_files", return_value=[])
    def test_falls_back_to_cache_when_fetch_returns_none(
        self,
        _mock_cached,
        _mock_current,
        _mock_fetch,
        mock_pick_random,
        mock_set_wallpaper,
        mock_notify,
    ):
        fallback_path = Path("/tmp/apod_2026-09-07.jpg")
        mock_pick_random.return_value = fallback_path

        with mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
            apod.main()

        mock_pick_random.assert_called_once()
        mock_set_wallpaper.assert_called_once_with(fallback_path, desktop_1_only=mock.ANY)
        mock_notify.assert_called_once()

    @mock.patch.object(apod, "pick_random_cached_wallpaper", return_value=None)
    @mock.patch.object(apod, "fetch_apod_with_fallback")
    @mock.patch.object(apod, "get_current_desktop_1_wallpaper", return_value=None)
    @mock.patch.object(apod, "cached_image_files", return_value=[])
    def test_exits_when_fallback_has_no_cached_images(
        self,
        _mock_cached,
        _mock_current,
        mock_fetch,
        _mock_pick_random,
    ):
        mock_fetch.return_value = {
            "title": "Video APOD",
            "date": "2026-09-09",
            "media_type": "video",
        }
        with mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
            with self.assertRaises(SystemExit) as cm:
                apod.main()
            self.assertEqual(cm.exception.code, 1)


class CachedWallpaperRefreshTest(unittest.TestCase):
    def test_reapplies_cached_today_to_all_desktops_without_network(self):
        today = apod.datetime.now().strftime("%Y-%m-%d")
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            today_image = directory / f"apod_{today}.jpg"
            other_image = directory / "apod_2000-01-01.jpg"
            today_image.write_bytes(JPEG_IMAGE)
            other_image.write_bytes(JPEG_IMAGE)

            with mock.patch.object(apod, "WALLPAPER_DIR", directory), \
                    mock.patch.object(apod, "is_valid_image", return_value=True), \
                    mock.patch.object(apod, "load_config", return_value={}), \
                    mock.patch.object(apod, "fetch_apod_with_fallback") as fetch, \
                    mock.patch.object(apod, "send_notification") as notify, \
                    mock.patch.object(apod.subprocess, "run") as run, \
                    mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
                run.side_effect = [mock.Mock(stdout="2\n"), mock.Mock()]
                apod.main()

            fetch.assert_not_called()
            notify.assert_not_called()
            self.assertEqual(
                [str(today_image), str(other_image)],
                run.call_args_list[1].args[0][3:],
            )

    def test_fetches_today_when_only_older_images_are_cached(self):
        today = apod.datetime.now().strftime("%Y-%m-%d")
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / "apod_2000-01-01.jpg").write_bytes(JPEG_IMAGE)
            today_image = directory / f"apod_{today}.jpg"

            with mock.patch.object(apod, "WALLPAPER_DIR", directory), \
                    mock.patch.object(apod, "load_config", return_value={}), \
                    mock.patch.object(apod, "fetch_apod_with_fallback") as fetch, \
                    mock.patch.object(apod, "download_apod_image", return_value=today_image), \
                    mock.patch.object(apod, "set_macos_wallpaper") as set_wallpaper, \
                    mock.patch.object(apod, "send_notification"), \
                    mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
                fetch.return_value = {"media_type": "image", "date": today}
                apod.main()

            fetch.assert_called_once_with(None, exit_on_error=False)
            set_wallpaper.assert_called_once_with(today_image, desktop_1_only=False)

    def test_replaces_invalid_cached_today_and_notifies_with_description(self):
        today = apod.datetime.now().strftime('%Y-%m-%d')
        data = {
            'date': today,
            'media_type': 'image',
            'hdurl': 'https://example.com/image.jpg',
            'title': 'A distant galaxy',
            'explanation': 'This galaxy contains billions of stars.',
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            image = directory / f'apod_{today}.jpg'
            image.write_text('<html>Service unavailable</html>')
            with mock.patch.object(apod, 'WALLPAPER_DIR', directory), \
                    mock.patch.object(apod, 'load_config', return_value={}), \
                    mock.patch.object(apod, 'fetch_apod_with_fallback', return_value=data) as fetch, \
                    mock.patch.object(apod.urllib.request, 'urlopen', return_value=io.BytesIO(JPEG_IMAGE)), \
                    mock.patch.object(apod, 'set_macos_wallpaper') as set_wallpaper, \
                    mock.patch.object(apod, 'send_notification') as notify, \
                    mock.patch('sys.argv', ['nasa_apod_wallpaper.py']):
                apod.main()

            self.assertEqual(JPEG_IMAGE, image.read_bytes())
            fetch.assert_called_once_with(None, exit_on_error=False)
            set_wallpaper.assert_called_once_with(image, desktop_1_only=False)
            notify.assert_called_once_with(data['title'], data['explanation'])

    def test_uses_valid_older_image_when_today_cache_is_invalid_and_api_fails(self):
        today = apod.datetime.now().strftime('%Y-%m-%d')
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            (directory / f'apod_{today}.jpg').write_text('<html>Error</html>')
            older_image = directory / 'apod_2000-01-01.jpg'
            older_image.write_bytes(JPEG_IMAGE)
            with mock.patch.object(apod, 'WALLPAPER_DIR', directory), \
                    mock.patch.object(apod, 'load_config', return_value={}), \
                    mock.patch.object(apod, 'fetch_apod_with_fallback', return_value=None), \
                    mock.patch.object(apod, 'get_current_desktop_1_wallpaper', return_value=None), \
                    mock.patch.object(apod, 'set_macos_wallpaper') as set_wallpaper, \
                    mock.patch.object(apod, 'send_notification'), \
                    mock.patch('sys.argv', ['nasa_apod_wallpaper.py']):
                apod.main()

            set_wallpaper.assert_called_once_with(older_image, desktop_1_only=False)

    def test_cached_refresh_respects_desktop_selection(self):
        today = apod.datetime.now().strftime("%Y-%m-%d")
        today_image = Path(f"/tmp/apod_{today}.jpg")
        for config, args, expected in [
            ({}, ["--desktop-1-only"], True),
            ({"desktop_1_only": True}, [], True),
            ({"desktop_1_only": True}, ["--all-desktops"], False),
        ]:
            with self.subTest(config=config, args=args):
                with mock.patch.object(apod, "load_config", return_value=config), \
                        mock.patch.object(apod, "cached_image_files", return_value=[today_image]), \
                        mock.patch.object(apod, "get_current_desktop_1_wallpaper", return_value=None), \
                        mock.patch.object(apod, "fetch_apod_with_fallback") as fetch, \
                        mock.patch.object(apod, "set_macos_wallpaper") as set_wallpaper, \
                        mock.patch("sys.argv", ["nasa_apod_wallpaper.py", *args]):
                    apod.main()
                fetch.assert_not_called()
                set_wallpaper.assert_called_once_with(today_image, desktop_1_only=expected)

    def test_cached_refresh_skips_when_desktop_1_already_set(self):
        today = apod.datetime.now().strftime("%Y-%m-%d")
        today_image = Path(f"/tmp/apod_{today}.jpg")
        with mock.patch.object(apod, "load_config", return_value={"desktop_1_only": True}), \
                mock.patch.object(apod, "cached_image_files", return_value=[today_image]), \
                mock.patch.object(apod, "get_current_desktop_1_wallpaper", return_value=today_image), \
                mock.patch.object(apod, "fetch_apod_with_fallback") as fetch, \
                mock.patch.object(apod, "set_macos_wallpaper") as set_wallpaper, \
                mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
            apod.main()
        fetch.assert_not_called()
        set_wallpaper.assert_not_called()

    def test_explicit_refresh_bypasses_today_cache(self):
        today = apod.datetime.now().strftime("%Y-%m-%d")
        today_image = Path(f"/tmp/apod_{today}.jpg")
        for argument, expected_date in [("--force", None), (today, today)]:
            with self.subTest(argument=argument):
                with mock.patch.object(apod, "load_config", return_value={}), \
                        mock.patch.object(apod, "cached_image_files", return_value=[today_image]), \
                        mock.patch.object(apod, "fetch_apod_with_fallback") as fetch, \
                        mock.patch.object(apod, "download_apod_image", return_value=today_image) as download, \
                        mock.patch.object(apod, "set_macos_wallpaper"), \
                        mock.patch.object(apod, "send_notification"), \
                        mock.patch("sys.argv", ["nasa_apod_wallpaper.py", argument]):
                    fetch.return_value = {"media_type": "image", "date": today}
                    apod.main()
                fetch.assert_called_once_with(expected_date, exit_on_error=False)
                download.assert_called_once_with(fetch.return_value, today, exit_on_error=False)


if __name__ == "__main__":
    unittest.main()

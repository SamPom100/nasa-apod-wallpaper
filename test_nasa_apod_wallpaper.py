import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("NASA_API_KEY", "test-key")

import nasa_apod_wallpaper as apod


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
                def write_image(_url, path):
                    Path(path).write_bytes(b"image")

                with mock.patch.object(
                    apod.urllib.request,
                    "urlretrieve",
                    side_effect=write_image,
                ):
                    result = apod.download_image(
                        "https://example.com/image.jpeg",
                        "apod_2026-08-20.jpeg",
                    )

            self.assertEqual(b"image", result.read_bytes())

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
            jpeg_path.touch()
            gif_path.touch()
            ignored_path.touch()

            with mock.patch.object(
                apod,
                "WALLPAPER_DIR",
                wallpaper_directory,
            ):
                result = apod.cached_image_files()

        self.assertCountEqual([jpeg_path, gif_path], result)


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


class GetCurrentDesktopWallpaperTest(unittest.TestCase):
    @mock.patch("subprocess.run")
    def test_returns_current_wallpaper_path(self, mock_run):
        mock_run.return_value = mock.Mock(stdout="/path/to/apod.jpg\n", returncode=0)
        wallpaper = apod.get_current_desktop_1_wallpaper()
        self.assertEqual(Path("/path/to/apod.jpg"), wallpaper)

    @mock.patch("subprocess.run", side_effect=Exception("AppleScript error"))
    def test_returns_none_on_error(self, _mock_run):
        self.assertIsNone(apod.get_current_desktop_1_wallpaper())


class MainAlreadyUpToDateTest(unittest.TestCase):
    @mock.patch.object(apod, "fetch_apod_with_fallback")
    @mock.patch.object(apod, "get_current_desktop_1_wallpaper")
    @mock.patch.object(apod, "cached_image_files")
    def test_skips_fetch_when_already_set(self, mock_cached, mock_current, mock_fetch):
        today = apod.datetime.now().strftime("%Y-%m-%d")
        today_image = Path(f"/tmp/apod_{today}.jpg")
        mock_cached.return_value = [today_image]
        mock_current.return_value = today_image

        with mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
            apod.main()

        mock_fetch.assert_not_called()


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


if __name__ == "__main__":
    unittest.main()


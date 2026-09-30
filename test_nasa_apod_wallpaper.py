import base64
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("NASA_API_KEY", "test-key")

import nasa_apod_wallpaper as apod


def setUpModule():
    directory = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(directory.cleanup)
    root = Path(directory.name)
    for name, path in [
        ('WALLPAPER_DIR', root),
        ('CONFIG_FILE', root / 'config.json'),
        ('WALLPAPER_STORE_INDEX', root / 'Index.plist'),
    ]:
        patch = mock.patch.object(apod, name, path)
        patch.start()
        unittest.addModuleCleanup(patch.stop)


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

    def test_uses_science_nasa_assets_url_when_apod_nasa_gov_is_provided(self):
        expected_path = Path("/tmp/apod_2026-09-26.jpg")
        data = {
            "hdurl": "https://apod.nasa.gov/apod/image/2609/MilkyWayMeteorLSTJeffDai.jpg",
            "url": "https://apod.nasa.gov/apod/image/2609/MilkyWayMeteorLSTJeffDai1024.jpg",
        }

        with mock.patch.object(
            apod,
            "download_image",
            return_value=expected_path,
        ) as download_image:
            result = apod.download_apod_image(data, "2026-09-26")

        self.assertEqual(expected_path, result)
        download_image.assert_called_once_with(
            "https://assets.science.nasa.gov/content/dam/science/cds/apod/apod/2026/september/MilkyWayMeteorLSTJeffDai.jpg",
            "apod_2026-09-26.jpg",
            exit_on_error=False,
        )


class ToScienceNasaUrlsTest(unittest.TestCase):
    def test_converts_apod_nasa_gov_url(self):
        urls = apod.to_science_nasa_urls(
            "https://apod.nasa.gov/apod/image/2609/NGC5139CadenasParra.jpg",
            "2026-09-25",
        )
        self.assertEqual([
            "https://assets.science.nasa.gov/content/dam/science/cds/apod/apod/2026/september/NGC5139CadenasParra.jpg",
            "https://assets.science.nasa.gov/dynamicimage/assets/science/cds/apod/apod/2026/september/NGC5139CadenasParra.jpg?w=4096&fit=clip",
        ], urls)


class FetchApodFromFeedTest(unittest.TestCase):
    def test_parses_feed_item_for_date(self):
        sample_rss = b"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0" xmlns:apod="https://science.nasa.gov/apod/">
<channel>
    <item>
        <title>Test Galaxy</title>
        <link>https://science.nasa.gov/image-article/apod-2026-september-30-test/</link>
        <pubDate>Wed, 30 Sep 2026 04:05:00 +0000</pubDate>
        <apod:hdurl>https://assets.science.nasa.gov/dynamicimage/assets/science/cds/apod/apod/2026/october/test.jpg?w=1772&amp;h=1182</apod:hdurl>
        <apod:url>https://science.nasa.gov/image-article/apod-2026-september-30-test/</apod:url>
        <apod:explanation><![CDATA[<strong>Explanation:</strong> A test explanation.]]></apod:explanation>
    </item>
</channel>
</rss>"""
        with mock.patch.object(apod.urllib.request, "urlopen", return_value=io.BytesIO(sample_rss)):
            result = apod.fetch_apod_from_feed("2026-09-30")

        self.assertIsNotNone(result)
        self.assertEqual("Test Galaxy", result["title"])
        self.assertEqual("2026-09-30", result["date"])
        self.assertEqual("https://assets.science.nasa.gov/content/dam/science/cds/apod/apod/2026/october/test.jpg", result["hdurl"])
        self.assertEqual("A test explanation.", result["explanation"])
        self.assertEqual("image", result["media_type"])

    def test_fallback_uses_feed_when_api_fails(self):
        expected_feed_data = {
            "title": "Feed Galaxy",
            "date": "2026-09-30",
            "media_type": "image",
            "hdurl": "https://example.com/feed.jpg",
        }
        with mock.patch.object(apod, "fetch_apod_data", return_value=None), \
                mock.patch.object(apod, "fetch_apod_from_feed", return_value=expected_feed_data) as mock_feed:
            result = apod.fetch_apod_with_fallback("2026-09-30")

        self.assertEqual(expected_feed_data, result)
        mock_feed.assert_called_once_with("2026-09-30")


class FetchApodArticleByUrlTest(unittest.TestCase):
    def test_parses_article_html(self):
        sample_html = """
        <html>
        <head><title>APOD: Arp 78</title></head>
        <body>
            <h1>APOD: 2026 September 30 - Arp 78: Peculiar Galaxy in Aries</h1>
            <p class="media-detail-hero__description"><strong>Explanation:</strong> Some description here.</p>
            <a href="https://assets.science.nasa.gov/dynamicimage/assets/science/cds/apod/apod/2026/october/NGC772_Robert_Eder.jpg?w=1772&amp;h=1182">Full image</a>
        </body>
        </html>
        """
        url = "https://science.nasa.gov/image-article/apod-2026-september-30-arp-78-peculiar-galaxy-in-aries/"
        with mock.patch.object(apod.urllib.request, "urlopen", return_value=io.BytesIO(sample_html.encode("utf-8"))):
            result = apod.fetch_apod_article_by_url(url)

        self.assertIsNotNone(result)
        self.assertEqual("Arp 78: Peculiar Galaxy in Aries", result["title"])
        self.assertEqual("2026-09-30", result["date"])
        self.assertEqual("https://assets.science.nasa.gov/content/dam/science/cds/apod/apod/2026/october/NGC772_Robert_Eder.jpg", result["hdurl"])
        self.assertEqual("Some description here.", result["explanation"])
        self.assertEqual("image", result["media_type"])


class FetchApodFromScienceNasaTest(unittest.TestCase):
    def test_delegates_to_fetch_apod_article_by_url_when_url_passed(self):
        url = "https://science.nasa.gov/image-article/apod-2026-september-30-arp-78-peculiar-galaxy-in-aries/"
        expected = {"title": "Arp 78", "date": "2026-09-30", "media_type": "image"}
        with mock.patch.object(apod, "fetch_apod_article_by_url", return_value=expected) as mock_article:
            result = apod.fetch_apod_from_science_nasa(url)

        self.assertEqual(expected, result)
        mock_article.assert_called_once_with(url)

    def test_queries_wp_api_when_feed_returns_none(self):
        wp_api_response = json.dumps([{
            "title": {"rendered": "Arp 78: Peculiar Galaxy"},
            "link": "https://science.nasa.gov/image-article/apod-2026-september-30-arp-78/",
            "featured_image_url": "https://assets.science.nasa.gov/dynamicimage/assets/science/cds/apod/apod/2026/october/test.jpg?w=1024",
            "content": {"rendered": "<p class=\"media-detail-hero__description\">Explanation: Peculiar galaxy description.</p>"}
        }]).encode("utf-8")

        with mock.patch.object(apod, "fetch_apod_from_feed", return_value=None):
            with mock.patch.object(apod.urllib.request, "urlopen", return_value=io.BytesIO(wp_api_response)):
                result = apod.fetch_apod_from_science_nasa("2026-09-30")

        self.assertIsNotNone(result)
        self.assertEqual("Arp 78: Peculiar Galaxy", result["title"])
        self.assertEqual("2026-09-30", result["date"])
        self.assertEqual("https://assets.science.nasa.gov/content/dam/science/cds/apod/apod/2026/october/test.jpg", result["hdurl"])
        self.assertEqual("Peculiar galaxy description.", result["explanation"])


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
    def test_primary_only_targets_space_1_while_space_2_is_active(self):
        contexts = [{'display_uuid': 'primary', 'space_uuid': space, 'current_space_uuid': 'space-2'}
                    for space in ('space-1', 'space-2')]
        image = Path('/tmp/apod_today.jpg')
        with mock.patch.object(apod, 'get_desktop_contexts', return_value=contexts), \
                mock.patch.object(apod, 'set_wallpapers_in_store', return_value=True) as write, \
                mock.patch.object(apod, 'pick_cache_images') as pick:
            apod.set_macos_wallpaper(image, desktop_1_only=True)
        write.assert_called_once_with([(contexts[0], image)])
        pick.assert_not_called()

    def test_unknown_desktops_do_not_write_any_wallpaper(self):
        with mock.patch.object(apod, 'get_desktop_contexts', return_value=[]), \
                mock.patch.object(apod, 'set_wallpapers_in_store') as write, \
                mock.patch.object(apod.time, 'sleep'):
            with self.assertRaises(SystemExit):
                apod.set_macos_wallpaper(Path('/today.jpg'))
        write.assert_not_called()


class GetCurrentDesktopWallpaperTest(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(apod, 'get_desktop_contexts', return_value=[{
            'display_uuid': 'primary', 'space_uuid': '', 'current_space_uuid': '',
        }])
        patch.start()
        self.addCleanup(patch.stop)

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
                                        {
                                            'Files': [],
                                            'Configuration': apod.plistlib.dumps({
                                                'type': 'imageFile',
                                                'url': {'relative': 'file:///path/to/store_apod.jpg'},
                                            }, fmt=apod.plistlib.FMT_BINARY),
                                        }
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
        mock_set.assert_called_once_with(today_image, desktop_1_only=False, apod_date=today)


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
        mock_set_wallpaper.assert_called_once_with(fallback_path, desktop_1_only=mock.ANY,
                                                  apod_date=video_data['date'])
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
        mock_set_wallpaper.assert_called_once_with(fallback_path, desktop_1_only=mock.ANY,
                                                  apod_date=image_data['date'])
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
        mock_set_wallpaper.assert_called_once_with(fallback_path, desktop_1_only=mock.ANY, apod_date=None)
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

    @mock.patch.object(apod, "send_notification")
    @mock.patch.object(apod, "set_macos_wallpaper")
    @mock.patch.object(apod, "download_apod_image")
    @mock.patch.object(apod, "fetch_apod_article_by_url")
    @mock.patch.object(apod, "get_current_desktop_1_wallpaper", return_value=None)
    @mock.patch.object(apod, "cached_image_files", return_value=[])
    def test_main_with_direct_article_url(
        self,
        _mock_cached,
        _mock_current,
        mock_fetch_article,
        mock_download,
        mock_set_wallpaper,
        mock_notify,
    ):
        article_url = "https://science.nasa.gov/image-article/apod-2026-september-30-arp-78-peculiar-galaxy-in-aries/"
        article_data = {
            "title": "Arp 78",
            "date": "2026-09-30",
            "media_type": "image",
            "hdurl": "https://assets.science.nasa.gov/content/dam/science/cds/apod/apod/2026/october/test.jpg",
            "explanation": "Test explanation.",
        }
        mock_fetch_article.return_value = article_data
        image_file = Path("/tmp/apod_2026-09-30.jpg")
        mock_download.return_value = image_file

        with mock.patch("sys.argv", ["nasa_apod_wallpaper.py", article_url]):
            apod.main()

        mock_fetch_article.assert_called_once_with(article_url)
        mock_download.assert_called_once_with(article_data, "2026-09-30", exit_on_error=False)
        mock_set_wallpaper.assert_called_once_with(image_file, desktop_1_only=mock.ANY, apod_date="2026-09-30")
        mock_notify.assert_called_once_with("Arp 78", "Test explanation.")


class CachedWallpaperRefreshTest(unittest.TestCase):
    def test_reapplies_cached_today_to_all_desktops_without_network(self):
        today = apod.datetime.now().strftime("%Y-%m-%d")
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            today_image = directory / f"apod_{today}.jpg"
            other_image = directory / "apod_2000-01-01.jpg"
            today_image.write_bytes(JPEG_IMAGE)
            other_image.write_bytes(JPEG_IMAGE)
            contexts = [{'display_uuid': 'primary', 'space_uuid': space, 'current_space_uuid': 'space-2'}
                        for space in ('space-1', 'space-2')]

            with mock.patch.object(apod, "WALLPAPER_DIR", directory), \
                    mock.patch.object(apod, "is_valid_image", return_value=True), \
                    mock.patch.object(apod, "load_config", return_value={}), \
                    mock.patch.object(apod, "fetch_apod_with_fallback") as fetch, \
                    mock.patch.object(apod, "send_notification") as notify, \
                    mock.patch.object(apod, 'get_desktop_contexts', return_value=contexts), \
                    mock.patch.object(apod, 'set_wallpapers_in_store', return_value=True) as write, \
                    mock.patch("sys.argv", ["nasa_apod_wallpaper.py"]):
                apod.main()

            fetch.assert_not_called()
            notify.assert_not_called()
            write.assert_called_once_with([(contexts[0], today_image), (contexts[1], other_image)])

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
            set_wallpaper.assert_called_once_with(today_image, desktop_1_only=False, apod_date=today)

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
            set_wallpaper.assert_called_once_with(image, desktop_1_only=False, apod_date=today)
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

            set_wallpaper.assert_called_once_with(older_image, desktop_1_only=False, apod_date=None)

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
                set_wallpaper.assert_called_once_with(today_image, desktop_1_only=expected, apod_date=today)

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

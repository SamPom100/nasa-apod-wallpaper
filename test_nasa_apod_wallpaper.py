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


if __name__ == "__main__":
    unittest.main()

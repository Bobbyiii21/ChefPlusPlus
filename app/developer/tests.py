from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from developer.gcs_bucket import BucketConfigurationError
from developer.gcs_bucket import delete_file
from developer.gcs_bucket import get_bucket_name
from developer.gcs_bucket import list_files
from developer.gcs_bucket import upload_file


class GcsBucketTests(SimpleTestCase):
    @patch.dict("os.environ", {"GCS_KNOWLEDGE_BUCKET": "frontend-assets"}, clear=True)
    def test_get_bucket_name_reads_env(self):
        self.assertEqual(get_bucket_name(), "frontend-assets")

    @patch.dict("os.environ", {}, clear=True)
    def test_get_bucket_name_requires_env(self):
        with self.assertRaises(BucketConfigurationError):
            get_bucket_name()

    @patch("developer.gcs_bucket.get_bucket")
    def test_list_files_returns_metadata(self, mock_get_bucket):
        blob = SimpleNamespace(
            name="images/hero.png",
            size=123,
            content_type="image/png",
            updated="2026-04-09T12:00:00Z",
            public_url="https://example.com/hero.png",
        )
        mock_get_bucket.return_value.list_blobs.return_value = [blob]

        files = list_files(prefix="images/")

        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].name, "images/hero.png")
        self.assertEqual(files[0].content_type, "image/png")
        mock_get_bucket.return_value.list_blobs.assert_called_once_with(prefix="images/")

    @patch("developer.gcs_bucket.get_bucket")
    def test_upload_file_uses_destination_name(self, mock_get_bucket):
        bucket = MagicMock()
        blob = MagicMock()
        blob.name = "uploads/mock.txt"
        blob.size = 10
        blob.content_type = "text/plain"
        blob.updated = "2026-04-09T12:00:00Z"
        blob.public_url = "https://example.com/mock.txt"
        bucket.blob.return_value = blob
        mock_get_bucket.return_value = bucket

        with NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write("hello gcs")
            tmp_path = Path(tmp.name)

        try:
            uploaded = upload_file(
                tmp_path,
                destination_name="uploads/mock.txt",
                content_type="text/plain",
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        bucket.blob.assert_called_once_with("uploads/mock.txt")
        blob.upload_from_filename.assert_called_once_with(
            str(tmp_path.resolve()),
            content_type="text/plain",
        )
        blob.reload.assert_called_once_with()
        self.assertEqual(uploaded.name, "uploads/mock.txt")

    @patch("developer.gcs_bucket.get_bucket")
    def test_delete_file_calls_blob_delete(self, mock_get_bucket):
        bucket = MagicMock()
        blob = MagicMock()
        bucket.blob.return_value = blob
        mock_get_bucket.return_value = bucket

        delete_file("images/hero.png")

        bucket.blob.assert_called_once_with("images/hero.png")
        blob.delete.assert_called_once_with()

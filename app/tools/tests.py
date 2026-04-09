"""
Test suite for the ``tools`` package.

All Vertex AI / Google Cloud calls are mocked so the tests run in CI
without credentials or network access.

Run from the ``app/`` directory::

    python -m pytest tools/tests.py -v

Or with Django's test runner (if Django is configured)::

    python manage.py test tools
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

# ====================================================================
# env_config tests
# ====================================================================


class TestGetEnv(unittest.TestCase):
    """tools.env_config.get_env / require_env behaviour."""

    def _reset_dotenv_flag(self):
        import tools.env_config as ec
        ec._dotenv_loaded = False

    def setUp(self):
        self._reset_dotenv_flag()

    @mock.patch.dict(os.environ, {"MY_VAR": "hello"}, clear=False)
    def test_get_env_from_os_environ(self):
        from tools.env_config import get_env
        self.assertEqual(get_env("MY_VAR"), "hello")

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_get_env_default_when_missing(self):
        from tools.env_config import get_env
        os.environ.pop("NONEXISTENT_VAR_XYZ", None)
        self.assertEqual(get_env("NONEXISTENT_VAR_XYZ", "fallback"), "fallback")

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_get_env_none_when_missing_no_default(self):
        from tools.env_config import get_env
        os.environ.pop("NONEXISTENT_VAR_XYZ", None)
        self.assertIsNone(get_env("NONEXISTENT_VAR_XYZ"))

    @mock.patch.dict(os.environ, {"MY_VAR": "  spaced  "}, clear=False)
    def test_get_env_strips_whitespace(self):
        from tools.env_config import get_env
        self.assertEqual(get_env("MY_VAR"), "spaced")

    @mock.patch.dict(os.environ, {"MY_VAR": "   "}, clear=False)
    def test_get_env_blank_uses_default(self):
        from tools.env_config import get_env
        self.assertEqual(get_env("MY_VAR", "default"), "default")

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_require_env_raises_on_missing(self):
        from tools.env_config import require_env, EnvVarMissing
        os.environ.pop("REQUIRED_MISSING_XYZ", None)
        with self.assertRaises(EnvVarMissing):
            require_env("REQUIRED_MISSING_XYZ")

    @mock.patch.dict(os.environ, {"REQUIRED_VAR": "ok"}, clear=False)
    def test_require_env_returns_value(self):
        from tools.env_config import require_env
        self.assertEqual(require_env("REQUIRED_VAR"), "ok")


class TestConvenienceAccessors(unittest.TestCase):
    """Convenience functions in env_config."""

    def _reset_dotenv_flag(self):
        import tools.env_config as ec
        ec._dotenv_loaded = False

    def setUp(self):
        self._reset_dotenv_flag()

    @mock.patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-proj"}, clear=False)
    def test_google_cloud_project(self):
        from tools.env_config import google_cloud_project
        self.assertEqual(google_cloud_project(), "my-proj")

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_vertex_ai_location_default(self):
        from tools.env_config import vertex_ai_location
        os.environ.pop("VERTEX_AI_LOCATION", None)
        self.assertEqual(vertex_ai_location(), "us-central1")

    @mock.patch.dict(os.environ, {"VERTEX_AI_LOCATION": "europe-west4"}, clear=False)
    def test_vertex_ai_location_custom(self):
        from tools.env_config import vertex_ai_location
        self.assertEqual(vertex_ai_location(), "europe-west4")

    @mock.patch.dict(os.environ, {"VERTEX_CHAT_MODEL": "gemini-2.0-flash"}, clear=False)
    def test_vertex_chat_model(self):
        from tools.env_config import vertex_chat_model
        self.assertEqual(vertex_chat_model(), "gemini-2.0-flash")

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_vertex_rag_corpus_none(self):
        from tools.env_config import vertex_rag_corpus
        os.environ.pop("VERTEX_RAG_CORPUS", None)
        self.assertIsNone(vertex_rag_corpus())

    @mock.patch.dict(
        os.environ,
        {"VERTEX_RAG_CORPUS": "projects/p/locations/l/ragCorpora/123"},
        clear=False,
    )
    def test_vertex_rag_corpus_set(self):
        from tools.env_config import vertex_rag_corpus
        self.assertEqual(
            vertex_rag_corpus(),
            "projects/p/locations/l/ragCorpora/123",
        )

    @mock.patch.dict(os.environ, {"GCS_BUCKET": "my-bucket"}, clear=False)
    def test_gcs_bucket(self):
        from tools.env_config import gcs_bucket
        self.assertEqual(gcs_bucket(), "my-bucket")

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_gcs_bucket_missing_raises(self):
        from tools.env_config import gcs_bucket, EnvVarMissing
        os.environ.pop("GCS_BUCKET", None)
        with self.assertRaises(EnvVarMissing):
            gcs_bucket()


class TestDotenvFallback(unittest.TestCase):
    """Verify that dotenv loading is attempted when os.environ misses a var."""

    def _reset_dotenv_flag(self):
        import tools.env_config as ec
        ec._dotenv_loaded = False

    def setUp(self):
        self._reset_dotenv_flag()

    @mock.patch("tools.env_config.load_dotenv", create=True)
    @mock.patch.dict(os.environ, {}, clear=False)
    def test_dotenv_loaded_once(self, mock_load):
        from tools.env_config import get_env, _ensure_dotenv
        os.environ.pop("SOME_VAR", None)
        _ensure_dotenv()
        _ensure_dotenv()


# ====================================================================
# vertex_chat tests
# ====================================================================


class TestSystemPromptManagement(unittest.TestCase):
    """get/set/reset system prompt in vertex_chat."""

    def setUp(self):
        import tools.vertex_chat as vc
        self._vc = vc
        vc._cached_model = None
        vc._vertex_inited = False
        vc._system_prompt = vc._DEFAULT_SYSTEM_PROMPT

    def test_get_default_prompt(self):
        prompt = self._vc.get_system_prompt()
        self.assertIn("Dietary Health Assistant", prompt)

    def test_set_prompt(self):
        self._vc.set_system_prompt("You are a test bot.")
        self.assertEqual(self._vc.get_system_prompt(), "You are a test bot.")

    def test_set_prompt_invalidates_cache(self):
        self._vc._cached_model = "fake_model"
        self._vc.set_system_prompt("New prompt")
        self.assertIsNone(self._vc._cached_model)

    def test_set_empty_prompt_raises(self):
        with self.assertRaises(ValueError):
            self._vc.set_system_prompt("")
        with self.assertRaises(ValueError):
            self._vc.set_system_prompt("   ")

    def test_reset_prompt(self):
        self._vc.set_system_prompt("Custom prompt")
        self._vc.reset_system_prompt()
        self.assertIn("Dietary Health Assistant", self._vc.get_system_prompt())


class TestRunChat(unittest.TestCase):
    """run_chat with mocked Vertex SDK."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "VERTEX_AI_LOCATION": "us-central1",
        "VERTEX_CHAT_MODEL": "gemini-2.0-flash",
    }

    def setUp(self):
        import tools.vertex_chat as vc
        self._vc = vc
        vc._cached_model = None
        vc._vertex_inited = False
        vc._system_prompt = vc._DEFAULT_SYSTEM_PROMPT
        import tools.env_config as ec
        ec._dotenv_loaded = False

    def test_empty_message_returns_error(self):
        result = self._vc.run_chat("")
        self.assertEqual(result["error"], "Message is required.")

    @mock.patch("tools.vertex_chat.vertexai")
    @mock.patch("tools.vertex_chat.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_successful_reply(self, MockModel, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock.MagicMock()]
        mock_response.text = "Hello! I can help with nutrition."
        MockModel.return_value.generate_content.return_value = mock_response

        result = self._vc.run_chat("What is protein?")
        self.assertEqual(result["reply"], "Hello! I can help with nutrition.")
        self.assertEqual(result["error"], "")

    @mock.patch("tools.vertex_chat.vertexai")
    @mock.patch("tools.vertex_chat.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_no_candidates(self, MockModel, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.candidates = []
        MockModel.return_value.generate_content.return_value = mock_response

        result = self._vc.run_chat("test")
        self.assertIn("No response", result["error"])

    @mock.patch("tools.vertex_chat.vertexai")
    @mock.patch("tools.vertex_chat.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_with_history(self, MockModel, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock.MagicMock()]
        mock_response.text = "Follow-up reply."
        MockModel.return_value.generate_content.return_value = mock_response

        history = [
            {"role": "user", "content": "Hi"},
            {"role": "model", "content": "Hello!"},
        ]
        result = self._vc.run_chat("Tell me more", history=history)
        self.assertEqual(result["reply"], "Follow-up reply.")

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_missing_project_env(self):
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        result = self._vc.run_chat("test")
        self.assertIn("GOOGLE_CLOUD_PROJECT", result["error"])

    @mock.patch("tools.vertex_chat.vertexai")
    @mock.patch("tools.vertex_chat.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_custom_prompt_used(self, MockModel, mock_vertexai):
        self._vc.set_system_prompt("You are a test bot.")
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock.MagicMock()]
        mock_response.text = "I'm a test bot."
        MockModel.return_value.generate_content.return_value = mock_response

        self._vc.run_chat("Hello")

        call_kwargs = MockModel.call_args
        self.assertIn("test bot", call_kwargs.kwargs.get("system_instruction", ""))


# ====================================================================
# rag_files tests
# ====================================================================


class TestRagFilesList(unittest.TestCase):
    """rag_files.list_files with mocked SDK."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "VERTEX_AI_LOCATION": "us-central1",
        "VERTEX_RAG_CORPUS": "projects/test-project/locations/us-central1/ragCorpora/123",
    }

    def setUp(self):
        import tools.rag_files as rf
        self._rf = rf
        rf._vertex_inited = False
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.rag_files.vertexai")
    @mock.patch("tools.rag_files.rag")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_list_files_returns_info(self, mock_rag, mock_vertexai):
        fake_file = mock.MagicMock()
        fake_file.display_name = "doc.pdf"
        fake_file.name = "projects/test-project/locations/us-central1/ragCorpora/123/ragFiles/456"
        mock_rag.list_files.return_value = [fake_file]

        result = self._rf.list_files()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].display_name, "doc.pdf")
        self.assertIn("ragFiles/456", result[0].name)

    @mock.patch("tools.rag_files.vertexai")
    @mock.patch("tools.rag_files.rag")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_list_files_empty(self, mock_rag, mock_vertexai):
        mock_rag.list_files.return_value = []
        result = self._rf.list_files()
        self.assertEqual(result, [])


class TestRagFilesImport(unittest.TestCase):
    """rag_files.import_files with mocked SDK."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "VERTEX_AI_LOCATION": "us-central1",
        "VERTEX_RAG_CORPUS": "projects/test-project/locations/us-central1/ragCorpora/123",
    }

    def setUp(self):
        import tools.rag_files as rf
        self._rf = rf
        rf._vertex_inited = False
        import tools.env_config as ec
        ec._dotenv_loaded = False

    def test_import_empty_paths_raises(self):
        with self.assertRaises(ValueError):
            self._rf.import_files([])

    @mock.patch("tools.rag_files.vertexai")
    @mock.patch("tools.rag_files.rag")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_import_files_success(self, mock_rag, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.imported_rag_files_count = 2
        mock_rag.import_files.return_value = mock_response

        result = self._rf.import_files(
            ["gs://bucket/file1.pdf", "gs://bucket/file2.pdf"]
        )
        self.assertEqual(result.imported_count, 2)
        mock_rag.import_files.assert_called_once()

    @mock.patch("tools.rag_files.vertexai")
    @mock.patch("tools.rag_files.rag")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_import_files_with_sink(self, mock_rag, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.imported_rag_files_count = 1
        mock_rag.import_files.return_value = mock_response

        self._rf.import_files(
            ["gs://bucket/file.pdf"],
            import_result_sink="gs://results/output.ndjson",
        )
        call_kwargs = mock_rag.import_files.call_args.kwargs
        self.assertEqual(call_kwargs["import_result_sink"], "gs://results/output.ndjson")

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_import_no_corpus_raises(self):
        os.environ.pop("VERTEX_RAG_CORPUS", None)
        os.environ["GOOGLE_CLOUD_PROJECT"] = "test"
        os.environ["VERTEX_AI_LOCATION"] = "us-central1"
        with self.assertRaises(RuntimeError):
            self._rf.import_files(["gs://bucket/file.pdf"])


class TestRagFilesDelete(unittest.TestCase):
    """rag_files.delete_file with mocked SDK."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "VERTEX_AI_LOCATION": "us-central1",
        "VERTEX_RAG_CORPUS": "projects/test-project/locations/us-central1/ragCorpora/123",
    }

    def setUp(self):
        import tools.rag_files as rf
        self._rf = rf
        rf._vertex_inited = False
        import tools.env_config as ec
        ec._dotenv_loaded = False

    def test_delete_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self._rf.delete_file("")

    @mock.patch("tools.rag_files.vertexai")
    @mock.patch("tools.rag_files.rag")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_delete_file_success(self, mock_rag, mock_vertexai):
        file_name = (
            "projects/test-project/locations/us-central1/"
            "ragCorpora/123/ragFiles/456"
        )
        self._rf.delete_file(file_name)
        mock_rag.delete_file.assert_called_once_with(name=file_name)


class TestRagFilesNoCorpus(unittest.TestCase):
    """Verify graceful error when VERTEX_RAG_CORPUS is unset."""

    def setUp(self):
        import tools.rag_files as rf
        self._rf = rf
        rf._vertex_inited = False
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.rag_files.vertexai")
    @mock.patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "p", "VERTEX_AI_LOCATION": "us-central1"}, clear=False)
    def test_list_no_corpus(self, mock_vertexai):
        os.environ.pop("VERTEX_RAG_CORPUS", None)
        with self.assertRaises(RuntimeError):
            self._rf.list_files()


# ====================================================================
# gcs_storage tests
# ====================================================================


class TestGcsStorageUploadFile(unittest.TestCase):
    """gcs_storage.upload_file with mocked GCS client."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GCS_BUCKET": "test-bucket",
    }

    def setUp(self):
        import tools.gcs_storage as gs
        self._gs = gs
        gs._client = None
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.gcs_storage.storage")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_upload_file_success(self, mock_storage):
        mock_blob = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_bucket.name = "test-bucket"
        mock_storage.Client.return_value.bucket.return_value = mock_bucket

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello")
            tmp_path = f.name

        try:
            uri = self._gs.upload_file(tmp_path)
            self.assertEqual(uri, f"gs://test-bucket/{os.path.basename(tmp_path)}")
            mock_blob.upload_from_filename.assert_called_once()
        finally:
            os.unlink(tmp_path)

    @mock.patch("tools.gcs_storage.storage")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_upload_file_custom_destination(self, mock_storage):
        mock_blob = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_bucket.name = "test-bucket"
        mock_storage.Client.return_value.bucket.return_value = mock_bucket

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"pdf content")
            tmp_path = f.name

        try:
            uri = self._gs.upload_file(
                tmp_path,
                destination_name="docs/report.pdf",
                content_type="application/pdf",
            )
            self.assertEqual(uri, "gs://test-bucket/docs/report.pdf")
            mock_bucket.blob.assert_called_with("docs/report.pdf")
            mock_blob.upload_from_filename.assert_called_once_with(
                tmp_path, content_type="application/pdf"
            )
        finally:
            os.unlink(tmp_path)

    def test_upload_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            self._gs.upload_file("/nonexistent/path/file.txt")


class TestGcsStorageUploadFromString(unittest.TestCase):
    """gcs_storage.upload_from_string with mocked GCS client."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GCS_BUCKET": "test-bucket",
    }

    def setUp(self):
        import tools.gcs_storage as gs
        self._gs = gs
        gs._client = None
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.gcs_storage.storage")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_upload_from_string(self, mock_storage):
        mock_blob = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_bucket.name = "test-bucket"
        mock_storage.Client.return_value.bucket.return_value = mock_bucket

        uri = self._gs.upload_from_string(
            b"raw data", "data/output.bin"
        )
        self.assertEqual(uri, "gs://test-bucket/data/output.bin")
        mock_blob.upload_from_string.assert_called_once_with(
            b"raw data", content_type="application/octet-stream"
        )

    def test_upload_from_string_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self._gs.upload_from_string(b"x", "")


class TestGcsStorageListFiles(unittest.TestCase):
    """gcs_storage.list_files with mocked GCS client."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GCS_BUCKET": "test-bucket",
    }

    def setUp(self):
        import tools.gcs_storage as gs
        self._gs = gs
        gs._client = None
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.gcs_storage.storage")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_list_files(self, mock_storage):
        blob1 = mock.MagicMock()
        blob1.name = "file1.txt"
        blob2 = mock.MagicMock()
        blob2.name = "uploads/file2.pdf"
        mock_bucket = mock.MagicMock()
        mock_bucket.list_blobs.return_value = [blob1, blob2]
        mock_storage.Client.return_value.bucket.return_value = mock_bucket

        result = self._gs.list_files()
        self.assertEqual(result, ["file1.txt", "uploads/file2.pdf"])

    @mock.patch("tools.gcs_storage.storage")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_list_files_with_prefix(self, mock_storage):
        blob = mock.MagicMock()
        blob.name = "uploads/file2.pdf"
        mock_bucket = mock.MagicMock()
        mock_bucket.list_blobs.return_value = [blob]
        mock_storage.Client.return_value.bucket.return_value = mock_bucket

        result = self._gs.list_files(prefix="uploads/")
        mock_bucket.list_blobs.assert_called_with(prefix="uploads/")
        self.assertEqual(result, ["uploads/file2.pdf"])

    @mock.patch("tools.gcs_storage.storage")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_list_files_empty(self, mock_storage):
        mock_bucket = mock.MagicMock()
        mock_bucket.list_blobs.return_value = []
        mock_storage.Client.return_value.bucket.return_value = mock_bucket

        self.assertEqual(self._gs.list_files(), [])


class TestGcsStorageDeleteFile(unittest.TestCase):
    """gcs_storage.delete_file with mocked GCS client."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "GCS_BUCKET": "test-bucket",
    }

    def setUp(self):
        import tools.gcs_storage as gs
        self._gs = gs
        gs._client = None
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.gcs_storage.storage")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_delete_file(self, mock_storage):
        mock_blob = mock.MagicMock()
        mock_bucket = mock.MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_bucket.name = "test-bucket"
        mock_storage.Client.return_value.bucket.return_value = mock_bucket

        self._gs.delete_file("uploads/old.txt")
        mock_bucket.blob.assert_called_with("uploads/old.txt")
        mock_blob.delete.assert_called_once()

    def test_delete_empty_name_raises(self):
        with self.assertRaises(ValueError):
            self._gs.delete_file("")


class TestGcsStorageMissingBucket(unittest.TestCase):
    """Verify error when GCS_BUCKET is unset."""

    def setUp(self):
        import tools.gcs_storage as gs
        self._gs = gs
        gs._client = None
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.gcs_storage.storage")
    @mock.patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "p"}, clear=False)
    def test_upload_no_bucket_raises(self, mock_storage):
        os.environ.pop("GCS_BUCKET", None)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"x")
            tmp_path = f.name
        try:
            from tools.env_config import EnvVarMissing
            with self.assertRaises(EnvVarMissing):
                self._gs.upload_file(tmp_path)
        finally:
            os.unlink(tmp_path)


# ====================================================================
# text_cleaner tests
# ====================================================================


class TestCleanTextEmptyInput(unittest.TestCase):
    """text_cleaner.clean_text rejects empty / blank input."""

    def test_empty_string(self):
        from tools.text_cleaner import clean_text
        result = clean_text("")
        self.assertEqual(result["text"], "")
        self.assertEqual(result["error"], "Input text is required.")

    def test_whitespace_only(self):
        from tools.text_cleaner import clean_text
        result = clean_text("    \n\t  ")
        self.assertEqual(result["error"], "Input text is required.")

    def test_none_input(self):
        from tools.text_cleaner import clean_text
        result = clean_text(None)
        self.assertEqual(result["error"], "Input text is required.")


class TestCleanTextSuccess(unittest.TestCase):
    """text_cleaner.clean_text with mocked Vertex SDK."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "VERTEX_AI_LOCATION": "us-central1",
    }

    def setUp(self):
        import tools.text_cleaner as tc
        self._tc = tc
        tc._cached_model = None
        tc._vertex_inited = False
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.text_cleaner.vertexai")
    @mock.patch("tools.text_cleaner.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_successful_clean(self, MockModel, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock.MagicMock()]
        mock_response.text = "Cleaned text about nutrition."
        MockModel.return_value.generate_content.return_value = mock_response

        result = self._tc.clean_text("  Lots   of   messy   text  here  ")
        self.assertEqual(result["text"], "Cleaned text about nutrition.")
        self.assertEqual(result["error"], "")

    @mock.patch("tools.text_cleaner.vertexai")
    @mock.patch("tools.text_cleaner.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_no_candidates(self, MockModel, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.candidates = []
        MockModel.return_value.generate_content.return_value = mock_response

        result = self._tc.clean_text("Some text")
        self.assertIn("No response", result["error"])
        self.assertEqual(result["text"], "")

    @mock.patch("tools.text_cleaner.vertexai")
    @mock.patch("tools.text_cleaner.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_safety_filter_valueerror(self, MockModel, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock.MagicMock()]
        mock_response.text = mock.PropertyMock(side_effect=ValueError("blocked"))
        type(mock_response).text = mock.PropertyMock(side_effect=ValueError("blocked"))
        MockModel.return_value.generate_content.return_value = mock_response

        result = self._tc.clean_text("Some text")
        self.assertIn("safety filter", result["error"])

    @mock.patch("tools.text_cleaner.vertexai")
    @mock.patch("tools.text_cleaner.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_uses_system_prompt(self, MockModel, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock.MagicMock()]
        mock_response.text = "Cleaned."
        MockModel.return_value.generate_content.return_value = mock_response

        self._tc.clean_text("raw input")
        call_kwargs = MockModel.call_args.kwargs
        self.assertIn("RAG", call_kwargs.get("system_instruction", ""))

    @mock.patch.dict(os.environ, {}, clear=False)
    def test_missing_project_env(self):
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        result = self._tc.clean_text("some text")
        self.assertIn("GOOGLE_CLOUD_PROJECT", result["error"])


class TestCleanTextDefaultModel(unittest.TestCase):
    """Verify the default model used by text_cleaner."""

    _ENV = {
        "GOOGLE_CLOUD_PROJECT": "test-project",
        "VERTEX_AI_LOCATION": "us-central1",
    }

    def setUp(self):
        import tools.text_cleaner as tc
        self._tc = tc
        tc._cached_model = None
        tc._vertex_inited = False
        import tools.env_config as ec
        ec._dotenv_loaded = False

    @mock.patch("tools.text_cleaner.vertexai")
    @mock.patch("tools.text_cleaner.GenerativeModel")
    @mock.patch.dict(os.environ, _ENV, clear=False)
    def test_default_model_is_flash_lite(self, MockModel, mock_vertexai):
        os.environ.pop("VERTEX_TEXT_CLEANER_MODEL", None)
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock.MagicMock()]
        mock_response.text = "cleaned"
        MockModel.return_value.generate_content.return_value = mock_response

        self._tc.clean_text("test")
        call_kwargs = MockModel.call_args.kwargs
        self.assertEqual(call_kwargs["model_name"], "gemini-2.0-flash-lite")

    @mock.patch("tools.text_cleaner.vertexai")
    @mock.patch("tools.text_cleaner.GenerativeModel")
    @mock.patch.dict(
        os.environ,
        {**_ENV, "VERTEX_TEXT_CLEANER_MODEL": "gemini-1.5-flash"},
        clear=False,
    )
    def test_custom_model_override(self, MockModel, mock_vertexai):
        mock_response = mock.MagicMock()
        mock_response.candidates = [mock.MagicMock()]
        mock_response.text = "cleaned"
        MockModel.return_value.generate_content.return_value = mock_response

        self._tc.clean_text("test")
        call_kwargs = MockModel.call_args.kwargs
        self.assertEqual(call_kwargs["model_name"], "gemini-1.5-flash")


if __name__ == "__main__":
    unittest.main()

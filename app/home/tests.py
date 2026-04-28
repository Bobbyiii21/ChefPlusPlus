import json
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from accounts.models import CPPUser
from developer.models import DatabaseFile

from home.views import (
    reference_downloads_for_reply,
    reference_downloads_for_source_refs,
)


class ReferenceDownloadsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get(
            "/chat/api/",
            HTTP_HOST="testserver",
        )
        self.user = CPPUser.objects.create_user(
            "refdl@test.example",
            "refdl_user",
            "x",
        )

    def test_empty_when_no_source_line(self):
        self.assertEqual(
            reference_downloads_for_reply(self.request, "Hello world."),
            [],
        )

    def test_matches_database_file_and_builds_media_absolute_url(self):
        DatabaseFile.objects.create(
            name="Dietary Guidelines",
            description="",
            file=SimpleUploadedFile("dg.pdf", b"%PDF-1.4"),
            uploader=self.user,
        )
        reply = "Meal plan.\n\nSource: Dietary Guidelines"
        out = reference_downloads_for_reply(self.request, reply)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["name"], "Dietary Guidelines")
        self.assertTrue(out[0]["url"].startswith("http://testserver/"))
        self.assertIn("/media/", out[0]["url"])

    def test_splits_commas_and_dedupes(self):
        DatabaseFile.objects.create(
            name="Doc A",
            description="",
            file=SimpleUploadedFile("a.txt", b"a"),
            uploader=self.user,
        )
        DatabaseFile.objects.create(
            name="Doc B",
            description="",
            file=SimpleUploadedFile("b.txt", b"b"),
            uploader=self.user,
        )
        reply = "x\n\nSource: Doc A, Doc B; Doc A"
        out = reference_downloads_for_reply(self.request, reply)
        names = [x["name"] for x in out]
        self.assertEqual(names, ["Doc A", "Doc B"])

    def test_source_refs_match_rag_resource_before_gcs_and_name(self):
        DatabaseFile.objects.create(
            name="GCS Match",
            description="",
            file=SimpleUploadedFile("gcs.txt", b"gcs"),
            gcs_uri="gs://bucket/doc.txt",
            uploader=self.user,
        )
        DatabaseFile.objects.create(
            name="Name Match",
            description="",
            file=SimpleUploadedFile("name.txt", b"name"),
            uploader=self.user,
        )
        DatabaseFile.objects.create(
            name="RAG Match",
            description="",
            file=SimpleUploadedFile("rag.txt", b"rag"),
            gcs_uri="gs://bucket/doc.txt",
            rag_resource_name="projects/p/locations/l/ragCorpora/c/ragFiles/rag-1",
            uploader=self.user,
        )

        out = reference_downloads_for_source_refs(
            self.request,
            [
                {
                    "rag_resource_name": (
                        "projects/p/locations/l/ragCorpora/c/ragFiles/rag-1"
                    ),
                    "gcs_uri": "gs://bucket/doc.txt",
                    "display_name": "Name Match",
                }
            ],
        )
        self.assertEqual([x["name"] for x in out], ["RAG Match"])

    def test_source_refs_fall_back_to_gcs_before_name(self):
        DatabaseFile.objects.create(
            name="Name Match",
            description="",
            file=SimpleUploadedFile("name.txt", b"name"),
            uploader=self.user,
        )
        DatabaseFile.objects.create(
            name="GCS Match",
            description="",
            file=SimpleUploadedFile("gcs.txt", b"gcs"),
            gcs_uri="gs://bucket/doc.txt",
            uploader=self.user,
        )

        out = reference_downloads_for_source_refs(
            self.request,
            [{"gcs_uri": "gs://bucket/doc.txt", "display_name": "Name Match"}],
        )
        self.assertEqual([x["name"] for x in out], ["GCS Match"])

    def test_source_refs_fall_back_to_display_name_and_skip_non_downloadable(self):
        DatabaseFile.objects.create(
            name="No File",
            description="",
            rag_resource_name="projects/p/locations/l/ragCorpora/c/ragFiles/missing",
            uploader=self.user,
        )
        DatabaseFile.objects.create(
            name="Display Match",
            description="",
            file=SimpleUploadedFile("display.txt", b"display"),
            uploader=self.user,
        )

        out = reference_downloads_for_source_refs(
            self.request,
            [
                {
                    "rag_resource_name": (
                        "projects/p/locations/l/ragCorpora/c/ragFiles/missing"
                    ),
                },
                {"display_name": "display match"},
            ],
        )
        self.assertEqual([x["name"] for x in out], ["Display Match"])

    @mock.patch("tools.vertex_chat.run_chat")
    def test_chat_api_uses_metadata_sources_without_source_line(self, mock_run_chat):
        DatabaseFile.objects.create(
            name="Recipe Notes",
            description="",
            file=SimpleUploadedFile("recipe.txt", b"recipe"),
            rag_resource_name="projects/p/locations/l/ragCorpora/c/ragFiles/recipe",
            uploader=self.user,
        )
        mock_run_chat.return_value = {
            "reply": "Use the recipe notes to balance the meal.",
            "error": "",
            "sources_used": [
                {
                    "rag_resource_name": (
                        "projects/p/locations/l/ragCorpora/c/ragFiles/recipe"
                    ),
                },
            ],
        }

        response = self.client.post(
            "/chat/api/",
            data=json.dumps({"message": "How should I adjust this recipe?"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["reply"], "Use the recipe notes to balance the meal.")
        self.assertEqual(payload["reference_downloads"][0]["name"], "Recipe Notes")

    @mock.patch("tools.vertex_chat.run_chat")
    def test_chat_api_falls_back_to_source_line_when_metadata_absent(self, mock_run_chat):
        DatabaseFile.objects.create(
            name="Fallback Doc",
            description="",
            file=SimpleUploadedFile("fallback.txt", b"fallback"),
            uploader=self.user,
        )
        mock_run_chat.return_value = {
            "reply": "Use this uploaded note.\n\nSource: Fallback Doc",
            "error": "",
            "sources_used": [],
        }

        response = self.client.post(
            "/chat/api/",
            data=json.dumps({"message": "What does my note say?"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["reference_downloads"][0]["name"], "Fallback Doc")

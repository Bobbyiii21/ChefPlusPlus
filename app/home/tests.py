from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase

from accounts.models import CPPUser
from developer.models import DatabaseFile

from home.views import reference_downloads_for_reply


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

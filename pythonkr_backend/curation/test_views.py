import pytest
import tempfile
import os
from unittest.mock import patch, mock_open, MagicMock
from django.test import Client
from django.urls import reverse

from .models import TranslatedContent, RSSFeed, RSSItem


@pytest.mark.django_db
class TestTranslatedContentView:
    """Test cases for TranslatedContent detail view."""

    def setup_method(self):
        """Set up test data for each test method."""
        self.client = Client()

        # Create test RSS feed and item
        self.feed = RSSFeed.objects.create(
            name="Test Feed", url="https://example.com/feed.xml", is_active=True
        )

        self.rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Original Article",
            link="https://example.com/original-article",
            crawling_status="completed",
        )

        # Create test TranslatedContent
        self.translated_content = TranslatedContent.objects.create(
            title="테스트 기사",
            slug="test-article",
            description="테스트 기사 설명입니다.",
            tags=["python", "django", "test"],
            written_date="2024-01-15",
            author="테스트 작성자",
            model_name="gemini:gemini-2.5-pro",
            source_rss_item=self.rss_item,
            source_url="https://example.com/original-article",
        )

    def test_translated_content_detail_success(self):
        """Test successful rendering of TranslatedContent detail page."""
        # Create a temporary file with markdown content
        test_content = "# 테스트 기사\n\n이것은 테스트 내용입니다.\n\n## 섹션 1\n\n내용이 있습니다."

        # Mock the file field to have a path and exist
        mock_file = MagicMock()
        mock_file.path = "/fake/path/to/file.md"
        mock_file.__bool__ = MagicMock(return_value=True)  # Make sure it's truthy

        with patch("curation.views.get_object_or_404") as mock_get_object:
            # Mock the retrieved object to have our mocked file
            mock_content = MagicMock()
            mock_content.id = self.translated_content.id
            mock_content.content = mock_file
            mock_get_object.return_value = mock_content

            with patch("curation.views.os.path.exists", return_value=True):
                with patch("curation.views.open", mock_open(read_data=test_content)):
                    url = reverse(
                        "curation:translated_content_detail",
                        args=[self.translated_content.id],
                    )
                    response = self.client.get(url)

                    assert response.status_code == 200
                    assert response.context["content"] == mock_content
                    assert response.context["markdown_content"] == test_content

    def test_translated_content_detail_404(self):
        """Test 404 response for non-existent TranslatedContent."""
        url = reverse("curation:translated_content_detail", args=[99999])
        response = self.client.get(url)

        assert response.status_code == 404

    def test_translated_content_detail_no_file(self):
        """Test handling when content file doesn't exist."""
        # Content object exists but no file is attached
        url = reverse(
            "curation:translated_content_detail", args=[self.translated_content.id]
        )
        response = self.client.get(url)

        assert response.status_code == 200
        assert response.context["markdown_content"] == "No content file available."

    def test_translated_content_detail_file_read_error(self):
        """Test handling of file reading errors."""
        # Mock the file field to have a path
        mock_file = MagicMock()
        mock_file.path = "/fake/path/to/file.md"

        with patch("curation.views.get_object_or_404") as mock_get_object:
            # Mock the retrieved object to have our mocked file
            mock_content = MagicMock()
            mock_content.id = self.translated_content.id
            mock_content.content = mock_file
            mock_get_object.return_value = mock_content

            with patch("curation.views.os.path.exists", return_value=True):
                with patch(
                    "curation.views.open", side_effect=IOError("Permission denied")
                ):
                    url = reverse(
                        "curation:translated_content_detail",
                        args=[self.translated_content.id],
                    )
                    response = self.client.get(url)

                    assert response.status_code == 200
                    assert (
                        "Error reading content file: Permission denied"
                        in response.context["markdown_content"]
                    )

    def test_translated_content_detail_with_file_content(self):
        """Test with actual file content attached."""
        test_content = "# 실제 파일 내용\n\n이것은 실제 파일에서 읽은 내용입니다."

        # Create a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(test_content)
            temp_file_path = f.name

        try:
            # Mock the content file field
            mock_file = MagicMock()
            mock_file.path = temp_file_path

            with patch("curation.views.get_object_or_404") as mock_get_object:
                # Mock the retrieved object to have our mocked file
                mock_content = MagicMock()
                mock_content.id = self.translated_content.id
                mock_content.content = mock_file
                mock_get_object.return_value = mock_content

                url = reverse(
                    "curation:translated_content_detail",
                    args=[self.translated_content.id],
                )
                response = self.client.get(url)

                assert response.status_code == 200
                assert response.context["markdown_content"] == test_content
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    def test_translated_content_context_data(self):
        """Test that all expected context data is passed to template."""
        test_content = "# Context Test\n\nTesting context data."

        # Mock the file field to have a path
        mock_file = MagicMock()
        mock_file.path = "/fake/path/to/file.md"

        with patch.object(self.translated_content, "content", mock_file):
            with patch("curation.views.os.path.exists", return_value=True):
                with patch("curation.views.open", mock_open(read_data=test_content)):
                    url = reverse(
                        "curation:translated_content_detail",
                        args=[self.translated_content.id],
                    )
                    response = self.client.get(url)

                    context = response.context
                    assert "content" in context
                    assert "markdown_content" in context

                    content = context["content"]
                    assert content.title == "테스트 기사"
                    assert content.slug == "test-article"
                    assert content.description == "테스트 기사 설명입니다."
                    assert content.tags == ["python", "django", "test"]
                    assert content.author == "테스트 작성자"
                    assert content.model_name == "gemini:gemini-2.5-pro"
                    assert content.source_rss_item == self.rss_item
                    assert content.source_url == "https://example.com/original-article"

    def test_translated_content_minimal_data(self):
        """Test with minimal TranslatedContent data."""
        minimal_content = TranslatedContent.objects.create(
            title="최소 콘텐츠",
            slug="minimal-content",
            description="최소한의 설명",
            model_name="test-model",
            source_url="https://example.com/minimal",
        )

        url = reverse("curation:translated_content_detail", args=[minimal_content.id])
        response = self.client.get(url)

        assert response.status_code == 200
        assert response.context["content"] == minimal_content
        assert response.context["markdown_content"] == "No content file available."


@pytest.mark.django_db
class TestTranslatedContentUrls:
    """Test cases for TranslatedContent URL patterns."""

    def setup_method(self):
        """Set up test data."""
        self.feed = RSSFeed.objects.create(
            name="Test Feed", url="https://example.com/feed.xml"
        )

        self.rss_item = RSSItem.objects.create(
            feed=self.feed, title="Test Item", link="https://example.com/test"
        )

        self.content = TranslatedContent.objects.create(
            title="URL Test Content",
            slug="url-test",
            description="Testing URLs",
            model_name="test-model",
            source_url="https://example.com/test",
        )

    def test_url_resolution(self):
        """Test that URL resolves correctly."""
        url = reverse("curation:translated_content_detail", args=[self.content.id])
        expected_url = f"/tr/{self.content.id}/"

        assert url == expected_url

    def test_url_with_different_ids(self):
        """Test URL generation with different ID values."""
        # Test with different ID values
        test_ids = [1, 123, 9999]

        for test_id in test_ids:
            url = reverse("curation:translated_content_detail", args=[test_id])
            expected_url = f"/tr/{test_id}/"
            assert url == expected_url

    def test_url_name_reverse(self):
        """Test that URL can be reversed by name."""
        url = reverse("curation:translated_content_detail", args=[self.content.id])
        response = Client().get(url)

        # Should get 200 (content exists) or 404 (content doesn't exist)
        # Both are valid responses for URL resolution test
        assert response.status_code in [200, 404]

    def test_invalid_url_parameters(self):
        """Test handling of invalid URL parameters."""
        client = Client()

        # Test with non-numeric ID (should result in 404 at URL level)
        response = client.get("/tr/invalid/")
        assert response.status_code == 404

        # Test with negative ID
        response = client.get("/tr/-1/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestTranslatedContentTemplateIntegration:
    """Test template rendering and integration."""

    def setup_method(self):
        """Set up test data."""
        self.client = Client()

        self.feed = RSSFeed.objects.create(
            name="Template Test Feed", url="https://example.com/template-feed.xml"
        )

        self.rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Template Test Item",
            link="https://example.com/template-test",
        )

        self.content = TranslatedContent.objects.create(
            title="템플릿 테스트",
            slug="template-test",
            description="템플릿 렌더링 테스트입니다.",
            tags=["template", "test", "django"],
            written_date="2024-01-20",
            author="템플릿 작성자",
            model_name="template-model",
            source_rss_item=self.rss_item,
            source_url="https://example.com/template-source",
        )

    def test_template_inheritance(self):
        """Test that template properly extends base template."""
        test_content = "# Template Test"

        # Mock the file field to have a path
        mock_file = MagicMock()
        mock_file.path = "/fake/path/to/file.md"

        with patch.object(self.content, "content", mock_file):
            with patch("curation.views.os.path.exists", return_value=True):
                with patch("curation.views.open", mock_open(read_data=test_content)):
                    url = reverse(
                        "curation:translated_content_detail", args=[self.content.id]
                    )
                    response = self.client.get(url)

                    assert response.status_code == 200

                    # Check for base template elements
                    content = response.content.decode()
                    assert '<html lang="ko">' in content
                    assert "파이썬 한국 사용자 모임" in content

    def test_template_content_display(self):
        """Test that all content fields are properly displayed."""
        test_markdown = "# 템플릿 마크다운\n\n템플릿 테스트 내용입니다."

        # Create a real temporary file for this test
        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(test_markdown)
            temp_file_path = f.name

        try:
            # Save the file path to the model using Django's File
            from django.core.files import File

            with open(temp_file_path, "rb") as f:
                self.content.content.save("test-content.md", File(f), save=True)

            url = reverse("curation:translated_content_detail", args=[self.content.id])
            response = self.client.get(url)

            content = response.content.decode()

            # Check all fields are displayed
            assert "템플릿 테스트" in content  # title
            assert "템플릿 작성자" in content  # author
            assert "2024년 01월 20일" in content  # written_date
            assert "template-model" in content  # model_name
            assert "템플릿 렌더링 테스트입니다." in content  # description
            assert "template" in content  # tags
            assert "test" in content
            assert "django" in content
            assert "템플릿 마크다운" in content  # markdown content title
            assert "템플릿 테스트 내용입니다" in content  # markdown content body
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            # Clean up the uploaded file if it exists
            if self.content.content:
                try:
                    self.content.content.delete()
                except Exception:
                    pass

    def test_template_source_information(self):
        """Test that source information is properly displayed."""
        # Mock the file field to have a path
        mock_file = MagicMock()
        mock_file.path = "/fake/path/to/file.md"

        with patch.object(self.content, "content", mock_file):
            with patch("curation.views.os.path.exists", return_value=True):
                with patch("curation.views.open", mock_open(read_data="# Test")):
                    url = reverse(
                        "curation:translated_content_detail", args=[self.content.id]
                    )
                    response = self.client.get(url)

                    response_content = response.content.decode()

                    # Check source information
                    assert "https://example.com/template-source" in response_content
                    assert "Template Test Feed" in response_content

    def test_template_missing_optional_fields(self):
        """Test template rendering when optional fields are missing."""
        minimal_content = TranslatedContent.objects.create(
            title="최소 템플릿 테스트",
            slug="minimal-template",
            description="최소한의 템플릿 테스트",
            model_name="minimal-model",
            source_url="https://example.com/minimal",
            # No author, written_date, tags, or source_rss_item
        )

        url = reverse("curation:translated_content_detail", args=[minimal_content.id])
        response = self.client.get(url)

        assert response.status_code == 200
        response_content = response.content.decode()

        # Check that missing fields don't break the template
        assert "최소 템플릿 테스트" in response_content  # title should be there
        assert "minimal-model" in response_content  # model should be there
        assert (
            "콘텐츠가 없습니다" in response_content
            or "No content file available" in response_content
        )

import pytest
from unittest.mock import patch, MagicMock, mock_open
from django.core.files.base import ContentFile

from .models import RSSItem, RSSFeed, TranslatedContent, LLMService, LLMUsage
from .utils import (
    fetch_content_from_url,
    parse_contents,
    get_summary_from_url,
    translate_to_korean,
    categorize_summary,
)
from .utils_trans import translate_rssitem


@pytest.mark.django_db
class TestUtilsFunctions:
    """Test cases for utility functions in utils.py."""

    @patch("httpx.get")
    def test_fetch_content_from_url_success(self, mock_get):
        """Test fetch_content_from_url with successful response."""
        mock_response = MagicMock()
        mock_response.text = "# Test Article\n\nThis is test content."
        mock_get.return_value = mock_response

        url = "https://example.com/test-article"
        result = fetch_content_from_url(url)

        assert result == "# Test Article\n\nThis is test content."
        mock_get.assert_called_once_with(f"https://r.jina.ai/{url}")

    @patch("httpx.get")
    def test_fetch_content_from_url_network_error(self, mock_get):
        """Test fetch_content_from_url with network error."""
        mock_get.side_effect = Exception("Network error")

        url = "https://example.com/test-article"

        with pytest.raises(Exception):
            fetch_content_from_url(url)

    def test_parse_contents_valid_format(self):
        """Test parse_contents with valid markdown format."""
        contents = """Title: Test Article
URL Source: https://example.com/test
Author: Test Author
Published: 2024-01-15

Markdown Content:
# Test Article

This is the main content of the article.

## Section 1
Some content here."""

        header, markdown_body = parse_contents(contents)

        assert header["Title"] == "Test Article"
        assert header["URL Source"] == "https://example.com/test"
        assert header["Author"] == "Test Author"
        assert header["Published"] == "2024-01-15"
        assert markdown_body.strip().startswith("# Test Article")
        assert "## Section 1" in markdown_body

    def test_parse_contents_minimal_format(self):
        """Test parse_contents with minimal header."""
        contents = """Title: Simple Article

Markdown Content:
# Simple Article

Just some content."""

        header, markdown_body = parse_contents(contents)

        assert header["Title"] == "Simple Article"
        assert len(header) == 1
        assert markdown_body.strip().startswith("# Simple Article")

    @patch("llm.get_model")
    def test_get_summary_from_url_success(self, mock_get_model):
        """Test get_summary_from_url with successful LLM response."""
        # Mock LLM model and response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = (
            "# 테스트 기사\n\n## 요약\n- 첫 번째 요점\n- 두 번째 요점\n- 세 번째 요점"
        )
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model

        with patch("curation.utils.fetch_content_from_url") as mock_fetch:
            mock_fetch.return_value = "Test article content"

            result = get_summary_from_url("https://example.com/test")

            assert "테스트 기사" in result
            assert "요약" in result
            assert "요점" in result

            mock_fetch.assert_called_once_with("https://example.com/test")
            mock_model.prompt.assert_called_once()

    @patch("llm.get_model")
    @patch("curation.utils.GEMINI_API_KEY", "test_key")
    def test_get_summary_from_url_with_api_key(self, mock_get_model):
        """Test that get_summary_from_url sets API key correctly."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Summary text"
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model

        with patch("curation.utils.fetch_content_from_url") as mock_fetch:
            mock_fetch.return_value = "Test content"
            get_summary_from_url("https://example.com/test")

            assert mock_model.key == "test_key"

    @patch("llm.get_model")
    def test_translate_to_korean_success(self, mock_get_model):
        """Test translate_to_korean with successful translation."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "번역된 텍스트입니다."
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model

        english_text = "This is a test text."
        result = translate_to_korean(english_text)

        assert result == "번역된 텍스트입니다."
        mock_model.prompt.assert_called_once()

        # Check prompt content
        call_args = mock_model.prompt.call_args
        assert english_text in call_args[0][0]
        assert "translate" in call_args[1]["system"].lower()
        assert "korean" in call_args[1]["system"].lower()

    @patch("llm.get_model")
    def test_categorize_summary_success(self, mock_get_model):
        """Test categorize_summary with successful categorization."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Web Development, Large Language Models"
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model

        summary = "This article discusses building web applications using LLMs."
        categories = [
            "Web Development",
            "Large Language Models",
            "Data Science",
            "Other",
        ]

        result = categorize_summary(summary, categories)

        assert result == "Web Development, Large Language Models"
        mock_model.prompt.assert_called_once()

        # Check that categories were included in prompt
        call_args = mock_model.prompt.call_args
        assert summary in call_args[0][0]
        system_prompt = call_args[1]["system"]
        assert "'Web Development'" in system_prompt
        assert "'Large Language Models'" in system_prompt

    @patch("llm.get_model")
    def test_categorize_summary_other_category(self, mock_get_model):
        """Test categorize_summary returns 'Other' when no fit."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Other"
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model

        summary = "This article discusses cooking recipes."
        categories = ["Web Development", "Data Science", "Other"]

        result = categorize_summary(summary, categories)

        assert result == "Other"


@pytest.mark.django_db
class TestUtilsTransFunctions:
    """Test cases for utility functions in utils_trans.py."""

    def setup_method(self):
        """Set up test data for each test method."""
        self.feed = RSSFeed.objects.create(
            name="Test Feed", url="https://example.com/feed.xml", is_active=True
        )

        # Create LLM service
        self.llm_service = LLMService.objects.create(
            provider="gemini", priority=1, is_active=True
        )

    @patch("curation.utils_trans.Agent")
    @patch.object(LLMService, "get_llm_provider_model")
    def test_translate_rssitem_success(self, mock_get_provider, mock_agent_class):
        """Test translate_rssitem with successful translation."""
        # Create RSS item with crawled content
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            is_translation_allowed=True,
            language="en",
        )

        # Mock crawled content file
        rss_item.crawled_content.name = "test_content.md"
        rss_item.save()

        # Create mock file content
        mock_content = "# Test Article\n\nThis is test content."

        # Mock LLM service response
        mock_get_provider.return_value = ("gemini", "gemini-2.5-pro")

        # Mock AI agent and result
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        mock_result = MagicMock()
        mock_result.output.title = "테스트 기사"
        mock_result.output.slug = "test-article"
        mock_result.output.description = "테스트 기사 설명"
        mock_result.output.author = "테스트 작성자"
        mock_result.output.tags = ["python", "django"]
        mock_result.output.written_date = "2024-01-15"
        mock_result.output.content = "# 테스트 기사\n\n테스트 내용입니다."

        # Mock usage tracking
        mock_usage = MagicMock()
        mock_usage.request_tokens = 100
        mock_usage.response_tokens = 200
        mock_usage.total_tokens = 300
        mock_result.usage.return_value = mock_usage

        mock_agent.run_sync.return_value = mock_result

        # Mock file operations
        mock_file = mock_open(read_data=mock_content)
        with patch("builtins.open", mock_file):
            result = translate_rssitem(rss_item.id)

            assert isinstance(result, TranslatedContent)
            assert result.title == "테스트 기사"
            assert result.slug == "test-article"
            assert result.description == "테스트 기사 설명"
            assert result.author == "테스트 작성자"
            assert result.tags == ["python", "django"]
            assert result.model_name == "gemini:gemini-2.5-pro"
            assert result.source_rss_item == rss_item
            assert result.source_url == rss_item.link

            # Check that LLM usage was recorded
            usage = LLMUsage.objects.get(model_name="gemini:gemini-2.5-pro")
            assert usage.input_tokens == 100
            assert usage.output_tokens == 200
            assert usage.total_tokens == 300

    @patch.object(LLMService, "get_llm_provider_model")
    def test_translate_rssitem_no_llm_service(self, mock_get_provider):
        """Test translate_rssitem when no LLM service is available."""
        mock_get_provider.return_value = (None, None)

        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            is_translation_allowed=True,
            language="en",
        )

        with pytest.raises(ValueError) as exc_info:
            translate_rssitem(rss_item.id)

        assert "No available LLM service found" in str(exc_info.value)

    def test_translate_rssitem_no_crawled_content(self):
        """Test translate_rssitem when RSS item has no crawled content."""
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            is_translation_allowed=True,
            language="en",
        )

        with pytest.raises(ValueError) as exc_info:
            translate_rssitem(rss_item.id)

        assert "RSS item has no crawled content" in str(exc_info.value)

    @patch("curation.utils_trans.Agent")
    @patch.object(LLMService, "get_llm_provider_model")
    def test_translate_rssitem_translation_error(
        self, mock_get_provider, mock_agent_class
    ):
        """Test translate_rssitem when translation fails."""
        # Create RSS item with crawled content
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            translate_status="pending",
            is_translation_allowed=True,
            language="en",
        )

        # Mock crawled content file
        rss_item.crawled_content.name = "test_content.md"
        rss_item.save()

        mock_content = "# Test Article\n\nThis is test content."

        mock_get_provider.return_value = ("gemini", "gemini-2.5-pro")

        # Mock agent to raise exception
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.run_sync.side_effect = Exception("Translation API error")

        mock_file = mock_open(read_data=mock_content)
        with patch("builtins.open", mock_file):
            with pytest.raises(Exception) as exc_info:
                translate_rssitem(rss_item.id)

            assert "Translation API error" in str(exc_info.value)

            # Check that RSS item status was updated
            rss_item.refresh_from_db()
            assert rss_item.crawling_status == "failed"
            assert "Translation API error" in rss_item.translate_error_message

    def test_translate_rssitem_nonexistent_rss_item(self):
        """Test translate_rssitem with non-existent RSS item ID."""
        with pytest.raises(Exception):
            translate_rssitem(99999)

    @patch("curation.utils_trans.Agent")
    @patch.object(LLMService, "get_llm_provider_model")
    def test_translate_rssitem_file_handling(self, mock_get_provider, mock_agent_class):
        """Test that translate_rssitem properly handles file operations."""
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            is_translation_allowed=True,
            language="en",
        )

        # Mock crawled content file
        rss_item.crawled_content.name = "test_content.md"
        rss_item.save()

        mock_content = "# Test Article\n\nThis is test content."

        mock_get_provider.return_value = ("openai", "gpt-4.1-2025-04-14")

        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        mock_result = MagicMock()
        mock_result.output.title = "Translated Title"
        mock_result.output.slug = "translated-title"
        mock_result.output.description = "Translated description"
        mock_result.output.author = "Translated author"
        mock_result.output.tags = ["test"]
        mock_result.output.written_date = "2024-01-15"
        mock_result.output.content = "Translated content"

        mock_usage = MagicMock()
        mock_usage.request_tokens = 50
        mock_usage.response_tokens = 100
        mock_usage.total_tokens = 150
        mock_result.usage.return_value = mock_usage

        mock_agent.run_sync.return_value = mock_result

        mock_file = mock_open(read_data=mock_content)
        with patch("builtins.open", mock_file):
            result = translate_rssitem(rss_item.id)

            # Verify the result is saved to database
            assert TranslatedContent.objects.filter(source_rss_item=rss_item).exists()

    @patch("curation.utils_trans.Agent")
    @patch.object(LLMService, "get_llm_provider_model")
    def test_translate_rssitem_system_prompt(self, mock_get_provider, mock_agent_class):
        """Test that translate_rssitem uses correct system prompt."""
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            is_translation_allowed=True,
            language="en",
        )

        # Mock crawled content file
        rss_item.crawled_content.name = "test_content.md"
        rss_item.save()

        mock_content = "# Test Article\n\nThis is test content."

        mock_get_provider.return_value = ("claude", "claude-sonnet-4-0")

        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        # Mock minimal successful result
        mock_result = MagicMock()
        mock_result.output.title = "Title"
        mock_result.output.slug = "slug"
        mock_result.output.description = "Description"
        mock_result.output.author = "Author"
        mock_result.output.tags = []
        mock_result.output.written_date = "2024-01-15"
        mock_result.output.content = "Content"
        mock_result.usage.return_value = MagicMock(
            request_tokens=10, response_tokens=20, total_tokens=30
        )

        mock_agent.run_sync.return_value = mock_result

        mock_file = mock_open(read_data=mock_content)
        with patch("builtins.open", mock_file):
            translate_rssitem(rss_item.id)

            # Check Agent was created with correct parameters
            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args

            assert call_args[0][0] == "claude:claude-sonnet-4-0"  # model name
            assert "korean" in call_args[1]["system_prompt"].lower()
            assert "translate" in call_args[1]["system_prompt"].lower()


@pytest.mark.django_db
class TestTranslatedContentModelIntegration:
    """Test cases for TranslatedContent model integration with views."""

    def setup_method(self):
        """Set up test data for each test method."""
        self.feed = RSSFeed.objects.create(
            name="Model Test Feed",
            url="https://example.com/model-feed.xml",
            is_active=True,
        )

        self.rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Model Test Item",
            link="https://example.com/model-test",
            crawling_status="completed",
        )

    def test_translated_content_creation(self):
        """Test creating TranslatedContent with all fields."""
        content = TranslatedContent.objects.create(
            title="모델 테스트 제목",
            slug="model-test-title",
            description="모델 테스트 설명입니다.",
            tags=["model", "test", "integration"],
            written_date="2024-01-15",
            author="모델 테스트 작성자",
            model_name="test-model:v1.0",
            source_rss_item=self.rss_item,
            source_url="https://example.com/model-source",
        )

        assert content.id is not None
        assert content.title == "모델 테스트 제목"
        assert content.slug == "model-test-title"
        assert content.description == "모델 테스트 설명입니다."
        assert content.tags == ["model", "test", "integration"]
        assert str(content.written_date) == "2024-01-15"
        assert content.author == "모델 테스트 작성자"
        assert content.model_name == "test-model:v1.0"
        assert content.source_rss_item == self.rss_item
        assert content.source_url == "https://example.com/model-source"

    def test_translated_content_minimal_fields(self):
        """Test creating TranslatedContent with only required fields."""
        content = TranslatedContent.objects.create(
            title="최소 필드 테스트",
            slug="minimal-fields",
            description="최소 필드만 가진 콘텐츠",
            model_name="minimal-model",
            source_url="https://example.com/minimal",
        )

        assert content.id is not None
        assert content.title == "최소 필드 테스트"
        assert content.tags == []  # Default empty list
        assert content.author is None
        assert content.written_date is None
        assert content.source_rss_item is None

    def test_translated_content_file_field(self):
        """Test TranslatedContent file field operations."""

        content = TranslatedContent.objects.create(
            title="파일 테스트",
            slug="file-test",
            description="파일 필드 테스트",
            model_name="file-model",
            source_url="https://example.com/file-test",
        )

        # Test file assignment
        test_file_content = "# 파일 테스트\n\n파일 내용입니다."
        content.content.save(
            "test-content.md", ContentFile(test_file_content.encode("utf-8"))
        )

        assert content.content.name is not None
        assert (
            "-ko" in content.content.name and ".md" in content.content.name
        )  # Check for the upload path pattern

    def test_translated_content_relationships(self):
        """Test TranslatedContent foreign key relationships."""
        content = TranslatedContent.objects.create(
            title="관계 테스트",
            slug="relationship-test",
            description="관계 테스트 설명",
            model_name="relationship-model",
            source_rss_item=self.rss_item,
            source_url=self.rss_item.link,
        )

        # Test forward relationship
        assert content.source_rss_item == self.rss_item
        assert content.source_rss_item.title == "Model Test Item"
        assert content.source_rss_item.feed == self.feed

        # Test reverse relationship
        translated_contents = self.rss_item.translated_contents.all()
        assert content in translated_contents
        assert translated_contents.count() == 1

    def test_translated_content_tags_field(self):
        """Test TranslatedContent JSONField for tags."""
        # Test with various tag formats
        test_cases = [
            [],  # Empty list
            ["single"],  # Single tag
            ["multiple", "tags", "here"],  # Multiple tags
            ["한글", "태그", "지원"],  # Korean tags
            ["spaces in tags", "special-chars_123"],  # Special characters
        ]

        for i, tags in enumerate(test_cases):
            content = TranslatedContent.objects.create(
                title=f"태그 테스트 {i}",
                slug=f"tag-test-{i}",
                description=f"태그 테스트 {i} 설명",
                tags=tags,
                model_name="tag-model",
                source_url=f"https://example.com/tag-test-{i}",
            )

            content.refresh_from_db()
            assert content.tags == tags

    def test_translated_content_cascade_delete(self):
        """Test CASCADE delete behavior with RSS item."""
        content = TranslatedContent.objects.create(
            title="삭제 테스트",
            slug="delete-test",
            description="CASCADE 삭제 테스트",
            model_name="delete-model",
            source_rss_item=self.rss_item,
            source_url=self.rss_item.link,
        )

        content_id = content.id
        rss_item_id = self.rss_item.id

        # Verify content exists
        assert TranslatedContent.objects.filter(id=content_id).exists()

        # Delete RSS item
        self.rss_item.delete()

        # Verify content is also deleted due to CASCADE
        assert not TranslatedContent.objects.filter(id=content_id).exists()
        assert not RSSItem.objects.filter(id=rss_item_id).exists()

    def test_translated_content_queryset_operations(self):
        """Test common queryset operations on TranslatedContent."""
        # Create multiple contents
        contents = []
        for i in range(3):
            content = TranslatedContent.objects.create(
                title=f"쿼리셋 테스트 {i}",
                slug=f"queryset-test-{i}",
                description=f"쿼리셋 테스트 {i} 설명",
                model_name=f"queryset-model-{i}",
                source_url=f"https://example.com/queryset-{i}",
            )
            contents.append(content)

        # Test filtering
        all_contents = TranslatedContent.objects.all()
        assert all_contents.count() >= 3

        # Test ordering
        ordered_contents = TranslatedContent.objects.order_by("title")
        assert ordered_contents.count() >= 3

        # Test filtering by model_name
        model_contents = TranslatedContent.objects.filter(
            model_name__startswith="queryset-model"
        )
        assert model_contents.count() == 3

        # Test search functionality
        search_contents = TranslatedContent.objects.filter(title__icontains="쿼리셋")
        assert search_contents.count() == 3

    def test_translated_content_str_representation(self):
        """Test string representation of TranslatedContent model."""
        content = TranslatedContent.objects.create(
            title="문자열 표현 테스트",
            slug="string-representation",
            description="문자열 표현 테스트 설명",
            model_name="string-model",
            source_url="https://example.com/string-test",
        )

        # TranslatedContent model doesn't have __str__ method defined,
        # so it should use the default Django model string representation
        str_repr = str(content)
        assert "TranslatedContent" in str_repr or str(content.id) in str_repr

    def test_translated_content_upload_path_function(self):
        """Test the upload path generation function."""
        from .models import translated_item_upload_path
        from datetime import datetime

        content = TranslatedContent.objects.create(
            title="업로드 경로 테스트",
            slug="upload-path-test",
            description="업로드 경로 테스트 설명",
            model_name="upload-model",
            source_url="https://example.com/upload-test",
        )

        # Test upload path generation
        filename = "test-content.md"
        path = translated_item_upload_path(content, filename)

        now = datetime.now()
        expected_pattern = f"tr/{now.year}/{now.month:02d}/{content.id}-ko.md"

        assert path == expected_pattern

    @patch("curation.models.datetime")
    def test_translated_content_upload_path_with_mock_date(self, mock_datetime):
        """Test upload path generation with mocked datetime."""
        from .models import translated_item_upload_path
        from datetime import datetime

        # Mock datetime to return a specific date
        mock_now = datetime(2024, 3, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_now

        content = TranslatedContent.objects.create(
            title="목킹된 날짜 테스트",
            slug="mocked-date-test",
            description="목킹된 날짜 테스트 설명",
            model_name="mocked-model",
            source_url="https://example.com/mocked-test",
        )

        filename = "mocked-content.md"
        path = translated_item_upload_path(content, filename)

        expected_path = f"tr/2024/03/{content.id}-ko.md"
        assert path == expected_path

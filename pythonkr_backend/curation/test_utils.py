import pytest
from unittest.mock import patch, MagicMock, mock_open
from django.core.files.base import ContentFile
from django.test import TestCase

from .models import RSSItem, RSSFeed, TranslatedContent, LLMService, LLMUsage
from .utils import fetch_content_from_url, parse_contents, get_summary_from_url, translate_to_korean, categorize_summary
from .utils_trans import translate_rssitem


@pytest.mark.django_db
class TestUtilsFunctions:
    """Test cases for utility functions in utils.py."""

    @patch('httpx.get')
    def test_fetch_content_from_url_success(self, mock_get):
        """Test fetch_content_from_url with successful response."""
        mock_response = MagicMock()
        mock_response.text = "# Test Article\n\nThis is test content."
        mock_get.return_value = mock_response
        
        url = "https://example.com/test-article"
        result = fetch_content_from_url(url)
        
        assert result == "# Test Article\n\nThis is test content."
        mock_get.assert_called_once_with(f"https://r.jina.ai/{url}")

    @patch('httpx.get')
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
        
        assert header['Title'] == 'Test Article'
        assert header['URL Source'] == 'https://example.com/test'
        assert header['Author'] == 'Test Author'
        assert header['Published'] == '2024-01-15'
        assert markdown_body.strip().startswith('# Test Article')
        assert '## Section 1' in markdown_body

    def test_parse_contents_minimal_format(self):
        """Test parse_contents with minimal header."""
        contents = """Title: Simple Article

Markdown Content:
# Simple Article

Just some content."""
        
        header, markdown_body = parse_contents(contents)
        
        assert header['Title'] == 'Simple Article'
        assert len(header) == 1
        assert markdown_body.strip().startswith('# Simple Article')

    @patch('llm.get_model')
    def test_get_summary_from_url_success(self, mock_get_model):
        """Test get_summary_from_url with successful LLM response."""
        # Mock LLM model and response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "# 테스트 기사\n\n## 요약\n- 첫 번째 요점\n- 두 번째 요점\n- 세 번째 요점"
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model
        
        with patch('curation.utils.fetch_content_from_url') as mock_fetch:
            mock_fetch.return_value = "Test article content"
            
            result = get_summary_from_url("https://example.com/test")
            
            assert "테스트 기사" in result
            assert "요약" in result
            assert "요점" in result
            
            mock_fetch.assert_called_once_with("https://example.com/test")
            mock_model.prompt.assert_called_once()

    @patch('llm.get_model')
    @patch('curation.utils.GEMINI_API_KEY', 'test_key')
    def test_get_summary_from_url_with_api_key(self, mock_get_model):
        """Test that get_summary_from_url sets API key correctly."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Summary text"
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model
        
        with patch('curation.utils.fetch_content_from_url') as mock_fetch:
            mock_fetch.return_value = "Test content"
            get_summary_from_url("https://example.com/test")
            
            assert mock_model.key == 'test_key'

    @patch('llm.get_model')
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
        assert "translate" in call_args[1]['system'].lower()
        assert "korean" in call_args[1]['system'].lower()

    @patch('llm.get_model')
    def test_categorize_summary_success(self, mock_get_model):
        """Test categorize_summary with successful categorization."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Web Development, Large Language Models"
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model
        
        summary = "This article discusses building web applications using LLMs."
        categories = ['Web Development', 'Large Language Models', 'Data Science', 'Other']
        
        result = categorize_summary(summary, categories)
        
        assert result == "Web Development, Large Language Models"
        mock_model.prompt.assert_called_once()
        
        # Check that categories were included in prompt
        call_args = mock_model.prompt.call_args
        assert summary in call_args[0][0]
        system_prompt = call_args[1]['system']
        assert "'Web Development'" in system_prompt
        assert "'Large Language Models'" in system_prompt

    @patch('llm.get_model')
    def test_categorize_summary_other_category(self, mock_get_model):
        """Test categorize_summary returns 'Other' when no fit."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "Other"
        mock_model.prompt.return_value = mock_response
        mock_get_model.return_value = mock_model
        
        summary = "This article discusses cooking recipes."
        categories = ['Web Development', 'Data Science', 'Other']
        
        result = categorize_summary(summary, categories)
        
        assert result == "Other"


@pytest.mark.django_db
class TestUtilsTransFunctions:
    """Test cases for utility functions in utils_trans.py."""

    def setup_method(self):
        """Set up test data for each test method."""
        self.feed = RSSFeed.objects.create(
            name="Test Feed",
            url="https://example.com/feed.xml",
            is_active=True
        )
        
        # Create LLM service
        self.llm_service = LLMService.objects.create(
            provider='gemini',
            priority=1,
            is_active=True
        )

    @patch('curation.utils_trans.Agent')
    @patch.object(LLMService, 'get_llm_provider_model')
    def test_translate_rssitem_success(self, mock_get_provider, mock_agent_class):
        """Test translate_rssitem with successful translation."""
        # Create RSS item with crawled content
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status='completed'
        )
        
        # Mock crawled content file
        rss_item.crawled_content.name = "test_content.md"
        rss_item.save()
        
        # Create mock file content
        mock_content = "# Test Article\n\nThis is test content."
        
        # Mock LLM service response
        mock_get_provider.return_value = ('gemini', 'gemini-2.5-pro')
        
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
        with patch('builtins.open', mock_file):
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

    @patch.object(LLMService, 'get_llm_provider_model')
    def test_translate_rssitem_no_llm_service(self, mock_get_provider):
        """Test translate_rssitem when no LLM service is available."""
        mock_get_provider.return_value = (None, None)
        
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status='completed'
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
            crawling_status='completed'
        )
        
        with pytest.raises(ValueError) as exc_info:
            translate_rssitem(rss_item.id)
        
        assert "RSS item has no crawled content" in str(exc_info.value)

    @patch('curation.utils_trans.Agent')
    @patch.object(LLMService, 'get_llm_provider_model')
    def test_translate_rssitem_translation_error(self, mock_get_provider, mock_agent_class):
        """Test translate_rssitem when translation fails."""
        # Create RSS item with crawled content
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status='completed',
            translate_status='pending'
        )
        
        # Mock crawled content file
        rss_item.crawled_content.name = "test_content.md"
        rss_item.save()
        
        mock_content = "# Test Article\n\nThis is test content."
        
        mock_get_provider.return_value = ('gemini', 'gemini-2.5-pro')
        
        # Mock agent to raise exception
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_agent.run_sync.side_effect = Exception("Translation API error")
        
        mock_file = mock_open(read_data=mock_content)
        with patch('builtins.open', mock_file):
            with pytest.raises(Exception) as exc_info:
                translate_rssitem(rss_item.id)
            
            assert "Translation API error" in str(exc_info.value)
            
            # Check that RSS item status was updated
            rss_item.refresh_from_db()
            assert rss_item.crawling_status == 'failed'
            assert "Translation API error" in rss_item.translate_error_message

    def test_translate_rssitem_nonexistent_rss_item(self):
        """Test translate_rssitem with non-existent RSS item ID."""
        with pytest.raises(Exception):
            translate_rssitem(99999)

    @patch('curation.utils_trans.Agent')
    @patch.object(LLMService, 'get_llm_provider_model')
    def test_translate_rssitem_file_handling(self, mock_get_provider, mock_agent_class):
        """Test that translate_rssitem properly handles file operations."""
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",  
            crawling_status='completed'
        )
        
        # Mock crawled content file
        rss_item.crawled_content.name = "test_content.md"
        rss_item.save()
        
        mock_content = "# Test Article\n\nThis is test content."
        
        mock_get_provider.return_value = ('openai', 'gpt-4.1-2025-04-14')
        
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
        with patch('builtins.open', mock_file):
            result = translate_rssitem(rss_item.id)
            
            # Verify the result is saved to database
            assert TranslatedContent.objects.filter(source_rss_item=rss_item).exists()

    @patch('curation.utils_trans.Agent')  
    @patch.object(LLMService, 'get_llm_provider_model')
    def test_translate_rssitem_system_prompt(self, mock_get_provider, mock_agent_class):
        """Test that translate_rssitem uses correct system prompt."""
        rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status='completed'
        )
        
        # Mock crawled content file
        rss_item.crawled_content.name = "test_content.md"
        rss_item.save()
        
        mock_content = "# Test Article\n\nThis is test content."
        
        mock_get_provider.return_value = ('claude', 'claude-sonnet-4-0')
        
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
        mock_result.usage.return_value = MagicMock(request_tokens=10, response_tokens=20, total_tokens=30)
        
        mock_agent.run_sync.return_value = mock_result
        
        mock_file = mock_open(read_data=mock_content)
        with patch('builtins.open', mock_file):
            translate_rssitem(rss_item.id)
            
            # Check Agent was created with correct parameters
            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            
            assert call_args[0][0] == 'claude:claude-sonnet-4-0'  # model name
            assert 'korean' in call_args[1]['system_prompt'].lower()
            assert 'translate' in call_args[1]['system_prompt'].lower()
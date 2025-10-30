"""
Tests for copyright analysis functionality.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.core.files.base import ContentFile
from .models import RSSFeed, RSSItem, LLMService
from .utils_copyright import (
    CopyrightAnalysisResult,
    analyze_copyright,
    _get_default_copyright_result,
    _analyze_with_gemini,
    _analyze_with_other_llm,
    summarize_korean_content,
    analyze_content_for_copyright,
)


class CopyrightAnalysisTests(TestCase):
    """Test copyright analysis utilities."""

    def setUp(self):
        """Set up test data."""
        # Create test RSS feed and item
        self.feed = RSSFeed.objects.create(
            name="Test Feed",
            url="http://example.com/feed.xml",
            is_active=True
        )
        
        self.rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Test Article",
            link="http://example.com/article",
            description="Test description"
        )
        
        # Create test LLM service
        self.llm_service = LLMService.objects.create(
            provider="openai",
            priority=1,
            is_active=True
        )

    def test_default_copyright_result(self):
        """Test default copyright result creation."""
        result = _get_default_copyright_result("Test reason")
        
        self.assertEqual(result.license_type, "All Rights Reserved")
        self.assertFalse(result.is_translation_allowed)
        self.assertTrue(result.attribution_required)
        self.assertEqual(result.confidence_score, 0.0)
        self.assertIn("Test reason", result.reasoning)

    def test_copyright_analysis_result_validation(self):
        """Test CopyrightAnalysisResult model validation."""
        # Valid result
        result = CopyrightAnalysisResult(
            license_type="MIT",
            is_translation_allowed=True,
            attribution_required=True,
            confidence_score=0.8,
            reasoning="Clear MIT license found"
        )
        self.assertEqual(result.license_type, "MIT")
        self.assertTrue(result.is_translation_allowed)
        self.assertEqual(result.confidence_score, 0.8)

        # Invalid confidence score
        with self.assertRaises(ValueError):
            CopyrightAnalysisResult(
                license_type="MIT",
                is_translation_allowed=True,
                attribution_required=True,
                confidence_score=1.5,  # Invalid: > 1.0
                reasoning="Test"
            )

    @patch('curation.models.LLMService.get_llm_provider_model')
    def test_analyze_copyright_no_llm_service(self, mock_get_llm):
        """Test copyright analysis when no LLM service is available."""
        mock_get_llm.return_value = (None, None)
        
        result = analyze_copyright("Test content", "http://example.com")
        
        self.assertEqual(result.license_type, "All Rights Reserved")
        self.assertFalse(result.is_translation_allowed)
        self.assertEqual(result.confidence_score, 0.0)
        self.assertIn("No LLM service available", result.reasoning)

    @patch('curation.utils_copyright.Agent')
    @patch('curation.models.LLMService.get_llm_provider_model')
    @patch('curation.models.LLMUsage.objects.create')
    def test_analyze_copyright_success(self, mock_usage_create, mock_get_llm, mock_agent):
        """Test successful copyright analysis."""
        # Mock LLM service
        mock_get_llm.return_value = ("openai", "gpt-4")
        
        # Mock AI agent response
        mock_result = Mock()
        mock_result.output = CopyrightAnalysisResult(
            license_type="MIT",
            is_translation_allowed=True,
            attribution_required=True,
            confidence_score=0.9,
            reasoning="Clear MIT license statement found"
        )
        mock_result.usage.return_value = Mock(
            request_tokens=100,
            response_tokens=50,
            total_tokens=150
        )
        
        mock_agent_instance = Mock()
        mock_agent_instance.run_sync.return_value = mock_result
        mock_agent.return_value = mock_agent_instance
        
        # Run analysis
        result = analyze_copyright("MIT License content", "http://example.com")
        
        # Verify results
        self.assertEqual(result.license_type, "MIT")
        self.assertTrue(result.is_translation_allowed)
        self.assertEqual(result.confidence_score, 0.9)
        self.assertIn("MIT license", result.reasoning)
        
        # Verify LLM usage was recorded
        mock_usage_create.assert_called_once()

    @patch('curation.utils_copyright.Agent')
    @patch('curation.models.LLMService.get_llm_provider_model')
    def test_analyze_copyright_failure(self, mock_get_llm, mock_agent):
        """Test copyright analysis failure handling."""
        mock_get_llm.return_value = ("openai", "gpt-4")
        
        # Mock agent failure
        mock_agent_instance = Mock()
        mock_agent_instance.run_sync.side_effect = Exception("API Error")
        mock_agent.return_value = mock_agent_instance
        
        result = analyze_copyright("Test content", "http://example.com")
        
        # Should return default result
        self.assertEqual(result.license_type, "All Rights Reserved")
        self.assertFalse(result.is_translation_allowed)
        self.assertIn("Analysis failed", result.reasoning)

    @patch('curation.utils_copyright.Agent')
    @patch('curation.models.LLMService.get_llm_provider_model')
    def test_summarize_korean_content_success(self, mock_get_llm, mock_agent):
        """Test successful Korean content summarization."""
        mock_get_llm.return_value = ("openai", "gpt-4")
        
        # Mock AI agent response
        mock_result = Mock()
        mock_result.output = "파이썬은 프로그래밍 언어입니다."
        mock_result.usage.return_value = Mock(
            request_tokens=100,
            response_tokens=20,
            total_tokens=120
        )
        
        mock_agent_instance = Mock()
        mock_agent_instance.run_sync.return_value = mock_result
        mock_agent.return_value = mock_agent_instance
        
        result = summarize_korean_content("긴 한국어 텍스트 내용...")
        
        self.assertEqual(result, "파이썬은 프로그래밍 언어입니다.")

    @patch('curation.models.LLMService.get_llm_provider_model')
    def test_summarize_korean_content_no_llm(self, mock_get_llm):
        """Test Korean summarization when no LLM service available."""
        mock_get_llm.return_value = (None, None)
        
        result = summarize_korean_content("한국어 텍스트")
        
        self.assertIsNone(result)

    def test_analyze_content_for_copyright_missing_item(self):
        """Test copyright analysis for non-existent RSS item."""
        result = analyze_content_for_copyright(99999)
        
        self.assertIn('error', result)
        self.assertIn('not found', result['error'])

    def test_analyze_content_for_copyright_no_content(self):
        """Test copyright analysis for RSS item without crawled content."""
        result = analyze_content_for_copyright(self.rss_item.id)
        
        self.assertIn('error', result)
        self.assertIn('No crawled content', result['error'])

    @patch('curation.utils_language.detect_content_language')
    @patch('curation.utils_copyright.summarize_korean_content')
    def test_analyze_content_korean(self, mock_summarize, mock_detect_lang):
        """Test content analysis for Korean content."""
        # Add crawled content to RSS item
        content = "한국어 콘텐츠 내용입니다."
        content_file = ContentFile(content.encode('utf-8'))
        self.rss_item.crawled_content.save('test.md', content_file)
        
        # Mock language detection
        mock_detect_lang.return_value = {
            'language': 'ko',
            'is_korean': True,
            'is_foreign': False,
            'confidence': 0.9
        }
        
        # Mock summarization
        mock_summarize.return_value = "한국어 요약입니다."
        
        result = analyze_content_for_copyright(self.rss_item.id)
        
        self.assertIn('language_detection', result)
        self.assertIn('summary', result)
        self.assertEqual(result['summary'], "한국어 요약입니다.")
        
        # Verify RSS item was updated
        self.rss_item.refresh_from_db()
        self.assertEqual(self.rss_item.language, 'ko')
        self.assertEqual(self.rss_item.summary, "한국어 요약입니다.")

    @patch('curation.utils_language.detect_content_language')
    @patch('curation.utils_copyright.analyze_copyright')
    def test_analyze_content_foreign(self, mock_analyze, mock_detect_lang):
        """Test content analysis for foreign content."""
        # Add crawled content to RSS item
        content = "English content here."
        content_file = ContentFile(content.encode('utf-8'))
        self.rss_item.crawled_content.save('test.md', content_file)
        
        # Mock language detection
        mock_detect_lang.return_value = {
            'language': 'en',
            'is_korean': False,
            'is_foreign': True,
            'confidence': 0.9
        }
        
        # Mock copyright analysis
        mock_analyze.return_value = CopyrightAnalysisResult(
            license_type="MIT",
            is_translation_allowed=True,
            attribution_required=True,
            confidence_score=0.8,
            reasoning="MIT license found"
        )
        
        result = analyze_content_for_copyright(self.rss_item.id)
        
        self.assertIn('language_detection', result)
        self.assertIn('copyright_analysis', result)
        self.assertEqual(result['copyright_analysis']['license_type'], "MIT")
        
        # Verify RSS item was updated
        self.rss_item.refresh_from_db()
        self.assertEqual(self.rss_item.language, 'en')
        self.assertEqual(self.rss_item.license_type, "MIT")
        self.assertTrue(self.rss_item.is_translation_allowed)

    # ========== New Gemini-related Tests ==========

    @patch('curation.utils_copyright.GEMINI_AVAILABLE', False)
    def test_analyze_with_gemini_unavailable(self):
        """Test Gemini analysis when library is not available."""
        result = _analyze_with_gemini("http://example.com")
        self.assertIsNone(result)

    @patch('curation.utils_copyright.GEMINI_AVAILABLE', True)
    @patch.dict('os.environ', {}, clear=True)
    def test_analyze_with_gemini_no_api_key(self):
        """Test Gemini analysis when API key is not set."""
        result = _analyze_with_gemini("http://example.com")
        self.assertIsNone(result)

    def test_analyze_with_gemini_mock_success(self):
        """Test successful Gemini copyright analysis using mock."""
        with patch('curation.utils_copyright.GEMINI_AVAILABLE', True), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}), \
             patch('curation.utils_copyright.genai') as mock_genai:
            
            # Mock Gemini model and response
            mock_model = Mock()
            mock_response = Mock()
            mock_response.text = '{"license_type": "MIT", "is_translation_allowed": true, "attribution_required": true, "confidence_score": 0.9, "reasoning": "Clear MIT license found", "copyright_notice": "", "license_url": ""}'
            
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            result = _analyze_with_gemini("http://example.com/mit-project")
            
            # Verify results
            self.assertIsNotNone(result)
            self.assertEqual(result.license_type, "MIT")
            self.assertTrue(result.is_translation_allowed)
            self.assertTrue(result.attribution_required)
            self.assertEqual(result.confidence_score, 0.9)
            self.assertIn("MIT license", result.reasoning)

    def test_analyze_with_gemini_mock_failure(self):
        """Test Gemini analysis failure handling."""
        with patch('curation.utils_copyright.GEMINI_AVAILABLE', True), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}), \
             patch('curation.utils_copyright.genai') as mock_genai:
            
            mock_model = Mock()
            mock_model.generate_content.side_effect = Exception("API Error")
            mock_genai.GenerativeModel.return_value = mock_model
            
            result = _analyze_with_gemini("http://example.com")
            
            self.assertIsNone(result)

    def test_analyze_with_gemini_mock_invalid_json(self):
        """Test Gemini analysis with invalid JSON response."""
        with patch('curation.utils_copyright.GEMINI_AVAILABLE', True), \
             patch.dict('os.environ', {'GEMINI_API_KEY': 'test-key'}), \
             patch('curation.utils_copyright.genai') as mock_genai:
            
            mock_model = Mock()
            mock_response = Mock()
            mock_response.text = 'Invalid JSON response'
            
            mock_model.generate_content.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model
            
            result = _analyze_with_gemini("http://example.com")
            
            self.assertIsNone(result)

    def test_analyze_with_other_llm_success(self):
        """Test successful analysis with other LLM providers."""
        with patch('curation.models.LLMService.get_llm_provider_model') as mock_get_llm, \
             patch('curation.utils_copyright.Agent') as mock_agent, \
             patch('curation.models.LLMUsage.objects.create') as mock_usage:
            
            # Mock LLM service
            mock_get_llm.return_value = ("openai", "gpt-4")
            
            # Mock agent response
            mock_result = Mock()
            mock_result.output = CopyrightAnalysisResult(
                license_type="Apache-2.0",
                is_translation_allowed=True,
                attribution_required=True,
                confidence_score=0.8,
                reasoning="Apache 2.0 license detected"
            )
            mock_result.usage.return_value = Mock(
                request_tokens=150,
                response_tokens=75,
                total_tokens=225
            )
            
            mock_agent_instance = Mock()
            mock_agent_instance.run_sync.return_value = mock_result
            mock_agent.return_value = mock_agent_instance
            
            result = _analyze_with_other_llm("Apache License content", "http://example.com")
            
            self.assertEqual(result.license_type, "Apache-2.0")
            self.assertTrue(result.is_translation_allowed)
            self.assertEqual(result.confidence_score, 0.8)
            mock_usage.assert_called_once()

    def test_analyze_with_other_llm_no_service(self):
        """Test other LLM analysis when no service is available."""
        with patch('curation.models.LLMService.get_llm_provider_model') as mock_get_llm:
            mock_get_llm.return_value = (None, None)
            
            result = _analyze_with_other_llm("content", "http://example.com")
            
            self.assertEqual(result.license_type, "All Rights Reserved")
            self.assertFalse(result.is_translation_allowed)
            self.assertIn("No LLM service available", result.reasoning)

    def test_analyze_with_other_llm_failure(self):
        """Test other LLM analysis failure handling."""
        with patch('curation.models.LLMService.get_llm_provider_model') as mock_get_llm, \
             patch('curation.utils_copyright.Agent') as mock_agent:
            
            mock_get_llm.return_value = ("openai", "gpt-4")
            
            mock_agent_instance = Mock()
            mock_agent_instance.run_sync.side_effect = Exception("LLM API Error")
            mock_agent.return_value = mock_agent_instance
            
            result = _analyze_with_other_llm("content", "http://example.com")
            
            self.assertEqual(result.license_type, "All Rights Reserved")
            self.assertIn("Analysis failed", result.reasoning)

    # ========== Integration Tests ==========

    @patch('curation.utils_copyright._analyze_with_gemini')
    def test_analyze_copyright_gemini_first_success(self, mock_gemini):
        """Test that analyze_copyright tries Gemini first when available."""
        mock_gemini.return_value = CopyrightAnalysisResult(
            license_type="CC BY 4.0",
            is_translation_allowed=True,
            attribution_required=True,
            confidence_score=0.95,
            reasoning="Creative Commons license clearly stated"
        )
        
        result = analyze_copyright("test content", "http://example.com")
        
        # Should use Gemini result
        self.assertEqual(result.license_type, "CC BY 4.0")
        self.assertTrue(result.is_translation_allowed)
        self.assertEqual(result.confidence_score, 0.95)
        
        # Verify Gemini was called
        mock_gemini.assert_called_once_with("http://example.com")

    @patch('curation.utils_copyright._analyze_with_other_llm')
    @patch('curation.utils_copyright._analyze_with_gemini')
    def test_analyze_copyright_fallback_to_other_llm(self, mock_gemini, mock_other_llm):
        """Test fallback to other LLM when Gemini fails."""
        # Gemini returns None (failed)
        mock_gemini.return_value = None
        
        # Other LLM succeeds
        mock_other_llm.return_value = CopyrightAnalysisResult(
            license_type="GPL-3.0",
            is_translation_allowed=True,
            attribution_required=True,
            confidence_score=0.7,
            reasoning="GPL license found in header"
        )
        
        result = analyze_copyright("GPL content", "http://example.com")
        
        # Should use fallback result
        self.assertEqual(result.license_type, "GPL-3.0")
        self.assertEqual(result.confidence_score, 0.7)
        
        # Verify both methods were called
        mock_gemini.assert_called_once_with("http://example.com")
        mock_other_llm.assert_called_once_with("GPL content", "http://example.com")

    @patch('curation.utils_copyright._analyze_with_other_llm')
    @patch('curation.utils_copyright._analyze_with_gemini')
    def test_analyze_copyright_both_fail(self, mock_gemini, mock_other_llm):
        """Test when both Gemini and other LLM fail."""
        mock_gemini.return_value = None
        mock_other_llm.return_value = _get_default_copyright_result("All methods failed")
        
        result = analyze_copyright("content", "http://example.com")
        
        # Should get default conservative result
        self.assertEqual(result.license_type, "All Rights Reserved")
        self.assertFalse(result.is_translation_allowed)
        self.assertEqual(result.confidence_score, 0.0)


if __name__ == '__main__':
    pytest.main([__file__])
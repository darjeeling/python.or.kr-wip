"""
Tests for language detection functionality.
"""

import pytest
from django.test import TestCase
from .utils_language import (
    detect_language,
    clean_text_for_detection,
    is_korean_content,
    is_foreign_content,
    detect_content_language,
    get_language_display_name,
)


class LanguageDetectionTests(TestCase):
    """Test language detection utilities."""

    def test_detect_korean_content(self):
        """Test Korean content detection."""
        korean_text = """
        파이썬은 간결하고 읽기 쉬운 프로그래밍 언어입니다. 
        데이터 분석, 웹 개발, 인공지능 등 다양한 분야에서 사용됩니다.
        """
        lang, confidence = detect_language(korean_text)
        self.assertEqual(lang, 'ko')
        self.assertGreater(confidence, 0.7)

    def test_detect_english_content(self):
        """Test English content detection."""
        english_text = """
        Python is a high-level, interpreted programming language with 
        dynamic semantics. Its high-level built-in data structures, 
        combined with dynamic typing and dynamic binding, make it very 
        attractive for Rapid Application Development.
        """
        lang, confidence = detect_language(english_text)
        self.assertEqual(lang, 'en')
        self.assertGreater(confidence, 0.7)

    def test_detect_japanese_content(self):
        """Test Japanese content detection."""
        japanese_text = """
        Pythonは、コードの可読性を重視して設計されたプログラミング言語です。
        シンプルで学習しやすく、様々な分野で広く使用されています。
        """
        lang, confidence = detect_language(japanese_text)
        self.assertEqual(lang, 'ja')
        self.assertGreater(confidence, 0.7)

    def test_short_text_fallback(self):
        """Test fallback for text that's too short."""
        short_text = "Hello"
        lang, confidence = detect_language(short_text)
        self.assertEqual(lang, 'en')  # Default fallback
        self.assertEqual(confidence, 0.0)

    def test_clean_text_for_detection(self):
        """Test text cleaning functionality."""
        markdown_text = """
        # Header
        
        This is a **bold** text with `inline code` and [link](http://example.com).
        
        ```python
        def hello():
            print("Hello World")
        ```
        
        Contact: user@example.com
        """
        
        cleaned = clean_text_for_detection(markdown_text)
        
        # Should remove markdown formatting
        self.assertNotIn('**', cleaned)
        self.assertNotIn('`', cleaned)
        self.assertNotIn('[', cleaned)
        self.assertNotIn('http://example.com', cleaned)
        self.assertNotIn('user@example.com', cleaned)
        self.assertNotIn('def hello():', cleaned)

    def test_is_korean_content(self):
        """Test Korean content identification."""
        self.assertTrue(is_korean_content('ko', 0.8))
        self.assertFalse(is_korean_content('ko', 0.5))  # Low confidence
        self.assertFalse(is_korean_content('en', 0.9))  # Wrong language

    def test_is_foreign_content(self):
        """Test foreign content identification."""
        self.assertTrue(is_foreign_content('en', 0.8))
        self.assertTrue(is_foreign_content('ja', 0.8))
        self.assertFalse(is_foreign_content('ko', 0.8))  # Korean
        self.assertFalse(is_foreign_content('en', 0.5))  # Low confidence

    def test_get_language_display_name(self):
        """Test language display name functionality."""
        self.assertEqual(get_language_display_name('ko'), 'Korean')
        self.assertEqual(get_language_display_name('en'), 'English')
        self.assertEqual(get_language_display_name('ja'), 'Japanese')
        self.assertEqual(get_language_display_name('unknown'), 'Unknown (unknown)')

    def test_comprehensive_detection(self):
        """Test comprehensive language detection with metadata."""
        korean_text = """
        파이썬 프로그래밍 언어는 매우 인기가 높습니다. 
        간결하고 읽기 쉬운 문법을 가지고 있어서 초보자들이 배우기 쉽습니다.
        데이터 분석, 웹 개발, 인공지능, 자동화 등 다양한 분야에서 사용됩니다.
        """
        result = detect_content_language(korean_text)
        
        self.assertEqual(result['language'], 'ko')
        self.assertGreater(result['confidence'], 0.7)
        self.assertEqual(result['display_name'], 'Korean')
        self.assertTrue(result['is_korean'])
        self.assertFalse(result['is_foreign'])
        self.assertTrue(result['is_supported'])
        self.assertTrue(result['meets_threshold'])

    def test_mixed_content_detection(self):
        """Test detection with mixed language content."""
        mixed_text = """
        Python programming language 파이썬 프로그래밍
        This text contains both English and Korean 한국어와 영어가 섞여있습니다.
        """
        lang, confidence = detect_language(mixed_text)
        # Should detect the dominant language
        self.assertIn(lang, ['ko', 'en'])
        self.assertGreater(confidence, 0.0)


if __name__ == '__main__':
    pytest.main([__file__])
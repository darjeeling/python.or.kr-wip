"""
Language detection utilities for content processing.

This module provides language detection functionality using the langdetect library,
with support for Korean, English, Japanese, and other languages.
"""

import logging
from typing import Optional, Tuple
from langdetect import detect, detect_langs, LangDetectException

logger = logging.getLogger(__name__)

# Supported languages with confidence thresholds
SUPPORTED_LANGUAGES = {
    'ko': {'name': 'Korean', 'min_confidence': 0.7},
    'en': {'name': 'English', 'min_confidence': 0.7},
    'ja': {'name': 'Japanese', 'min_confidence': 0.7},
    'zh': {'name': 'Chinese', 'min_confidence': 0.7},
    'es': {'name': 'Spanish', 'min_confidence': 0.7},
    'fr': {'name': 'French', 'min_confidence': 0.7},
    'de': {'name': 'German', 'min_confidence': 0.7},
}

# Fallback language for detection failures
DEFAULT_LANGUAGE = 'en'


def detect_language(text: str, min_length: int = 50) -> Tuple[str, float]:
    """
    Detect the language of a given text.
    
    Args:
        text: The text to analyze
        min_length: Minimum text length required for detection (default: 50)
        
    Returns:
        Tuple of (language_code, confidence_score)
        Returns (DEFAULT_LANGUAGE, 0.0) if detection fails
    """
    if not text or len(text.strip()) < min_length:
        logger.warning(f"Text too short for language detection (length: {len(text)})")
        return DEFAULT_LANGUAGE, 0.0
    
    # Clean text for better detection
    clean_text = clean_text_for_detection(text)
    
    try:
        # Get detailed language detection results
        lang_probs = detect_langs(clean_text)
        
        if not lang_probs:
            logger.warning("No language detection results returned")
            return DEFAULT_LANGUAGE, 0.0
            
        # Get the most probable language
        best_lang = lang_probs[0]
        language_code = best_lang.lang
        confidence = best_lang.prob
        
        # Check if language is supported and meets confidence threshold
        if language_code in SUPPORTED_LANGUAGES:
            min_confidence = SUPPORTED_LANGUAGES[language_code]['min_confidence']
            if confidence >= min_confidence:
                logger.info(f"Detected language: {language_code} (confidence: {confidence:.3f})")
                return language_code, confidence
            else:
                logger.warning(
                    f"Low confidence for {language_code}: {confidence:.3f} "
                    f"(min required: {min_confidence})"
                )
        else:
            logger.info(f"Unsupported language detected: {language_code} (confidence: {confidence:.3f})")
        
        # Return best guess even if not supported or low confidence
        return language_code, confidence
        
    except LangDetectException as e:
        logger.error(f"Language detection failed: {e}")
        return DEFAULT_LANGUAGE, 0.0
    except Exception as e:
        logger.error(f"Unexpected error in language detection: {e}")
        return DEFAULT_LANGUAGE, 0.0


def clean_text_for_detection(text: str) -> str:
    """
    Clean text to improve language detection accuracy.
    
    Args:
        text: Raw text content
        
    Returns:
        Cleaned text suitable for language detection
    """
    import re
    
    # Remove markdown formatting
    text = re.sub(r'```[\s\S]*?```', '', text)  # Code blocks
    text = re.sub(r'`[^`]*`', '', text)  # Inline code
    text = re.sub(r'#{1,6}\s', '', text)  # Headers
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Links
    text = re.sub(r'\*{1,2}([^\*]+)\*{1,2}', r'\1', text)  # Bold/italic
    
    # Remove URLs
    text = re.sub(r'https?://[^\s]+', '', text)
    
    # Remove email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def is_korean_content(language_code: str, confidence: float) -> bool:
    """
    Check if content is Korean based on detection results.
    
    Args:
        language_code: Detected language code
        confidence: Detection confidence score
        
    Returns:
        True if content is considered Korean
    """
    return (
        language_code == 'ko' and 
        confidence >= SUPPORTED_LANGUAGES['ko']['min_confidence']
    )


def is_foreign_content(language_code: str, confidence: float) -> bool:
    """
    Check if content is foreign (non-Korean) based on detection results.
    
    Args:
        language_code: Detected language code
        confidence: Detection confidence score
        
    Returns:
        True if content is considered foreign
    """
    return (
        language_code != 'ko' and 
        language_code in SUPPORTED_LANGUAGES and 
        confidence >= SUPPORTED_LANGUAGES[language_code]['min_confidence']
    )


def get_language_display_name(language_code: str) -> str:
    """
    Get human-readable display name for a language code.
    
    Args:
        language_code: Language code (e.g., 'ko', 'en')
        
    Returns:
        Display name for the language
    """
    if language_code in SUPPORTED_LANGUAGES:
        return SUPPORTED_LANGUAGES[language_code]['name']
    return f"Unknown ({language_code})"


def detect_content_language(content: str) -> dict:
    """
    Comprehensive language detection with metadata.
    
    Args:
        content: Text content to analyze
        
    Returns:
        Dictionary with detection results:
        {
            'language': str,           # Language code
            'confidence': float,       # Confidence score
            'display_name': str,       # Human-readable name
            'is_korean': bool,         # True if Korean
            'is_foreign': bool,        # True if foreign
            'is_supported': bool,      # True if supported language
            'meets_threshold': bool    # True if confidence meets threshold
        }
    """
    language_code, confidence = detect_language(content)
    
    return {
        'language': language_code,
        'confidence': confidence,
        'display_name': get_language_display_name(language_code),
        'is_korean': is_korean_content(language_code, confidence),
        'is_foreign': is_foreign_content(language_code, confidence),
        'is_supported': language_code in SUPPORTED_LANGUAGES,
        'meets_threshold': (
            language_code in SUPPORTED_LANGUAGES and 
            confidence >= SUPPORTED_LANGUAGES[language_code]['min_confidence']
        )
    }
"""
Copyright analysis utilities for content processing.

This module provides AI-powered copyright analysis using LLM services
to determine licensing status and translation permissions for foreign content.
"""

import logging
import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from pydantic_ai import Agent

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)


class CopyrightAnalysisResult(BaseModel):
    """Structured result from copyright analysis."""
    license_type: str = Field(
        description="The identified license type (e.g., 'MIT', 'CC BY-SA 4.0', 'All Rights Reserved', 'Unknown')"
    )
    is_translation_allowed: bool = Field(
        description="Whether translation is permitted based on the license and content"
    )
    attribution_required: bool = Field(
        description="Whether attribution to the original author/source is required"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="Confidence level in the analysis (0.0 to 1.0)"
    )
    reasoning: str = Field(
        description="Detailed explanation of the analysis and decision-making process"
    )
    copyright_notice: str = Field(
        default="",
        description="Any specific copyright notice found in the content"
    )
    license_url: str = Field(
        default="",
        description="URL to the license text if found"
    )


# System prompt for copyright analysis
COPYRIGHT_ANALYSIS_PROMPT = """
You are a legal AI assistant specialized in copyright and licensing analysis. 

Your task is to analyze web content and determine:
1. The copyright license type
2. Whether translation is permitted
3. Whether attribution is required
4. Your confidence in the analysis

IMPORTANT GUIDELINES:
- Be conservative: when in doubt, assume stricter restrictions
- Look for explicit license statements, copyright notices, and terms of use
- Consider common license types: MIT, Apache, GPL, CC (Creative Commons), All Rights Reserved
- If no clear license is found, assume "All Rights Reserved" and no translation permission
- Provide detailed reasoning for your analysis
- Score confidence based on clarity of licensing information found

ANALYSIS CRITERIA:
- Explicit license statements (highest confidence)
- Copyright notices in footer/header
- Terms of service or usage policies
- Creative Commons indicators
- Open source project indicators
- Educational/non-profit context
- Blog/personal content (usually All Rights Reserved unless stated)

TRANSLATION PERMISSION RULES:
- MIT, Apache, BSD: Usually allows translation with attribution
- GPL: Allows translation but derivative work must be GPL
- CC BY: Allows translation with attribution
- CC BY-SA: Allows translation with attribution, share-alike
- CC BY-NC: Allows translation with attribution, non-commercial only
- All Rights Reserved: No translation without permission
- Unknown/Unclear: Assume no permission (be conservative)

ANALYSIS FOCUS:
When analyzing content, focus on finding:
1. Any explicit license statements
2. Copyright notices
3. Terms of use or usage policies
4. Creative Commons indicators
5. Attribution requirements

Return your analysis with high confidence only when licensing is clearly stated.
Be thorough but concise in your analysis.
"""


def _analyze_with_gemini(url: str) -> Optional[CopyrightAnalysisResult]:
    """
    Analyze copyright using Gemini's URL direct processing capability.
    
    Args:
        url: The URL to analyze directly
        
    Returns:
        CopyrightAnalysisResult or None if failed
    """
    if not GEMINI_AVAILABLE:
        return None
        
    # Check for Gemini API key
    gemini_api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not gemini_api_key:
        logger.warning("Gemini API key not found, falling back to other LLM providers")
        return None
    
    try:
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        
        # Create model with JSON response format
        model = genai.GenerativeModel(
            'gemini-2.5-lite',
            generation_config={"response_mime_type": "application/json"},
            system_instruction=f"Analyze the provided URL's web content for copyright information and return JSON response matching this schema: {CopyrightAnalysisResult.model_json_schema()}"
        )
        
        # Create prompt for URL analysis
        prompt = f"""
        Analyze this webpage's copyright and licensing status: {url}
        
        Determine:
        1. License type (look for explicit licenses, copyright notices, terms of use)
        2. Whether translation is permitted for Korean blog publication
        3. Whether attribution is required
        4. Your confidence in the analysis
        5. Detailed reasoning for your decision
        
        Be conservative: assume stricter restrictions when in doubt.
        """
        
        # Generate response
        response = model.generate_content(prompt)
        
        # Parse JSON response
        copyright_result = CopyrightAnalysisResult.model_validate_json(response.text)
        
        logger.info(f"Gemini copyright analysis completed for {url}: {copyright_result.license_type}")
        return copyright_result
        
    except Exception as e:
        logger.error(f"Gemini copyright analysis failed for {url}: {e}")
        return None


def _analyze_with_other_llm(content: str, url: str) -> CopyrightAnalysisResult:
    """
    Analyze copyright using other LLM providers (fallback method).
    
    Args:
        content: The full text content to analyze
        url: The source URL for additional context
        
    Returns:
        CopyrightAnalysisResult with analysis findings
    """
    from .models import LLMService, LLMUsage
    
    # Get available LLM provider
    provider, model = LLMService.get_llm_provider_model()
    if not provider or not model:
        logger.error("No available LLM service for copyright analysis")
        return _get_default_copyright_result("No LLM service available")
    
    model_name = f"{provider}:{model}"
    
    # Prepare content for analysis
    analysis_prompt = f"""URL: {url}

Content to analyze:
{content[:4000]}"""
    
    try:
        # Create AI agent for copyright analysis
        agent = Agent(
            model_name,
            output_type=CopyrightAnalysisResult,
            system_prompt=COPYRIGHT_ANALYSIS_PROMPT,
        )
        
        # Run analysis
        result = agent.run_sync(analysis_prompt)
        
        # Log LLM usage
        usage = result.usage()
        LLMUsage.objects.create(
            model_name=model_name,
            input_tokens=usage.request_tokens,
            output_tokens=usage.response_tokens,
            total_tokens=usage.total_tokens,
        )
        
        logger.info(f"Copyright analysis completed for {url}: {result.output.license_type}")
        return result.output
        
    except Exception as e:
        logger.error(f"Copyright analysis failed for {url}: {e}")
        return _get_default_copyright_result(f"Analysis failed: {str(e)}")


def analyze_copyright(content: str, url: str) -> CopyrightAnalysisResult:
    """
    Analyze copyright and licensing status of content using AI.
    
    First attempts to use Gemini's URL direct processing, then falls back to other LLM providers.
    
    Args:
        content: The full text content to analyze
        url: The source URL for additional context
        
    Returns:
        CopyrightAnalysisResult with analysis findings
    """
    # Try Gemini first for URL direct analysis
    gemini_result = _analyze_with_gemini(url)
    if gemini_result:
        return gemini_result
    
    # Fall back to other LLM providers with content
    return _analyze_with_other_llm(content, url)


def _get_default_copyright_result(reason: str) -> CopyrightAnalysisResult:
    """
    Get default conservative copyright result when analysis fails.
    
    Args:
        reason: Reason for using default result
        
    Returns:
        Conservative CopyrightAnalysisResult
    """
    return CopyrightAnalysisResult(
        license_type="All Rights Reserved",
        is_translation_allowed=False,
        attribution_required=True,
        confidence_score=0.0,
        reasoning=f"Default conservative result used. {reason}",
        copyright_notice="",
        license_url=""
    )


def summarize_korean_content(content: str) -> Optional[str]:
    """
    Generate AI summary for Korean content.
    
    Args:
        content: Korean text content to summarize
        
    Returns:
        Generated summary or None if failed
    """
    from .models import LLMService, LLMUsage
    
    # Get available LLM provider
    provider, model = LLMService.get_llm_provider_model()
    if not provider or not model:
        logger.error("No available LLM service for content summarization")
        return None
    
    model_name = f"{provider}:{model}"
    
    # Prepare summarization prompt
    summary_prompt = f"""
    다음 한국어 콘텐츠를 간결하고 정확하게 요약해주세요:

    {content[:3000]}  # Limit content to avoid token limits
    
    요약 시 다음 사항을 고려해주세요:
    1. 핵심 내용과 주요 포인트 포함
    2. 2-3문장으로 간결하게 작성
    3. 기술적 내용의 경우 주요 개념과 결론 포함
    4. 원문의 톤과 맥락 유지
    """
    
    try:
        # Create AI agent for summarization
        agent = Agent(
            model_name,
            output_type=str,
            system_prompt="You are a helpful AI assistant that creates concise, accurate summaries of Korean content."
        )
        
        # Generate summary
        result = agent.run_sync(summary_prompt)
        
        # Log LLM usage
        usage = result.usage()
        LLMUsage.objects.create(
            model_name=model_name,
            input_tokens=usage.request_tokens,
            output_tokens=usage.response_tokens,
            total_tokens=usage.total_tokens,
        )
        
        logger.info("Korean content summary generated successfully")
        return result.output
        
    except Exception as e:
        logger.error(f"Korean content summarization failed: {e}")
        return None


def analyze_content_for_copyright(rss_item_id: int) -> Dict[str, Any]:
    """
    Comprehensive copyright analysis for an RSSItem.
    
    Args:
        rss_item_id: ID of the RSSItem to analyze
        
    Returns:
        Dictionary with analysis results and any errors
    """
    from .models import RSSItem
    from .utils_language import detect_content_language
    
    try:
        rss_item = RSSItem.objects.get(id=rss_item_id)
    except RSSItem.DoesNotExist:
        return {'error': f'RSSItem {rss_item_id} not found'}
    
    # Read crawled content
    if not rss_item.crawled_content:
        return {'error': 'No crawled content available'}
    
    try:
        with rss_item.crawled_content.open('r') as f:
            content = f.read()
    except Exception as e:
        return {'error': f'Failed to read content: {e}'}
    
    # Detect language
    lang_result = detect_content_language(content)
    
    # Update language field
    rss_item.language = lang_result['language']
    
    result = {
        'language_detection': lang_result,
        'copyright_analysis': None,
        'summary': None
    }
    
    # Process based on language
    if lang_result['is_korean']:
        # Korean content: generate summary
        summary = summarize_korean_content(content)
        if summary:
            rss_item.summary = summary
            result['summary'] = summary
            logger.info(f"Summary generated for Korean content: {rss_item.title}")
        
    elif lang_result['is_foreign']:
        # Foreign content: copyright analysis
        copyright_result = analyze_copyright(content, rss_item.link)
        
        # Update RSSItem with analysis results
        rss_item.license_type = copyright_result.license_type
        rss_item.is_translation_allowed = copyright_result.is_translation_allowed
        rss_item.attribution_required = copyright_result.attribution_required
        rss_item.confidence_score = copyright_result.confidence_score
        rss_item.reasoning = copyright_result.reasoning
        
        result['copyright_analysis'] = {
            'license_type': copyright_result.license_type,
            'is_translation_allowed': copyright_result.is_translation_allowed,
            'attribution_required': copyright_result.attribution_required,
            'confidence_score': copyright_result.confidence_score,
            'reasoning': copyright_result.reasoning,
            'copyright_notice': copyright_result.copyright_notice,
            'license_url': copyright_result.license_url
        }
        
        logger.info(f"Copyright analysis completed for: {rss_item.title}")
    
    else:
        # Unsupported language or low confidence
        logger.warning(f"Unsupported or low-confidence language detection: {lang_result}")
    
    # Save updated RSSItem
    rss_item.save()
    
    return result
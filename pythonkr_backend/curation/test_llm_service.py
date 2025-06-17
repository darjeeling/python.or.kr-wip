import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase
import pytz

from .models import LLMService, LLMUsage


@pytest.mark.django_db
class TestLLMService:
    """Test cases for LLMService model and its methods."""

    def setup_method(self):
        """Set up test data for each test method."""
        # Create test LLM services with different priorities
        self.gemini_service = LLMService.objects.create(
            provider='gemini',
            priority=1,
            is_active=True
        )
        self.openai_service = LLMService.objects.create(
            provider='openai',
            priority=2,
            is_active=True
        )
        self.claude_service = LLMService.objects.create(
            provider='claude',
            priority=3,
            is_active=True
        )

    def test_string_representation(self):
        """Test __str__ method of LLMService."""
        assert str(self.gemini_service) == "Gemini (Priority: 1)"
        assert str(self.openai_service) == "OpenAI (Priority: 2)"

    def test_get_llm_provider_model_no_active_services(self):
        """Test get_llm_provider_model when no services are active."""
        LLMService.objects.update(is_active=False)
        
        provider, model = LLMService.get_llm_provider_model()
        
        assert provider is None
        assert model is None

    @patch.object(LLMService, '_get_available_models_for_provider')
    def test_get_llm_provider_model_priority_order(self, mock_get_available):
        """Test that get_llm_provider_model respects priority order."""
        # Mock gemini (priority 1) to have no available models
        # Mock openai (priority 2) to have available models
        def side_effect(provider, config):
            if provider == 'gemini':
                return []  # No available models
            elif provider == 'openai':
                return ['gpt-4.1-2025-04-14']
            elif provider == 'claude':
                return ['claude-sonnet-4-0']
            return []
        
        mock_get_available.side_effect = side_effect
        
        provider, model = LLMService.get_llm_provider_model()
        
        assert provider == 'openai'
        assert model == 'gpt-4.1-2025-04-14'

    @patch.object(LLMService, '_get_available_models_for_provider')
    def test_get_llm_provider_model_fallback_to_claude(self, mock_get_available):
        """Test fallback to Claude when other providers are unavailable."""
        def side_effect(provider, config):
            if provider in ['gemini', 'openai']:
                return []  # No available models
            elif provider == 'claude':
                return ['claude-sonnet-4-0']
            return []
        
        mock_get_available.side_effect = side_effect
        
        provider, model = LLMService.get_llm_provider_model()
        
        assert provider == 'claude'
        assert model == 'claude-sonnet-4-0'

    def test_get_available_models_for_provider_gemini_no_usage(self):
        """Test _get_available_models_for_provider for Gemini with no usage."""
        model_configs = {
            'google-gla:gemini-2.5-pro-preview-06-05': {
                'daily_requests': 25,
                'daily_tokens': 1000000,
                'provider': 'gemini'
            },
            'google-gla:gemini-2.5-flash-preview-05-20': {
                'daily_requests': 500,
                'provider': 'gemini'
            }
        }
        
        available_models = LLMService._get_available_models_for_provider('gemini', model_configs)
        
        expected_models = ['gemini-2.5-pro-preview-06-05', 'gemini-2.5-flash-preview-05-20']
        assert set(available_models) == set(expected_models)

    def test_get_available_models_for_provider_gemini_with_usage(self):
        """Test _get_available_models_for_provider for Gemini with existing usage."""
        # Create usage that exceeds daily request limit for pro model
        pacific_tz = pytz.timezone('US/Pacific')
        now_pacific = timezone.now().astimezone(pacific_tz)
        start_of_day_pacific = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_day_utc = start_of_day_pacific.astimezone(pytz.UTC)
        
        # Create 25 usage records (at the limit)
        for i in range(25):
            LLMUsage.objects.create(
                model_name='google-gla:gemini-2.5-pro-preview-06-05',
                input_tokens=1000,
                output_tokens=500,
                total_tokens=1500,
                date=start_of_day_utc + timedelta(minutes=i)
            )
        
        model_configs = {
            'google-gla:gemini-2.5-pro-preview-06-05': {
                'daily_requests': 25,
                'daily_tokens': 1000000,
                'provider': 'gemini'
            },
            'google-gla:gemini-2.5-flash-preview-05-20': {
                'daily_requests': 500,
                'provider': 'gemini'
            }
        }
        
        available_models = LLMService._get_available_models_for_provider('gemini', model_configs)
        
        # Pro model should be excluded due to request limit, flash should be available
        assert 'gemini-2.5-pro-preview-06-05' not in available_models
        assert 'gemini-2.5-flash-preview-05-20' in available_models

    def test_get_available_models_for_provider_openai_no_usage(self):
        """Test _get_available_models_for_provider for OpenAI with no usage."""
        model_configs = {
            'openai:gpt-4.1-2025-04-14': {
                'daily_tokens': 250000,
                'provider': 'openai',
                'combined_with': ['openai:gpt-4.5-preview-2025-02-27']
            },
            'openai:gpt-4.5-preview-2025-02-27': {
                'daily_tokens': 250000,
                'provider': 'openai',
                'combined_with': ['openai:gpt-4.1-2025-04-14']
            },
            'openai:gpt-4.1-mini-2025-04-14': {
                'daily_tokens': 2500000,
                'provider': 'openai'
            }
        }
        
        available_models = LLMService._get_available_models_for_provider('openai', model_configs)
        
        expected_models = ['gpt-4.1-2025-04-14', 'gpt-4.5-preview-2025-02-27', 'gpt-4.1-mini-2025-04-14']
        assert set(available_models) == set(expected_models)

    def test_get_available_models_for_provider_openai_combined_quota_exceeded(self):
        """Test OpenAI combined quota handling when limit is exceeded."""
        # Create usage that exceeds combined quota (90% of 250000)
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Add usage for both combined models totaling 230000 tokens (over 90% limit)
        LLMUsage.objects.create(
            model_name='openai:gpt-4.1-2025-04-14',
            input_tokens=100000,
            output_tokens=50000,
            total_tokens=150000,
            date=today_start + timedelta(hours=1)
        )
        LLMUsage.objects.create(
            model_name='openai:gpt-4.5-preview-2025-02-27',
            input_tokens=60000,
            output_tokens=20000,
            total_tokens=80000,
            date=today_start + timedelta(hours=2)
        )
        
        model_configs = {
            'openai:gpt-4.1-2025-04-14': {
                'daily_tokens': 250000,
                'provider': 'openai',
                'combined_with': ['openai:gpt-4.5-preview-2025-02-27']
            },
            'openai:gpt-4.5-preview-2025-02-27': {
                'daily_tokens': 250000,
                'provider': 'openai',
                'combined_with': ['openai:gpt-4.1-2025-04-14']
            },
            'openai:gpt-4.1-mini-2025-04-14': {
                'daily_tokens': 2500000,
                'provider': 'openai'
            }
        }
        
        available_models = LLMService._get_available_models_for_provider('openai', model_configs)
        
        # Combined quota models should be excluded, mini should be available
        assert 'gpt-4.1-2025-04-14' not in available_models
        assert 'gpt-4.5-preview-2025-02-27' not in available_models
        assert 'gpt-4.1-mini-2025-04-14' in available_models

    def test_get_available_models_for_provider_claude_always_available(self):
        """Test that Claude is always available as fallback."""
        model_configs = {}  # Empty config
        
        available_models = LLMService._get_available_models_for_provider('claude', model_configs)
        
        assert available_models == ['claude-sonnet-4-0']

    def test_get_available_models_for_provider_unknown_provider(self):
        """Test behavior with unknown provider."""
        model_configs = {}
        
        available_models = LLMService._get_available_models_for_provider('unknown', model_configs)
        
        assert available_models == []

    def test_timezone_handling_gemini_pacific(self):
        """Test that Gemini usage correctly handles Pacific timezone."""
        # Create usage at different Pacific times to test timezone conversion
        pacific_tz = pytz.timezone('US/Pacific')
        utc_tz = pytz.UTC
        
        # Create usage at 11 PM Pacific (should count as same day)
        pacific_time = pacific_tz.localize(datetime(2024, 1, 15, 23, 0, 0))
        utc_time = pacific_time.astimezone(utc_tz)
        
        LLMUsage.objects.create(
            model_name='google-gla:gemini-2.5-pro-preview-06-05',
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            date=utc_time
        )
        
        # Mock the current time to be next day at 1 AM Pacific
        next_day_pacific = pacific_tz.localize(datetime(2024, 1, 16, 1, 0, 0))
        
        with patch('django.utils.timezone.now') as mock_now:
            mock_now.return_value = next_day_pacific.astimezone(utc_tz)
            
            model_configs = {
                'google-gla:gemini-2.5-pro-preview-06-05': {
                    'daily_requests': 25,
                    'provider': 'gemini'
                }
            }
            
            available_models = LLMService._get_available_models_for_provider('gemini', model_configs)
            
            # Should be available since it's a new Pacific day
            assert 'gemini-2.5-pro-preview-06-05' in available_models

    def test_meta_options(self):
        """Test model meta options."""
        meta = LLMService._meta
        assert meta.verbose_name == "LLM Service"
        assert meta.verbose_name_plural == "LLM Services"
        assert meta.ordering == ['priority']
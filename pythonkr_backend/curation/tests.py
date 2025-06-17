"""
Test suite for the curation app.

This module organizes all tests for the curation app, including:
- LLMService model tests (test_llm_service.py)
- RSS crawling and Celery task tests (test_tasks.py) 
- Utility function tests (test_utils.py)

Run tests with: uv run pytest pythonkr_backend/curation/
"""

import pytest
from django.test import TestCase

# Test modules are automatically discovered by pytest
# No need to explicitly import test classes


class CurationAppTestCase(TestCase):
    """
    Base test case for curation app.
    
    This class can be extended for integration tests that need
    to test interactions between different components.
    """
    pass


@pytest.mark.django_db
def test_curation_app_basic():
    """Basic test to ensure the curation app is properly configured."""
    from django.apps import apps
    from django.conf import settings
    
    # Check that the curation app is installed
    assert 'curation' in settings.INSTALLED_APPS
    
    # Check that the app config is loaded
    app_config = apps.get_app_config('curation')
    assert app_config.name == 'curation'

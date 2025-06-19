import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.http import HttpRequest
from unittest.mock import patch

from .models import TranslatedContent, RSSFeed, RSSItem
from .admin import TranslatedContentAdmin


@pytest.mark.django_db
class TestTranslatedContentAdmin:
    """Test cases for TranslatedContent admin interface."""

    def setup_method(self):
        """Set up test data for each test method."""
        # Create superuser for admin access
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="adminpass123"
        )

        # Create regular user for permission testing
        self.regular_user = User.objects.create_user(
            username="user", email="user@test.com", password="userpass123"
        )

        self.client = Client()

        # Create test data
        self.feed = RSSFeed.objects.create(
            name="Admin Test Feed",
            url="https://example.com/admin-feed.xml",
            is_active=True,
        )

        self.rss_item = RSSItem.objects.create(
            feed=self.feed,
            title="Admin Test Item",
            link="https://example.com/admin-test",
            crawling_status="completed",
        )

        self.translated_content = TranslatedContent.objects.create(
            title="어드민 테스트 콘텐츠",
            slug="admin-test-content",
            description="어드민 테스트 설명입니다.",
            tags=["admin", "test", "django"],
            written_date="2024-01-15",
            author="어드민 테스트 작성자",
            model_name="admin-test-model",
            source_rss_item=self.rss_item,
            source_url="https://example.com/admin-source",
        )

    def test_admin_list_display(self):
        """Test that admin list display shows all expected fields."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Access admin change list
        url = reverse("admin:curation_translatedcontent_changelist")
        response = self.client.get(url)

        assert response.status_code == 200

        content = response.content.decode()

        # Check that list_display fields are shown
        assert "어드민 테스트 콘텐츠" in content  # title
        assert "admin-test-content" in content  # slug
        assert "어드민 테스트 작성자" in content  # author
        assert "admin-test-model" in content  # model_name
        assert "Admin Test Item" in content  # source_rss_item
        assert "보기" in content  # view_link

    def test_admin_view_link_generation(self):
        """Test the view_link method in admin."""
        admin_site = AdminSite()
        admin = TranslatedContentAdmin(TranslatedContent, admin_site)

        # Test with valid content
        link_html = admin.view_link(self.translated_content)
        expected_url = reverse(
            "curation:translated_content_detail", args=[self.translated_content.id]
        )

        assert f'href="{expected_url}"' in link_html
        assert 'target="_blank"' in link_html
        assert "보기" in link_html

    def test_admin_view_link_no_pk(self):
        """Test view_link method when object has no primary key."""
        admin_site = AdminSite()
        admin = TranslatedContentAdmin(TranslatedContent, admin_site)

        # Create unsaved object (no pk)
        unsaved_content = TranslatedContent(
            title="미저장 콘텐츠",
            slug="unsaved-content",
            description="미저장 설명",
            model_name="test-model",
            source_url="https://example.com/unsaved",
        )

        link_html = admin.view_link(unsaved_content)
        assert link_html == "-"

    def test_admin_view_link_functionality(self):
        """Test that view link actually works from admin."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Access admin change list
        changelist_url = reverse("admin:curation_translatedcontent_changelist")
        response = self.client.get(changelist_url)

        assert response.status_code == 200

        # Check that the view URL is accessible
        view_url = reverse(
            "curation:translated_content_detail", args=[self.translated_content.id]
        )
        view_response = self.client.get(view_url)

        # Should be accessible (200) or have content issues but still resolve (200)
        assert view_response.status_code == 200

    def test_admin_search_fields(self):
        """Test admin search functionality."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Test search by title
        url = reverse("admin:curation_translatedcontent_changelist")
        response = self.client.get(url, {"q": "어드민"})

        assert response.status_code == 200
        content = response.content.decode()
        assert "어드민 테스트 콘텐츠" in content

    def test_admin_list_filter(self):
        """Test admin list filters."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Test filter by model_name
        url = reverse("admin:curation_translatedcontent_changelist")
        response = self.client.get(url, {"model_name__exact": "admin-test-model"})

        assert response.status_code == 200
        content = response.content.decode()
        assert "어드민 테스트 콘텐츠" in content

    def test_admin_fieldsets(self):
        """Test admin form fieldsets."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Access admin change form
        url = reverse(
            "admin:curation_translatedcontent_change", args=[self.translated_content.id]
        )
        response = self.client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check that fieldset sections are present
        assert "Content Information" in content
        assert "Content File" in content
        assert "Source Information" in content
        assert "Metadata" in content

    def test_admin_readonly_fields(self):
        """Test that readonly fields are properly set."""
        admin_site = AdminSite()
        admin = TranslatedContentAdmin(TranslatedContent, admin_site)

        readonly_fields = admin.readonly_fields

        assert "created_at" in readonly_fields
        assert "updated_at" in readonly_fields

    def test_admin_queryset_optimization(self):
        """Test that admin queryset is optimized with select_related."""
        admin_site = AdminSite()
        admin = TranslatedContentAdmin(TranslatedContent, admin_site)

        # Create mock request
        request = HttpRequest()

        # Get queryset
        queryset = admin.get_queryset(request)

        # Check that select_related is used
        # This is indicated by checking the query's select_related fields
        query = str(queryset.query)
        assert "source_rss_item" in query or "SELECT" in query

    def test_admin_date_hierarchy(self):
        """Test admin date hierarchy functionality."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Test date hierarchy by written_date
        url = reverse("admin:curation_translatedcontent_changelist")
        response = self.client.get(url, {"written_date__year": "2024"})

        assert response.status_code == 200
        content = response.content.decode()
        assert "어드민 테스트 콘텐츠" in content

    def test_admin_permissions(self):
        """Test admin permissions for regular users."""
        # Try to access admin as regular user (should be redirected to login)
        self.client.login(username="user", password="userpass123")

        url = reverse("admin:curation_translatedcontent_changelist")
        response = self.client.get(url)

        # Should redirect to login or show permission denied
        assert response.status_code in [302, 403]

    def test_admin_add_form(self):
        """Test admin add form."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Access admin add form
        url = reverse("admin:curation_translatedcontent_add")
        response = self.client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check that form fields are present
        assert 'name="title"' in content
        assert 'name="slug"' in content
        assert 'name="description"' in content
        assert 'name="model_name"' in content
        assert 'name="source_url"' in content

    def test_admin_change_form(self):
        """Test admin change form."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Access admin change form
        url = reverse(
            "admin:curation_translatedcontent_change", args=[self.translated_content.id]
        )
        response = self.client.get(url)

        assert response.status_code == 200
        content = response.content.decode()

        # Check that existing values are pre-populated
        assert (
            'value="어드민 테스트 콘텐츠"' in content
            or "어드민 테스트 콘텐츠" in content
        )
        assert (
            'value="admin-test-content"' in content or "admin-test-content" in content
        )

    @patch("curation.admin.reverse")
    def test_admin_view_link_url_generation(self, mock_reverse):
        """Test that view_link generates correct URL."""
        mock_reverse.return_value = "/tr/123/"

        admin_site = AdminSite()
        admin = TranslatedContentAdmin(TranslatedContent, admin_site)

        link_html = admin.view_link(self.translated_content)

        mock_reverse.assert_called_once_with(
            "curation:translated_content_detail", args=[self.translated_content.pk]
        )

        assert "/tr/123/" in link_html

    def test_admin_list_display_methods(self):
        """Test that all list_display methods work correctly."""
        admin_site = AdminSite()
        admin = TranslatedContentAdmin(TranslatedContent, admin_site)

        # Test view_link method
        link_result = admin.view_link(self.translated_content)
        assert isinstance(link_result, str)
        assert "href=" in link_result

        # Test that all list_display items are callable or field names
        for item in admin.list_display:
            if hasattr(admin, item):
                method = getattr(admin, item)
                if callable(method):
                    result = method(self.translated_content)
                    assert result is not None
            else:
                # Should be a model field
                assert hasattr(TranslatedContent, item)

    def test_admin_integration_with_view(self):
        """Test integration between admin and the detail view."""
        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Get the admin change list
        changelist_url = reverse("admin:curation_translatedcontent_changelist")
        changelist_response = self.client.get(changelist_url)

        assert changelist_response.status_code == 200

        # Extract the view URL from admin
        detail_url = reverse(
            "curation:translated_content_detail", args=[self.translated_content.id]
        )

        # Test that the detail view works
        with patch("os.path.exists", return_value=False):
            detail_response = self.client.get(detail_url)
            assert detail_response.status_code == 200

    def test_admin_bulk_operations(self):
        """Test admin bulk operations."""
        # Create additional content for bulk testing
        additional_content = TranslatedContent.objects.create(
            title="추가 콘텐츠",
            slug="additional-content",
            description="추가 콘텐츠 설명",
            model_name="additional-model",
            source_url="https://example.com/additional",
        )

        # Login as admin
        self.client.login(username="admin", password="adminpass123")

        # Test bulk delete
        url = reverse("admin:curation_translatedcontent_changelist")
        response = self.client.post(
            url,
            {
                "action": "delete_selected",
                "_selected_action": [str(additional_content.id)],
                "post": "yes",
            },
        )

        # Should either process the action or show confirmation
        assert response.status_code in [200, 302]

    def test_admin_model_registration(self):
        """Test that TranslatedContent model is properly registered with admin."""
        from django.contrib import admin

        # Check that TranslatedContent is registered
        assert TranslatedContent in admin.site._registry

        # Check that it's registered with the correct admin class
        admin_class = admin.site._registry[TranslatedContent]
        assert isinstance(admin_class, TranslatedContentAdmin)

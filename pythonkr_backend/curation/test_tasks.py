import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone
import requests

from .models import RSSFeed, RSSItem
from .tasks import (
    crawl_all_rss_feeds,
    crawl_single_rss_feed,
    crawl_rss,
    crawl_rss_item_content,
    translate_pending_rss_item,
)


@pytest.mark.django_db
class TestRSSCrawlingTasks:
    """Test cases for RSS crawling tasks and functions."""

    def setup_method(self):
        """Set up test data for each test method."""
        self.feed1 = RSSFeed.objects.create(
            name="Test Feed 1", url="https://example.com/feed1.xml", is_active=True
        )
        self.feed2 = RSSFeed.objects.create(
            name="Test Feed 2", url="https://example.com/feed2.xml", is_active=True
        )
        self.inactive_feed = RSSFeed.objects.create(
            name="Inactive Feed",
            url="https://example.com/inactive.xml",
            is_active=False,
        )

    def test_crawl_all_rss_feeds_success(self):
        """Test crawl_all_rss_feeds with successful crawling."""
        with patch("curation.tasks.crawl_single_rss_feed") as mock_crawl:
            mock_crawl.return_value = {"new_items": 3}

            results = crawl_all_rss_feeds()

            assert results["total_feeds"] == 2  # Only active feeds
            assert results["processed_feeds"] == 2
            assert results["new_items"] == 6  # 3 * 2 feeds
            assert len(results["errors"]) == 0
            assert mock_crawl.call_count == 2

    def test_crawl_all_rss_feeds_with_errors(self):
        """Test crawl_all_rss_feeds when some feeds fail."""
        with patch("curation.tasks.crawl_single_rss_feed") as mock_crawl:
            # First feed succeeds, second fails
            mock_crawl.side_effect = [{"new_items": 2}, Exception("Network error")]

            results = crawl_all_rss_feeds()

            assert results["total_feeds"] == 2
            assert results["processed_feeds"] == 1  # Only first succeeded
            assert results["new_items"] == 2
            assert len(results["errors"]) == 1
            assert "Network error" in results["errors"][0]

    def test_crawl_single_rss_feed_success(self):
        """Test crawl_single_rss_feed with valid RSS feed."""
        mock_feed_data = MagicMock()
        mock_feed_data.bozo = False
        mock_feed_data.entries = [
            type(
                "Entry",
                (),
                {
                    "title": "Test Article 1",
                    "link": "https://example.com/article1",
                    "summary": "Test summary 1",
                    "author": "Test Author",
                    "tags": [
                        type("Tag", (), {"term": "python"})(),
                        type("Tag", (), {"term": "django"})(),
                    ],
                    "id": "article1",
                    "published_parsed": (2024, 1, 15, 12, 0, 0, 0, 15, 0),
                },
            )(),
            type(
                "Entry",
                (),
                {
                    "title": "Test Article 2",
                    "link": "https://example.com/article2",
                    "summary": "Test summary 2",
                    "author": "Test Author 2",
                    "tags": [],
                    "guid": "article2",
                    "updated_parsed": (2024, 1, 16, 10, 0, 0, 0, 16, 0),
                },
            )(),
        ]

        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value = mock_feed_data

            result = crawl_single_rss_feed(self.feed1.id)

            assert result["feed_name"] == "Test Feed 1"
            assert result["new_items"] == 2
            assert result["total_entries"] == 2

            # Check that RSS items were created
            items = RSSItem.objects.filter(feed=self.feed1)
            assert items.count() == 2

            item1 = items.get(link="https://example.com/article1")
            assert item1.title == "Test Article 1"
            assert item1.author == "Test Author"
            assert item1.category == "python, django"
            assert item1.guid == "article1"

            item2 = items.get(link="https://example.com/article2")
            assert item2.title == "Test Article 2"
            assert item2.guid == "article2"

    def test_crawl_single_rss_feed_duplicate_prevention(self):
        """Test that duplicate entries are not created."""
        # Create existing RSS item
        existing_item = RSSItem.objects.create(
            feed=self.feed1,
            title="Existing Article",
            link="https://example.com/existing",
            guid="existing",
        )

        mock_feed_data = MagicMock()
        mock_feed_data.bozo = False
        mock_feed_data.entries = [
            type(
                "Entry",
                (),
                {
                    "title": "Existing Article",
                    "link": "https://example.com/existing",
                    "summary": "Test summary",
                    "author": "Test Author",
                    "tags": [],
                    "id": "existing",
                },
            )(),
            type(
                "Entry",
                (),
                {
                    "title": "New Article",
                    "link": "https://example.com/new",
                    "summary": "New summary",
                    "author": "Test Author",
                    "tags": [],
                    "id": "new",
                },
            )(),
        ]

        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value = mock_feed_data

            result = crawl_single_rss_feed(self.feed1.id)

            assert result["new_items"] == 1  # Only new article should be added
            assert result["total_entries"] == 2

            # Should still have only 2 items total (1 existing + 1 new)
            assert RSSItem.objects.filter(feed=self.feed1).count() == 2

    def test_crawl_single_rss_feed_nonexistent_feed(self):
        """Test crawl_single_rss_feed with non-existent feed ID."""
        with pytest.raises(Exception) as exc_info:
            crawl_single_rss_feed(99999)

        assert "RSS Feed with id 99999 not found" in str(exc_info.value)

    def test_crawl_single_rss_feed_malformed_feed(self):
        """Test crawl_single_rss_feed with malformed RSS feed."""
        mock_feed_data = MagicMock()
        mock_feed_data.bozo = True
        mock_feed_data.bozo_exception = "XML parsing error"
        mock_feed_data.entries = []

        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value = mock_feed_data

            result = crawl_single_rss_feed(self.feed1.id)

            assert result["new_items"] == 0
            assert result["total_entries"] == 0

    def test_crawl_single_rss_feed_network_error(self):
        """Test crawl_single_rss_feed with network error."""
        with patch("feedparser.parse") as mock_parse:
            mock_parse.side_effect = requests.RequestException("Connection failed")

            with pytest.raises(Exception) as exc_info:
                crawl_single_rss_feed(self.feed1.id)

            assert "Network error while fetching RSS feed" in str(exc_info.value)

    def test_crawl_single_rss_feed_field_truncation(self):
        """Test that long field values are properly truncated."""
        mock_feed_data = MagicMock()
        mock_feed_data.bozo = False
        mock_feed_data.entries = [
            type(
                "Entry",
                (),
                {
                    "title": "A" * 600,  # Longer than 500 char limit
                    "link": "https://example.com/long",
                    "summary": "Test summary",
                    "author": "B" * 250,  # Longer than 200 char limit
                    "tags": [
                        type("Tag", (), {"term": "tag" + str(i)})() for i in range(50)
                    ],  # Many tags
                    "id": "C" * 600,  # Longer than 500 char limit
                    "published_parsed": (2024, 1, 15, 12, 0, 0, 0, 15, 0),
                },
            )()
        ]

        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value = mock_feed_data

            result = crawl_single_rss_feed(self.feed1.id)

            item = RSSItem.objects.get(link="https://example.com/long")
            assert len(item.title) == 500  # Truncated
            assert len(item.author) == 200  # Truncated
            assert len(item.guid) == 500  # Truncated
            assert len(item.category) <= 200  # Truncated

    @patch("curation.tasks.crawl_all_rss_feeds")
    def test_crawl_rss_celery_task(self, mock_crawl_all):
        """Test crawl_rss Celery task."""
        mock_crawl_all.return_value = {"total_feeds": 2, "new_items": 5}

        result = crawl_rss()

        assert result["total_feeds"] == 2
        assert result["new_items"] == 5
        mock_crawl_all.assert_called_once()

    def test_crawl_rss_item_content_success(self):
        """Test crawl_rss_item_content with successful crawling."""
        # Create pending RSS item
        pub_date = timezone.now() - timedelta(days=1)
        rss_item = RSSItem.objects.create(
            feed=self.feed1,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="pending",
            pub_date=pub_date,
        )

        mock_response = MagicMock()
        mock_response.text = "# Test Article\n\nThis is test content."
        mock_response.raise_for_status = MagicMock()

        with patch("requests.get") as mock_get:
            mock_get.return_value = mock_response

            result = crawl_rss_item_content()

            assert result["status"] == "success"
            assert result["item_id"] == rss_item.id
            assert result["item_title"] == "Test Article"
            assert result["content_length"] == len(mock_response.text)

            # Check that item was updated
            rss_item.refresh_from_db()
            assert rss_item.crawling_status == "completed"
            assert rss_item.crawled_at is not None
            assert rss_item.error_message == ""
            assert rss_item.crawled_content is not None

            # Verify Jina URL was called
            expected_url = f"https://r.jina.ai/{rss_item.link}"
            mock_get.assert_called_once_with(expected_url, timeout=30)

    def test_crawl_rss_item_content_no_pending_items(self):
        """Test crawl_rss_item_content when no pending items exist."""
        result = crawl_rss_item_content()

        assert result["status"] == "no_items"
        assert result["message"] == "No pending items to crawl"

    def test_crawl_rss_item_content_old_items_ignored(self):
        """Test that items older than 2 weeks are ignored."""
        # Create old pending RSS item (older than 2 weeks)
        old_pub_date = timezone.now() - timedelta(days=15)
        RSSItem.objects.create(
            feed=self.feed1,
            title="Old Article",
            link="https://example.com/old-article",
            crawling_status="pending",
            pub_date=old_pub_date,
        )

        result = crawl_rss_item_content()

        assert result["status"] == "no_items"

    def test_crawl_rss_item_content_network_error(self):
        """Test crawl_rss_item_content with network error."""
        pub_date = timezone.now() - timedelta(days=1)
        rss_item = RSSItem.objects.create(
            feed=self.feed1,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="pending",
            pub_date=pub_date,
        )

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Connection failed")

            result = crawl_rss_item_content()

            assert result["status"] == "failed"
            assert result["item_id"] == rss_item.id
            assert "Network error" in result["error"]

            # Check that item status was updated
            rss_item.refresh_from_db()
            assert rss_item.crawling_status == "failed"
            assert "Network error" in rss_item.error_message

    def test_crawl_rss_item_content_unexpected_error(self):
        """Test crawl_rss_item_content with unexpected error."""
        pub_date = timezone.now() - timedelta(days=1)
        rss_item = RSSItem.objects.create(
            feed=self.feed1,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="pending",
            pub_date=pub_date,
        )

        with patch("requests.get") as mock_get:
            mock_get.side_effect = Exception("Unexpected error")

            result = crawl_rss_item_content()

            assert result["status"] == "failed"
            assert result["item_id"] == rss_item.id
            assert "Unexpected error" in result["error"]

            # Check that item status was updated
            rss_item.refresh_from_db()
            assert rss_item.crawling_status == "failed"
            assert "Unexpected error" in rss_item.error_message

    @patch("curation.tasks.translate_rssitem")
    def test_translate_pending_rss_item_success(self, mock_translate):
        """Test translate_pending_rss_item with successful translation."""
        # Create completed RSS item pending translation
        rss_item = RSSItem.objects.create(
            feed=self.feed1,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            translate_status="pending",
            crawled_at=timezone.now(),
            is_translation_allowed=True,
            language="en",
        )

        # Mock successful translation
        mock_translated_content = MagicMock()
        mock_translated_content.id = 123
        mock_translate.return_value = mock_translated_content

        result = translate_pending_rss_item()

        assert result["status"] == "success"
        assert result["item_id"] == rss_item.id
        assert result["item_title"] == "Test Article"
        assert result["translated_content_id"] == 123

        # Check that item status was updated
        rss_item.refresh_from_db()
        assert rss_item.translate_status == "completed"
        assert rss_item.translate_error_message == ""

        mock_translate.assert_called_once_with(rss_item.id)

    def test_translate_pending_rss_item_no_pending_items(self):
        """Test translate_pending_rss_item when no pending items exist."""
        result = translate_pending_rss_item()

        assert result["status"] == "no_items"
        assert result["message"] == "No items eligible for translation"

    @patch("curation.tasks.translate_rssitem")
    def test_translate_pending_rss_item_translation_error(self, mock_translate):
        """Test translate_pending_rss_item with translation error."""
        rss_item = RSSItem.objects.create(
            feed=self.feed1,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            translate_status="pending",
            crawled_at=timezone.now(),
            is_translation_allowed=True,
            language="en",
        )

        mock_translate.side_effect = Exception("Translation failed")

        result = translate_pending_rss_item()

        assert result["status"] == "failed"
        assert result["item_id"] == rss_item.id
        assert "Translation failed" in result["error"]

        # Check that item status was updated
        rss_item.refresh_from_db()
        assert rss_item.translate_status == "failed"
        assert "Translation failed" in rss_item.translate_error_message

    def test_translate_pending_rss_item_excludes_already_translated(self):
        """Test that items with existing translations are excluded."""
        from .models import TranslatedContent

        # Create RSS item with existing translation
        rss_item = RSSItem.objects.create(
            feed=self.feed1,
            title="Test Article",
            link="https://example.com/test-article",
            crawling_status="completed",
            translate_status="pending",
            crawled_at=timezone.now(),
        )

        # Create existing translation
        TranslatedContent.objects.create(
            title="번역된 제목",
            slug="translated-title",
            description="번역된 설명",
            model_name="test:model",
            source_rss_item=rss_item,
            source_url=rss_item.link,
        )

        result = translate_pending_rss_item()

        assert result["status"] == "no_items"

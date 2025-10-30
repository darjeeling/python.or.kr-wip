"""
Tests for newsletter link extraction functionality.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.core.files.base import ContentFile
from .models import RSSFeed, RSSItem
from .utils_newsletter import (
    extract_newsletter_links,
    process_newsletter_url,
    clean_tracking_url,
    is_valid_article_link,
    extract_title_from_url,
    process_newsletter_rss_item,
    is_newsletter_domain,
)


class NewsletterExtractionTests(TestCase):
    """Test newsletter link extraction utilities."""

    def setUp(self):
        """Set up test data."""
        self.newsletter_feed = RSSFeed.objects.create(
            name="Test Newsletter",
            url="http://example.com/newsletter.xml",
            is_active=True,
            is_newsletter=True
        )
        
        self.regular_feed = RSSFeed.objects.create(
            name="Regular Feed",
            url="http://example.com/feed.xml",
            is_active=True,
            is_newsletter=False
        )

    def test_extract_newsletter_links_html(self):
        """Test link extraction from HTML newsletter content."""
        html_content = """
        <html>
        <body>
            <h1>Weekly Newsletter</h1>
            <p>Check out these articles:</p>
            <ul>
                <li><a href="https://example.com/article1">Python Tips</a></li>
                <li><a href="https://blog.example.com/django-tutorial">Django Tutorial</a></li>
                <li><a href="https://twitter.com/user">Follow us</a></li>
                <li><a href="mailto:contact@example.com">Contact</a></li>
                <li><a href="#section1">Internal Link</a></li>
            </ul>
        </body>
        </html>
        """
        
        links = extract_newsletter_links(html_content, "http://newsletter.com")
        
        # Should extract valid article links, exclude social media and internal links
        valid_links = [link['url'] for link in links]
        self.assertIn("https://example.com/article1", valid_links)
        self.assertIn("https://blog.example.com/django-tutorial", valid_links)
        
        # Should exclude Twitter and email links
        self.assertNotIn("https://twitter.com/user", valid_links)
        self.assertNotIn("mailto:contact@example.com", valid_links)

    def test_process_newsletter_url(self):
        """Test URL processing and normalization."""
        base_url = "http://newsletter.com"
        
        # Test relative URL resolution
        relative_url = "/article/123"
        processed = process_newsletter_url(relative_url, base_url)
        self.assertEqual(processed, "http://newsletter.com/article/123")
        
        # Test absolute URL passthrough
        absolute_url = "https://example.com/article"
        processed = process_newsletter_url(absolute_url, base_url)
        self.assertEqual(processed, absolute_url)
        
        # Test invalid URL handling
        invalid_url = "javascript:void(0)"
        processed = process_newsletter_url(invalid_url, base_url)
        self.assertIsNone(processed)

    def test_clean_tracking_url(self):
        """Test removal of tracking parameters."""
        tracking_url = (
            "https://example.com/article?utm_source=newsletter&utm_medium=email"
            "&utm_campaign=weekly&fbclid=abc123&ref=newsletter"
        )
        
        cleaned = clean_tracking_url(tracking_url)
        
        # Should remove tracking parameters
        self.assertNotIn("utm_source", cleaned)
        self.assertNotIn("utm_medium", cleaned)
        self.assertNotIn("fbclid", cleaned)
        self.assertNotIn("ref", cleaned)
        
        # Should preserve the base URL
        self.assertIn("https://example.com/article", cleaned)

    def test_is_valid_article_link(self):
        """Test article link validation."""
        # Valid article links
        self.assertTrue(is_valid_article_link(
            "https://example.com/blog/python-tutorial", 
            "Python Tutorial"
        ))
        self.assertTrue(is_valid_article_link(
            "https://dev.to/author/awesome-article", 
            "Awesome Development Article"
        ))
        
        # Invalid links - social media
        self.assertFalse(is_valid_article_link(
            "https://twitter.com/user", 
            "Follow us"
        ))
        self.assertFalse(is_valid_article_link(
            "https://facebook.com/page", 
            "Like our page"
        ))
        
        # Invalid links - navigation
        self.assertFalse(is_valid_article_link(
            "https://example.com/unsubscribe", 
            "Unsubscribe"
        ))
        self.assertFalse(is_valid_article_link(
            "https://example.com/contact", 
            "Contact Us"
        ))
        
        # Invalid links - short URLs or home pages
        self.assertFalse(is_valid_article_link(
            "https://example.com/", 
            "Home"
        ))
        self.assertFalse(is_valid_article_link(
            "https://example.com/a", 
            "Short"
        ))

    def test_extract_title_from_url(self):
        """Test title extraction from URLs."""
        # Test with descriptive path
        url1 = "https://example.com/python-web-scraping-tutorial"
        title1 = extract_title_from_url(url1)
        self.assertEqual(title1, "Python Web Scraping Tutorial")
        
        # Test with file extension
        url2 = "https://blog.com/django-models-guide.html"
        title2 = extract_title_from_url(url2)
        self.assertEqual(title2, "Django Models Guide")
        
        # Test with domain fallback
        url3 = "https://example.com/"
        title3 = extract_title_from_url(url3)
        self.assertEqual(title3, "Example.Com")

    def test_is_newsletter_domain(self):
        """Test newsletter domain detection."""
        # Known newsletter domains
        self.assertTrue(is_newsletter_domain("https://user.substack.com/p/article"))
        self.assertTrue(is_newsletter_domain("https://newsletter.beehiiv.com/p/post"))
        
        # Regular domains
        self.assertFalse(is_newsletter_domain("https://example.com/blog"))
        self.assertFalse(is_newsletter_domain("https://github.com/user/repo"))

    def test_process_newsletter_rss_item_not_newsletter(self):
        """Test processing non-newsletter RSS item."""
        regular_item = RSSItem.objects.create(
            feed=self.regular_feed,
            title="Regular Article",
            link="http://example.com/article"
        )
        
        result = process_newsletter_rss_item(regular_item.id)
        
        self.assertIn('error', result)
        self.assertIn('not from a newsletter feed', result['error'])

    def test_process_newsletter_rss_item_no_content(self):
        """Test processing newsletter item without crawled content."""
        newsletter_item = RSSItem.objects.create(
            feed=self.newsletter_feed,
            title="Newsletter Issue",
            link="http://newsletter.com/issue/1"
        )
        
        result = process_newsletter_rss_item(newsletter_item.id)
        
        self.assertIn('error', result)
        self.assertIn('No crawled content', result['error'])

    def test_process_newsletter_rss_item_success(self):
        """Test successful newsletter processing."""
        # Create newsletter item with content
        newsletter_item = RSSItem.objects.create(
            feed=self.newsletter_feed,
            title="Newsletter Issue #1",
            link="http://newsletter.com/issue/1",
            crawling_status="completed",
            guid="newsletter-issue-1"  # Provide unique GUID
        )
        
        # Add HTML content with links
        html_content = """
        <h1>Newsletter Issue #1</h1>
        <ul>
            <li><a href="https://example.com/python-tutorial">Python Tutorial</a></li>
            <li><a href="https://dev.to/django-tips">Django Tips</a></li>
            <li><a href="https://twitter.com/follow">Follow us</a></li>
        </ul>
        """
        content_file = ContentFile(html_content.encode('utf-8'))
        newsletter_item.crawled_content.save('newsletter.md', content_file)
        
        result = process_newsletter_rss_item(newsletter_item.id)
        
        # Should extract valid links and create RSS items
        self.assertEqual(result['extracted_count'], 2)  # Excludes Twitter link
        self.assertEqual(result['created_count'], 2)
        self.assertIn('created_items', result)
        
        # Verify created items
        created_items = RSSItem.objects.filter(source_item=newsletter_item)
        self.assertEqual(created_items.count(), 2)
        
        # Check that created items have correct source relationship
        for item in created_items:
            self.assertEqual(item.source_item, newsletter_item)
            self.assertEqual(item.feed, self.newsletter_feed)
            self.assertEqual(item.crawling_status, 'pending')

    def test_process_newsletter_rss_item_duplicate_links(self):
        """Test newsletter processing with duplicate links."""
        # Create newsletter item
        newsletter_item = RSSItem.objects.create(
            feed=self.newsletter_feed,
            title="Newsletter Issue",
            link="http://newsletter.com/issue/1",
            crawling_status="completed",
            guid="newsletter-duplicate-test"  # Provide unique GUID
        )
        
        # Create an existing RSS item with same URL
        existing_url = "https://example.com/existing-article"
        RSSItem.objects.create(
            feed=self.newsletter_feed,
            title="Existing Article",
            link=existing_url,
            guid=f"existing-{existing_url}"  # Provide unique GUID
        )
        
        # Add content with duplicate link
        html_content = f"""
        <h1>Newsletter</h1>
        <ul>
            <li><a href="{existing_url}">Existing Article</a></li>
            <li><a href="https://example.com/new-article">New Article</a></li>
        </ul>
        """
        content_file = ContentFile(html_content.encode('utf-8'))
        newsletter_item.crawled_content.save('newsletter.md', content_file)
        
        result = process_newsletter_rss_item(newsletter_item.id)
        
        # Should only create item for new link
        self.assertEqual(result['extracted_count'], 2)
        self.assertEqual(result['created_count'], 1)  # Only new article created

    def test_process_newsletter_rss_item_no_valid_links(self):
        """Test newsletter processing with no valid article links."""
        newsletter_item = RSSItem.objects.create(
            feed=self.newsletter_feed,
            title="Newsletter Issue",
            link="http://newsletter.com/issue/1",
            crawling_status="completed",
            guid="newsletter-no-valid-links-test"  # Provide unique GUID
        )
        
        # Add content with only invalid links
        html_content = """
        <h1>Newsletter</h1>
        <ul>
            <li><a href="https://twitter.com/follow">Follow us</a></li>
            <li><a href="mailto:contact@example.com">Contact</a></li>
            <li><a href="#top">Back to top</a></li>
        </ul>
        """
        content_file = ContentFile(html_content.encode('utf-8'))
        newsletter_item.crawled_content.save('newsletter.md', content_file)
        
        result = process_newsletter_rss_item(newsletter_item.id)
        
        self.assertEqual(result['extracted_count'], 0)
        self.assertIn('No valid article links found', result['message'])


if __name__ == '__main__':
    pytest.main([__file__])
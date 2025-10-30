"""
Newsletter link extraction utilities.

This module provides functionality to extract individual article links
from newsletter-type RSS content and create separate RSSItem objects.
"""

import logging
import re
from typing import List, Dict, Set, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from django.utils import timezone

logger = logging.getLogger(__name__)

# Common newsletter domains that should be processed for link extraction
NEWSLETTER_DOMAINS = {
    'substack.com',
    'beehiiv.com', 
    'convertkit.com',
    'mailchimp.com',
    'constantcontact.com',
    'buttondown.email',
}

# Domains to exclude from link extraction (internal/promotional links)
EXCLUDED_DOMAINS = {
    'twitter.com', 'x.com',
    'facebook.com', 'fb.com',
    'linkedin.com',
    'instagram.com',
    'youtube.com', 'youtu.be',
    'tiktok.com',
    'github.com',  # Usually just profile links, not articles
    'medium.com',  # Will be in RSS feeds if relevant
    'substack.com',  # Internal substack navigation
    'beehiiv.com',
    'unsubscribe',
}

# Minimum URL length to consider valid
MIN_URL_LENGTH = 20


def extract_newsletter_links(content: str, base_url: str) -> List[Dict[str, str]]:
    """
    Extract external article links from newsletter content.
    
    Args:
        content: Newsletter HTML or markdown content
        base_url: Base URL for resolving relative links
        
    Returns:
        List of dictionaries with 'url' and 'title' keys
    """
    links = []
    
    try:
        # Parse content with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract all links
        raw_links = soup.find_all('a', href=True)
        
        processed_urls = set()  # Avoid duplicates
        
        for link in raw_links:
            url = link.get('href', '').strip()
            title = link.get_text(strip=True)
            
            # Process and validate URL
            processed_url = process_newsletter_url(url, base_url)
            
            if processed_url and processed_url not in processed_urls:
                if is_valid_article_link(processed_url, title):
                    links.append({
                        'url': processed_url,
                        'title': title or extract_title_from_url(processed_url)
                    })
                    processed_urls.add(processed_url)
        
        logger.info(f"Extracted {len(links)} unique links from newsletter content")
        return links
        
    except Exception as e:
        logger.error(f"Error extracting newsletter links: {e}")
        return []


def process_newsletter_url(url: str, base_url: str) -> Optional[str]:
    """
    Process and normalize a URL from newsletter content.
    
    Args:
        url: Raw URL from content
        base_url: Base URL for resolving relatives
        
    Returns:
        Processed URL or None if invalid
    """
    if not url:
        return None
    
    # Remove tracking parameters and clean URL
    url = clean_tracking_url(url)
    
    # Resolve relative URLs
    if not url.startswith(('http://', 'https://')):
        url = urljoin(base_url, url)
    
    # Basic validation
    if len(url) < MIN_URL_LENGTH:
        return None
    
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return None
        return url
    except Exception:
        return None


def clean_tracking_url(url: str) -> str:
    """
    Remove common tracking parameters from URLs.
    
    Args:
        url: URL with potential tracking parameters
        
    Returns:
        Cleaned URL
    """
    # Common tracking parameters to remove
    tracking_params = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'ref', 'referer', 'referrer',
        'fbclid', 'gclid', 'mc_cid', 'mc_eid',
        '_ga', '_gl', '_hsenc', '_hsmi',
        'source', 'campaign', 'medium'
    }
    
    try:
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Remove tracking parameters
        cleaned_params = {
            k: v for k, v in query_params.items() 
            if k.lower() not in tracking_params
        }
        
        # Rebuild URL
        new_query = urlencode(cleaned_params, doseq=True)
        cleaned_url = urlunparse((
            parsed.scheme, parsed.netloc, parsed.path,
            parsed.params, new_query, parsed.fragment
        ))
        
        return cleaned_url
        
    except Exception:
        return url  # Return original if parsing fails


def is_valid_article_link(url: str, title: str) -> bool:
    """
    Determine if a URL represents a valid article link worth extracting.
    
    Args:
        url: URL to validate
        title: Link text/title
        
    Returns:
        True if URL should be extracted as an article link
    """
    try:
        parsed = urlparse(url.lower())
        domain = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # Skip excluded domains
        for excluded in EXCLUDED_DOMAINS:
            if excluded in domain:
                return False
        
        # Skip common non-article patterns
        non_article_patterns = [
            'unsubscribe', 'subscribe', 'signup', 'login', 'register',
            'contact', 'about', 'privacy', 'terms', 'policy',
            'support', 'help', 'faq',
            'mailto:', 'tel:', 'sms:',
            '#', 'javascript:', 'void(',
            '/tag/', '/category/', '/archive/',
            '.pdf', '.doc', '.zip', '.exe',
        ]
        
        url_lower = url.lower()
        for pattern in non_article_patterns:
            if pattern in url_lower:
                return False
        
        # Skip if title suggests non-article content
        if title:
            title_lower = title.lower()
            non_article_titles = [
                'unsubscribe', 'subscribe', 'follow', 'share',
                'twitter', 'facebook', 'linkedin', 'social',
                'download', 'pdf', 'home', 'back to',
                'click here', 'learn more', 'read more',
                'view in browser', 'forward to friend',
            ]
            
            for bad_title in non_article_titles:
                if bad_title in title_lower:
                    return False
        
        # Require minimum title length if present
        if title and len(title.strip()) < 5:
            return False
        
        # Must have a reasonable path (not just domain)
        if not path or path == '/' or len(path) < 3:
            return False
        
        return True
        
    except Exception:
        return False


def extract_title_from_url(url: str) -> str:
    """
    Extract a reasonable title from URL path when no title is available.
    
    Args:
        url: URL to extract title from
        
    Returns:
        Extracted title
    """
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        if path:
            # Get last segment of path
            segments = path.split('/')
            last_segment = segments[-1]
            
            # Clean up common URL patterns
            title = last_segment.replace('-', ' ').replace('_', ' ')
            title = re.sub(r'\.(html?|php|asp|jsp)$', '', title, flags=re.IGNORECASE)
            title = re.sub(r'[^a-zA-Z0-9\s]', ' ', title)
            title = re.sub(r'\s+', ' ', title).strip().title()
            
            if len(title) > 5:
                return title
        
        # Fallback to domain
        return parsed.netloc.replace('www.', '').title()
        
    except Exception:
        return "Extracted Link"


def process_newsletter_rss_item(rss_item_id: int) -> Dict[str, any]:
    """
    Process a newsletter RSSItem to extract individual article links.
    
    Args:
        rss_item_id: ID of the newsletter RSSItem to process
        
    Returns:
        Dictionary with processing results
    """
    from .models import RSSItem
    
    try:
        rss_item = RSSItem.objects.get(id=rss_item_id)
    except RSSItem.DoesNotExist:
        return {'error': f'RSSItem {rss_item_id} not found'}
    
    # Check if this is a newsletter item
    if not rss_item.feed.is_newsletter:
        return {'error': 'RSSItem is not from a newsletter feed'}
    
    # Read crawled content
    if not rss_item.crawled_content:
        return {'error': 'No crawled content available'}
    
    try:
        with rss_item.crawled_content.open('r') as f:
            content = f.read()
    except Exception as e:
        return {'error': f'Failed to read content: {e}'}
    
    # Extract links from content
    extracted_links = extract_newsletter_links(content, rss_item.link)
    
    if not extracted_links:
        return {
            'message': 'No valid article links found in newsletter',
            'extracted_count': 0
        }
    
    # Create RSSItem objects for extracted links
    created_items = []
    errors = []
    
    for link_data in extracted_links:
        try:
            # Check if link already exists
            existing_item = RSSItem.objects.filter(link=link_data['url']).first()
            if existing_item:
                logger.debug(f"Link already exists: {link_data['url']}")
                continue
            
            # Create new RSSItem
            new_item = RSSItem.objects.create(
                feed=rss_item.feed,
                title=link_data['title'][:500],  # Respect field length limit
                link=link_data['url'],
                description=f"Extracted from newsletter: {rss_item.title}",
                author=rss_item.author,
                category=rss_item.category,
                guid=f"newsletter-{rss_item.id}-{hash(link_data['url']) % 1000000}",  # Generate unique GUID
                pub_date=rss_item.pub_date or timezone.now(),
                source_item=rss_item,  # Track the source newsletter
                crawling_status='pending'  # Will be processed by regular crawling task
            )
            
            created_items.append({
                'id': new_item.id,
                'title': new_item.title,
                'url': new_item.link
            })
            
            logger.info(f"Created RSSItem for extracted link: {link_data['title']}")
            
        except Exception as e:
            error_msg = f"Failed to create RSSItem for {link_data['url']}: {e}"
            errors.append(error_msg)
            logger.error(error_msg)
    
    result = {
        'extracted_count': len(extracted_links),
        'created_count': len(created_items),
        'created_items': created_items,
        'source_item': {
            'id': rss_item.id,
            'title': rss_item.title,
            'url': rss_item.link
        }
    }
    
    if errors:
        result['errors'] = errors
    
    logger.info(
        f"Newsletter processing completed. "
        f"Extracted: {len(extracted_links)}, Created: {len(created_items)}"
    )
    
    return result


def is_newsletter_domain(url: str) -> bool:
    """
    Check if a URL is from a known newsletter service.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is from a newsletter service
    """
    try:
        domain = urlparse(url.lower()).netloc
        return any(newsletter_domain in domain for newsletter_domain in NEWSLETTER_DOMAINS)
    except Exception:
        return False
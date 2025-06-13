import logfire

from celery import shared_task
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from django.utils import timezone as django_timezone
from django.core.files.base import ContentFile
from .models import RSSFeed, RSSItem
import logging

logger = logging.getLogger(__name__)

def crawl_all_rss_feeds():
    """모든 활성화된 RSS 피드를 크롤링합니다."""
    active_feeds = RSSFeed.objects.filter(is_active=True)
    
    results = {
        'total_feeds': active_feeds.count(),
        'processed_feeds': 0,
        'new_items': 0,
        'errors': []
    }
    
    for feed in active_feeds:
        try:
            result = crawl_single_rss_feed(feed.id)
            results['processed_feeds'] += 1
            results['new_items'] += result.get('new_items', 0)
            logfire.info(f"Successfully crawled feed {feed.name}: {result.get('new_items', 0)} new items")
            logger.info(f"Successfully crawled feed {feed.name}: {result.get('new_items', 0)} new items")
        except Exception as e:
            error_msg = f"Error crawling feed {feed.name}: {str(e)}"
            results['errors'].append(error_msg)
            logfire.error(error_msg)
            logger.error(error_msg)
    
    return results


def crawl_single_rss_feed(feed_id):
    """단일 RSS 피드를 크롤링합니다."""
    try:
        feed = RSSFeed.objects.get(id=feed_id)
    except RSSFeed.DoesNotExist:
        raise Exception(f"RSS Feed with id {feed_id} not found")
    
    logfire.info(f"Starting to crawl RSS feed: {feed.name} ({feed.url})")
    logger.info(f"Starting to crawl RSS feed: {feed.name} ({feed.url})")
    
    try:
        # RSS 피드 파싱
        parsed_feed = feedparser.parse(feed.url)
        
        if parsed_feed.bozo:
            logfire.warning(f"RSS feed {feed.name} has parsing issues: {parsed_feed.bozo_exception}")
            logger.warning(f"RSS feed {feed.name} has parsing issues: {parsed_feed.bozo_exception}")
        
        new_items_count = 0
        
        for entry in parsed_feed.entries:
            # GUID 또는 링크를 고유 식별자로 사용
            guid = getattr(entry, 'id', '') or getattr(entry, 'guid', '') or getattr(entry, 'link', '')
            link = getattr(entry, 'link', '')
            
            if not guid and not link:
                logfire.warning(f"Skipping entry without GUID or link in feed {feed.name}")
                logger.warning(f"Skipping entry without GUID or link in feed {feed.name}")
                continue
            
            # 중복 체크
            existing_item = None
            if guid:
                existing_item = RSSItem.objects.filter(guid=guid).first()
            if not existing_item and link:
                existing_item = RSSItem.objects.filter(link=link).first()
            
            if existing_item:
                continue  # 이미 존재하는 아이템은 스킵
            
            # 발행일 파싱
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                try:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                try:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass
            
            # 새 RSS 아이템 생성
            try:
                rss_item = RSSItem.objects.create(
                    feed=feed,
                    title=getattr(entry, 'title', '')[:500],  # 길이 제한
                    link=link,
                    description=getattr(entry, 'summary', '') or getattr(entry, 'description', ''),
                    author=getattr(entry, 'author', '')[:200],  # 길이 제한
                    category=', '.join([tag.term for tag in getattr(entry, 'tags', [])])[:200],  # 길이 제한
                    guid=guid[:500],  # 길이 제한
                    pub_date=pub_date
                )
                new_items_count += 1
                logfire.debug(f"Created new RSS item: {rss_item.title}")
                logger.debug(f"Created new RSS item: {rss_item.title}")
                
            except Exception as e:
                logfire.error(f"Error creating RSS item for {link}: {str(e)}")
                logger.error(f"Error creating RSS item for {link}: {str(e)}")
                continue
        
        # 마지막 크롤링 시간 업데이트
        feed.last_fetched = django_timezone.now()
        feed.save(update_fields=['last_fetched'])
        
        result = {
            'feed_name': feed.name,
            'new_items': new_items_count,
            'total_entries': len(parsed_feed.entries)
        }
        
        logfire.info(f"Completed crawling {feed.name}: {new_items_count} new items out of {len(parsed_feed.entries)} total entries")
        logger.info(f"Completed crawling {feed.name}: {new_items_count} new items out of {len(parsed_feed.entries)} total entries")
        return result
        
    except requests.RequestException as e:
        raise Exception(f"Network error while fetching RSS feed: {str(e)}")
    except Exception as e:
        raise Exception(f"Unexpected error while crawling RSS feed: {str(e)}")


@shared_task  
def crawl_rss():
    """10분마다 실행되는 RSS 크롤링 태스크"""
    logfire.info("start to crawl rss")
    logger.info("start to crawl rss")
    return crawl_all_rss_feeds()


@shared_task
def crawl_rss_item_content():
    """RSS 아이템의 본문을 크롤링하는 태스크 (10분마다 실행)"""
    logfire.info("Starting RSS item content crawling")
    logger.info("Starting RSS item content crawling")
    
    # 2주 이내의 크롤링되지 않은 최신 1개 아이템 가져오기
    two_weeks_ago = django_timezone.now() - timedelta(days=14)
    pending_item = RSSItem.objects.filter(
        crawling_status='pending',
        pub_date__gte=two_weeks_ago
    ).order_by('-pub_date', '-created_at').first()
    
    if not pending_item:
        logfire.info("No pending RSS items to crawl")
        logger.info("No pending RSS items to crawl")
        return {"status": "no_items", "message": "No pending items to crawl"}
    
    logfire.info(f"Crawling RSS item: {pending_item.title} ({pending_item.link})")
    logger.info(f"Crawling RSS item: {pending_item.title} ({pending_item.link})")
    
    # 크롤링 상태를 진행 중으로 변경 (동시 처리 방지)
    pending_item.crawling_status = 'completed'  # 임시로 설정하여 중복 처리 방지
    pending_item.save(update_fields=['crawling_status'])
    
    try:
        # Jina AI를 사용하여 콘텐츠 크롤링
        jina_url = f"https://r.jina.ai/{pending_item.link}"
        
        response = requests.get(jina_url, timeout=30)
        response.raise_for_status()
        
        # 마크다운 콘텐츠 저장
        markdown_content = response.text
        
        # 파일 저장
        filename = f"{pending_item.id}-crawl.md"
        content_file = ContentFile(markdown_content.encode('utf-8'))
        
        pending_item.crawled_content.save(filename, content_file, save=False)
        pending_item.crawling_status = 'completed'
        pending_item.crawled_at = django_timezone.now()
        pending_item.error_message = ''  # 성공 시 에러 메시지 초기화
        pending_item.save()
        
        logfire.info(f"Successfully crawled RSS item: {pending_item.title}")
        logger.info(f"Successfully crawled RSS item: {pending_item.title}")
        
        return {
            "status": "success",
            "item_id": pending_item.id,
            "item_title": pending_item.title,
            "content_length": len(markdown_content)
        }
        
    except requests.RequestException as e:
        error_msg = f"Network error while crawling {pending_item.link}: {str(e)}"
        pending_item.crawling_status = 'failed'
        pending_item.error_message = error_msg
        pending_item.save(update_fields=['crawling_status', 'error_message'])
        
        logfire.error(error_msg)
        logger.error(error_msg)
        
        return {
            "status": "failed",
            "item_id": pending_item.id,
            "error": error_msg
        }
        
    except Exception as e:
        error_msg = f"Unexpected error while crawling {pending_item.link}: {str(e)}"
        pending_item.crawling_status = 'failed'
        pending_item.error_message = error_msg
        pending_item.save(update_fields=['crawling_status', 'error_message'])
        
        logfire.error(error_msg)
        logger.error(error_msg)
        
        return {
            "status": "failed",
            "item_id": pending_item.id,
            "error": error_msg
        }

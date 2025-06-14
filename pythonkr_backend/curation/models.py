from django.db import models
from django.utils.text import slugify
from .utils import get_summary_from_url, translate_to_korean, categorize_summary 
import readtime
import os
from datetime import timedelta, datetime
from django.utils import timezone
import pytz


def rss_item_upload_path(instance, filename):
    """Generate upload path for RSS item crawled content"""
    now = datetime.now()
    return f"rssitem-crawling/{now.year}/{now.month:02d}/{instance.id}-crawl.md"


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, help_text="The name of the category (e.g., 'Web Development', 'LLM').")
    slug = models.SlugField(max_length=100, unique=True, help_text="A URL-friendly slug for the category.", blank=True) # Optional but good practice

    def save(self, *args, **kwargs):
        # Auto-generate slug if blank (optional)
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories" # Nicer plural name in admin
        ordering = ['name'] # Optional: Order categories alphabetically


class Article(models.Model):
    url = models.URLField(unique=True, max_length=2048, help_text="The unique URL of the article.")
    title = models.CharField(max_length=512, blank=True, help_text="Article title (can be fetched automatically or entered manually).")
    summary = models.TextField(blank=True, help_text="AI-generated summary of the article.")
    summary_ko = models.TextField(blank=True, help_text="Korean translation of the summary (via OpenAI).")
    reading_time_minutes = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Estimated reading time in minutes (based on full article content)."
    )
    categories = models.ManyToManyField(
        Category,
        blank=True, # An article might have no categories initially or after processing
        related_name='articles', # How Category model refers back to Articles
        help_text="Select one or more categories for this article."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or self.url
        
    def calculate_reading_time(self, full_text: str):
        """
        Calculates reading time based on the provided text.
        """
        if full_text:
            try:
                result = readtime.of_text(full_text)
                self.reading_time_minutes = result.minutes
            except Exception as e:
                print(f"Error calculating reading time for article {self.id}: {e}")
                self.reading_time_minutes = None # Set to None on calculation error
        else:
            self.reading_time_minutes = None

    def fetch_and_summarize(self) -> str:
        """
        Fetches content, calculates reading time on full text, generates summary,
        translates summary, and saves all results.
        """
        if not self.url:
            return "Error: No URL provided."

        try:
            summary_text = get_summary_from_url(self.url)

            self.calculate_reading_time(summary_text) # Call updated method

            if not summary_text:
                self.summary = ""
                self.summary_ko = ""
                self.save(update_fields=['title', 'summary', 'summary_ko', 'reading_time_minutes', 'updated_at'])
                return "Error extracting summary. Other details saved."

            self.summary = summary_text # Set summary

            categorization_status = "Categorization skipped (no summary)."
            if self.summary: # Only categorize if summary was successful
                 categorization_status = self.assign_categories() # Call the revised method
                 print(f"Categorization status for article {self.id}: {categorization_status}")

            translation_status = self.translate_summary_to_korean() # Call translation
            print(f"Translation status for article {self.id}: {translation_status}")
            translation_failed = "Error" in translation_status

            self.save(update_fields=[
                'title',
                'summary',
                'summary_ko',
                'reading_time_minutes',
                'updated_at'
            ])

            translation_failed = "Error" in translation_status # Re-evaluate this variable if needed

            final_message = "Fetch, Read Time, Summary completed."
            final_message += " Translation failed." if translation_failed else " Translation completed."
            final_message += f" {categorization_status}" # Include categorization status message
            return final_message

        except ImportError as e:
            return f"Error with required libraries: {str(e)}"
        except Exception as e:
             print(f"Unexpected error during fetch/summarize/translate for {self.id}: {e}")
             return f"Unexpected error processing article: {str(e)}"
            
    def translate_summary_to_korean(self):
        """
        Translates the summary to Korean using the OpenAI API via Langchain.
        """
        if not self.summary:
            self.summary_ko = ""
            return "No summary to translate."

        try:
            translated_text = translate_to_korean(self.summary)

            self.summary_ko = translated_text.strip() if translated_text else ""
            self.save(update_fields=['summary_ko', 'updated_at'])
            return "Summary translated successfully using OpenAI."

        except Exception as e:
            print(f"Error translating article {self.id} using OpenAI: {e}")
            self.summary_ko = "" # Clear on error
            self.save(update_fields=['summary_ko', 'updated_at'])
            return f"Error during OpenAI translation: {str(e)[:150]}"
            
    def assign_categories(self):
        """Assigns multiple categories based on the summary using an LLM."""
        if not self.summary:
            self.categories.clear() # Clear existing categories if no summary
            return "Error: No summary available to categorize."

        try:
            defined_category_names = [
                'Web Development', 'MLOps', 'Large Language Models',
                'Data Science', 'AI General', 'Software Engineering', 'Other'
            ]
            category_objects = []
            created_names = []
            for name in defined_category_names:
                cat, created = Category.objects.get_or_create(name=name)
                category_objects.append(cat)
                if created:
                  created_names.append(name)
                  cat.save()

            if created_names:
                print(f"Ensured categories exist. Created new: {created_names}")

            response_text = categorize_summary(self.summary, defined_category_names).replace("'", "").replace('"', "")
            assigned_category_names = [name.strip() for name in response_text.split(',') if name.strip()]

            valid_categories = Category.objects.filter(name__in=assigned_category_names).filter(name__in=defined_category_names)
            valid_category_names = list(valid_categories.values_list('name', flat=True))

            print(f"LLM suggested: {assigned_category_names}, Validated & Found: {valid_category_names}")

            self.categories.clear() # Remove old associations first
            if valid_categories:
                self.categories.add(*valid_categories) # Add the new set using the splat operator
                return f"Article categories set to: {', '.join(valid_category_names)}."
            elif 'Other' in assigned_category_names:
                 other_cat = Category.objects.filter(name='Other').first()
                 if other_cat:
                     self.categories.add(other_cat)
                     return "Article category set to: Other."

            return "Warning: No valid categories assigned based on LLM response."

        except Exception as e:
            print(f"Error categorizing article {self.id}: {e}")
            return f"Error during categorization: {str(e)[:150]}"


# LicenseType Enum for license choices
class LicenseType(models.TextChoices):
    MIT = 'MIT', 'MIT License'
    BSD2 = 'BSD-2-Clause', 'BSD 2-Clause License'
    APACHE2 = 'Apache-2.0', 'Apache License 2.0'
    GPLV3 = 'GPL-3.0', 'GNU GPL v3'
    LGPLV3 = 'LGPL-3.0', 'GNU LGPL v3'
    MPL2 = 'MPL-2.0', 'Mozilla Public License 2.0'
    CC0 = 'CC0-1.0', 'CC0 1.0 Universal'
    CC_BY = 'CC-BY-4.0', 'Creative Commons Attribution 4.0'
    CC_BY_SA = 'CC-BY-SA-4.0', 'Creative Commons Attribution-ShareAlike 4.0'
    PROPRIETARY = 'PROPRIETARY', 'Proprietary License'


class CrawlingSources(models.Model):
    name = models.CharField(
        max_length=256,
        verbose_name="Crawling Source Name"
    )
    rss_feed_url = models.URLField(
        null=True,
        blank=True,
        verbose_name="RSS Feed URL"
    )
    fetch_interval = models.DurationField(
        default=timedelta(minutes=60),
        help_text="크롤링 주기 (시간 단위)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.rss_feed_url or 'No RSS URL'})"


class CrawlingSite(models.Model):
    source = models.ForeignKey(
        CrawlingSources,
        on_delete=models.CASCADE,
        related_name="sites",
        help_text="이 사이트가 속한 크롤링 소스"
    )
    name = models.CharField(
        max_length=256,
        verbose_name="Site Name"
    )
    url = models.URLField(
        unique=True,
        db_index=True,
        help_text="사이트의 기본 URL"
    )
    license_type = models.CharField(
        max_length=20,
        choices=LicenseType.choices,
        default=LicenseType.MIT,
        help_text="Select the license type for the crawling source."
    )
    copyright_notice_required = models.BooleanField(
        default=False,
        help_text="저작권 고지가 필요한지 여부"
    )
    copyright_link = models.URLField(
        null=True,
        blank=True,
        help_text="저작권 고지 링크 (필요한 경우)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        # 예: 특정 라이선스(GPL 계열)는 copyright_link가 반드시 필요
        if self.license_type in [LicenseType.GPLV3, LicenseType.LGPLV3] and not self.copyright_link:
            from django.core.exceptions import ValidationError
            raise ValidationError({
                'copyright_link': "GPL 계열 라이선스의 경우 반드시 저작권 고지 링크를 입력해야 합니다."
            })

    def save(self, *args, **kwargs):
        # Set copyright_notice_required based on license_type
        if self.license_type in [LicenseType.CC0, LicenseType.PROPRIETARY]:
            self.copyright_notice_required = False
        else:
            self.copyright_notice_required = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.url})"


class RSSFeed(models.Model):
    name = models.CharField(max_length=200, help_text="RSS 피드 이름")
    url = models.URLField(unique=True, help_text="RSS 피드 URL")
    is_active = models.BooleanField(default=True, help_text="활성화 여부")
    last_fetched = models.DateTimeField(null=True, blank=True, help_text="마지막 크롤링 시간")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "RSS Feed"
        verbose_name_plural = "RSS Feeds"


class RSSItem(models.Model):
    CRAWLING_STATUS_CHOICES = [
        ('pending', '크롤링 대기'),
        ('completed', '크롤링 완료'),
        ('failed', '크롤링 실패'),
    ]
    
    TRANSLATE_STATUS_CHOICES = [
        ('pending', '번역 대기'),
        ('completed', '번역 완료'),
        ('failed', '번역 실패'),
    ]
    
    feed = models.ForeignKey(
        RSSFeed,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="이 아이템이 속한 RSS 피드"
    )
    title = models.CharField(max_length=500, help_text="제목")
    link = models.URLField(unique=True, help_text="아이템 URL")
    description = models.TextField(blank=True, help_text="설명")
    author = models.CharField(max_length=200, blank=True, help_text="작성자")
    category = models.CharField(max_length=200, blank=True, help_text="카테고리")
    guid = models.CharField(max_length=500, blank=True, unique=True, help_text="GUID")
    pub_date = models.DateTimeField(null=True, blank=True, help_text="발행일")
    crawling_status = models.CharField(
        max_length=20,
        choices=CRAWLING_STATUS_CHOICES,
        default='pending',
        help_text="크롤링 상태"
    )
    crawled_content = models.FileField(
        upload_to=rss_item_upload_path,
        blank=True,
        null=True,
        help_text="크롤링된 마크다운 콘텐츠 파일"
    )
    crawled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="크롤링 완료 시간"
    )
    error_message = models.TextField(
        blank=True,
        help_text="크롤링 실패 시 에러 메시지"
    )
    translate_status = models.CharField(
        max_length=20,
        choices=TRANSLATE_STATUS_CHOICES,
        default='pending',
        help_text="번역 상태"
    )
    translate_error_message = models.TextField(
        blank=True,
        help_text="번역 실패 시 에러 메시지"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "RSS Item"
        verbose_name_plural = "RSS Items"
        ordering = ['-pub_date', '-created_at']


class CrawlURL(models.Model):
    site = models.ForeignKey(
        CrawlingSite,
        on_delete=models.CASCADE,
        related_name="crawl_urls",
        help_text="이 URL이 속한 사이트"
    )
    url = models.URLField(
        unique=True,
        verbose_name="Crawling Article URL"
    )
    STATUS_CHOICES = [
        ('pending', '대기 중'),
        ('success', '성공'),
        ('failed', '실패'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="크롤링 상태"
    )
    crawl_creation_date = models.DateTimeField(
        auto_now_add=True,
        help_text="크롤링이 생성된 시각(자동 기록)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.url} [{self.get_status_display()}]"


class CrawledContent(models.Model):
    crawl_url = models.ForeignKey(
        CrawlURL,
        on_delete=models.CASCADE,
        related_name="contents",
        help_text="원본 URL 객체"
    )
    title = models.CharField(
        max_length=512,
        blank=True,
        help_text="기사 제목"
    )
    content = models.TextField(
        help_text="크롤링 본문"
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="원문 게시 시각"
    )
    is_visible = models.BooleanField(
        default=False,
        help_text="라이선스/저작권 검증 결과 콘텐츠 노출 여부"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or self.crawl_url.url


class LLMService(models.Model):
    LLM_PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('claude', 'Claude'),
        ('gemini', 'Gemini'),
    ]
    
    provider = models.CharField(
        max_length=20,
        choices=LLM_PROVIDER_CHOICES,
        unique=True,
        help_text="LLM 서비스 제공자"
    )
    priority = models.PositiveIntegerField(
        help_text="우선순위 (1이 가장 높음)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="서비스 활성화 여부"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_provider_display()} (Priority: {self.priority})"

    @classmethod
    def get_llm_provider_model(cls):
        """
        Calculate today's usage and return available provider and model based on priority.
        Returns tuple: (provider, model_name) or (None, None) if no models available.
        """
        # Model configurations with daily limits
        MODEL_CONFIGS = {
            'google-gla:gemini-2.5-pro-preview-06-05': {
                'daily_requests': 25,
                'rpm': 5,
                'tpm': 250000,
                'daily_tokens': 1000000,
                'provider': 'gemini'
            },
            'google-gla:gemini-2.5-flash-preview-05-20': {
                'daily_requests': 500,
                'rpm': 10,
                'tpm': 250000,
                'daily_tokens': None,  # Not specified
                'provider': 'gemini'
            },
            'openai:gpt-4.1-2025-04-14': {
                'daily_tokens': 250000,  # Combined with gpt-4.5-preview-2025-02-27
                'provider': 'openai',
                'combined_with': ['openai:gpt-4.5-preview-2025-02-27']
            },
            'openai:gpt-4.5-preview-2025-02-27': {
                'daily_tokens': 250000,  # Combined with gpt-4.1-2025-04-14
                'provider': 'openai',
                'combined_with': ['openai:gpt-4.1-2025-04-14']
            },

            'openai:gpt-4.1-mini-2025-04-14': {
                'daily_tokens': 2500000,
                'provider': 'openai'
            },
            'anthropic:claude-3-5-haiku-latest': {
                'provider': 'claude'
            },
            'anthropic:claude-sonnet-4-0': {
                'provider': 'claude'
            }
        }

        # Get active services ordered by priority
        active_services = cls.objects.filter(is_active=True).order_by('priority')
        
        for service in active_services:
            available_models = cls._get_available_models_for_provider(service.provider, MODEL_CONFIGS)
            if available_models:
                return service.provider, available_models[0]
        
        return None, None

    @classmethod
    def _get_available_models_for_provider(cls, provider, model_configs):
        """Get available models for a specific provider based on usage limits."""
        available_models = []
        
        if provider == 'gemini':
            # Check Google Gemini models with Pacific Time reset
            pacific_tz = pytz.timezone('US/Pacific')
            now_pacific = timezone.now().astimezone(pacific_tz)
            start_of_day_pacific = now_pacific.replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_day_utc = start_of_day_pacific.astimezone(pytz.UTC)
            
            for model_key, config in model_configs.items():
                if not model_key.startswith('google-gla:'):
                    continue
                    
                model_name = model_key.split(':', 1)[1]
                today_usage = LLMUsage.objects.filter(
                    model_name=model_key,
                    date__gte=start_of_day_utc
                ).aggregate(
                    total_tokens=models.Sum(models.F('total_tokens')),
                    total_requests=models.Count('id')
                )
                
                total_tokens = today_usage['total_tokens'] or 0
                total_requests = today_usage['total_requests'] or 0
                
                # Check daily limits
                if config.get('daily_requests') and total_requests >= config['daily_requests']:
                    continue
                if config.get('daily_tokens') and total_tokens >= config['daily_tokens']:
                    continue
                    
                available_models.append(model_name)
        
        elif provider == 'openai':
            # Check OpenAI models with UTC midnight reset
            today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Handle combined quota models (gpt-4.5 and gpt-4.1)
            combined_models = ['openai:gpt-4.5-preview-2025-02-27', 'openai:gpt-4.1-2025-04-14']
            combined_usage = LLMUsage.objects.filter(
                model_name__in=combined_models,
                date__gte=today_start
            ).aggregate(
                total_tokens=models.Sum(models.F('total_tokens'))
            )
            combined_tokens = combined_usage['total_tokens'] or 0
            
            # Check individual models
            for model_key, config in model_configs.items():
                if not model_key.startswith('openai:'):
                    continue
                    
                model_name = model_key.split(':', 1)[1]
                
                if model_key in combined_models:
                    # Check combined quota
                    if combined_tokens < 250000:
                        available_models.append(model_name)
                else:
                    # Check individual quota (gpt-4.1-mini)
                    today_usage = LLMUsage.objects.filter(
                        model_name=model_key,
                        date__gte=today_start
                    ).aggregate(
                        total_tokens=models.Sum(models.F('total_tokens'))
                    )
                    total_tokens = today_usage['total_tokens'] or 0
                    
                    if total_tokens < config['daily_tokens']:
                        available_models.append(model_name)
        
        elif provider == 'claude':
            # Claude as fallback - assume always available
            available_models = ['claude-sonnet-4-0']
        
        return available_models

    class Meta:
        verbose_name = "LLM Service"
        verbose_name_plural = "LLM Services"
        ordering = ['priority']


class LLMUsage(models.Model):
    date = models.DateTimeField(
        auto_now_add=True,
        help_text="사용 날짜"
    )
    model_name = models.CharField(
        max_length=100,
        help_text="사용된 모델명"
    )
    input_tokens = models.PositiveIntegerField(
        help_text="입력 토큰 수"
    )
    output_tokens = models.PositiveIntegerField(
        help_text="출력 토큰 수"
    )
    total_tokens = models.PositiveIntegerField(
        help_text="총 토큰 수"
        # gemini 가 다른 경우가 있어서 별도로 저장.
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.model_name} - {self.date} (In: {self.input_tokens}, Out: {self.output_tokens})"

    class Meta:
        verbose_name = "LLM Usage"
        verbose_name_plural = "LLM Usage"
        ordering = ['-date', '-created_at']

def translated_item_upload_path(instance, filename):
    """Generate upload path for RSS item translated content"""
    now = datetime.now()
    return f"tr/{now.year}/{now.month:02d}/{instance.id}-ko.md"


class TranslatedContent(models.Model):
    title = models.CharField(
        max_length=512,
        help_text="제목"
    )
    slug = models.SlugField(
        max_length=512,
        help_text="slug"
    )
    description = models.TextField(
        help_text="설명"
    )
    tags = models.JSONField(
        default=list,
        help_text="태그"
    )
    written_date = models.DateField(
        help_text="작성 일자",
        blank=True,
        null=True,
    )
    author = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="작성자"
    )
    content = models.FileField(
        upload_to=translated_item_upload_path,
        blank=True,
        null=True,
        help_text="번역된 마크다운 콘텐츠 파일"
    )

    model_name = models.CharField(
        max_length=100,
        help_text="사용된 모델명"
    )

    source_rss_item = models.ForeignKey(
        RSSItem,
        on_delete=models.CASCADE,
        related_name="translated_contents",
        null=True,
        help_text="원본 RSS 아이템"
    )
    source_url = models.URLField(
        help_text="원본 URL"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

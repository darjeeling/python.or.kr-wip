from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Article,
    Category,
    RSSFeed,
    RSSItem,
    LLMService,
    LLMUsage,
    TranslatedContent,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}  # Auto-populate slug from name


@admin.action(description="Fetch content, summarize, and translate selected articles")
def summarize_selected_articles(modeladmin, request, queryset):
    success_count = 0
    errors = []

    for article in queryset:
        result = article.fetch_and_summarize()
        if result.startswith("Error"):
            errors.append(f"{article.url}: {result}")
        else:
            success_count += 1

    if success_count > 0:
        modeladmin.message_user(
            request,
            f"Successfully processed {success_count} article(s) (fetch, summarize, translate).",
            messages.SUCCESS,
        )

    if errors:
        error_message = "Errors encountered:\n" + "\n".join(errors)
        modeladmin.message_user(request, error_message, messages.WARNING)


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = (
        "url",
        "title",
        "display_categories",
        "summary_preview",
        "summary_ko_preview",
        "reading_time_minutes",
        "updated_at",
        "created_at",
    )
    list_filter = ("categories", "created_at", "updated_at")
    search_fields = ("url", "title", "summary", "summary_ko", "categories__name")
    readonly_fields = (
        "created_at",
        "updated_at",
        "summary",
        "summary_ko",
        "reading_time_minutes",
    )
    actions = [summarize_selected_articles]
    filter_horizontal = ("categories",)

    fieldsets = (
        ("Article Information", {"fields": ("url", "title", "categories")}),
        (
            "Generated Content",
            {
                "fields": ("summary", "summary_ko", "reading_time_minutes"),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Categories")
    def display_categories(self, obj):
        """Displays categories as a comma-separated string in the list view."""
        if obj.categories.exists():
            return ", ".join([category.name for category in obj.categories.all()])
        return "-"  # Or None, or empty string

    def get_readonly_fields(self, request, obj=None):
        # Make 'categories' always read-only as it's set by the LLM
        readonly = list(super().get_readonly_fields(request, obj))
        if "categories" not in readonly:
            readonly.append("categories")
        return readonly

    @admin.display(description="Summary Preview")
    def summary_preview(self, obj):
        if obj.summary:
            preview = obj.summary[:100]
            return f"{preview}..." if len(obj.summary) > 100 else preview
        return "No summary available"

    @admin.display(description="Korean Summary Preview")
    def summary_ko_preview(self, obj):
        if obj.summary_ko:
            if obj.summary_ko.startswith("Translation Error"):
                return obj.summary_ko
            preview = obj.summary_ko[:50]
            return f"{preview}..." if len(obj.summary_ko) > 50 else preview
        return "No Korean summary"


@admin.register(RSSFeed)
class RSSFeedAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "url",
        "is_active",
        "is_newsletter",
        "last_fetched",
        "item_count",
        "created_at",
    )
    list_filter = ("is_active", "is_newsletter", "created_at", "last_fetched")
    search_fields = ("name", "url")
    readonly_fields = ("last_fetched", "created_at", "updated_at")

    fieldsets = (
        ("Feed Information", {"fields": ("name", "url", "is_active", "is_newsletter")}),
        (
            "Status",
            {
                "fields": ("last_fetched", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Items Count")
    def item_count(self, obj):
        return obj.items.count()

    actions = ["crawl_selected_feeds"]

    @admin.action(description="Crawl selected RSS feeds")
    def crawl_selected_feeds(self, request, queryset):
        from .tasks import crawl_single_rss_feed

        success_count = 0
        total_new_items = 0
        errors = []

        for feed in queryset:
            try:
                result = crawl_single_rss_feed(feed.id)
                success_count += 1
                total_new_items += result.get("new_items", 0)
            except Exception as e:
                errors.append(f"{feed.name}: {str(e)}")

        if success_count > 0:
            self.message_user(
                request,
                f"Successfully crawled {success_count} feed(s). Found {total_new_items} new items.",
                messages.SUCCESS,
            )

        if errors:
            error_message = "Errors encountered:\n" + "\n".join(errors)
            self.message_user(request, error_message, messages.WARNING)


@admin.register(RSSItem)
class RSSItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "feed",
        "language",
        "crawling_status",
        "translate_status",
        "translation_allowed_display",
        "author",
        "pub_date",
        "crawled_at",
        "created_at",
    )
    list_filter = (
        "feed",
        "language",
        "crawling_status",
        "translate_status",
        "is_translation_allowed",
        "pub_date",
        "created_at",
        "author",
    )
    search_fields = ("title", "description", "author", "link", "license_type")
    readonly_fields = ("created_at", "crawled_at", "confidence_score")
    date_hierarchy = "pub_date"

    def get_fieldsets(self, request, obj=None):
        """Dynamic fieldsets based on content language and analysis status."""
        base_fieldsets = [
            (
                "⚠️ 법적 고지",
                {
                    "fields": (),
                    "description": (
                        "<div style='background-color: #fff3cd; border: 1px solid #ffeaa7; "
                        "padding: 15px; border-radius: 5px; margin-bottom: 20px;'>"
                        "<strong>🚨 중요 안내:</strong><br>"
                        "본 AI 분석 결과는 참고용이며 <strong>법적 효력이 없습니다</strong>. "
                        "콘텐츠의 최종 사용 결정은 반드시 관리자의 책임하에 이루어져야 하며, "
                        "필요시 법무 전문가의 자문을 받으시기 바랍니다.<br>"
                        "<em>AI analysis results are for reference only and have no legal validity. "
                        "Final content usage decisions must be made under administrator responsibility.</em>"
                        "</div>"
                    ),
                },
            ),
            (
                "Item Information",
                {"fields": ("feed", "title", "link", "author", "category", "source_item")},
            ),
            ("Content", {"fields": ("description",), "classes": ("collapse",)}),
        ]
        
        # Language and processing fields
        if obj and obj.language:
            if obj.language == 'ko':
                # Korean content - show summary
                base_fieldsets.append((
                    "🇰🇷 Korean Content Processing",
                    {
                        "fields": ("language", "summary"),
                        "description": "한국어 콘텐츠는 AI 요약이 생성됩니다.",
                    },
                ))
            else:
                # Foreign content - show copyright analysis
                base_fieldsets.append((
                    "🌐 Copyright Analysis (Foreign Content)",
                    {
                        "fields": (
                            "language",
                            "license_type",
                            "is_translation_allowed",
                            "attribution_required",
                            "confidence_score",
                            "reasoning",
                        ),
                        "description": "외국어 콘텐츠의 저작권 분석 결과입니다.",
                    },
                ))
        else:
            # No language detected yet
            base_fieldsets.append((
                "🔍 Content Analysis",
                {
                    "fields": ("language",),
                    "description": "콘텐츠 분석이 완료되면 언어별 처리 결과가 표시됩니다.",
                },
            ))
        
        # Standard status fields
        base_fieldsets.extend([
            (
                "Crawling Status",
                {
                    "fields": (
                        "crawling_status",
                        "crawled_content",
                        "crawled_at",
                        "error_message",
                    ),
                },
            ),
            (
                "Translation Status",
                {
                    "fields": ("translate_status", "translate_error_message"),
                },
            ),
            (
                "Metadata",
                {"fields": ("guid", "pub_date", "created_at"), "classes": ("collapse",)},
            ),
        ])
        
        return base_fieldsets

    @admin.display(description="Translation Allowed", boolean=True)
    def translation_allowed_display(self, obj):
        """Display translation permission status with visual indicator."""
        if obj.language == 'ko':
            return None  # Not applicable for Korean content
        return obj.is_translation_allowed

    @admin.display(description="Source Type")
    def source_type_display(self, obj):
        """Display whether item is from newsletter or regular feed."""
        if obj.source_item:
            return "📧 Newsletter Extract"
        elif obj.feed.is_newsletter:
            return "📧 Newsletter Original"
        return "📰 Regular Feed"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("feed")


@admin.register(LLMService)
class LLMServiceAdmin(admin.ModelAdmin):
    list_display = ("provider", "priority", "is_active", "updated_at", "created_at")
    list_filter = ("is_active", "provider", "created_at")
    search_fields = ("provider",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Service Configuration", {"fields": ("provider", "priority", "is_active")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    list_display = (
        "model_name",
        "date",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "created_at",
    )
    list_filter = ("date", "model_name", "created_at")
    search_fields = ("model_name",)
    readonly_fields = ("date", "created_at")
    date_hierarchy = "date"

    fieldsets = (
        (
            "Usage Information",
            {"fields": ("model_name", "date", "input_tokens", "output_tokens")},
        ),
        ("Metadata", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    @admin.display(description="Total Tokens")
    def total_tokens(self, obj):
        return obj.input_tokens + obj.output_tokens

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TranslatedContent)
class TranslatedContentAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "view_link",
        "slug",
        "author",
        "written_date",
        "model_name",
        "source_rss_item",
        "created_at",
    )
    list_filter = ("written_date", "model_name", "created_at", "author")
    search_fields = ("title", "slug", "description", "author", "source_url")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "written_date"

    fieldsets = (
        (
            "Content Information",
            {
                "fields": (
                    "title",
                    "slug",
                    "description",
                    "tags",
                    "author",
                    "written_date",
                )
            },
        ),
        ("Content File", {"fields": ("content",)}),
        (
            "Source Information",
            {"fields": ("source_rss_item", "source_url", "model_name")},
        ),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="View")
    def view_link(self, obj):
        if obj.pk:
            url = reverse("curation:translated_content_detail", args=[obj.pk])
            return format_html('<a href="{}" target="_blank">보기</a>', url)
        return "-"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("source_rss_item", "source_rss_item__feed")
        )

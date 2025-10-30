from wagtail.models import Page
from wagtail.fields import RichTextField
from wagtail.admin.panels import FieldPanel
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.apps import apps
import httpx
import markdown


class PKBasePage(Page):
    class Meta:
        abstract = True

    def get_context(self, request, *args, **kwargs):
        "common context for Python Korea"
        context = super().get_context(request, *args, **kwargs)

        SponsorPageModel = apps.get_model("pythonkr", "PKSponsors")
        try:
            sponsor_page = SponsorPageModel.objects.get()
        except ObjectDoesNotExist:
            return context

        context["looking_for_sponsors"] = sponsor_page.is_looking_for_sponsors
        context["current_sponsors"] = []

        return context


class PKSponsors(PKBasePage):
    content = RichTextField()
    is_looking_for_sponsors = models.BooleanField(default=False)

    parent_page_types = ["pythonkr.PKHomePage"]

    content_panels = Page.content_panels + [
        FieldPanel("content"),
        FieldPanel("is_looking_for_sponsors"),
    ]


class PKPage(PKBasePage):
    template = "pythonkr/pk_page.html"
    content = RichTextField(blank=True)

    parent_page_types = ["pythonkr.PKHomePage"]

    content_panels = Page.content_panels + [
        FieldPanel("content"),
    ]


class PKDocPage(PKBasePage):
    template = "pythonkr/pk_markdown_doc.html"

    content = RichTextField(blank=True)
    markdown_url = models.URLField(blank=True, null=True)
    parent_page_types = ["pythonkr.PKHomePage"]

    content_panels = Page.content_panels + [
        FieldPanel("content"),
        FieldPanel("markdown_url"),
    ]

    def _render_markdown(self, markdown_text):
        return markdown.markdown(markdown_text)

    def get_rendered_content(self):
        if self.markdown_url:
            response = httpx.get(self.markdown_url)
            if response.status_code == 200:
                return self._render_markdown(response.text)
        return self.content

    def save(self, *args, **kwargs):
        if self.markdown_url:
            response = httpx.get(self.markdown_url)
            if response.status_code == 200:
                self.content = self._render_markdown(response.text)
        super().save(*args, **kwargs)


class PKHomePage(PKBasePage):
    template = "pythonkr/pk_home.html"
    content = RichTextField(blank=True)

    subpage_types = [
        PKPage,
        PKDocPage,
        'pythonkr.PKEvents',
    ]

    content_panels = Page.content_panels + [
        FieldPanel("content"),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        return context

class PKEvent(PKBasePage):
    template = "pythonkr/event.html"

    # Date & Time fields
    event_startdate = models.DateField(help_text="이벤트 시작 날짜")
    event_enddate = models.DateField(
        blank=True,
        null=True,
        help_text="이벤트 종료 날짜 (다일 이벤트인 경우)"
    )
    time_from = models.TimeField(
        blank=True,
        null=True,
        help_text="시작 시간"
    )
    time_to = models.TimeField(
        blank=True,
        null=True,
        help_text="종료 시간"
    )

    # Location
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="이벤트 장소"
    )

    # Short description for list view
    short_description = models.CharField(
        max_length=200,
        blank=True,
        help_text="이벤트 목록에 표시될 간단한 설명"
    )

    # Content
    content = RichTextField(blank=True, help_text="이벤트 상세 내용")

    # External link
    external_homepage = models.URLField(
        null=True,
        blank=True,
        help_text="외부 홈페이지 링크"
    )

    # Visibility
    listed = models.BooleanField(
        default=False,
        help_text="전체 이벤트 리스트에 노출여부"
    )

    parent_page_types = ['pythonkr.PKEvents']

    content_panels = Page.content_panels + [
        FieldPanel('event_startdate'),
        FieldPanel('event_enddate'),
        FieldPanel('time_from'),
        FieldPanel('time_to'),
        FieldPanel('location'),
        FieldPanel('short_description'),
        FieldPanel('content'),
        FieldPanel('external_homepage'),
        FieldPanel('listed'),
    ]

    @property
    def is_multiday(self):
        """Check if this is a multi-day event"""
        return self.event_enddate and self.event_enddate != self.event_startdate

class PKEvents(PKBasePage):
    template = "pythonkr/event_list.html"
    content = RichTextField(blank=True, help_text="이벤트 페이지 소개 내용")

    parent_page_types = ['pythonkr.PKHomePage']
    subpage_types = ['pythonkr.PKEvent']

    content_panels = Page.content_panels + [
        FieldPanel('content'),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Get listed events, ordered by date (newest first)
        events = (
            PKEvent.objects.child_of(self)
            .filter(listed=True)
            .live()
            .order_by("-event_startdate")
        )

        # Simple pagination (12 per page)
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

        paginator = Paginator(events, 12)
        page = request.GET.get('page', 1)

        try:
            events_page = paginator.page(page)
        except PageNotAnInteger:
            events_page = paginator.page(1)
        except EmptyPage:
            events_page = paginator.page(paginator.num_pages)

        context["events"] = events_page
        return context
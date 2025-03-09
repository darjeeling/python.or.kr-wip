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
        "common context for PK"
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
    body = RichTextField(blank=True)

    subpage_types = [
        PKPage,
        PKDocPage,
    ]

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        return context
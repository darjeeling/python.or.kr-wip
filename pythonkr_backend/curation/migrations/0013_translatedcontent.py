# Generated by Django 5.2.1 on 2025-06-14 05:26

import curation.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("curation", "0012_llmusage_total_tokens"),
    ]

    operations = [
        migrations.CreateModel(
            name="TranslatedContent",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("title", models.CharField(help_text="제목", max_length=512)),
                ("slug", models.SlugField(help_text="slug", max_length=512)),
                ("description", models.TextField(help_text="설명")),
                ("tags", models.JSONField(default=list, help_text="태그")),
                (
                    "written_date",
                    models.DateField(blank=True, help_text="작성 일자", null=True),
                ),
                (
                    "author",
                    models.CharField(
                        blank=True, help_text="작성자", max_length=100, null=True
                    ),
                ),
                (
                    "content",
                    models.FileField(
                        blank=True,
                        help_text="번역된 마크다운 콘텐츠 파일",
                        null=True,
                        upload_to=curation.models.translated_item_upload_path,
                    ),
                ),
                (
                    "model_name",
                    models.CharField(help_text="사용된 모델명", max_length=100),
                ),
                ("source_url", models.URLField(help_text="원본 URL")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source_rss_item",
                    models.ForeignKey(
                        help_text="원본 RSS 아이템",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="translated_contents",
                        to="curation.rssitem",
                    ),
                ),
            ],
        ),
    ]

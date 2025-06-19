from django.shortcuts import render, get_object_or_404
from .models import TranslatedContent
import os


def translated_content_detail(request, id):
    """Display TranslatedContent detail with markdown content"""
    content = get_object_or_404(TranslatedContent, id=id)

    # Read markdown content from file
    markdown_content = ""
    if (
        content.content
        and hasattr(content.content, "path")
        and os.path.exists(content.content.path)
    ):
        try:
            with open(content.content.path, "r", encoding="utf-8") as f:
                markdown_content = f.read()
        except Exception as e:
            markdown_content = f"Error reading content file: {str(e)}"
    else:
        markdown_content = "No content file available."

    context = {
        "content": content,
        "markdown_content": markdown_content,
    }

    return render(request, "curation/translated_content_detail.html", context)

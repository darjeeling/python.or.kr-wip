from django.urls import path
from . import views

app_name = "curation"

urlpatterns = [
    path(
        "tr/<int:id>/",
        views.translated_content_detail,
        name="translated_content_detail",
    ),
]

from django.urls import path, re_path
from .views import messages_view, message_detail_view, reply_view, reply_detail_view

urlpatterns = [
    path("messages/", messages_view, name="contact_messages"),
    path("messages/<int:pk>/", message_detail_view, name="contact_message_detail"),
    path("messages/<int:pk>/reply/", reply_view, name="contact_message_reply"),
    path("replies/<int:pk>/", reply_detail_view, name="contact_reply_detail"),
]

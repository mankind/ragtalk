from django.urls import path 

from . import views 
app_name = "echo"

urlpatterns = [
    path("upload/", views.upload_document, name="upload_document"),
]

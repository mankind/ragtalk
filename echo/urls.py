from django.urls import path 

from . import views 
app_name = "echo"

urlpatterns = [
    path("", views.index, name="index"),    
    path("upload/", views.upload_document, name="upload_document"),
]

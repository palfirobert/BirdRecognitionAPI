"""
URL configuration for BirdRecognitionAPI project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.getData),
    path('predictionwithlocation', views.getDataWithLocation),
    path('login', views.login),
    path('signup', views.signup),
    path('updateuserdetails', views.updateUserDetails),
    path('addsound', views.insert_sound),
    path('downloadusersounds', views.download_user_sounds),
    path('deletesound', views.delete_sound),
    path('getcreationdate', views.get_creation_date_of_sounds),
    path('addobservationsheet', views.insert_observation),
    path('observations/<str:user_id>/', views.get_observations_by_user),
    path('deleteobservationsheet',views.delete_observation)
]

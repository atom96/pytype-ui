"""pytype URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
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
from main_view.views import modules_view, module_view, function_view, similarity_view, modules_similarity_view, all_packages_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', all_packages_view),
    path('module/<str:repo_name>', modules_view),
    path('module/<str:repo_name>/<str:module_prefix>', modules_view),
    path('flat_module/<str:repo_name>/<str:module_name>/<str:add_init>', module_view),
    path('similarity/<str:repo_name>/<str:module_name>/<str:add_init>', similarity_view),
    path('module_similarity/<str:repo_name>', modules_similarity_view),
    path('module_similarity/<str:repo_name>/<str:module_prefix>', modules_similarity_view),
    path('function/<str:repo_name>/<str:module_name>/<str:function_name>/<str:add_init>', function_view)
]

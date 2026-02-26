"""
URL configuration for diet_agent_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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

# diet_agent_backend/urls.py
from django.contrib import admin
from django.urls import path, include  # 记得导入 include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('agent.urls')), # 所有 agent 的接口都以 /api/ 开头
]
from django.urls import path
from .views import AgentChatView, UserProfileView # 引入新的 View

urlpatterns = [
    path('chat/', AgentChatView.as_view(), name='agent_chat'),
    path('profile/', UserProfileView.as_view(), name='user_profile'), # 新增这行
]
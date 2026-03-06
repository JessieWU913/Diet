from django.urls import path
from .views import AgentChatView, UserProfileView, UserAuthView, FeedbackView, RecipeDetailView

urlpatterns = [
    path('chat/', AgentChatView.as_view(), name='chat'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('auth/', UserAuthView.as_view(), name='auth'),
    path('feedback/', FeedbackView.as_view(), name='feedback'),
    path('recipe/', RecipeDetailView.as_view(), name='recipe'),
]
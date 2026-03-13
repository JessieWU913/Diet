from django.urls import path
from .views import (
    AgentChatView, UserProfileView, UserAuthView, FeedbackView,
    RecipeDetailView, MealEventView, FoodSearchView, DietLogView,
    NutritionSummaryView, RecommendMealsView, FavoriteIngredientsView,
    SimilarIngredientView, FoodConflictView, UserCollectionView, ChatHistoryView,
    IngredientDetailView
)

urlpatterns = [
    path('chat/', AgentChatView.as_view(), name='chat'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('auth/', UserAuthView.as_view(), name='auth'),
    path('feedback/', FeedbackView.as_view(), name='feedback'),
    path('recipe/', RecipeDetailView.as_view(), name='recipe'),
    path('meal-event/', MealEventView.as_view(), name='meal_event'),
    path('food-search/', FoodSearchView.as_view(), name='food_search'),
    path('ingredient-detail/', IngredientDetailView.as_view(), name='ingredient_detail'),
    path('diet-log/', DietLogView.as_view(), name='diet_log'),
    path('nutrition-summary/', NutritionSummaryView.as_view(), name='nutrition_summary'),
    path('recommend-meals/', RecommendMealsView.as_view(), name='recommend_meals'),
    path('favorite-ingredients/', FavoriteIngredientsView.as_view(), name='favorite_ingredients'),
    path('similar-ingredient/', SimilarIngredientView.as_view(), name='similar_ingredient'),
    path('food-conflict/', FoodConflictView.as_view(), name='food_conflict'),
    path('collection/', UserCollectionView.as_view(), name='collection'),
    path('chat-history/', ChatHistoryView.as_view(), name='chat_history'),
]
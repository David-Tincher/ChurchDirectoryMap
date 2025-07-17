from django.urls import path
from . import views

app_name = 'churches'

urlpatterns = [
    # Web views
    path('', views.index, name='index'),
    
    # API endpoints
    path('api/churches/', views.ChurchListAPIView.as_view(), name='church-list'),
    path('api/churches/<int:id>/', views.ChurchDetailAPIView.as_view(), name='church-detail'),
    path('api/churches/map/', views.ChurchMapAPIView.as_view(), name='church-map'),
    path('api/churches/search/', views.ChurchSearchAPIView.as_view(), name='church-search'),
    path('api/churches/stats/', views.church_stats, name='church-stats'),
    
    # OpenRouteService Integration APIs
    path('api/geocoding/', views.geocoding_api, name='geocoding-api'),
    path('api/directions/', views.directions_api, name='directions-api'),
    path('api/reverse-geocoding/', views.reverse_geocoding_api, name='reverse-geocoding-api'),
]
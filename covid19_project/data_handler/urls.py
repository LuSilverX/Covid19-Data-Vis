from django.urls import path
from .views import dashboard_view
from django.views.generic import TemplateView

urlpatterns = [
    path('dashboard/', dashboard_view, name='dashboard'),
    path('', TemplateView.as_view(template_name='main.html'), name='main'),  # Main page
    path('pandemic/', TemplateView.as_view(template_name='dashboard.html'), name='pandemic_data_page'),  # Pandemic Data
    path('live/', TemplateView.as_view(template_name='live_data.html'), name='live_data_page'),  # Live Data
]
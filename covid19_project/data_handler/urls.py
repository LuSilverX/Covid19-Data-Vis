from django.urls import path
from django.views.generic import TemplateView
from .views import early_dashboard, get_paginated_data, live_dashboard

urlpatterns = [
    path('', TemplateView.as_view(template_name='main.html'), name='main'),  # renders main page
    path('early_pandemic/', early_dashboard, name='early_pandemic_data_page'),  # displays early data
    path('live_data/', live_dashboard, name='live_data_page'),  # display live data
    path('api/data/', get_paginated_data, name='get_paginated_data'),
]



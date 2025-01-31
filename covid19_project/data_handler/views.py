from django.shortcuts import render
from django.core.paginator import Paginator
from .models import CovidCountyData, CovidStateData, CovidUSData

def pre_dashboard(request):
    page_number = int(request.GET.get('page', 1))  # Get current page from URL, default to 1

    # Determine which 100-entry chunk to load
    chunk_size = 100
    current_chunk = ((page_number - 1) // (chunk_size // 10)) * chunk_size  # Adjust chunk based on page

    # Load only the current chunk from the database
    county_list = CovidCountyData.objects.all()[current_chunk:current_chunk + chunk_size]
    state_list = CovidStateData.objects.all()[current_chunk:current_chunk + chunk_size]
    us_list = CovidUSData.objects.all()[current_chunk:current_chunk + chunk_size]

    # Paginate within the 100-entry chunk (10 entries per page)
    county_paginator = Paginator(county_list, 10)
    state_paginator = Paginator(state_list, 10)
    us_paginator = Paginator(us_list, 10)

    # Get the paginated results for the current page
    county_data = county_paginator.get_page(page_number % (chunk_size // 10) or (chunk_size // 10))
    state_data = state_paginator.get_page(page_number % (chunk_size // 10) or (chunk_size // 10))
    us_data = us_paginator.get_page(page_number % (chunk_size // 10) or (chunk_size // 10))

    context = {
        'county_data': county_data,
        'state_data': state_data,
        'us_data': us_data,
        'page_number': page_number,
    }
    return render(request, 'pre_dashboard.html', context)
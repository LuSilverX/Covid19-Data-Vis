import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import CovidCountyData, CovidStateData, CovidUSData

def get_paginated_data(request):
    # Get the page numbers from the request (default to 1)
    county_page = int(request.GET.get('county_page', 1))
    state_page = int(request.GET.get('state_page', 1))
    us_page = int(request.GET.get('us_page', 1))

    # Number of entries per page for each dataset
    entries_per_page = 10

    # Query all data and order by date (change ordering if desired)
    county_queryset = CovidCountyData.objects.all().order_by('date')
    state_queryset = CovidStateData.objects.all().order_by('date')
    us_queryset = CovidUSData.objects.all().order_by('date')

    # Create individual paginators
    county_paginator = Paginator(county_queryset, entries_per_page)
    state_paginator = Paginator(state_queryset, entries_per_page)
    us_paginator = Paginator(us_queryset, entries_per_page)

    # Get each requested page
    county_page_obj = county_paginator.get_page(county_page)
    state_page_obj = state_paginator.get_page(state_page)
    us_page_obj = us_paginator.get_page(us_page)

    # Convert each set of objects to a list of dictionaries
    county_data = list(county_page_obj.object_list.values())
    state_data = list(state_page_obj.object_list.values())
    us_data = list(us_page_obj.object_list.values())

    # Build and return a JSON response
    return JsonResponse({
        'county_data': county_data,
        'county_pagination': {
            'has_next': county_page_obj.has_next(),
            'has_previous': county_page_obj.has_previous(),
            'current_page': county_page_obj.number,
            'total_pages': county_paginator.num_pages,
        },
        'state_data': state_data,
        'state_pagination': {
            'has_next': state_page_obj.has_next(),
            'has_previous': state_page_obj.has_previous(),
            'current_page': state_page_obj.number,
            'total_pages': state_paginator.num_pages,
        },
        'us_data': us_data,
        'us_pagination': {
            'has_next': us_page_obj.has_next(),
            'has_previous': us_page_obj.has_previous(),
            'current_page': us_page_obj.number,
            'total_pages': us_paginator.num_pages,
        },
    })


def pre_dashboard(request):
    # Separate page numbers for each dataset
    county_page = int(request.GET.get('county_page', 1))
    state_page = int(request.GET.get('state_page', 1))
    us_page = int(request.GET.get('us_page', 1))

    # Fetch and order the data
    county_list = CovidCountyData.objects.all().order_by('date')
    state_list = CovidStateData.objects.all().order_by('date')
    us_list = CovidUSData.objects.all().order_by('date')

    # Paginator for each dataset
    county_paginator = Paginator(county_list, 10)
    state_paginator = Paginator(state_list, 10)
    us_paginator = Paginator(us_list, 10)

    # Get pages
    county_data = county_paginator.get_page(county_page)
    state_data = state_paginator.get_page(state_page)
    us_data = us_paginator.get_page(us_page)

    context = {
        'county_data': county_data,
        'state_data': state_data,
        'us_data': us_data,
    }
    return render(request, 'pre_dashboard.html', context)

def live_dashboard(request):
        # Retrieve query parameters from the request
        date_param = request.GET.get('date', '')
        country = request.GET.get('country', '')
        region = request.GET.get('region', '')
        county = request.GET.get('county', '')

        # Validation / Default: API requires either date or country.
        # For dashboard purposes, if neither is provided, default to United States.
        if not (date_param or country):
            country = "United States"

        # Build the parameters dictionary for the API call
        params = {}
        if date_param:
            params['date'] = date_param
        if country:
            params['country'] = country
        if region:
            params['region'] = region
        if county:
            params['county'] = county

        # API Ninjas COVID-19 endpoint and API key (replace "YOUR_API_KEY" with your actual key)
        api_url = "https://api-ninjas.com/api/covid19"
        headers = {"X-Api-Key": "xwxWr+NMRgjCiE6KfSiWWA==HYSKdpGFBTtWvOes"}

        # Make the API request with parameters
        response = requests.get(api_url, headers=headers, params=params)

        if response.status_code == 200:
            # Expecting a JSON array of records
            covid_data = response.json()
        else:
            covid_data = []
            error_message = f"API request failed with status code {response.status_code}."
            # Pass error_message in the context for display if desired.
            context = {'error': error_message, 'covid_data': covid_data}
            return render(request, 'live_dashboard.html', context)

        # Organize the data into sections.
        # For United States data, we assume entries might include fields for 'region' (state) or 'county'.
        national_data = []
        state_data = []
        county_data = []

        for entry in covid_data:
            if country.lower() == "united states":
                # If a county is specified or the entry has a non-empty 'county' field, assume county-level data.
                if 'county' in entry and entry.get('county'):
                    county_data.append(entry)
                # Else if a region (state) is specified or present, assume state-level data.
                elif 'region' in entry and entry.get('region'):
                    state_data.append(entry)
                else:
                    national_data.append(entry)
            else:
                # For other countries, assume the data is only at the national level.
                national_data.append(entry)

        # Prepare a static list of countries for a drop-down selector.
        countries_list = [
            "United States", "Canada", "United Kingdom", "Germany",
            "France", "Brazil", "India", "Italy", "Spain"
        ]

        # Build the context for the template
        context = {
            'covid_data': covid_data,  # full API response
            'national_data': national_data,  # aggregated or national-level data
            'state_data': state_data,  # state or regional data for US
            'county_data': county_data,  # county-level data for US
            'selected_date': date_param,
            'selected_country': country,
            'selected_region': region,
            'selected_county': county,
            'countries_list': countries_list,  # for the drop-down selection in the template
        }

        return render(request, 'live_dashboard.html', context)
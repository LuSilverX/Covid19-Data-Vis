import requests
import csv
from io import StringIO
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


def early_dashboard(request):
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
    return render(request, 'early_dashboard.html', context)

def live_dashboard(request):
    """
    Fetches three dashboards:
      1. US state-level data (CDC, endpoint: 9mfq-cb36.json)
      2. US county-level data (CDC, endpoint: 8xkx-amqh.json)
      3. Global data (WHO CSV)
    Applies filters based on request parameters and paginates each dataset.
    """
    # Get filter parameters from the request
    selected_date = request.GET.get('date', '')
    selected_country = request.GET.get('country', '')
    selected_region = request.GET.get('region', '')
    selected_county = request.GET.get('county', '')

    # --------------------------
    # 1. US State-Level Data
    # --------------------------
    cdc_state_api_url = "https://data.cdc.gov/resource/9mfq-cb36.json"
    cdc_state_params = {}
    if selected_date:
        # Use a $where clause to match the date prefix (e.g., "2025-03-12%")
        cdc_state_params["$where"] = f"submission_date like '{selected_date}%'"
    if selected_region:
        # Note: The state field often contains abbreviations (e.g., "CA" for California)
        cdc_state_params['state'] = selected_region

    try:
        state_response = requests.get(cdc_state_api_url, params=cdc_state_params, timeout=10)
        state_response.raise_for_status()
        us_state_data_raw = state_response.json()
    except requests.RequestException as e:
        print(f"CDC state-level API request failed: {e}")
        us_state_data_raw = []

    us_state_data = []
    for record in us_state_data_raw:
        us_state_data.append({
            'state': record.get('state', ''),
            'date': record.get('submission_date', '')[:10],
            'cases_new': record.get('new_case', 0),
            'cases_total': record.get('total_case', 0),
            'deaths_new': record.get('new_death', 0),
            'deaths_total': record.get('total_death', 0),
        })

    # --------------------------
    # 2. US County-Level Data
    # --------------------------
    cdc_county_api_url = "https://data.cdc.gov/resource/8xkx-amqh.json"
    cdc_county_params = {}
    if selected_date:
        cdc_county_params["$where"] = f"submission_date like '{selected_date}%'"
    if selected_region:
        cdc_county_params['state'] = selected_region
    if selected_county:
        cdc_county_params['county'] = selected_county

    try:
        county_response = requests.get(cdc_county_api_url, params=cdc_county_params, timeout=10)
        county_response.raise_for_status()
        us_county_data_raw = county_response.json()
    except requests.RequestException as e:
        print(f"CDC county-level API request failed: {e}")
        us_county_data_raw = []

    us_county_data = []
    for record in us_county_data_raw:
        us_county_data.append({
            'state': record.get('state', ''),
            'county': record.get('county', ''),
            'date': record.get('submission_date', '')[:10],
            'cases_new': record.get('new_case', 0),
            'cases_total': record.get('total_case', 0),
            'deaths_new': record.get('new_death', 0),
            'deaths_total': record.get('total_death', 0),
        })

    # --------------------------
    # 3. Global Data (WHO CSV)
    # --------------------------
    global_csv_url = "https://covid19.who.int/WHO-COVID-19-global-data.csv"
    try:
        csv_response = requests.get(global_csv_url, timeout=10)
        csv_response.raise_for_status()
        csv_text = csv_response.text
        csv_file = StringIO(csv_text)
        reader = csv.DictReader(csv_file)
        global_data_raw = list(reader)
    except requests.RequestException as e:
        print(f"Failed to fetch WHO CSV data: {e}")
        global_data_raw = []

    global_data = []
    for row in global_data_raw:
        # Apply filtering for global data if provided.
        if selected_date and row.get('Date_reported') != selected_date:
            continue
        if selected_country and row.get('Country') != selected_country:
            continue
        global_data.append({
            'date': row.get('Date_reported', ''),
            'country': row.get('Country', ''),
            'region': row.get('WHO_region', ''),
            'cases_new': row.get('New_cases', 0),
            'cases_total': row.get('Cumulative_cases', 0),
            'deaths_new': row.get('New_deaths', 0),
            'deaths_total': row.get('Cumulative_deaths', 0),
            'recovered_new': 0,
            'recovered_total': 0,
        })

    # --------------------------
    # Pagination
    # --------------------------
    entries_per_page = 10

    state_paginator = Paginator(us_state_data, entries_per_page)
    county_paginator = Paginator(us_county_data, entries_per_page)
    global_paginator = Paginator(global_data, entries_per_page)

    state_page = request.GET.get('state_page', 1)
    county_page = request.GET.get('county_page', 1)
    global_page = request.GET.get('global_page', 1)

    state_page_obj = state_paginator.get_page(state_page)
    county_page_obj = county_paginator.get_page(county_page)
    global_page_obj = global_paginator.get_page(global_page)

    context = {
        'selected_date': selected_date,
        'selected_country': selected_country,
        'selected_region': selected_region,
        'selected_county': selected_county,
        'us_state_data': state_page_obj,
        'us_county_data': county_page_obj,
        'global_data': global_page_obj,
        'state_pagination': {
            'has_next': state_page_obj.has_next(),
            'has_previous': state_page_obj.has_previous(),
            'current_page': state_page_obj.number,
            'total_pages': state_paginator.num_pages,
        },
        'county_pagination': {
            'has_next': county_page_obj.has_next(),
            'has_previous': county_page_obj.has_previous(),
            'current_page': county_page_obj.number,
            'total_pages': county_paginator.num_pages,
        },
        'global_pagination': {
            'has_next': global_page_obj.has_next(),
            'has_previous': global_page_obj.has_previous(),
            'current_page': global_page_obj.number,
            'total_pages': global_paginator.num_pages,
        },
        # Pagination ranges for template loops
        'state_pagination_range': state_paginator.page_range,
        'county_pagination_range': county_paginator.page_range,
        'global_pagination_range': global_paginator.page_range,
    }
    return render(request, 'live_dashboard.html', context)
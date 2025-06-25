import requests
import csv
from django.views.decorators.http import require_POST
from io import StringIO
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from .models import CovidCountyData, CovidStateData, CovidUSData, CDCData, WHOData
import logging
from django.core.cache import cache
from .tasks import fetch_cdc_data, fetch_who_data

logger = logging.getLogger(__name__)

def get_paginated_data(request):
    # Extract pagination parameters from the GET request, defaulting to page 1.
    county_page = int(request.GET.get('county_page', 1))
    state_page = int(request.GET.get('state_page', 1))
    us_page = int(request.GET.get('us_page', 1))

    entries_per_page = 10

    # Pre-fetch and order the querysets for each data model.
    county_queryset = CovidCountyData.objects.all().order_by('date')
    state_queryset = CovidStateData.objects.all().order_by('date')
    us_queryset = CovidUSData.objects.all().order_by('date')

    # Instantiate a paginator for each queryset.
    county_paginator = Paginator(county_queryset, entries_per_page)
    state_paginator = Paginator(state_queryset, entries_per_page)
    us_paginator = Paginator(us_queryset, entries_per_page)

    # Retrieve the requested page object for each dataset.
    county_page_obj = county_paginator.get_page(county_page)
    state_page_obj = state_paginator.get_page(state_page)
    us_page_obj = us_paginator.get_page(us_page)

    # Serialize the paginated objects into dictionary lists for the JSON response.
    county_data = list(county_page_obj.object_list.values())
    state_data = list(state_page_obj.object_list.values())
    us_data = list(us_page_obj.object_list.values())

    # Construct the final JSON payload with data and pagination metadata.
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

# This view provides the initial, non-AJAX render of the data.
# It's essentially a simplified, server-rendered version of the above.(landing page)
def early_data(request):
    county_page = int(request.GET.get('county_page', 1))
    state_page = int(request.GET.get('state_page', 1))
    us_page = int(request.GET.get('us_page', 1))

    county_list = CovidCountyData.objects.all().order_by('date')
    state_list = CovidStateData.objects.all().order_by('date')
    us_list = CovidUSData.objects.all().order_by('date')

    county_paginator = Paginator(county_list, 10)
    state_paginator = Paginator(state_list, 10)
    us_paginator = Paginator(us_list, 10)

    county_data = county_paginator.get_page(county_page)
    state_data = state_paginator.get_page(state_page)
    us_data = us_paginator.get_page(us_page)
    
    # Pass the paginator objects directly into the template context.
    context = {
        'county_data': county_data,
        'state_data': state_data,
        'us_data': us_data,
    }
    return render(request, 'early_data.html', context)

def format_chart_data(queryset, label_prefix="", cases_label="Cases", deaths_label="Deaths"):
    '''Helper function to transform a queryset into a Chart.js-compatible dictionary.'''
    if not queryset: 
        return None

    try:
        # Deconstruct the queryset into lists for labels and data points.
        labels = [item.date.strftime('%Y-%m-%d') for item in queryset]
        cases_data = [item.cases for item in queryset]
        deaths_data = [item.deaths for item in queryset]
        
        # Return the structured dictionary that Chart.js expects.
        return {
            'labels': labels,
            'datasets': [
                {
                    'label': f'{label_prefix} {cases_label}',
                    'data': cases_data,
                    'borderColor': 'rgb(75, 192, 192)',
                    'tension': 0.1
                },
                {
                    'label': f'{label_prefix} {deaths_label}',
                    'data': deaths_data,
                    'borderColor': 'rgb(255, 99, 132)',
                    'tension': 0.1
                }
            ]
        }
    except AttributeError:
        # This will trigger if the queryset items lack the expected 'date', 'cases', or 'deaths' fields.
        logger.error(f"AttributeError while formatting chart data for prefix: {label_prefix}. Queryset might be malformed.")
        return None


def chart_data_api(request):
    """
    API endpoint that serves data formatted for Chart.js.
    Supports filtering by 'state' and 'county' via GET parameters.
    """
    state_name = request.GET.get('state')
    county_name = request.GET.get('county')

    chart_data = None
    error_message = None
    status_code = 200

    try:
        if state_name and county_name:
            # Granular search: county within a state.
            queryset = CovidCountyData.objects.filter(
                state__iexact=state_name, 
                county__iexact=county_name
            ).order_by('date')
            if queryset.exists():
                label = f"{county_name.title()}, {state_name.title()}"
                chart_data = format_chart_data(queryset, label_prefix=label)
            else:
                error_message = f"No data found for County: {county_name}, State: {state_name}"
                status_code = 404

        elif state_name:
            # Broader search: state-level data.
            queryset = CovidStateData.objects.filter(
                state__iexact=state_name
            ).order_by('date')
            if queryset.exists():
                 label = f"{state_name.title()}"
                 chart_data = format_chart_data(queryset, label_prefix=label)
            else:
                error_message = f"No data found for State: {state_name}"
                status_code = 404

        else:
            # Default case: nationwide data.
            queryset = CovidUSData.objects.all().order_by('date')
            if queryset.exists():
                 chart_data = format_chart_data(queryset, label_prefix="US")
            else:
                error_message = "No US data found"
                status_code = 404

        if chart_data:
            return JsonResponse(chart_data)
        else:
            # Ensure a meaningful error is returned if data processing fails.
            if not error_message:
                error_message = "Data formatting error or empty queryset."
                status_code = 500 # Indicates an internal server issue.
            return JsonResponse({'error': error_message}, status=status_code)

    except Exception as e:
        # Generic exception handler for unforeseen issues.
        logger.error(f"Unexpected error in chart_data_api: {e}")
        return JsonResponse({'error': 'An unexpected server error occurred.'}, status=500)

def get_states_api(request):
    """API endpoint to fetch a distinct, sorted list of states."""
    try:
        # Efficiently retrieve a unique list of states directly from the database.
        states = CovidStateData.objects.exclude(state__isnull=True).exclude(state__exact='').order_by('state').values_list('state', flat=True).distinct()
        return JsonResponse(list(states), safe=False) # safe=False is required to serialize a list.
    except Exception as e:
        logger.error(f"Error in get_states_api: {e}")
        return JsonResponse({'error': 'Could not retrieve states.'}, status=500)


def get_counties_api(request):
    """API endpoint to fetch counties for a given state."""
    state_name = request.GET.get('state')
    if not state_name:
        return JsonResponse({'error': 'State parameter is required.'}, status=400)
    try:
        # Filter counties based on the provided state name (case-insensitive).
        counties = CovidCountyData.objects.filter(state__iexact=state_name).exclude(county__isnull=True).exclude(county__exact='').order_by('county').values_list('county', flat=True).distinct()
        # It's valid for a state to have no counties, so return an empty list.
        return JsonResponse(list(counties), safe=False)
    except Exception as e:
         logger.error(f"Error in get_counties_api for state {state_name}: {e}")
         return JsonResponse({'error': 'Could not retrieve counties.'}, status=500)


def live_data(request):
    """
    Main view for displaying live data. It handles the initial HTML render
    and subsequent AJAX requests for filtering, pagination, and status polling.
    """
    # Differentiate between a full page load and an AJAX call.
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    logger.info(f"Entering live_data view. AJAX: {is_ajax}")

    # --- Ingest request parameters ---
    selected_state = request.GET.get('selected_state', 'united states').lower()
    selected_country = request.GET.get('selected_country', '')
    selected_region = request.GET.get('selected_region', '')
    ajax_target = request.GET.get('target') if is_ajax else None
    is_check_status = request.GET.get('check_status') == 'true'

    us_page_num = request.GET.get('us_page', '1')
    global_page_num = request.GET.get('global_page', '1')

    # --- Initialize context and data variables ---
    us_data_page_obj = None
    global_data_page_obj = None
    who_country_list = []
    cdc_data_exists = False
    who_data_exists = False
    cdc_task_error = None

    # --- CDC Data Processing (from local DB) ---
    # This block runs for initial loads, CDC-targeted AJAX, or status checks.
    if not ajax_target or ajax_target == 'cdc' or is_check_status:
        logger.info(f"Processing CDC data logic for state: {selected_state}")
        us_queryset = CDCData.objects.filter(state__iexact=selected_state)
        cdc_data_exists = us_queryset.exists()

        if not cdc_data_exists:
            # Check cache for a recent task error to avoid re-triggering constantly.
            cache_key = f"cdc_task_error_{selected_state}"
            cdc_task_error = cache.get(cache_key)
            # On initial load, if data is missing and there's no cached error, trigger a Celery task.
            if selected_state and not is_ajax and not cdc_task_error:
                logger.info(f"Queueing fetch_cdc_data task for {selected_state}.")
                try:
                    fetch_cdc_data.delay(selected_state, '')
                except Exception as e:
                    logger.error(f"Error queueing fetch_cdc_data: {e}")
                    cdc_task_error = "Failed to start data fetch task."

        # Paginate only if data exists or if it's an AJAX request needing a (potentially empty) page object.
        if cdc_data_exists or (is_ajax and ajax_target == 'cdc'):
            cdc_paginator = Paginator(us_queryset, 10)
            try:
                us_data_page_obj = cdc_paginator.page(us_page_num)
            except PageNotAnInteger:
                us_data_page_obj = cdc_paginator.page(1)
            except EmptyPage:
                us_data_page_obj = cdc_paginator.page(cdc_paginator.num_pages)

    # --- WHO Data Processing (from local DB) ---
    if not ajax_target or ajax_target == 'who':
        who_queryset = WHOData.objects.all()

        # On initial load, check if the WHO table has any data at all.
        if not is_ajax and not who_queryset.exists():
             logger.warning("WHOData table is empty. Queueing initial fetch_who_data.")
             try:
                fetch_who_data.delay()
             except Exception as e:
                logger.error(f"Error queueing fetch_who_data: {e}")
        else:
             who_data_exists = True

        # Apply filters if they were provided in the request.
        if selected_country:
             who_queryset = who_queryset.filter(country__iexact=selected_country)
        if selected_region:
             who_queryset = who_queryset.filter(who_region__icontains=selected_region)

        # Paginate the filtered WHO queryset.
        who_paginator = Paginator(who_queryset, 10)
        try:
            global_data_page_obj = who_paginator.page(global_page_num)
        except PageNotAnInteger:
            global_data_page_obj = who_paginator.page(1)
        except EmptyPage:
            global_data_page_obj = who_paginator.page(who_paginator.num_pages) 

    # --- Populate Country List for Dropdown --- 
    # Only fetch this on the initial page load to populate the filter dropdown.
    if not is_ajax and who_data_exists:
         try:
            who_country_list = list(WHOData.objects.order_by('country').values_list('country', flat=True).distinct())
         except Exception as e:
            logger.error(f"Error fetching WHO country list: {e}")
            who_country_list = []


    # --- Prepare response based on request type (AJAX vs. Full Render) ---
    if is_ajax:
        logger.info(f"Preparing AJAX response. Target: {ajax_target}, Check Status: {is_check_status}")
        response_data = {}
        try:
            # --- AJAX: Paginate/Filter CDC Data ---
            if ajax_target == 'cdc':
                if us_data_page_obj:
                    # Serialize the object list and pagination state.
                    object_list = list(us_data_page_obj.object_list.values('state', 'date', 'deaths_total'))
                    for item in object_list:
                         item_date = item.get('date')
                         item['date'] = item_date.strftime('%Y-%m-%d') if item_date else None
                    response_data['us_data'] = {
                        'object_list': object_list,
                        'current_page': us_data_page_obj.number,
                        'total_pages': us_data_page_obj.paginator.num_pages,
                        'has_previous': us_data_page_obj.has_previous(),
                        'has_next': us_data_page_obj.has_next(),
                    }
                response_data['cdc_data_exists'] = cdc_data_exists
                response_data['cdc_task_error'] = cdc_task_error

            # --- AJAX: Paginate/Filter WHO Data ---
            elif ajax_target == 'who':
                 if global_data_page_obj:
                     object_list = list(global_data_page_obj.object_list.values( 'date_reported', 'country', 'who_region', 'new_cases', 'cumulative_cases', 'new_deaths', 'cumulative_deaths' ))
                     for item in object_list:
                         item_date = item.get('date_reported')
                         item['date_reported'] = item_date.strftime('%Y-%m-%d') if item_date else None
                     response_data['global_data'] = {
                         'object_list': object_list,
                         'current_page': global_data_page_obj.number,
                         'total_pages': global_data_page_obj.paginator.num_pages,
                         'has_previous': global_data_page_obj.has_previous(),
                         'has_next': global_data_page_obj.has_next(),
                     }

            # --- AJAX: Poll for Task Status --- 
            elif is_check_status:
                 logger.info(f"Handling check_status=true. Original Target: {ajax_target}")
                 # This polling mechanism checks if the background data fetch is complete.
                 response_data = {'cdc_data_exists': cdc_data_exists, 'cdc_task_error': cdc_task_error}
                 # If the data has arrived, include the first page in this response to avoid a second request.
                 if cdc_data_exists and us_data_page_obj:
                     logger.info("Data found during check_status poll, embedding payload.")
                     object_list = list(us_data_page_obj.object_list.values('state', 'date', 'deaths_total'))
                     for item in object_list:
                         item_date = item.get('date')
                         item['date'] = item_date.strftime('%Y-%m-%d') if item_date else None
                     response_data['us_data'] = {
                          'object_list': object_list,
                          'current_page': us_data_page_obj.number,
                          'total_pages': us_data_page_obj.paginator.num_pages,
                          'has_previous': us_data_page_obj.has_previous(),
                          'has_next': us_data_page_obj.has_next(),
                      }
            else:
                 logger.warning(f"AJAX request with unhandled parameters. Target: {ajax_target}, Check Status: {is_check_status}")
                 response_data = {'error': 'Invalid AJAX request parameters'}

            return JsonResponse(response_data)

        except Exception as e:
            logger.error(f"Exception during AJAX response preparation: {e}", exc_info=True)
            return JsonResponse({'error': 'An internal server error occurred during AJAX processing.'}, status=500)

    else: # --- Full Page Render ---
        context = {
            'selected_state': selected_state,
            'selected_country': selected_country,
            'selected_region': selected_region,
            'us_data': us_data_page_obj,
            'global_data': global_data_page_obj,
            'cdc_data_exists': cdc_data_exists,
            'cdc_task_error': cdc_task_error,
            'who_country_list': who_country_list,
        }
        logger.info("Rendering full HTML template for live_data.")
        return render(request, 'live_data.html', context)


@require_POST # Enforce that this endpoint only accepts POST requests.
def trigger_data_refresh(request):
    """
    Handles AJAX POST requests to trigger Celery tasks for data fetching.
    This acts as a secure bridge between the frontend and the task queue.
    """
    source = request.POST.get('source')
    selected_state = request.POST.get('selected_state')

    logger.info(f"Data refresh POST request for source: '{source}', state: '{selected_state}'")

    if source == 'cdc':
        if not selected_state:
            return HttpResponseBadRequest("Missing 'selected_state' parameter for CDC refresh.")
        try:
            # Asynchronously dispatch the Celery task.
            fetch_cdc_data.delay(selected_state=selected_state.lower(), selected_date='')
            logger.info(f"Successfully queued fetch_cdc_data task for state: {selected_state}")
            return JsonResponse({'status': 'success', 'message': f'CDC data refresh initiated for "{selected_state.title()}".'})
        except Exception as e:
            logger.exception(f"Failed to queue fetch_cdc_data task for state: {selected_state}")
            return JsonResponse({'status': 'error', 'message': 'Failed to queue CDC refresh task.'}, status=500)

    elif source == 'who':
        try:
            fetch_who_data.delay()
            logger.info("Successfully queued fetch_who_data task.")
            return JsonResponse({'status': 'success', 'message': 'WHO data refresh initiated.'})
        except Exception as e:
            logger.exception("Failed to queue fetch_who_data task.")
            return JsonResponse({'status': 'error', 'message': 'Failed to queue WHO refresh task.'}, status=500)

    else:
        logger.error(f"Invalid or missing 'source' parameter in POST: {source}")
        return HttpResponseBadRequest("Invalid or missing 'source' parameter.")
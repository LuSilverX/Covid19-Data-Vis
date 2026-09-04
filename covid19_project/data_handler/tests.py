from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import CovidStateData, CovidUSData


class PageTests(TestCase):
    """Basic checks for the application's main pages."""

    def test_landing_page_loads(self):
        response = self.client.get(reverse("main"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "main.html")

    def test_historical_page_loads(self):
        response = self.client.get(reverse("early_pandemic_data_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "early_data.html")

    @patch("data_handler.views.fetch_who_data.delay")
    @patch("data_handler.views.fetch_cdc_deaths_from_api_weekly.delay")
    def test_live_page_loads_without_running_background_tasks(
        self,
        mock_cdc_task,
        mock_who_task,
    ):
        # Celery calls are mocked so the test does not need Redis or internet access.
        response = self.client.get(reverse("live_data_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "live_data.html")
        mock_cdc_task.assert_called_once_with("united states")
        mock_who_task.assert_called_once_with()


class ChartDataApiTests(TestCase):
    """Checks the JSON data used to build the historical charts."""

    def test_national_chart_returns_cases_and_deaths(self):
        CovidUSData.objects.create(
            date=date(2020, 1, 21),
            cases=1,
            deaths=0,
        )
        CovidUSData.objects.create(
            date=date(2020, 1, 22),
            cases=2,
            deaths=1,
        )

        response = self.client.get(reverse("chart_data_api"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "labels": ["2020-01-21", "2020-01-22"],
                "datasets": [
                    {
                        "label": "US Cases",
                        "data": [1, 2],
                        "borderColor": "rgb(75, 192, 192)",
                        "tension": 0.1,
                    },
                    {
                        "label": "US Deaths",
                        "data": [0, 1],
                        "borderColor": "rgb(255, 99, 132)",
                        "tension": 0.1,
                    },
                ],
            },
        )

    def test_state_chart_only_returns_selected_state(self):
        # A second state makes sure the API is actually applying the filter.
        CovidStateData.objects.create(
            date=date(2020, 1, 21),
            state="California",
            fips=6,
            cases=10,
            deaths=1,
        )
        CovidStateData.objects.create(
            date=date(2020, 1, 21),
            state="Texas",
            fips=48,
            cases=20,
            deaths=2,
        )

        response = self.client.get(
            reverse("chart_data_api"),
            {"state": "California"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["datasets"][0]["data"], [10])
        self.assertEqual(response.json()["datasets"][1]["data"], [1])

    def test_unknown_state_returns_404(self):
        response = self.client.get(
            reverse("chart_data_api"),
            {"state": "Atlantis"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

from django.db import models

class CovidCountyData(models.Model):
    date = models.DateField(primary_key=True)
    county = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    fips = models.IntegerField(null=True, blank=True)
    cases = models.IntegerField()
    deaths = models.IntegerField()

    class Meta:
        db_table = "us_counties_data"  # Match existing MySQL table

    def __str__(self):
        return f"{self.county}, {self.state} - {self.date}: {self.cases} cases, {self.deaths} deaths"


class CovidStateData(models.Model):
    date = models.DateField(primary_key=True)
    state = models.CharField(max_length=100)
    fips = models.IntegerField()
    cases = models.IntegerField()
    deaths = models.IntegerField()

    class Meta:
        db_table = "us_states_data"  # Match existing MySQL table

    def __str__(self):
        return f"{self.state} - {self.date}: {self.cases} cases, {self.deaths} deaths"


class CovidUSData(models.Model):
    date = models.DateField(primary_key=True)
    cases = models.IntegerField()
    deaths = models.IntegerField()

    class Meta:
        db_table = "us_covid_data"  # Match existing MySQL table

    def __str__(self):
        return f"US - {self.date}: {self.cases} cases, {self.deaths} deaths"

class CDCData(models.Model):
    state = models.CharField(max_length=100)  # For Geography (e.g., "United States" or a state like "California")
    date = models.DateField()
    deaths_total = models.IntegerField(default=0)  # For Cumulative Deaths
    data_as_of = models.DateField(null=True, blank=True) 

    class Meta:
        unique_together = ('state', 'date')  # Prevent duplicates
        ordering = ['-date']  # Latest dates first

    def __str__(self):
        return f"{self.state} - {self.date.strftime('%Y-%m-%d') if self.date else 'No Date'}"

class WHOData(models.Model):
    """
    Model to store the COVID-19 global data from WHO.
    """
    # Corresponds to 'Date_reported' in CSV (YYYY-MM-DD format)
    date_reported = models.DateField(db_index=True)

    # Corresponds to 'Country_code' (e.g., 'US', 'GB'). Max length 2 seems safe.
    country_code = models.CharField(max_length=10, blank=True, db_index=True) # Allow blank, add index

    # Corresponds to 'Country' (e.g., 'United States of America'). Increased max length.
    country = models.CharField(max_length=100, db_index=True) # Add index

    # Corresponds to 'WHO_region' (e.g., 'AMRO', 'EURO'). Max length 10 seems safe.
    who_region = models.CharField(max_length=10, blank=True)

    # Corresponds to 'New_cases'. Default to 0.
    new_cases = models.IntegerField(default=0)

    # Corresponds to 'Cumulative_cases'. Default to 0.
    cumulative_cases = models.IntegerField(default=0)

    # Corresponds to 'New_deaths'. Default to 0.
    new_deaths = models.IntegerField(default=0)

    # Corresponds to 'Cumulative_deaths'. Default to 0.
    cumulative_deaths = models.IntegerField(default=0)

    class Meta:
        # Prevent duplicate entries for the same country on the same date
        unique_together = ('date_reported', 'country_code')
        # Default ordering: Latest date first, then by country name
        ordering = ['-date_reported', 'country']
        # Optional: Define a specific table name if desired
        # db_table = 'who_covid_data'
        verbose_name = "WHO COVID Data"
        verbose_name_plural = "WHO COVID Data"

    def __str__(self):
        # Provides a readable representation, e.g., in Django Admin
        return f"{self.country} ({self.country_code}) - {self.date_reported.strftime('%Y-%m-%d')}"


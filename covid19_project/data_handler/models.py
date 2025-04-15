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
    date = models.CharField(max_length=20)  # For Date (e.g., "Apr  5 2025")
    deaths_total = models.IntegerField(default=0)  # For Cumulative Deaths
    data_as_of = models.CharField(max_length=20)  # For Death Data As Of (e.g., "Apr 10 2025")

    class Meta:
        unique_together = ('state', 'date')  # Prevent duplicates
        ordering = ['-date']  # Latest dates first

    def __str__(self):
        return f"{self.state} - {self.date}"
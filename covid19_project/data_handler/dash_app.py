from django_plotly_dash import DjangoDash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
from .models import CovidCountyData, CovidStateData, CovidUSData

# Function to convert Django ORM QuerySet to Pandas DataFrame
def fetch_data_as_dataframe(queryset):
    """
    Converts a Django ORM QuerySet to a Pandas DataFrame.
    """
    df = pd.DataFrame.from_records(queryset.values())
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])  # Ensure date format is correct
    return df

# Fetch data from MySQL using Django ORM
county_data = fetch_data_as_dataframe(CovidCountyData.objects.all())
state_data = fetch_data_as_dataframe(CovidStateData.objects.all())
us_data = fetch_data_as_dataframe(CovidUSData.objects.all())

# Precompute total cases and deaths
total_cases = f"{us_data['cases'].max():,}" if not us_data.empty else "0"
total_deaths = f"{us_data['deaths'].max():,}" if not us_data.empty else "0"

# Placeholder figure for empty graphs
placeholder_fig = px.line(title="Select a state or county to view data.")
placeholder_fig.update_layout(xaxis={'visible': False}, yaxis={'visible': False})

# Reusable function for filtering data
def filter_data(data, **filters):
    for key, value in filters.items():
        if value is not None and key in data.columns:
            data = data[data[key] == value]
    return data

# Initialize the Dash app
app = DjangoDash('CovidDashboard')
app.title = "COVID-19 Interactive Dashboard"

# Define the layout of the app
app.layout = html.Div([
    dcc.Interval(id='dummy-interval', interval=1000, n_intervals=0, max_intervals=1),  # Dummy trigger for US graph

    html.H1("COVID-19 Interactive Dashboard", style={'textAlign': 'center'}),

    # National Overview
    html.Div([
        html.H2("U.S. COVID-19 Overview", style={'textAlign': 'center'}),

        html.Div([
            html.Div([
                html.H3("Total Cases", style={'textAlign': 'center'}),
                html.P(total_cases, id='total-cases', style={'textAlign': 'center'})
            ], style={'width': '45%', 'display': 'inline-block', 'padding': '10px'}),

            html.Div([
                html.H3("Total Deaths", style={'textAlign': 'center'}),
                html.P(total_deaths, id='total-deaths', style={'textAlign': 'center'})
            ], style={'width': '45%', 'display': 'inline-block', 'padding': '10px'}),
        ], style={'textAlign': 'center'}),

        dcc.Graph(id='us-graph', style={'height': '500px'})
    ], style={'margin-bottom': '50px'}),

    # State Selection
    html.Div([
        html.H2("State-Level Data", style={'textAlign': 'center'}),
        dcc.Dropdown(
            id='state-dropdown',
            options=[{'label': state, 'value': state} for state in sorted(state_data['state'].unique())] if not state_data.empty else [],
            placeholder="Select a state",
            style={'width': '50%', 'margin': '0 auto'}
        ),
        dcc.Graph(id='state-graph', style={'height': '500px'})
    ], style={'margin-bottom': '50px'}),

    # County Selection
    html.Div([
        html.H2("County-Level Data", style={'textAlign': 'center'}),
        dcc.Dropdown(
            id='county-dropdown',
            placeholder="Select a county",
            disabled=True,
            style={'width': '50%', 'margin': '0 auto'}
        ),
        dcc.Graph(id='county-graph', style={'height': '500px'})
    ])
], style={'width': '90%', 'margin': '0 auto', 'font-family': 'Arial, sans-serif'})

print("dash_app.py for CovidDashboard has been imported!")

# Callback to update the U.S. overview graph using the dummy interval as input
@app.callback(
    Output('us-graph', 'figure'),
    [Input('dummy-interval', 'n_intervals')]
)
def update_us_graph(n_intervals):
    print("Dummy interval triggered, n_intervals =", n_intervals)
    if us_data.empty:
        return placeholder_fig

    fig = px.line(
        us_data,
        x='date',
        y='cases',
        title="COVID-19 Cases in the U.S.",
        labels={'cases': 'Number of Cases', 'date': 'Date'}
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Number of Cases')
    return fig

# Callback to update the state-level graph based on the selected state
@app.callback(
    Output('state-graph', 'figure'),
    [Input('state-dropdown', 'value')]
)
def update_state_graph(selected_state):
    if not selected_state or state_data.empty:
        return placeholder_fig

    filtered_state_data = filter_data(state_data, state=selected_state)
    fig = px.line(
        filtered_state_data,
        x='date',
        y='cases',
        title=f"COVID-19 Cases in {selected_state}",
        labels={'cases': 'Number of Cases', 'date': 'Date'}
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Number of Cases')
    return fig

# Callback to update the county dropdown options based on the selected state
@app.callback(
    [Output('county-dropdown', 'options'),
     Output('county-dropdown', 'disabled')],
    [Input('state-dropdown', 'value')]
)
def update_county_dropdown(selected_state):
    if not selected_state or county_data.empty:
        return [], True

    counties = county_data[county_data['state'] == selected_state]['county'].unique()
    county_options = [{'label': county, 'value': county} for county in sorted(counties)]
    return county_options, False

# Callback to update the county-level graph based on selected county and state
@app.callback(
    Output('county-graph', 'figure'),
    [Input('county-dropdown', 'value'),
     Input('state-dropdown', 'value')]
)
def update_county_graph(selected_county, selected_state):
    if not selected_county or not selected_state or county_data.empty:
        return placeholder_fig

    filtered_county_data = filter_data(county_data, state=selected_state, county=selected_county)
    fig = px.line(
        filtered_county_data,
        x='date',
        y='cases',
        title=f"COVID-19 Cases in {selected_county}, {selected_state}",
        labels={'cases': 'Number of Cases', 'date': 'Date'}
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Number of Cases')
    return fig
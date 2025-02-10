import os
from django_plotly_dash import DjangoDash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
from .load_data import county_data, state_data, us_data

# Constants
TITLE = "COVID-19 Interactive Dashboard"
CENTER_STYLE = {'textAlign': 'center'}
DROPDOWN_STYLE = {'width': '50%', 'margin': '0 auto'}
SECTION_STYLE = {'margin-bottom': '50px'}
METRIC_STYLE = {'width': '45%', 'display': 'inline-block', 'padding': '10px'}
CONTAINER_STYLE = {'textAlign': 'center'}
APP_STYLE = {'width': '90%', 'margin': '0 auto', 'font-family': 'Arial, sans-serif'}

# Precomputed values for metrics
total_cases = f"{us_data['cases'].max():,}"  # Precomputed total cases
total_deaths = f"{us_data['deaths'].max():,}"  # Precomputed total deaths

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
app.title = TITLE

# Define the layout of the app including a dummy interval component.
# Make sure your Django template correctly embeds this app.
app.layout = html.Div([
    # Dummy interval component to trigger the U.S. graph callback
    dcc.Interval(id='dummy-interval', interval=1000, n_intervals=0, max_intervals=1),

    html.H1(TITLE, style=CENTER_STYLE),

    # National Overview
    html.Div([
        html.H2("U.S. COVID-19 Overview", style=CENTER_STYLE),

        # Summary Metrics
        html.Div([
            html.Div([
                html.H3("Total Cases", style=CENTER_STYLE),
                html.P(total_cases, id='total-cases', style=CENTER_STYLE)
            ], className='metric', style=METRIC_STYLE),

            html.Div([
                html.H3("Total Deaths", style=CENTER_STYLE),
                html.P(total_deaths, id='total-deaths', style=CENTER_STYLE)
            ], className='metric', style=METRIC_STYLE),
        ], className='metrics-container', style=CONTAINER_STYLE),

        # Line Chart for U.S. data
        dcc.Graph(id='us-graph', style={'height': '500px'})
    ], className='section', style=SECTION_STYLE),

    # State Selection
    html.Div([
        html.H2("State-Level Data", style=CENTER_STYLE),
        dcc.Dropdown(
            id='state-dropdown',
            options=[{'label': state, 'value': state} for state in sorted(state_data['state'].unique())],
            placeholder="Select a state",
            style=DROPDOWN_STYLE
        ),
        dcc.Graph(id='state-graph', style={'height': '500px'})
    ], className='section', style=SECTION_STYLE),

    # County Selection
    html.Div([
        html.H2("County-Level Data", style=CENTER_STYLE),
        dcc.Dropdown(
            id='county-dropdown',
            placeholder="Select a county",
            disabled=True,
            style=DROPDOWN_STYLE
        ),
        dcc.Graph(id='county-graph', style={'height': '500px'})
    ], className='section')
], style=APP_STYLE)

print("dash_app.py for CovidDashboard has been imported!")

# Callback to update the U.S. overview graph using the dummy interval as input
@app.callback(
    Output('us-graph', 'figure'),
    [Input('dummy-interval', 'n_intervals')]
)
def update_us_graph(n_intervals):
    print("Dummy interval triggered, n_intervals =", n_intervals)
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
    if not selected_state:
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
    if not selected_state:
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
    if not selected_county or not selected_state:
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
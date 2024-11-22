import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
from load_data import county_data, state_data, us_data

# Initialize the Dash app
app = dash.Dash(__name__)
app.title = "COVID-19 Dashboard"

# Define the layout of the app
app.layout = html.Div([
    html.H1("COVID-19 Interactive Dashboard", style={'textAlign': 'center'}),
    
    # National Overview
    html.Div([
        html.H2("U.S. COVID-19 Overview", style={'textAlign': 'center'}),
        
        # Summary Metrics
        html.Div([
            html.Div([
                html.H3("Total Cases", style={'textAlign': 'center'}),
                html.P(id='total-cases', children="Loading...", style={'textAlign': 'center'})
            ], className='metric', style={'width': '45%', 'display': 'inline-block', 'padding': '10px'}),
            
            html.Div([
                html.H3("Total Deaths", style={'textAlign': 'center'}),
                html.P(id='total-deaths', children="Loading...", style={'textAlign': 'center'})
            ], className='metric', style={'width': '45%', 'display': 'inline-block', 'padding': '10px'}),
        ], className='metrics-container', style={'textAlign': 'center'}),
        
        # Line Chart
        dcc.Graph(id='us-graph')
    ], className='section', style={'margin-bottom': '50px'}),
    
    # State Selection
    html.Div([
        html.H2("State-Level Data", style={'textAlign': 'center'}),
        dcc.Dropdown(
            id='state-dropdown',
            options=[{'label': state, 'value': state} for state in sorted(state_data['state'].unique())],
            placeholder="Select a state",
            style={'width': '50%', 'margin': '0 auto'}
        ),
        dcc.Graph(id='state-graph')
    ], className='section', style={'margin-bottom': '50px'}),
    
    # County Selection
    html.Div([
        html.H2("County-Level Data", style={'textAlign': 'center'}),
        dcc.Dropdown(
            id='county-dropdown',
            placeholder="Select a county",
            disabled=True,
            style={'width': '50%', 'margin': '0 auto'}
        ),
        dcc.Graph(id='county-graph')
    ], className='section')
], style={'width': '90%', 'margin': '0 auto', 'font-family': 'Arial, sans-serif'})

# Callback to update total cases
@app.callback(
    Output('total-cases', 'children'),
    []
)
def update_total_cases():
    total_cases = us_data['cases'].max()  # Assuming 'cases' is cumulative
    return f"{total_cases:,}"  # Format with commas

# Callback to update total deaths
@app.callback(
    Output('total-deaths', 'children'),
    []
)
def update_total_deaths():
    total_deaths = us_data['deaths'].max()  # Assuming 'deaths' is cumulative
    return f"{total_deaths:,}"  # Format with commas

# Callback to update the U.S. overview graph
@app.callback(
    Output('us-graph', 'figure'),
    []
)
def update_us_graph():
    fig = px.line(
        us_data, 
        x='date',
        y='cases', 
        title="COVID-19 Cases in the U.S.",
        labels={'cases': 'Number of Cases', 'date': 'Date'}
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Number of Cases')
    return fig

# Callback to update the state-level graph based on selected state
@app.callback(
    Output('state-graph', 'figure'),
    [Input('state-dropdown', 'value')]
)
def update_state_graph(selected_state):
    if not selected_state:
        # Return an empty figure with a placeholder message
        fig = px.line(title="Select a state to view data.")
        fig.update_layout(xaxis={'visible': False}, yaxis={'visible': False})
        return fig
    # Filter data for the selected state
    filtered_state_data = state_data[state_data['state'] == selected_state]
    # Create a line chart for the selected state
    fig = px.line(
        filtered_state_data, 
        x='date', 
        y='cases', 
        title=f"COVID-19 Cases in {selected_state}",
        labels={'cases': 'Number of Cases', 'date': 'Date'}
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Number of Cases')
    return fig

# Callback to update the county dropdown options based on selected state
@app.callback(
    [Output('county-dropdown', 'options'),
     Output('county-dropdown', 'disabled')],
    [Input('state-dropdown', 'value')]
)
def update_county_dropdown(selected_state):
    if not selected_state:
        # No state selected, disable the county dropdown
        return [], True
    # Get unique counties for the selected state
    counties = county_data[county_data['state'] == selected_state]['county'].unique()
    # Create dropdown options
    county_options = [{'label': county, 'value': county} for county in sorted(counties)]
    return county_options, False  # Enable the dropdown

# Callback to update the county-level graph based on selected county and state
@app.callback(
    Output('county-graph', 'figure'),
    [Input('county-dropdown', 'value'),
     Input('state-dropdown', 'value')]
)
def update_county_graph(selected_county, selected_state):
    if not selected_county or not selected_state:
        # Return an empty figure with a placeholder message
        fig = px.line(title="Select a county to view data.")
        fig.update_layout(xaxis={'visible': False}, yaxis={'visible': False})
        return fig
    # Filter data for the selected county and state
    filtered_county_data = county_data[
        (county_data['state'] == selected_state) & 
        (county_data['county'] == selected_county)
    ]
    # Create a line chart for the selected county
    fig = px.line(
        filtered_county_data, 
        x='date', 
        y='cases', 
        title=f"COVID-19 Cases in {selected_county}, {selected_state}",
        labels={'cases': 'Number of Cases', 'date': 'Date'}
    )
    fig.update_layout(xaxis_title='Date', yaxis_title='Number of Cases')
    return fig

# Run the app
if __name__ == '__main__':
    print("Starting Dash app...")
    app.run_server(debug=True, port=8051)  # You can try other ports like 8051 if needed
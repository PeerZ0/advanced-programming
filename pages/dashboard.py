# pages/dashboard.py
"""
Portfolio Dashboard Page

This module implements the portfolio visualization dashboard that displays:
1. Portfolio performance metrics and statistics
2. Interactive visualizations including returns, volatility, and allocations
3. Portfolio strategy selection and data export functionality

The dashboard provides a comprehensive view of the portfolio's performance and
characteristics using a terminal-themed design for consistency with the application.
"""

import dash
from dash import html, dcc, Input, Output, State, callback
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
from state import user  # Shared state where portfolio is already initialized
from services.export_portfolio import export_portfolio
from models.portfolio import Portfolio

# Register the page
dash.register_page(__name__, path="/dashboard")

# Layout with terminal styling
layout = html.Div([
    # Header section
    html.Div([
        dbc.Button(
            "← BACK", 
            id="back-button",
            className="mb-3 terminal-button",
            href="/"
        ),
        html.H1("PORTFOLIO OPTIMIZATION DASHBOARD", className="text-center terminal-title"),

        html.Div([
            html.Label("SELECT PORTFOLIO STRATEGY:", className="text-info mb-2"),
            dcc.Dropdown(
                id='portfolio-strategy-dropdown',
                options=[
                    {'label': 'MINIMUM VARIANCE PORTFOLIO', 'value': 'min_variance'},
                    {'label': 'EQUAL WEIGHT PORTFOLIO', 'value': 'equal_weight'},
                    {'label': 'MAXIMUM SHARPE RATIO PORTFOLIO', 'value': 'max_sharpe'}
                ],
                value='min_variance',
                className="dash-dropdown-modern terminal-input w-50 mx-auto",
            )
        ], className="text-center mb-4"),

        html.Div([
            dbc.Button(
                "DOWNLOAD PORTFOLIO DATA",
                id="btn-download",
                className="terminal-button my-3"
            ),
            dcc.Download(id="download-dataframe-csv"),
        ], className="text-center")
    ]),

    html.Br(),

    # Summary statistics
    html.Div([
        html.H2("SUMMARY STATISTICS", className="text-center terminal-title"),
        html.Div(
            id='summary-statistics-table',
            className="terminal-card p-4 w-75 mx-auto my-4"
        )
    ]),

    # Visualization section
    html.Div([
        html.H2("PORTFOLIO VISUALIZATION", className="text-center terminal-title"),
        html.Div([
            dcc.Graph(id='cumulative-returns-plot', className="mb-4"),
            dcc.Graph(id='sector-allocation-plot', className="mb-4"),
            dcc.Graph(id='rolling-volatility-plot', className="mb-4"),  # Add this line
            dcc.Graph(id='annualized-returns-plot', className="mb-4"),
            dcc.Graph(id='monthly-returns-plot', className="mb-4"),
            dcc.Graph(id='monthly-returns-histogram', className="mb-4"),
            dcc.Graph(id='daily-returns-plot', className="mb-4"),
        ], className="w-85 mx-auto")
    ]),

    html.Div(
        "DASHBOARD CREATED USING DASH & PLOTLY", 
        className="text-center mt-5 text-info"
    )
], className="terminal-container py-4")

@callback(
    [
        Output('summary-statistics-table', 'children'),
        Output('cumulative-returns-plot', 'figure'),
        Output('sector-allocation-plot', 'figure'),
        Output('rolling-volatility-plot', 'figure'),
        Output('annualized-returns-plot', 'figure'),
        Output('monthly-returns-plot', 'figure'),
        Output('monthly-returns-histogram', 'figure'),
        Output('daily-returns-plot', 'figure'),
    ],
    Input('portfolio-strategy-dropdown', 'value')
)
def update_dashboard(selected_strategy):
    """
    Update all dashboard components based on the selected portfolio strategy.

    This callback handles:
    1. Portfolio initialization if needed
    2. Weight calculation based on selected strategy
    3. Generation of summary statistics table
    4. Creation of all visualization plots

    Parameters
    ----------
    selected_strategy : str
        The selected portfolio strategy ('min_variance', 'equal_weight', or 'max_sharpe')

    Returns
    -------
    tuple
        Contains (summary_table, plot1, plot2, ..., plotN) where:
        - summary_table : dash_html_components.Table
            Formatted table of portfolio statistics
        - plot1..plotN : plotly.graph_objects.Figure
            Various portfolio visualization plots
    """
    if not user.portfolio:
        user.portfolio = Portfolio(user)
    
    portfolio = user.portfolio
    
    # Get weights based on strategy
    weights_map = {
        'min_variance': portfolio.weights_min,
        'equal_weight': portfolio.weights_eq,
        'max_sharpe': portfolio.weights_sharpe
    }
    portfolio_weights = weights_map.get(selected_strategy)
    if not portfolio_weights:
        return None, None, None, None, None, None, None

    # Create summary table with terminal styling
    summary_df = portfolio.get_summary_statistics_table(portfolio_weights)
    summary_table = html.Table(
        [
            html.Thead(html.Tr([
                html.Th(col, style={
                    'color': '#FF8000',
                    'padding': '10px',
                    'border-bottom': '1px solid #FF8000',
                    'text-align': 'left'
                }) for col in summary_df.columns
            ])),
            html.Tbody([
                html.Tr([
                    html.Td(
                        summary_df.iloc[i][col],
                        style={
                            'color': '#FFFFFF',
                            'padding': '10px',
                            'border-bottom': '1px solid #333'
                        }
                    ) for col in summary_df.columns
                ]) for i in range(len(summary_df))
            ])
        ],
        style={
            'width': '100%',
            'border-collapse': 'collapse',
            'backgroundColor': '#111',
            'borderRadius': '5px',
            'overflow': 'hidden'
        }
    )

    # Generate plots with terminal theme
    plots = [
        portfolio.plot_cumulative_returns(portfolio_weights),
        portfolio.plot_rolling_volatility(portfolio_weights),  # Add this line
        portfolio.create_weighted_sector_treemap(portfolio_weights),
        portfolio.plot_annualized_returns(portfolio_weights),
        portfolio.plot_monthly_returns_distribution(portfolio_weights),
        portfolio.plot_monthly_returns_histogram(portfolio_weights),
        portfolio.plot_daily_returns_series(portfolio_weights),
    ]

    # Apply terminal theme to all plots
    for plot in plots:
        plot.update_layout(
            template="plotly_dark",
            paper_bgcolor="#000000",
            plot_bgcolor="#000000",
            font=dict(
                family="Roboto Mono",
                color="#FFFFFF"
            ),
            title_font_color="#FF8000"
        )

    return summary_table, *plots

@callback(
    Output("download-dataframe-csv", "data"),
    Input("btn-download", "n_clicks"),
    State("portfolio-strategy-dropdown", "value"),
    prevent_initial_call=True
)
def download_csv(n_clicks, selected_strategy):
    """
    Export portfolio data to CSV based on selected strategy.

    Parameters
    ----------
    n_clicks : int
        Number of times the download button has been clicked
    selected_strategy : str
        The selected portfolio strategy

    Returns
    -------
    dict
        Download specification for Dash's dcc.Download component

    Raises
    ------
    PreventUpdate
        If button hasn't been clicked or invalid strategy selected
    """
    if n_clicks is None:
        raise PreventUpdate

    # Ensure portfolio is initialized
    if not user.portfolio:
        user.portfolio = Portfolio(user)

    portfolio = user.portfolio

    if selected_strategy == 'min_variance':
        portfolio_weights = portfolio.weights_min
        strategy_name = "Minimum_Variance_Strategy"
    elif selected_strategy == 'equal_weight':
        portfolio_weights = portfolio.weights_eq
        strategy_name = "Equal_Weight_Strategy"
    elif selected_strategy == 'max_sharpe':
        portfolio_weights = portfolio.weights_sharpe
        strategy_name = "Maximum_Sharpe_Ratio_Strategy"
    else:
        raise PreventUpdate

    # Export portfolio and return file download spec
    df = export_portfolio(portfolio_weights, strategy_name)
    return dcc.send_data_frame(df.to_csv, f"portfolio_{strategy_name}.csv", index=False)
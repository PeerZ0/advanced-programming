#%%
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import yfinance as yf
import datetime
import plotly.graph_objs as go
import plotly.subplots as sp



class Portfolio:
    def __init__(self, user, min_weight: float = 0.0, start_date = '2023-01-01', end_date = datetime.date.today()):
        """
        Initialize the MinVariancePortfolio with stock ticker data and calculate mean returns and covariance matrix.
        
        Parameters:
        tickers (list): A list of stock ticker symbols.
        start_date (str): The start date for fetching historical data in 'YYYY-MM-DD' format.
        end_date (str): The end date for fetching historical data in 'YYYY-MM-DD' format.
        """
        self.tickers = user.data['available_stocks']
        self.start_date = start_date
        self.end_date = end_date
        self.data_retrieval_success = False
        self.data = self._get_data()
        self.returns = self.calculate_returns()
        self.mean_returns = self.returns.mean()
        self.cov_matrix = self.returns.cov()
        #self.bounds = tuple((0.05,0.4) for _ in range(len(self.tickers)))
        self.bounds = tuple((0, user.data['max_equity_investment']/100) for _ in range(len(self.tickers)))
        self.constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}, {'type': 'ineq', 'fun': lambda x: np.sum(x) - len(self.tickers) * min_weight}]
        self.sp500 = yf.download('^GSPC', start=start_date, end=end_date)['Adj Close']

    def _get_data(self):
        """
        Fetch historical stock price data from Yahoo Finance.
        
        Returns:
        pd.DataFrame: A DataFrame containing historical stock prices of the assets.
        """
        data_list = []
        for ticker in self.tickers:
            try:
                df = yf.download(ticker, self.start_date, self.end_date, progress=False)['Adj Close']
                data_list.append(df)
            except KeyError as e:
                print(f"Error fetching data for {ticker}: {e}")
        self.data_retrieval_success = True
        data = pd.concat(data_list, axis=1)
        data = data.sort_index()
        data = data.dropna(axis=1, how='all')
        data.ffill(inplace=True)
        
        for column in data.columns:
            max_nan_streak = (data[column].isna().groupby((~data[column].isna()).cumsum()).cumsum()).max()
            if max_nan_streak >= 4:
                data.drop(columns=[column], inplace=True)
            else:
                data[column].fillna(method='ffill', inplace=True)
        
        if pd.isna(data.iloc[0]).any() and len(data) > 1:
            data.iloc[0] = data.iloc[1]
        
        self.tickers = list(data.columns)
        return data
        
    def calculate_returns(self):
        """
        Calculate daily returns from stock price data.
        
        Returns:
        pd.DataFrame: A DataFrame containing daily returns of the assets.
        """
        return self.data.pct_change().dropna()

    def min_variance_portfolio(self):
        """
        Find the portfolio with the minimum possible variance.
        
        Returns:
        dict: A dictionary containing the optimized weights for each ticker.
        """
        num_assets = len(self.tickers)
        initial_weights = np.ones(num_assets) / num_assets

        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))

        result = minimize(portfolio_volatility, initial_weights, method='SLSQP', bounds=self.bounds, constraints=self.constraints)
        return dict(zip(self.tickers, result.x))

    def equal_weight_portfolio(self):
        """
        Create an equally weighted portfolio.
        
        Returns:
        dict: A dictionary containing equal weights for each ticker.
        """
        num_assets = len(self.tickers)
        weights = np.ones(num_assets) / num_assets
        return dict(zip(self.tickers, weights))

    def max_sharpe_ratio_portfolio(self, risk_free_rate=0.01):
        """
        Find the portfolio that maximizes the Sharpe ratio.
        
        Parameters:
        risk_free_rate (float): The risk-free rate used to calculate the Sharpe ratio.
        
        Returns:
        dict: A dictionary containing the optimized weights for each ticker.
        """
        num_assets = len(self.tickers)
        initial_weights = np.ones(num_assets) / num_assets
        #constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})

        def negative_sharpe_ratio(weights):
            portfolio_return = np.sum(weights * self.mean_returns)
            portfolio_volatility = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            sharpe_ratio = (portfolio_return - risk_free_rate) / portfolio_volatility
            return -sharpe_ratio

        result = minimize(negative_sharpe_ratio, initial_weights, method='SLSQP', bounds=self.bounds, constraints=self.constraints)
        return dict(zip(self.tickers, result.x))


    def choose_best_return_portfolio(self, yearly_rebalance='no'):
        """
        Choose the portfolio with the highest return.
        
        Parameters:
        yearly_rebalance (str): Whether to rebalance the portfolio annually ('yes' or 'no').

        Returns:
        dict: A dictionary containing the optimized weights for the portfolio with the highest return.
        """
        portfolios = {
            'min_variance': self.min_variance_portfolio(),
            'equal_weight': self.equal_weight_portfolio(),
            'max_sharpe': self.max_sharpe_ratio_portfolio(0.01)
        }
        
        best_portfolio = None
        best_return = -float('inf')

        for name, weights in portfolios.items():
            if yearly_rebalance == 'yes':
                cumulative_value = 1.0  # Starting with an initial wealth of 1
                rebalanced_weights = self.yearly_rebalance(weights)
                
                # Iteratively apply yearly returns
                for year, year_weights in rebalanced_weights.items():
                    yearly_returns = self.returns[self.returns.index.year == year]
                    
                    if yearly_returns.empty:
                        continue
                    
                    # Apply the weights to the returns for the given year
                    weighted_returns = yearly_returns.dot(pd.Series(year_weights))
                    
                    # Calculate the cumulative return for the year
                    cumulative_year_return = (1 + weighted_returns).prod() - 1
                    
                    # Update the overall portfolio value based on the year's return
                    cumulative_value *= (1 + cumulative_year_return)
                    
                total_return = cumulative_value - 1  # Calculate the overall return
            else:
                # No rebalancing: calculate return using original weights across the whole period
                weighted_returns = self.returns.dot(pd.Series(weights))
                total_return = (1 + weighted_returns).prod() - 1  # Final cumulative return

            if total_return > best_return:
                best_return = total_return
                best_portfolio = weights
        
        return best_portfolio
    

    def calculate_max_drawdowns(self, returns):
        """
        Calculate the maximum drawdown of a returns series.
        
        Parameters:
        returns (pd.Series): The returns series.
        
        Returns:
        float: The maximum drawdown.
        """
        cumulative = (1 + returns).cumprod()
        peak = cumulative.cummax()
        drawdown = (cumulative - peak) / peak
        return drawdown.min()


    def plot_cumulative_returns(self, portfolio_weights):
        """
        Plot cumulative returns of the given portfolio weights using Plotly.
        
        Parameters:
        portfolio_weights (dict): A dictionary containing the weights of each ticker in the portfolio.
        """
        # Load S&P 500 returns using yfinance
        sp500_returns = self.sp500.pct_change().dropna()
        self.sp500_returns = sp500_returns

        # Calculate portfolio weighted returns
        weighted_returns = self.returns.dot(pd.Series(portfolio_weights))

        # Align dates
        aligned_data = pd.concat([weighted_returns, sp500_returns], axis=1, join="inner")
        aligned_data.columns = ["Portfolio", "S&P 500"]

        # Calculate cumulative returns
        cumulative_returns = (1 + aligned_data["Portfolio"]).cumprod()
        cumulative_sp500_returns = (1 + aligned_data["S&P 500"]).cumprod()

        # Debug output (optional)
        print("Cumulative Portfolio Returns:", cumulative_returns.head())
        print("Cumulative S&P 500 Returns:", cumulative_sp500_returns.head())

        # Create the plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cumulative_returns.index, y=cumulative_returns, mode='lines', name='Portfolio'))
        fig.add_trace(go.Scatter(x=cumulative_sp500_returns.index, y=cumulative_sp500_returns, mode='lines', name='S&P 500 Benchmark'))
        
        fig.update_layout(
            title='Cumulative Returns of Portfolio vs S&P 500',
            xaxis_title='Date',
            yaxis_title='Cumulative Return',
            template='plotly_white'
        )
        return fig

    def get_summary_statistics(self, portfolio_weights, risk_free_rate=0.01):
        """
        Get summary statistics of the given portfolio.
        
        Parameters:
        portfolio_weights (dict): A dictionary containing the weights of each ticker in the portfolio.
        risk_free_rate (float): The risk-free rate used to calculate the Sharpe ratio.
        
        Returns:
        dict: A dictionary containing summary statistics of the portfolio.
        """
        # Calculate portfolio returns
        weighted_returns = self.returns.dot(pd.Series(portfolio_weights))
        
        # Calculate cumulative return
        cumulative_return = (1 + weighted_returns).prod() - 1
        
        # Calculate annualized return
        annualized_return = weighted_returns.mean() * 252
        
        # Calculate annualized volatility
        annualized_volatility = weighted_returns.std() * np.sqrt(252)
        
        # Calculate Sharpe ratio
        sharpe_ratio = (annualized_return - risk_free_rate) / annualized_volatility
        
        # Calculate maximum drawdown
        max_drawdown = self.calculate_max_drawdowns(weighted_returns)
        
        # Create a summary dictionary
        summary_stats = {
            'Cumulative Return': cumulative_return,
            'Annualized Return': annualized_return,
            'Annualized Volatility': annualized_volatility,
            'Sharpe Ratio': sharpe_ratio,
            'Maximum Drawdown': max_drawdown,
        }
        
        return summary_stats

    def get_summary_statistics_table(self, portfolio_weights, risk_free_rate=0.01):
        """
        Get a summary statistics table of the given portfolio.
        
        Parameters:
        portfolio_weights (dict): A dictionary containing the weights of each ticker in the portfolio.
        risk_free_rate (float): The risk-free rate used to calculate the Sharpe ratio.
        
        Returns:
        pd.DataFrame: A DataFrame containing summary statistics of the portfolio.
        """
        summary_stats = self.get_summary_statistics(portfolio_weights, risk_free_rate)
        summary_df = pd.DataFrame(list(summary_stats.items()), columns=['Metric', 'Value'])
        return summary_df


    def plot_portfolio_allocation(self, portfolio_weights):
        """
        Plot a pie chart showing the allocation of the given portfolio weights using Plotly.
        
        Parameters:
        portfolio_weights (dict): A dictionary containing the weights of each ticker in the portfolio.
        """
        labels = list(portfolio_weights.keys())
        values = list(portfolio_weights.values())
        fig = go.Figure(data=[go.Pie(labels=labels, values=values)])
        fig.update_layout(title_text='Portfolio Allocation', template='plotly_white')
        return fig
    
    def create_weighted_sector_treemap(self, weights):
        """
        Generate a weighted treemap of sectors for the given tickers.

        Parameters:
        weights (dict): A dictionary mapping tickers to their respective weights.

        Returns:
        plotly.graph_objects.Figure: A treemap figure showing sectors with their respective weights.
        """
        # Check if all tickers have corresponding weights
        if set(self.tickers) - set(weights.keys()):
            raise ValueError("All tickers must have corresponding weights in the weights dictionary.")

        sector_data = []
        missing_tickers = []

        # Fetch sector information for each ticker
        for ticker in self.tickers:
            try:
                stock_info = yf.Ticker(ticker).info
                sector = stock_info.get('sector', 'Unknown')  # Default to 'Unknown' if sector is missing
                weight = weights.get(ticker, 0)  # Get weight for the ticker, default to 0 if not found
                sector_data.append({'Ticker': ticker, 'Sector': sector, 'Weight': weight})
            except Exception as e:
                print(f"Error fetching sector for {ticker}: {e}")
                missing_tickers.append(ticker)
        
        # Create a DataFrame for sector data
        df = pd.DataFrame(sector_data)

        # Aggregate weights by sector
        sector_weights = df.groupby('Sector')['Weight'].sum().reset_index()

        # Create the treemap
        fig = go.Figure(go.Treemap(
            labels=sector_weights['Sector'],  # Sector names
            parents=[""] * len(sector_weights),  # Top-level nodes
            values=sector_weights['Weight'],  # Aggregate weights
            textinfo="label+value+percent entry",
            marker=dict(colorscale="Viridis")
        ))

        fig.update_layout(
            title="Weighted Treemap of Sectors",
            template="plotly_white"
        )

        # Return the treemap figure
        return fig

    

    def plot_annualized_returns(self, portfolio_weights):
        """
        Plot a bar chart showing the annualized returns of the individual assets in the portfolio.
        
        Parameters:
        portfolio_weights (dict): A dictionary containing the weights of each ticker in the portfolio.
        """
        annualized_returns = self.mean_returns * 252
        labels = self.tickers
        values = [annualized_returns[ticker] for ticker in self.tickers]
        
        fig = go.Figure(data=[go.Bar(x=labels, y=values)])
        fig.update_layout(
            title='Annualized Returns of Individual Assets',
            xaxis_title='Asset',
            yaxis_title='Annualized Return',
            template='plotly_white'
        )
        return fig


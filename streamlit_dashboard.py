import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import yfinance as yf

# Title of the dashboard
st.title('Equity Momentum Scanner Dashboard')

# Sidebar for user input
st.sidebar.header('User Input Features')

# Function to get NSE stock data
def get_stock_data(ticker):
    stock_data = yf.download(ticker, period='1y')
    return stock_data

# List of stock tickers (For demonstration purposes, add more as needed)
tickers = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS']
selected_ticker = st.sidebar.selectbox('Select Stock Ticker', tickers)

# Get stock data
stock_data = get_stock_data(selected_ticker)

# Display raw data
if st.sidebar.checkbox('Show Raw Data'):
    st.subheader('Raw Data')
    st.write(stock_data)

# Adding a filters section
st.sidebar.subheader('Filters')
# Example filter to choose the date range
start_date = st.sidebar.date_input('Start Date', stock_data.index.min())
end_date = st.sidebar.date_input('End Date', stock_data.index.max())
filtered_data = stock_data[(stock_data.index >= start_date) & (stock_data.index <= end_date)]

# Function to plot data
def plot_data(data):
    plt.figure(figsize=(10,5))
    plt.plot(data['Close'], label='Close Price')
    plt.title(f'Stock Price for {selected_ticker}')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    st.pyplot(plt)

# Call plot function with filtered data
plot_data(filtered_data)

# Displaying momentum indicators
st.subheader('Momentum Indicators')
# Technical analysis example: Simple Moving Average
sma = filtered_data['Close'].rolling(window=20).mean()
plt.figure(figsize=(10,5))
plt.plot(filtered_data['Close'], label='Close Price')
plt.plot(sma, label='20-Day SMA', linestyle='--')
plt.title(f'Momentum Indicators for {selected_ticker}')
plt.xlabel('Date')
plt.ylabel('Price')
plt.legend()
st.pyplot(plt)

# Watchlist management example
watchlist = st.sidebar.text_area('Watchlist (comma separated)', 'RELIANCE.NS, TCS.NS, INFY.NS')
watchlist_stocks = [w.strip() for w in watchlist.split(',')]

# Display Watchlist
if st.sidebar.button('Show Watchlist'):
    st.subheader('Your Watchlist')
    st.write(watchlist_stocks)

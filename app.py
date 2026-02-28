import streamlit as st
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime
import time

# Function to fetch live data from NSE API
def fetch_data(symbol):
    url = f"https://api.example.com/nse_data/{symbol}"  # Replace with actual API URL
    response = requests.get(url)
    return response.json()

# Function to calculate momentum indicators
def calculate_momentum(data):
    data['Momentum'] = data['Close'].diff(1)
    return data

# Function to create interactive charts
def plot_data(data):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data['Date'], y=data['Close'], mode='lines', name='Close Price'))
    fig.update_layout(title='Live NSE Data', xaxis_title='Date', yaxis_title='Price')
    st.plotly_chart(fig)

# Streamlit application layout
st.title("Equity Momentum Scanner")
interval = 30  # Refresh interval in seconds

symbol = st.sidebar.text_input("Enter NSE Symbol", "RELIANCE")
if st.button("Fetch Data"):
    while True:
        data = fetch_data(symbol)
        if data:
            data = pd.DataFrame(data)
            data = calculate_momentum(data)
            st.write(data)
            plot_data(data)
        st.empty()
        time.sleep(interval)

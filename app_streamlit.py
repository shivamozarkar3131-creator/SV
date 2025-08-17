import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from sr_core import analyze, SRConfig
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import requests
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="S/R with RSI, MACD & Volume", layout="wide")
st.title("📈 Support & Resistance + RSI & MACD + Volume Confirmation + Trading Signals")

# --------------------------
# Auto-refresh every 30 seconds
# --------------------------
refresh_count = st_autorefresh(interval=30_000, key="live_refresh")
st.sidebar.write(f"🔄 Auto-refresh count: {refresh_count}")

# --------------------------
# Google Sheets Setup
# --------------------------
gcreds_json = st.secrets["g_sheet_json"]
gcreds_dict = json.loads(gcreds_json)
spreadsheet_id = st.secrets["g_sheet_id"]
tab_name = st.secrets.get("g_sheet_tab", "Sheet1")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(gcreds_dict, scopes=scope)
gc = gspread.authorize(creds)
sh = gc.open_by_key(spreadsheet_id)
worksheet = sh.worksheet(tab_name)

def read_watchlist():
    try:
        values = worksheet.col_values(1)
        return [v.strip().upper() for v in values if v.strip()]
    except:
        return []

def add_to_watchlist(symbol):
    symbol = symbol.strip().upper()
    if symbol and symbol not in st.session_state.watchlist:
        st.session_state.watchlist.append(symbol)
        worksheet.append_row([symbol])

def remove_from_watchlist(symbol):
    symbol = symbol.strip().upper()
    if symbol in st.session_state.watchlist:
        st.session_state.watchlist.remove(symbol)
        try:
            cell = worksheet.find(symbol)
            if cell:
                worksheet.delete_row(cell.row)
        except:
            pass

# --------------------------
# Load watchlist from Google Sheets
# --------------------------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = read_watchlist() or ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

# --------------------------
# Tabs for Home & Watchlist
# --------------------------
tab = st.sidebar.radio("Select View", ["Home", "Watchlist"])

# --------------------------
# Manage Watchlist
# --------------------------
st.sidebar.subheader("Manage Watchlist")
st.sidebar.write("Current Watchlist:")
for sym in st.session_state.watchlist:
    st.sidebar.write(f"- {sym}")

# Add new symbol
new_symbol = st.sidebar.text_input("Add Symbol (e.g., HDFCBANK.NS)")
if st.sidebar.button("Add Symbol"):
    add_to_watchlist(new_symbol)
    st.success(f"Added {new_symbol.upper()} to watchlist")

# Remove a symbol
remove_symbol = st.sidebar.selectbox("Remove Symbol", [""] + st.session_state.watchlist)
if st.sidebar.button("Remove Symbol"):
    remove_from_watchlist(remove_symbol)
    st.warning(f"Removed {remove_symbol} from watchlist")

# --------------------------
# General Inputs
# --------------------------
st.sidebar.subheader("Analysis Options")
symbol_input = st.sidebar.text_input("Stock Symbol for Home", "RELIANCE.NS")
period = st.sidebar.selectbox("Select Period", ["1mo", "3mo", "6mo", "1y", "2y"])
interval = st.sidebar.selectbox("Select Interval", ["5m", "15m", "30m", "1h", "2h", "1d"])
distance = st.sidebar.number_input("SR Distance", min_value=1, max_value=50, value=5, step=1)
tolerance = st.sidebar.number_input("SR Tolerance", min_value=0.001, max_value=0.05, value=0.01, step=0.001)

# Indicator options
st.sidebar.subheader("Indicator Options")
show_rsi = st.sidebar.checkbox("Show RSI Chart", value=True)
show_macd = st.sidebar.checkbox("Show MACD Chart", value=True)
enable_sound_alert = st.sidebar.checkbox("Enable Sound Alerts", value=False)
enable_email_alert = st.sidebar.checkbox("Enable Email Alerts", value=False)

# Email credentials
if enable_email_alert:
    st.sidebar.subheader("Email Settings")
    email_sender = st.sidebar.text_input("Sender Email (Outlook)", "signalvyapar@outlook.com")
    email_password = st.sidebar.text_input("Password / App Password", type="password")
    email_receiver = st.sidebar.text_input("Recipient Email", "shivamozarkar3131@gmail.com")

# Telegram settings
st.sidebar.subheader("📲 Telegram Alerts")
enable_telegram_alert = st.sidebar.checkbox("Enable Telegram Alerts", value=False)
telegram_token = st.secrets.get("telegram_token", "")
telegram_chat_id = st.secrets.get("telegram_chat_id", "")

# Telegram test button
if st.sidebar.button("Send Test Telegram Alert"):
    if telegram_token and telegram_chat_id:
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            payload = {"chat_id": telegram_chat_id, "text": "✅ Test Telegram Alert from S/R App!"}
            requests.post(url, data=payload)
            st.sidebar.success("Test Telegram alert sent successfully!")
        except Exception as e:
            st.sidebar.error(f"Failed to send test alert: {e}")
    else:
        st.sidebar.warning("Please provide Bot Token and Chat ID in Streamlit secrets!")

# --------------------------
# RSI & MACD Parameters
# --------------------------
st.sidebar.subheader("Indicator Parameters")
rsi_period = st.sidebar.number_input("RSI Period", min_value=5, max_value=50, value=14, step=1)
macd_fast = st.sidebar.number_input("MACD Fast EMA", min_value=5, max_value=50, value=12, step=1)
macd_slow = st.sidebar.number_input("MACD Slow EMA", min_value=10, max_value=100, value=26, step=1)
macd_signal = st.sidebar.number_input("MACD Signal EMA", min_value=5, max_value=30, value=9, step=1)

# Volume filter
st.sidebar.subheader("Volume Confirmation")
enable_volume_filter = st.sidebar.checkbox("Enable Volume Confirmation for Signals", value=True)

# --------------------------
# Email and Telegram functions
# --------------------------
def send_email_alert(subject, body, from_email, password, to_email):
    from email.mime.text import MIMEText
    import smtplib
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    try:
        with smtplib.SMTP('smtp.office365.com', 587) as server:
            server.starttls()
            server.login(from_email, password)
            server.send_message(msg)
            st.success(f"✅ Email sent to {to_email}")
    except Exception as e:
        st.error(f"Email send failed: {e}")

def send_telegram_alert(message, token, chat_id):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message}
        requests.post(url, data=payload)
        st.success("📲 Telegram alert sent!")
    except Exception as e:
        st.error(f"Telegram send failed: {e}")

# --------------------------
# Function to show stock
# --------------------------
def show_stock(symbol, hide_sr=False):
    st.subheader(f"🔹 {symbol}")
    try:
        cfg = SRConfig(distance=distance, tolerance=tolerance, min_touches=2)
        sr, df, signals = analyze(
            symbol=symbol, period=period, interval=interval, cfg=cfg,
            rsi_period=rsi_period, macd_fast=macd_fast, macd_slow=macd_slow,
            macd_signal=macd_signal, use_volume=enable_volume_filter
        )

        if "last_alert" not in st.session_state:
            st.session_state.last_alert = {}
        if symbol not in st.session_state.last_alert:
            st.session_state.last_alert[symbol] = None

        st.write("🚨 Live Alerts")
        for sig in signals:
            alert_text = f"{sig['signal']} Signal! Price: {sig['price']}\nReason: {sig['reason']}"
            if sig.get("Volume"):
                alert_text += f"\nVolume: {sig['Volume']:.0f}"
            is_new = sig['signal'] != st.session_state.last_alert.get(symbol)
            color = "green" if sig["signal"] == "BUY" else "red" if sig["signal"] == "SELL" else "blue"

            if is_new:
                st.markdown(f"<div style='color:{color}; padding:10px'>{alert_text}</div>", unsafe_allow_html=True)

                if sig["signal"] in ["BUY", "SELL"]:
                    if enable_email_alert and email_sender and email_password and email_receiver:
                        send_email_alert(f"{sig['signal']} Alert for {symbol}", alert_text,
                                         email_sender, email_password, email_receiver)
                    if enable_telegram_alert and telegram_token and telegram_chat_id:
                        send_telegram_alert(f"🚨 {sig['signal']} Alert for {symbol}\n{alert_text}",
                                            telegram_token, telegram_chat_id)
                st.session_state.last_alert[symbol] = sig['signal']

    except Exception as e:
        st.error(f"Error fetching {symbol}: {e}")

# --------------------------
# Display stocks based on tab
# --------------------------
if tab == "Home":
    selected_stock = st.sidebar.selectbox("Select a stock from watchlist", st.session_state.watchlist)
    if selected_stock:
        show_stock(selected_stock, hide_sr=False)
else:
    st.subheader("📢 Watchlist Live Alerts Only")
    for sym in st.session_state.watchlist:
        show_stock(sym, hide_sr=True)

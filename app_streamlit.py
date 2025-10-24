import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from sr_core import analyze, SRConfig
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh
import requests
import json
import os

# --------------------------
# Watchlist persistence
# --------------------------
WATCHLIST_FILE = "watchlist.json"

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f:
            return json.load(f)
    return ["TATAMOTORS.NS", "IDFCFIRSTB.NS", "WIPRO.NS", "LODHA.NS", "VBL.NS", "ATHERENERG.NS", "TATASTEEL.NS"]

def save_watchlist(watchlist):
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(watchlist, f)

# --------------------------
# Streamlit page config
# --------------------------
st.set_page_config(page_title="S/R with RSI, MACD & Volume", layout="wide")
st.title("📈 Signalv14")

# --------------------------
# Auto-refresh every 30 seconds
# --------------------------
refresh_count = st_autorefresh(interval=30_000, key="live_refresh")
st.sidebar.write(f"🔄 Auto-refresh count: {refresh_count}")

# --------------------------
# Tabs for Home & Watchlist
# --------------------------
tab = st.sidebar.radio("Select View", ["Home", "Watchlist"])

# --------------------------
# Watchlist management
# --------------------------
if "watchlist" not in st.session_state:
    st.session_state.watchlist = load_watchlist()

st.sidebar.subheader("Manage Watchlist")
st.sidebar.write("Current Watchlist:")
for sym in st.session_state.watchlist:
    st.sidebar.write(f"- {sym}")

# Add new symbol
new_symbol = st.sidebar.text_input("Add Symbol (e.g., HDFCBANK.NS)")
if st.sidebar.button("Add Symbol"):
    if new_symbol.strip() and new_symbol.upper() not in st.session_state.watchlist:
        st.session_state.watchlist.append(new_symbol.upper())
        save_watchlist(st.session_state.watchlist)
        st.success(f"Added {new_symbol.upper()} to watchlist")

# Remove a symbol
remove_symbol = st.sidebar.selectbox("Remove Symbol", [""] + st.session_state.watchlist)
if st.sidebar.button("Remove Symbol"):
    if remove_symbol in st.session_state.watchlist:
        st.session_state.watchlist.remove(remove_symbol)
        save_watchlist(st.session_state.watchlist)
        st.warning(f"Removed {remove_symbol} from watchlist")

# --------------------------
# General Inputs
# --------------------------
st.sidebar.subheader("Analysis Options")
symbol_input = st.sidebar.text_input("Stock Symbol for Home", "RELIANCE.NS")
period = st.sidebar.selectbox("Select Period", ["1mo", "3mo", "6mo", "1y", "2y"])
interval = st.sidebar.selectbox("Select Interval", ["1h", "15m", "30m", "5m", "2h", "1d"])
distance = st.sidebar.number_input("SR Distance", min_value=1, max_value=50, value=5, step=1)
tolerance = st.sidebar.number_input("SR Tolerance", min_value=0.001, max_value=0.05, value=0.01, step=0.001)

# --------------------------
# Indicator options
# --------------------------
st.sidebar.subheader("Indicator Options")
show_rsi = st.sidebar.checkbox("Show RSI Chart", value=True)
show_macd = st.sidebar.checkbox("Show MACD Chart", value=True)
enable_sound_alert = st.sidebar.checkbox("Enable Sound Alerts", value=False)
enable_email_alert = st.sidebar.checkbox("Enable Email Alerts", value=False)

# --------------------------
# Telegram & Email credentials from Streamlit secrets
# --------------------------
telegram_token = st.secrets.get("telegram_token", "")
telegram_chat_id = st.secrets.get("telegram_chat_id", "")
email_sender = st.secrets.get("email_sender", "")
email_password = st.secrets.get("email_password", "")
email_receiver = st.secrets.get("email_receiver", "")

# --------------------------
# Telegram test alert button
# --------------------------
st.sidebar.subheader("📲 Test Telegram Alert")
if st.sidebar.button("Send Test Telegram Alert"):
    if telegram_token and telegram_chat_id:
        try:
            url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
            payload = {"chat_id": telegram_chat_id, "text": "✅ Chaltay Re Bhawa Barobr !! - v1.1"}
            requests.post(url, data=payload)
            st.sidebar.success("Test Telegram alert sent successfully!")
        except Exception as e:
            st.sidebar.error(f"Failed to send test alert: {e}")
    else:
        st.sidebar.warning("Please set Telegram credentials in Streamlit secrets.toml!")

# --------------------------
# Indicator Parameters
# --------------------------
st.sidebar.subheader("Indicator Parameters")
rsi_period = st.sidebar.number_input("RSI Period", min_value=5, max_value=50, value=14, step=1)
macd_fast = st.sidebar.number_input("MACD Fast EMA", min_value=5, max_value=50, value=12, step=1)
macd_slow = st.sidebar.number_input("MACD Slow EMA", min_value=10, max_value=100, value=26, step=1)
macd_signal = st.sidebar.number_input("MACD Signal EMA", min_value=5, max_value=30, value=9, step=1)

# --------------------------
# Volume Confirmation Toggle
# --------------------------
st.sidebar.subheader("Volume Confirmation")
enable_volume_filter = st.sidebar.checkbox("Enable Volume Confirmation for Signals", value=False)

# --------------------------
# CSS & JS for pop-up alerts
# --------------------------
st.markdown("""
<style>
@keyframes blink { 0% { background-color: inherit; } 50% { background-color: yellow; } 100% { background-color: inherit; } }
.blink { animation: blink 1s linear 2; }
#popup-alert {
    position: fixed; top: 20px; right: 20px;
    background-color: #ffcc00; color: black; padding: 15px;
    border-radius: 10px; box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
    z-index: 9999; font-weight: bold; display: none;
}
</style>
<script>
function showPopup(message) {
    var popup = document.getElementById('popup-alert');
    popup.innerText = message;
    popup.style.display = 'block';
    setTimeout(function() { popup.style.display = 'none'; }, 5000);
}
</script>
<div id="popup-alert"></div>
""", unsafe_allow_html=True)

# --------------------------
# Email alert function
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

# --------------------------
# Telegram alert function
# --------------------------
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

        if not hide_sr:
            st.write("📊 Support & Resistance Levels")
            st.dataframe(pd.DataFrame(sr))

        st.write("🚨 Live Alerts")
        for sig in signals:
            alert_text = f"{sig['signal']} Signal! Price: {sig['price']}\nReason: {sig['reason']}"
            if sig.get("Volume"):
                alert_text += f"\nVolume: {sig['Volume']:.0f}"

            is_new = sig['signal'] != st.session_state.last_alert.get(symbol)
            color = "green" if sig["signal"] == "BUY" else "red" if sig["signal"] == "SELL" else "blue"

            if is_new:
                st.markdown(f"<div class='blink' style='color:{color}; padding:10px; border-radius:5px; background-color:white'>{alert_text}</div>", unsafe_allow_html=True)

                if sig["signal"] in ["BUY", "SELL"]:
                    components.html(f"<script>showPopup('{alert_text}');</script>", height=0)

                    if enable_sound_alert:
                        components.html("""<audio autoplay><source src="https://www.soundjay.com/buttons/sounds/beep-07.mp3" type="audio/mpeg"></audio>""", height=0)

                    if enable_email_alert and email_sender and email_password and email_receiver:
                        send_email_alert(subject=f"{sig['signal']} Alert for {symbol}", body=alert_text,
                                         from_email=email_sender, password=email_password, to_email=email_receiver)
                    if telegram_token and telegram_chat_id:
                            volume_status = "CONFIRMED" if enable_volume_filter else "NOT CONFIRMED"
                            send_telegram_alert(
                                f"📊 v1.1\n"
                                f"🚨 {sig['signal']} Alert for {symbol}\n"
                                f"⏳ Period: {period}, Interval: {interval}\n"
                                f"Volume: {volume_status}\n"
                                f"{alert_text}",
                                telegram_token,
                                telegram_chat_id
                            )


                st.session_state.last_alert[symbol] = sig['signal']
            else:
                st.markdown(f"<div style='color:gray; padding:10px; border-radius:5px; background-color:#f5f5f5'>{alert_text}</div>", unsafe_allow_html=True)

        if not hide_sr:
            if show_rsi:
                st.subheader("📊 RSI Indicator")
                fig_rsi = go.Figure()
                fig_rsi.add_trace(go.Scatter(x=df.index, y=df["RSI"], mode="lines", name="RSI"))
                fig_rsi.add_hline(y=70, line_dash="dot", line_color="red")
                fig_rsi.add_hline(y=30, line_dash="dot", line_color="green")
                st.plotly_chart(fig_rsi, use_container_width=True)
            if show_macd:
                st.subheader("📊 MACD Indicator")
                fig_macd = go.Figure()
                fig_macd.add_trace(go.Scatter(x=df.index, y=df["MACD"], mode="lines", name="MACD"))
                fig_macd.add_trace(go.Scatter(x=df.index, y=df["MACD_Signal"], mode="lines", name="Signal"))
                st.plotly_chart(fig_macd, use_container_width=True)

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

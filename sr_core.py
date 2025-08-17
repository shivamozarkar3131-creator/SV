import pandas as pd
import numpy as np
from scipy.signal import find_peaks
import yfinance as yf

# ------------------------------
# Configuration class
# ------------------------------
class SRConfig:
    """Configuration for Support/Resistance detection."""
    def __init__(self, distance: int = 5, tolerance: float = 0.01, min_touches: int = 2):
        self.distance = distance
        self.tolerance = tolerance
        self.min_touches = min_touches

# ------------------------------
# Swing detection
# ------------------------------
def find_swings(df, cfg):
    highs = pd.to_numeric(df['High'], errors='coerce').dropna().values
    lows = pd.to_numeric(df['Low'], errors='coerce').dropna().values
    peak_idx, _ = find_peaks(highs, distance=cfg.distance)
    trough_idx, _ = find_peaks(-lows, distance=cfg.distance)
    return peak_idx, trough_idx

# ------------------------------
# Compute SR levels
# ------------------------------
def compute_sr_levels(df, cfg):
    peak_idx, trough_idx = find_swings(df, cfg)
    sr_levels = []

    for idx in peak_idx:
        sr_levels.append({"type": "resistance", "price": df['High'].iloc[idx], "date": df.index[idx]})
    for idx in trough_idx:
        sr_levels.append({"type": "support", "price": df['Low'].iloc[idx], "date": df.index[idx]})

    sr_levels.sort(key=lambda x: x['date'])
    return sr_levels

# ------------------------------
# Technical Indicators
# ------------------------------
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period, min_periods=1).mean()
    rs = gain / (loss + 1e-6)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

# ------------------------------
# Generate Live Trading Signals
# ------------------------------
def generate_signals(df, sr_levels, use_volume=False):
    signals = []
    last_row = df.iloc[-1]

    rsi = last_row.get("RSI", None)
    macd = last_row.get("MACD", None)
    macd_signal = last_row.get("MACD_Signal", None)
    close_price = last_row["Close"]
    current_volume = last_row.get("Volume", None)
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1] if 'Volume' in df.columns else None
    signal_generated = False

    for lvl in sr_levels[-5:]:
        # Support / BUY
        if lvl["type"] == "support" and close_price <= lvl["price"] * 1.01:
            if rsi is not None and macd is not None and macd_signal is not None:
                if rsi < 30 and macd > macd_signal and (not use_volume or (current_volume and avg_volume and current_volume > avg_volume)):
                    signals.append({
                        "signal": "BUY",
                        "reason": "RSI oversold + near support + MACD bullish" + (" + Volume confirmation" if use_volume else ""),
                        "price": close_price,
                        "time": last_row.name,
                        "RSI": rsi,
                        "MACD": macd,
                        "Volume": current_volume
                    })
                    signal_generated = True

        # Resistance / SELL
        if lvl["type"] == "resistance" and close_price >= lvl["price"] * 0.99:
            if rsi is not None and macd is not None and macd_signal is not None:
                if rsi > 70 and macd < macd_signal and (not use_volume or (current_volume and avg_volume and current_volume > avg_volume)):
                    signals.append({
                        "signal": "SELL",
                        "reason": "RSI overbought + near resistance + MACD bearish" + (" + Volume confirmation" if use_volume else ""),
                        "price": close_price,
                        "time": last_row.name,
                        "RSI": rsi,
                        "MACD": macd,
                        "Volume": current_volume
                    })
                    signal_generated = True

    # Only add HOLD if no BUY/SELL signals
    if not signal_generated:
        signals.append({
            "signal": "HOLD",
            "reason": "No strong signal",
            "price": close_price,
            "time": last_row.name,
            "RSI": rsi,
            "MACD": macd,
            "Volume": current_volume
        })

    return signals

# ------------------------------
# Main analysis function
# ------------------------------
def analyze(symbol=None, period=None, interval=None, csv_path=None, df=None, cfg=None,
            rsi_period=14, macd_fast=12, macd_slow=26, macd_signal=9, use_volume=False):
    if cfg is None:
        cfg = SRConfig()

    # Fetch or use existing data
    if df is not None:
        data = df.copy()
    elif csv_path:
        data = pd.read_csv(csv_path)
    elif symbol is not None:
        data = yf.download(symbol, period=period or "6mo", interval=interval or "1d", auto_adjust=True)
        if data.empty:
            raise ValueError("No data fetched from yfinance. Check symbol or internet.")
    else:
        raise ValueError("Must provide df, csv_path, or symbol to analyze.")

    # Flatten MultiIndex columns if any
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = ['_'.join(col).strip() if isinstance(col, tuple) else col for col in data.columns]

    # Standardize column names
    col_map = {}
    for col in data.columns:
        col_lower = col.lower()
        if 'open' in col_lower: col_map[col] = 'Open'
        elif 'high' in col_lower: col_map[col] = 'High'
        elif 'low' in col_lower: col_map[col] = 'Low'
        elif 'close' in col_lower: col_map[col] = 'Close'
        elif 'volume' in col_lower: col_map[col] = 'Volume'
    data = data.rename(columns=col_map)

    # Ensure required columns exist
    required_cols = {'High', 'Low', 'Open', 'Close', 'Volume'}
    if not required_cols.issubset(data.columns):
        raise ValueError(f"Data must contain columns: {required_cols}")

    # Convert columns to numeric
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    data.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'], inplace=True)

    # Ensure datetime index
    if not isinstance(data.index, pd.DatetimeIndex):
        if 'Date' in data.columns:
            data['Date'] = pd.to_datetime(data['Date'])
            data.set_index('Date', inplace=True)
        else:
            data.index = pd.to_datetime(data.index)

    # Compute SR, RSI, MACD
    sr = compute_sr_levels(data, cfg)
    data["RSI"] = compute_rsi(data["Close"], period=rsi_period)
    data["MACD"], data["MACD_Signal"] = compute_macd(data["Close"],
                                                     fast=macd_fast,
                                                     slow=macd_slow,
                                                     signal=macd_signal)

    # Generate signals
    signals = generate_signals(data, sr, use_volume=use_volume)
    return sr, data, signals

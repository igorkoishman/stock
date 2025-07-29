import io, os, re
import numpy as np
import pandas as pd
from urllib.parse import urlparse
from app.db import get_db_connection

def extract_file_base_name(filename_or_url):
    if filename_or_url.startswith('http'):
        parsed = urlparse(filename_or_url)
        file = os.path.basename(parsed.path)
    else:
        file = os.path.basename(filename_or_url)
    return os.path.splitext(file)[0]

def parse_csv(content):
    df = pd.read_csv(io.StringIO(content))
    for col in ['Close/Last', 'Open', 'High', 'Low']:
        df[col] = df[col].replace(r'[\$,]', '', regex=True).astype(float)
    df['Volume'] = df['Volume'].replace(r'[,]', '', regex=True).astype(int)
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
    return df

def insert_data(df, file_name):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for _, row in df.iterrows():
                try:
                    cur.execute("""
                        INSERT INTO stock_prices
                        (date, close_last, volume, open, high, low, label)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date, label) DO NOTHING;
                    """, (
                        row['Date'], row['Close/Last'], row['Volume'],
                        row['Open'], row['High'], row['Low'],
                        file_name.split('_')[0].upper()
                    ))
                except Exception as e:
                    print(f"Error inserting row: {e}")
        conn.commit()

def parse_search(search):
    conditions = []
    params = []
    parts = [p.strip() for p in re.split(r'\band\b|,', search, flags=re.I) if p.strip()]
    valid_cols = {'label', 'date', 'volume', 'close_last', 'open', 'high', 'low'}

    for part in parts:
        if ':' in part:
            col, val = [x.strip() for x in part.split(':', 1)]
            col = col.lower()
            if col in valid_cols:
                if col == 'label':
                    m = re.match(r'^(=|==)?\s*(.*)$', val)
                    if m:
                        conditions.append(f"{col} ILIKE %s")
                        params.append(f'%{m.group(2)}%')
                elif col == 'date':
                    conditions.append("CAST(date AS TEXT) ILIKE %s")
                    params.append(f'%{val}%')
                elif col in {'volume', 'close_last', 'open', 'high', 'low'}:
                    m = re.match(r'^(>=|<=|>|<|=)?\s*(.*)$', val)
                    if m:
                        op = m.group(1) or '='
                        number = m.group(2).replace(',', '').replace(' ', '')
                        try:
                            floatval = float(number)
                            conditions.append(f"{col} {op} %s")
                            params.append(floatval)
                        except ValueError:
                            pass
        else:
            conditions.append("(label ILIKE %s OR CAST(date AS TEXT) ILIKE %s)")
            params.extend([f'%{part}%', f'%{part}%'])

    return ("WHERE " + " AND ".join(conditions), params) if conditions else ("", [])

def sanitize_fig(obj):
    if isinstance(obj, dict):
        return {k: sanitize_fig(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_fig(x) for x in obj]
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, float):
        return None if np.isnan(obj) or np.isinf(obj) else obj
    return obj

def safe_float(val):
    try:
        if val is None or pd.isna(val) or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
            return None
        return float(val)
    except Exception:
        return None

def generate_suggestions(df, price_col='close_last', avg_col='avg'):
    if avg_col not in df or df[avg_col].isna().all():
        return []

    df['avg_prev'] = df[avg_col].shift(1)
    df['avg_gradient'] = df[avg_col] - df['avg_prev']
    df['diff'] = df[price_col] - df[avg_col]
    df['crossing'] = df['diff'] * df['diff'].shift(1) < 0

    suggestions = []
    last_action = "Nothing"
    long_position = False
    for idx, row in df.iterrows():
        date = str(row.get('date_str', row['date']))
        price = safe_float(row[price_col])
        avg = safe_float(row[avg_col])
        gradient = row['avg_gradient']
        crossing = row['crossing']
        diff = row['diff']

        action = "Nothing"
        if not long_position and crossing:
            if gradient > 0 and diff > 0:
                action = "Long"
                long_position = True
            elif gradient < 0 and diff < 0:
                action = "Short"
                long_position = True
        elif long_position and last_action == "Long" and crossing:
            if gradient > 0 and diff < 0 or gradient > 0 and diff > 0:
                action = "Sell"
                long_position = False
            elif gradient < 0 and diff < 0:
                action = "Short"
        elif long_position and last_action == "Short" and crossing:
            if gradient > 0 and diff > 0:
                action = "Long"
                long_position = True
            elif gradient > 0 and diff < 0 or gradient < 0 and diff > 0:
                action = "Sell"
                long_position = False

        if action in ["Long", "Short", "Sell"]:
            last_action = action

        suggestions.append({"date": date, "price": price, "avg": avg, "action": action})
    return suggestions

def get_long_decision_summary(suggestions):
    first_oper = next((s for s in suggestions if s['action'] in ["Long", "Short"]), None)
    if not first_oper:
        return None
    last = suggestions[-1]
    try:
        percent_change = 100 * (last['price'] - first_oper['price']) / first_oper['price']
    except Exception:
        percent_change = None
    return {
        "first_operation_date": first_oper["date"],
        "first_operation_price": first_oper["price"],
        "last_operation_date": last["date"],
        "last_operation_price": last["price"],
        "percent_change": round(percent_change, 2) if percent_change is not None else None
    }

def clean_suggestions_keep_last_as_sell(suggestions):
    if not suggestions:
        return []
    cleaned = [s for s in suggestions[:-1] if s['action'] != "Nothing"]
    last = suggestions[-1].copy()
    if last['action'] == "Nothing":
        last['action'] = "Sell"
    cleaned.append(last)
    return cleaned

def analyze_trades(suggestions):
    from datetime import datetime
    trades = []
    i = 0
    while i < len(suggestions) - 1:
        entry, exit = suggestions[i], suggestions[i+1]
        if entry["action"] not in ["Long", "Short"] or exit["action"] != "Sell":
            i += 1
            continue

        pnl_pct = 100 * (exit["price"] - entry["price"]) / entry["price"] if entry["action"] == "Long" else 100 * (entry["price"] - exit["price"]) / entry["price"]
        pct = 100 * (exit["price"] / entry["price"]) if entry["action"] == "Long" else 100 * (entry["price"] / exit["price"])
        holding_days = (datetime.strptime(exit["date"], "%Y-%m-%d") - datetime.strptime(entry["date"], "%Y-%m-%d")).days

        trades.append({
            "stock": entry["stock"],
            "entry_action": entry["action"],
            "entry_date": entry["date"],
            "entry_price": entry["price"],
            "exit_date": exit["date"],
            "exit_price": exit["price"],
            "pnl_pct": round(pnl_pct, 2),
            "pnl_percentage": f"{round(pct, 2)}%",
            "holding_days": holding_days
        })
        i += 2
    return trades

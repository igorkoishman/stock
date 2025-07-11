import os
import io
import glob
import numpy as np
import pandas as pd
import psycopg2
import plotly.graph_objs as go
from urllib.parse import urlparse
from flask import Flask, request, render_template, jsonify
from sqlalchemy import create_engine
import re


# --- CONFIG ---
PG_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
PG_DB   = os.environ.get('POSTGRES_DB', 'stocks')
PG_USER = os.environ.get('POSTGRES_USER', 'postgres')
PG_PASS = os.environ.get('POSTGRES_PASSWORD', 'postgres')
PG_PORT = int(os.environ.get('POSTGRES_PORT', 5432))

app = Flask(__name__)

engine = create_engine(f'postgresql+psycopg2://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}')

def get_db_connection():
    """Creates a new psycopg2 connection."""
    return psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        port=PG_PORT
    )

def extract_file_base_name(filename_or_url):
    """Extracts base filename from a path or URL (without extension)."""
    if filename_or_url.startswith('http'):
        parsed = urlparse(filename_or_url)
        file = os.path.basename(parsed.path)
    else:
        file = os.path.basename(filename_or_url)
    base, _ = os.path.splitext(file)
    return base

def parse_csv(content):
    """Parses CSV content to DataFrame, cleans price and volume columns."""
    df = pd.read_csv(io.StringIO(content))
    for col in ['Close/Last', 'Open', 'High', 'Low']:
        df[col] = df[col].replace(r'[\$,]', '', regex=True).astype(float)
    df['Volume'] = df['Volume'].replace(r'[,]', '', regex=True).astype(int)
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
    return df

def insert_data(df, file_name):
    """Inserts stock DataFrame rows into DB, skipping duplicates."""
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

def safe_float(val):
    """Converts a value to float or returns None if not safe."""
    try:
        if val is None or pd.isna(val) or (isinstance(val, float) and (np.isnan(val) or np.isinf(val))):
            return None
        return float(val)
    except Exception:
        return None

def generate_suggestions(df, price_col='close_last', avg_col='avg'):
    """Generate buy/sell/hold suggestions based on price/avg crossovers."""
    if avg_col not in df or df[avg_col].isna().all():
        print("No average data, skipping suggestions.")
        return []

    suggestions = []
    prev_relation = None
    for idx, row in df.iterrows():
        date = str(row['date_str']) if 'date_str' in row else str(row['date'])
        price = safe_float(row[price_col])
        avg = safe_float(row[avg_col])
        if price is None or avg is None:
            continue

        action = "Nothing"
        relation = price - avg
        if prev_relation is not None:
            if prev_relation < 0 and relation > 0:
                action = "Buy"
            elif prev_relation > 0 and relation < 0:
                action = "Sell"
        prev_relation = relation

        suggestions.append({
            "date": date,
            "price": price,
            "avg": avg,
            "action": action
        })
    print(f"Generated {len(suggestions)} suggestion(s) based on average.")
    return suggestions

def parse_search(search):
    """Returns (where_clause, params) for SQL based on advanced search string."""
    conditions = []
    params = []
    # Split on 'and' or ',' (case-insensitive), remove empty entries
    parts = [p.strip() for p in re.split(r'\band\b|,', search, flags=re.I) if p.strip()]
    valid_cols = {'label', 'date', 'volume', 'close_last', 'open', 'high', 'low'}

    for part in parts:
        if ':' in part:
            col, val = [x.strip() for x in part.split(':', 1)]
            col = col.lower()
            if col in valid_cols:
                if col == 'label':
                    # Support =, ==, or default equals, and ilike for partial
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
            # fallback: plain text search on label or date
            conditions.append("(label ILIKE %s OR CAST(date AS TEXT) ILIKE %s)")
            params.extend([f'%{part}%', f'%{part}%'])

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)
    else:
        where_clause = ""
    return where_clause, params

@app.route('/', methods=['GET'])
def index():
    """Main page: Displays table of stock data, with multi-condition search support."""
    search = request.args.get('search', '').strip()
    base_query = """
        SELECT date, close_last, volume, open, high, low, label
        FROM stock_prices
    """
    where_clause, params = parse_search(search) if search else ("", [])
    query = base_query + " " + where_clause + " ORDER BY date DESC, label ASC"

    params_tuple = tuple(params) if params else ()
    df = pd.read_sql_query(query, engine, params=params_tuple)
    table_html = df.to_html(classes="table table-striped table-bordered align-middle", index=False, border=0, justify="center")
    return render_template("index.html", table_html=table_html, search=search)

@app.route('/upload', methods=['POST'])
def upload():
    """Upload endpoint for CSV files or folders."""
    files = request.files.getlist('file')
    if files and files[0].filename != '':
        not_csv = [f.filename for f in files if not f.filename.lower().endswith('.csv')]
        if not_csv:
            return jsonify({'error': f"All files must be CSV! These files are not: {', '.join(not_csv)}"}), 400
        results = []
        for uploaded_file in files:
            csv_data = uploaded_file.read().decode()
            file_name = extract_file_base_name(uploaded_file.filename)
            try:
                df = parse_csv(csv_data)
                insert_data(df, file_name)
                results.append({'file': file_name, 'rows': len(df), 'status': 'ok'})
            except Exception as e:
                results.append({'file': file_name, 'error': str(e), 'status': 'fail'})
        return jsonify({'results': results})

    folder_path = request.form.get('folder_path')
    if folder_path:
        results = []
        all_files = glob.glob(os.path.join(folder_path, '*'))
        csv_files = [f for f in all_files if f.lower().endswith('.csv')]
        if not csv_files:
            return jsonify({'error': 'No .csv files found in that folder.'}), 400
        for filepath in csv_files:
            with open(filepath, 'r', encoding='utf-8') as f:
                csv_data = f.read()
            file_name = extract_file_base_name(filepath)
            try:
                df = parse_csv(csv_data)
                insert_data(df, file_name)
                results.append({'file': file_name, 'rows': len(df), 'status': 'ok'})
            except Exception as e:
                results.append({'file': file_name, 'error': str(e), 'status': 'fail'})
        return jsonify({'results': results})
    return jsonify({'error': 'No files or folder path provided.'}), 400

@app.route('/charts')
def charts():
    """Charts UI endpoint: List available stocks."""
    with engine.connect() as conn:
        stock_names = pd.read_sql_query("SELECT DISTINCT label FROM stock_prices ORDER BY label;", conn)
    return render_template("charts.html", stock_names=stock_names['label'].tolist())

def sanitize_fig(obj):
    """
    Recursively sanitize Plotly figure dict:
      - Converts np.ndarray -> list
      - NaN/inf -> None
    """
    if isinstance(obj, dict):
        return {k: sanitize_fig(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_fig(x) for x in obj]
    elif isinstance(obj, np.ndarray):
        return [sanitize_fig(x) for x in obj.tolist()]
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return obj
    else:
        return obj

@app.route('/chart-data')
def chart_data():
    """
    API endpoint: returns plotly JSON & suggestions for given stocks/date range/params.
    """
    stocks = request.args.get("stock", "").split(",")
    start = request.args.get("start")
    end = request.args.get("end")
    chart_type = request.args.get("type")
    avg_days = request.args.get("avg")
    include_current = request.args.get("include") == "1"

    if not stocks or not start or not end or not chart_type:
        return jsonify({"error": "Missing required parameters."}), 400

    if include_current and not avg_days:
        return jsonify({"error": "Include current requires average_days_back."}), 400

    df = pd.read_sql_query(
        """
        SELECT date, close_last, open, high, low, label
        FROM stock_prices
        WHERE label = ANY(%s)
          AND date BETWEEN %s AND %s
        ORDER BY date ASC
        """,
        con=engine,
        params=(stocks, start, end)
    )

    if df.empty:
        return jsonify({"error": "No data found in range."}), 404

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ["open", "high", "low", "close_last"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["date", "open", "high", "low", "close_last"])
    df = df.sort_values(["label", "date"])
    df["date_str"] = df["date"].dt.strftime("%Y-%m-%d")

    fig = go.Figure()
    all_suggestions = []

    for stock in stocks:
        s_df = df[df["label"] == stock].copy()
        if s_df.empty:
            continue

        if chart_type == "line":
            fig.add_trace(go.Scatter(
                x=s_df["date_str"],
                y=s_df["close_last"],
                mode="lines",
                name=stock
            ))
        elif chart_type == "candlestick":
            fig.add_trace(go.Candlestick(
                x=s_df["date_str"],
                open=s_df["open"],
                high=s_df["high"],
                low=s_df["low"],
                close=s_df["close_last"],
                name=stock
            ))
        else:
            return jsonify({"error": f"Unknown chart type: {chart_type}"}), 400

        # Optional overlay: average line and suggestions
        suggestions = []
        if avg_days:
            try:
                window = int(avg_days)
                if include_current:
                    s_df["avg"] = s_df["close_last"].rolling(window=window).mean()
                else:
                    s_df["avg"] = s_df["close_last"].shift(1).rolling(window=window).mean()

                fig.add_trace(go.Scatter(
                    x=s_df["date_str"],
                    y=s_df["avg"],
                    mode="lines",
                    name=f"{stock} Avg {window}d",
                    line=dict(dash="solid")
                ))
                suggestions = generate_suggestions(s_df)
            except Exception as e:
                print(f"⚠️ Failed to calculate average for {stock}: {e}")

        all_suggestions += [
            dict(stock=stock, **item)
            for item in (suggestions or [])
        ]

    fig.update_layout(
        title=f"{chart_type.capitalize()} Chart for {', '.join(stocks)}",
        xaxis_title="Date",
        yaxis_title="Price",
        xaxis=dict(
            type="category" if chart_type == "candlestick" else "date",
            rangeslider={"visible": chart_type == "candlestick"}
        ),
        margin=dict(t=60)
    )

    fig_dict = fig.to_dict()
    fig_dict = sanitize_fig(fig_dict)
    return jsonify({
        "plotly_figure": fig_dict,
        "suggestions": all_suggestions
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

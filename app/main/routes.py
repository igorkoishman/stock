import glob
import os
import pandas as pd
import plotly.graph_objs as go
from flask import Blueprint, request, render_template, jsonify
from flask_login import login_required
from sqlalchemy import create_engine
from app.main.utils import (
    extract_file_base_name, parse_csv, insert_data, parse_search, sanitize_fig,
    generate_suggestions, get_long_decision_summary, clean_suggestions_keep_last_as_sell, analyze_trades
)
from flask import current_app

main_bp = Blueprint('main', __name__)

def get_engine():
    return create_engine(
        f"postgresql+psycopg2://{current_app.config['PG_USER']}:{current_app.config['PG_PASS']}@"
        f"{current_app.config['PG_HOST']}:{current_app.config['PG_PORT']}/{current_app.config['PG_DB']}"
    )

@main_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '').strip()
    engine = get_engine()
    base_query = """
        SELECT date, close_last, volume, open, high, low, label
        FROM stock_prices
    """
    where_clause, params = parse_search(search) if search else ("", [])
    query = base_query + " " + where_clause + " ORDER BY date DESC, label ASC"
    df = pd.read_sql_query(query, engine, params=tuple(params) if params else ())
    table_html = df.to_html(classes="table table-striped table-bordered align-middle", index=False, border=0, justify="center")
    return render_template("index.html", table_html=table_html, search=search)

@main_bp.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('file')
    results = []

    if files and files[0].filename != '':
        not_csv = [f.filename for f in files if not f.filename.lower().endswith('.csv')]
        if not_csv:
            return jsonify({'error': f"All files must be CSV! These files are not: {', '.join(not_csv)}"}), 400

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

@main_bp.route('/charts')
@login_required
def charts():
    engine = get_engine()
    with engine.connect() as conn:
        stock_names = pd.read_sql_query("SELECT DISTINCT label FROM stock_prices ORDER BY label;", conn)
    return render_template("charts.html", stock_names=stock_names['label'].tolist())

@main_bp.route('/chart-data')
@login_required
def chart_data():
    stocks = request.args.get("stock", "").split(",")
    start = request.args.get("start")
    end = request.args.get("end")
    chart_type = request.args.get("type")
    avg_days = request.args.get("avg")
    include_current = request.args.get("include") == "1"

    if not stocks or not chart_type:
        return jsonify({"error": "Missing required parameters."}), 400

    if include_current and not avg_days:
        return jsonify({"error": "Include current requires average_days_back."}), 400

    engine = get_engine()
    query = """
        SELECT date, close_last, open, high, low, label
        FROM stock_prices
        WHERE label = ANY(%s)
    """
    params = (stocks,)

    if start and end:
        query += " AND date BETWEEN %s AND %s"
        params.extend([start, end])

    query += " ORDER BY date ASC"
    print("Params:", params)
    print("Param types:", [type(p) for p in params])
    df = pd.read_sql_query(query, con=engine, params=params)

    if df.empty:
        return jsonify({"error": "No data found in range."}), 404

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
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

    fig_dict = sanitize_fig(fig.to_dict())
    default_operation = get_long_decision_summary(all_suggestions)
    cleaned = clean_suggestions_keep_last_as_sell(all_suggestions)
    trade_table = analyze_trades(cleaned)

    return jsonify({
        "plotly_figure": fig_dict,
        "suggestions": all_suggestions,
        "default_operation": default_operation,
        "trade_table": trade_table
    })

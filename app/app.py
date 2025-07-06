import os
import io
import glob
from urllib.parse import urlparse
import pandas as pd
import psycopg2
from flask import Flask, request, render_template, jsonify

# --- CONFIG ---
PG_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
PG_DB = os.environ.get('POSTGRES_DB', 'stocks')
PG_USER = os.environ.get('POSTGRES_USER', 'postgres')
PG_PASS = os.environ.get('POSTGRES_PASSWORD', 'postgres')
PG_PORT = int(os.environ.get('POSTGRES_PORT', 5432))

app = Flask(__name__)

# --- DB Connection ---
def get_db_connection():
    return psycopg2.connect(
        host=PG_HOST,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASS,
        port=PG_PORT
    )

def extract_file_base_name(filename_or_url):
    if filename_or_url.startswith('http'):
        parsed = urlparse(filename_or_url)
        file = os.path.basename(parsed.path)
    else:
        file = os.path.basename(filename_or_url)
    base, _ = os.path.splitext(file)
    return base

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
                        (date, close_last, volume, open, high, low, file_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (date, file_name) DO NOTHING;
                    """, (row['Date'], row['Close/Last'], row['Volume'],
                          row['Open'], row['High'], row['Low'], file_name.split('_')[0]))
                except Exception as e:
                    print(f"Error inserting row: {e}")
        conn.commit()

@app.route('/', methods=['GET'])
def index():
    search = request.args.get('search', '').strip()
    with get_db_connection() as conn:
        base_query = """
            SELECT date, close_last, volume, open, high, low, file_name
            FROM stock_prices
        """
        params = []
        where_clause = ""

        if search:
            if ':' in search:
                parts = [part.strip() for part in search.split(':', 1)]
                if len(parts) == 2:
                    col, val = parts
                    col = col.lower()
                    valid_cols = {'file_name', 'date', 'volume', 'close_last', 'open', 'high', 'low'}
                    if col in valid_cols:
                        if col in ['file_name']:
                            where_clause = f"WHERE {col} ILIKE %s"
                            params = [f'%{val}%']
                        elif col == 'date':
                            where_clause = "WHERE CAST(date AS TEXT) ILIKE %s"
                            params = [f'%{val}%']
                        elif col in ['volume']:
                            try:
                                intval = int(val.replace(',', '').replace(' ', ''))
                                where_clause = f"WHERE {col} = %s"
                                params = [intval]
                            except ValueError:
                                where_clause = "WHERE 1=0"
                        else:
                            try:
                                floatval = float(val)
                                where_clause = f"WHERE ABS({col} - %s) < 1e-6"
                                params = [floatval]
                            except ValueError:
                                where_clause = "WHERE 1=0"
            else:
                where_clause = "WHERE file_name ILIKE %s OR CAST(date AS TEXT) ILIKE %s"
                params = [f'%{search}%', f'%{search}%']

        query = base_query + " " + where_clause + " ORDER BY date DESC, file_name ASC"
        df = pd.read_sql_query(query, conn, params=params)

    table_html = df.to_html(classes="table table-striped table-bordered align-middle", index=False, border=0, justify="center")
    return render_template("index.html", table_html=table_html, search=search)

@app.route('/upload', methods=['POST'])
def upload():
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
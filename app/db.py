import psycopg2
from flask import current_app

def get_db_connection():
    return psycopg2.connect(
        host=current_app.config['PG_HOST'],
        dbname=current_app.config['PG_DB'],
        user=current_app.config['PG_USER'],
        password=current_app.config['PG_PASS'],
        port=current_app.config['PG_PORT']
    )

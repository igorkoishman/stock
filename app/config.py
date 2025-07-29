import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev_super_secret_change_me")
    PG_HOST = os.environ.get('POSTGRES_HOST', 'localhost')
    PG_DB   = os.environ.get('POSTGRES_DB', 'stocks')
    PG_USER = os.environ.get('POSTGRES_USER', 'postgres')
    PG_PASS = os.environ.get('POSTGRES_PASSWORD', 'postgres')
    PG_PORT = int(os.environ.get('POSTGRES_PORT', 55432))
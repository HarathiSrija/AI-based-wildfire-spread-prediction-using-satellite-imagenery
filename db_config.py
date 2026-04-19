# db_config.py
import mysql.connector

def get_db_connection():
    db = mysql.connector.connect(
        host="localhost",
        port=3306,          # your MySQL port
        user="root",
        password="root",
        database="wildfire"
    )
    return db
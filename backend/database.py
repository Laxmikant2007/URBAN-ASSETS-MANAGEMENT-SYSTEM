
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "urban_assets_db"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
    )

if __name__ == "__main__":
    try:
        connection = get_db_connection()

        if connection.is_connected():
            print("SUCCESS: Connected to urban_assets_db!")

            cursor = connection.cursor()
            cursor.execute("SHOW TABLES")

            print("\nTables in the database:")
            for table in cursor.fetchall():
                print("-", table[0])

            cursor.close()
            connection.close()

    except mysql.connector.Error as error:
        print("MySQL connection failed.")
        print("Error:", error)

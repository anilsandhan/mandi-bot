import psycopg2
import os

url = "postgresql://postgres:Sandhan%402021@db.loflxnrbalaamtzdpdtf.supabase.co:5432/postgres"

print("Trying direct connection...")
try:
    conn = psycopg2.connect(url, sslmode="require", connect_timeout=10)
    print("SUCCESS -- connected to Supabase")
    conn.close()
except Exception as e:
    print(f"FAILED: {e}")

print("\nTrying without SSL...")
try:
    conn = psycopg2.connect(url, connect_timeout=10)
    print("SUCCESS -- connected without SSL")
    conn.close()
except Exception as e:
    print(f"FAILED: {e}")
import os
import sqlite3

import requests
from bs4 import BeautifulSoup

BASE = r"C:\Users\PC\OneDrive\Documentos\GitHub\Lumini"
TDB = os.path.join(BASE, 'colegios_db', 'testcolegio.db')
conn = sqlite3.connect(TDB)
c = conn.cursor()

print("=== RECTORES ===")
for r in c.execute("SELECT id, usuario FROM rectores").fetchall():
    print(f"  id={r[0]}, usuario={r[1]}")

print("=== PROFESORES ===")
for r in c.execute("SELECT id, usuario FROM profesores").fetchall():
    print(f"  id={r[0]}, usuario={r[1]}")

print("=== DIRECTORAS ===")
for r in c.execute("SELECT id, usuario FROM directoras").fetchall():
    print(f"  id={r[0]}, usuario={r[1]}")

conn.close()

# Now try logging in with correct usernames
SERVER = "http://127.0.0.1:5050"

def get_csrf(html):
    t = BeautifulSoup(html, 'html.parser').find("input", {"name": "_csrf_token"})
    return t["value"] if t and t.get("value") else "x"

print("\n=== TRY RECTOR ===")
s = requests.Session()
r = s.get(f"{SERVER}/testcolegio/rector/login")
tok = get_csrf(r.text)
r = s.post(f"{SERVER}/testcolegio/rector/login",
           data={"usuario":"rector_prueba","password":"test123","_csrf_token":tok},
           allow_redirects=False)
print(f"  Status: {r.status_code}, Location: {r.headers.get('Location','')}")
if r.status_code in (302, 303):
    r2 = s.get(f"{SERVER}/testcolegio/rector")
    print(f"  Panel size: {len(r2.text)}b, final URL: {r2.url}")

print("\n=== TRY TEACHER ===")
s2 = requests.Session()
r = s2.get(f"{SERVER}/testcolegio/login")
tok = get_csrf(r.text)
# Try juan_perez first
for usr in ["juan_perez", "profesor", "ana_lopez"]:
    s3 = requests.Session()
    r = s3.get(f"{SERVER}/testcolegio/login")
    tok = get_csrf(r.text)
    r = s3.post(f"{SERVER}/testcolegio/login",
                data={"accion":"profesor_login","usuario":usr,"password":"test123","_csrf_token":tok},
                allow_redirects=False)
    print(f"  Teacher '{usr}': Status={r.status_code}, Location={r.headers.get('Location','')[:50] if r.headers.get('Location') else 'none'}")

print("\n=== TRY DIRECTORA ===")
s4 = requests.Session()
r = s4.get(f"{SERVER}/testcolegio/directora/login")
tok = get_csrf(r.text)
for usr in ["directora", "coord_test"]:
    s5 = requests.Session()
    r = s5.get(f"{SERVER}/testcolegio/directora/login")
    tok = get_csrf(r.text)
    r = s5.post(f"{SERVER}/testcolegio/directora/login",
                data={"username":usr,"password":"test123","_csrf_token":tok},
                allow_redirects=False)
    print(f"  Directora '{usr}': Status={r.status_code}, Location={r.headers.get('Location','')[:50] if r.headers.get('Location') else 'none'}")

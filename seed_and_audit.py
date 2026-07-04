"""Seed DB with test users and run visual audit"""
import sqlite3, os, hashlib, bcrypt, requests, re, json
from bs4 import BeautifulSoup
from collections import defaultdict

BASE = r"C:\Users\PC\OneDrive\Documentos\GitHub\Lumini"
TDB = os.path.join(BASE, 'colegios_db', 'testcolegio.db')
SERVER = "http://127.0.0.1:5050"

def hash_sha256(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def hash_bcrypt(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=12)).decode()

def get_csrf(html):
    soup = BeautifulSoup(html, 'html.parser')
    t = soup.find("input", {"name": "_csrf_token"})
    return t["value"] if t and t.get("value") else "x"

def seed_db():
    print("Seeding testcolegio.db...")
    conn = sqlite3.connect(TDB)
    c = conn.cursor()
    
    # Update all rectores to known password
    pwd = hash_sha256("test123")
    c.execute("UPDATE rectores SET password=? WHERE password IS NOT NULL", (pwd,))
    affected = c.rowcount
    print(f"  Updated {affected} rector password(s) to 'test123'")
    
    # Update all profesores to known password
    pwd = hash_bcrypt("test123")
    c.execute("UPDATE profesores SET password=? WHERE password IS NOT NULL", (pwd,))
    affected = c.rowcount
    print(f"  Updated {affected} profesor password(s) to 'test123'")
    
    # Update all directoras to known password
    c.execute("UPDATE directoras SET password=? WHERE password IS NOT NULL", (pwd,))
    affected = c.rowcount
    print(f"  Updated {affected} directora password(s) to 'test123'")
    
    conn.commit()
    conn.close()
    print("Seeding complete!")

def fetch_and_analyze():
    s = requests.Session()
    issues = []
    pages_data = []
    
    def login(path, data):
        r = s.post(f"{SERVER}{path}", data=data, allow_redirects=False)
        return r.status_code in (302, 303)
    
    # Login attempts
    print("\nLogging in...")
    
    r = s.get(f"{SERVER}/testcolegio/rector/login")
    tok = get_csrf(r.text)
    ok = login("/testcolegio/rector/login", {"usuario":"rector","password":"test123","_csrf_token":tok})
    print(f"  Rector login: {'OK' if ok else 'FAIL'}")
    
    r = s.get(f"{SERVER}/testcolegio/login")
    tok = get_csrf(r.text)
    ok = login("/testcolegio/login", {"username":"profesor","password":"test123","accion":"profesor_login","_csrf_token":tok})
    print(f"  Teacher login: {'OK' if ok else 'FAIL'}")
    
    # Directora login via /<slug>/directora/login
    r = s.get(f"{SERVER}/testcolegio/directora/login")
    tok = get_csrf(r.text)
    ok = login("/testcolegio/directora/login", {"username":"directora","password":"test123","_csrf_token":tok})
    print(f"  Directora login: {'OK' if ok else 'FAIL'}")
    
    # Admin login
    ok = login("/admin", {"password":"R5Uj6nq3a8ZfAmgz","_csrf_token":"x"})
    print(f"  Admin login: {'OK' if ok else 'FAIL'}")
    
    # Pages to fetch
    pages_to_fetch = [
        ("/", "landing", False),
        ("/admin/login","admin_login", False),
        ("/testcolegio/login","login_v2", False),
        ("/testcolegio/rector/login","rector_login", False),
        ("/testcolegio/directora/login","directora_login", False),
        ("/admin","admin_panel", True),
        ("/admin/codigos","admin_codigos", True),
        ("/testcolegio","index_profesor", True),
        ("/testcolegio/rector","rector_panel", True),
        ("/testcolegio/rector/profesores","rector_profesores", True),
        ("/testcolegio/rector/estudiantes","rector_estudiantes", True),
        ("/testcolegio/rector/cursos","rector_cursos", True),
        ("/testcolegio/rector/horarios","rector_horarios", True),
        ("/testcolegio/rector/reportes","rector_reportes", True),
        ("/testcolegio/rector/configuracion","rector_configuracion", True),
        ("/testcolegio/rector/comunicaciones","rector_comunicaciones", True),
        ("/testcolegio/rector/comunicaciones/nueva","rector_comunicacion_nueva", True),
        ("/testcolegio/rector/canales","rector_canales", True),
        ("/testcolegio/rector/auditoria","rector_auditoria", True),
        ("/testcolegio/rector/solicitudes","rector_solicitudes", True),
        ("/testcolegio/notificaciones","notificaciones", True),
        ("/testcolegio/horarios","horarios_profesor", True),
        ("/testcolegio/archivados","archivados", True),
        ("/testcolegio/transferir_curso","transferir_curso", True),
        ("/testcolegio/cambiar_password","cambiar_password", True),
        ("/testcolegio/seleccionar","seleccionar_jornada", True),
        ("/testcolegio/estudiante","estudiante", True),
        ("/testcolegio/directora","directora_panel", True),
    ]
    
    checked = set()
    for path, name, need_auth in pages_to_fetch:
        try:
            r = s.get(f"{SERVER}{path}", timeout=10, allow_redirects=True)
            html = r.text
            key = path + ":" + str(hash(html) % 100000)
            if key in checked:
                continue
            checked.add(key)
            
            pages_data.append({"path": path, "name": name, "status": r.status_code, "size": len(html), "final_url": r.url})
            
            soup = BeautifulSoup(html, 'html.parser')
            
            right_page = True
            if need_auth and len(html) < 1000:
                issues.append(f"[AUTH] {name} ({path}): Too small ({len(html)}b) - got login/error page")
                right_page = False
            
            # Check for login page markers in need_auth pages
            if need_auth and right_page:
                body_text = html[:2000].lower()
                if "usuario" in body_text and "contraseña" in body_text and len(html) < 2000:
                    issues.append(f"[AUTH] {name} ({path}): Got login page instead of dashboard")
                    right_page = False
            
            if right_page and len(html) > 1000:
                icons = soup.find_all("i", attrs={"data-lucide": True})
                stat_cards = soup.find_all(class_="stat-card")
                stat_grids = soup.find_all(class_="stats-grid")
                quick_actions = soup.find_all(class_="quick-actions-grid")
                
                if stat_cards and not stat_grids:
                    issues.append(f"[GRID] {name}: {len(stat_cards)} stat-card(s) without stats-grid")
                
                sidebar = soup.find(class_="sidebar")
                main = soup.find(class_="main")
                if sidebar and not main and "login" not in name:
                    issues.append(f"[LAYOUT] {name}: sidebar without .main")
                
                # Check for rendering issues
                body_tag = soup.find("body")
                if body_tag:
                    inline_count = len(body_tag.find_all(style=True))
                    if inline_count > 100:
                        issues.append(f"[STYLE] {name}: {inline_count} inline styles")
                
                print(f"  {r.status_code:3d} {name:35s} ({len(html):6d}b) icons:{len(icons):2d} cards:{len(stat_cards)} final:{r.url}")
            else:
                print(f"  {r.status_code:3d} {name:35s} ({len(html):6d}b) {'(redirect/no-auth)' if not right_page else ''}")
            
        except Exception as e:
            issues.append(f"[FETCH] {name} ({path}): {e}")
            print(f"  ERR {name}: {e}")
    
    print(f"\n{'='*60}")
    print(f"Pages fetched: {len(pages_data)}")
    print(f"Issues found: {len(issues)}")
    print(f"{'='*60}")
    for iss in sorted(set(issues)):
        print(f"  ! {iss}")
    
    with open(os.path.join(BASE, "audit_live.json"), "w") as f:
        json.dump({"pages": pages_data, "issues": sorted(set(issues))}, f, indent=2)
    print("\nSaved audit_live.json")

if __name__ == "__main__":
    seed_db()
    fetch_and_analyze()

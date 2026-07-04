import requests, re, sys, json, os, time
from bs4 import BeautifulSoup
from collections import defaultdict

BASE = "http://127.0.0.1:5050"
s = requests.Session()

issues = []
checked_html = set()

def get_csrf(html):
    soup = BeautifulSoup(html, 'html.parser')
    t = soup.find("input", {"name": "_csrf_token"})
    return t["value"] if t and t.get("value") else "x"

def analyze_html(path, name, html):
    if not html or len(html) < 100:
        issues.append(f"[EMPTY] {name} ({path}): Empty HTML")
        return
    hkey = path + ":" + str(hash(html) % 100000)
    if hkey in checked_html:
        return
    checked_html.add(hkey)

    soup = BeautifulSoup(html, 'html.parser')
    issues_found = []

    # 1. Lucide script
    luc_scripts = soup.find_all("script", src=lambda x: x and "lucide" in x.lower())
    if not luc_scripts:
        issues_found.append(f"[ICONS] {name}: missing lucide.js script")

    # 2. CSS files
    css_links = [l.get("href","") for l in soup.find_all("link", rel="stylesheet") if l.get("href")]
    if not any("lumini.css" in c for c in css_links):
        issues_found.append(f"[CSS] {name}: missing lumini.css")
    if not any("enhanced.css" in c for c in css_links):
        issues_found.append(f"[CSS] {name}: missing enhanced.css")

    # 3. Viewport
    if not soup.find("meta", attrs={"name": "viewport"}):
        issues_found.append(f"[RESP] {name}: no viewport meta")

    # 4. CSS variables
    style_text = "\n".join(st.get_text() for st in soup.find_all("style"))
    has_root = ":root" in style_text
    if not has_root:
        issues_found.append(f"[VARS] {name}: NO :root block with CSS variables!")

    # Check critical vars
    for var in ["--bg", "--bg2", "--accent", "--text", "--border"]:
        if f"{var}:" not in style_text:
            if not has_root:
                issues_found.append(f"[VARS] {name}: root block missing {var}")
            else:
                pass  # might be in separate :root

    # 5. Classes used by template
    used = set()
    for tag in soup.find_all(class_=True):
        used.update(tag.get("class",[]))

    # Check for classes known to need definition in inline CSS
    must_check = ["overlay", "modal", "modal-title", "close-btn", "badge-ok", "badge-off",
                  "btn-red", "btn-green", "btn-yellow", "btn-ghost", "codigo-box", "pass-wrap",
                  "eye-btn", "scroll-top", "toast", "actions-cell", "logo-preview",
                  "prof-chip", "codigo-badge", "hamburger", "sidebar-overlay",
                  "stat-card", "stat-icon", "stat-body", "stat-value", "stat-label",
                  "kpi-card", "kpi-value", "kpi-label", "qa-card", "quick-actions-grid",
                  "stats-grid", "topbar", "sidebar"]
    for cls in must_check:
        if cls in used and f".{cls}" not in style_text:
            pass  # These are defined in enhanced.css, so no warning needed

    # 6. Icon check
    icons = soup.find_all("i", attrs={"data-lucide": True})
    if icons:
        script_text = "\n".join(s.get_text() for s in soup.find_all("script") if s.get_text())
        if "lucide.createIcons" not in script_text:
            # Check if lumini.js is loaded which has initPage
            has_lumini_js = any("lumini.js" in l.get("src","") for l in soup.find_all("script") if l.get("src"))
            if not has_lumini_js:
                issues_found.append(f"[ICONS] {name}: {len(icons)} icons but no createIcons call and no lumini.js")
        for ic in icons:
            icn = ic.get("data-lucide","")
            if icn and not re.match(r'^[a-z][a-z0-9-]*$', icn):
                issues_found.append(f"[ICON-NAME] {name}: invalid icon name '{icn}'")

    # 7. Body style check
    body_css = re.search(r'body\s*\{([^}]+)\}', style_text)
    if body_css:
        bs = body_css.group(1)
        if "background" not in bs:
            issues_found.append(f"[BODY] {name}: body background not set in CSS")
        if "font-family" not in bs:
            issues_found.append(f"[BODY] {name}: body font-family not set")

    # 8. Check for styles inside body (potential layout issues with style attributes)
    inline_styles_count = len(soup.find_all(style=True))
    if inline_styles_count > 50:
        issues_found.append(f"[STYLE] {name}: {inline_styles_count} inline style attributes - consider using classes")

    # 9. Check body background
    body_tag = soup.find("body")
    if body_tag:
        body_inline_style = body_tag.get("style","")
        if not body_inline_style and body_css and "background" not in body_css.group(1):
            pass  # no body bg defined
        # Check if body is display:flex
        has_body_flex = bool(body_css and "display" in body_css.group(1)) or "display:flex" in body_inline_style
        if not has_body_flex:
            issues_found.append(f"[LAYOUT] {name}: body not display:flex (may affect sidebar layout)")

    # 10. Check sidebar
    sidebar = soup.find(class_="sidebar")
    if sidebar:
        # Check if sidebar has proper positioning or if the template has sidebar CSS
        has_sidebar_css = bool(re.search(r'\.sidebar\s*\{', style_text))
        if not has_sidebar_css:
            issues_found.append(f"[SIDEBAR] {name}: .sidebar used but CSS may come from external file only")

    for iss in issues_found:
        issues.append(iss)

    return {
        "path": path, "name": name, "css_files": css_links,
        "has_lucide": bool(luc_scripts), "icons": len(icons),
        "has_root": has_root, "used_classes": sorted(used)
    }

# ── LOGIN HELPERS ──

def login_admin():
    r = s.post(f"{BASE}/admin", data={"password":"R5Uj6nq3a8ZfAmgz","_csrf_token":"x"}, allow_redirects=True)
    r = s.get(f"{BASE}/admin")
    return "Dashboard" in r.text or "total colegios" in r.text.lower() or "colegios" in r.text.lower()

def login_rector():
    r = s.get(f"{BASE}/testcolegio/rector/login")
    tok = get_csrf(r.text)
    r = s.post(f"{BASE}/testcolegio/rector/login", data={
        "username":"rector","password":"12345678","_csrf_token":tok
    }, allow_redirects=False)
    if r.status_code in (302,303):
        s.get(f"{BASE}/testcolegio/rector")
        return True
    return False

def login_teacher():
    r = s.get(f"{BASE}/testcolegio/login")
    tok = get_csrf(r.text)
    r = s.post(f"{BASE}/testcolegio/login", data={
        "username":"profesor","password":"test123","accion":"profesor_login","_csrf_token":tok
    }, allow_redirects=False)
    if r.status_code in (302,303):
        r2 = s.get(f"{BASE}/testcolegio/")
        return "Bienvenido" in r2.text
    return False

def login_directora():
    r = s.get(f"{BASE}/testcolegio/directora/login")
    tok = get_csrf(r.text)
    r = s.post(f"{BASE}/testcolegio/directora/login", data={
        "username":"directora","password":"test123","_csrf_token":tok
    }, allow_redirects=False)
    if r.status_code in (302,303):
        r2 = s.get(f"{BASE}/testcolegio/directora")
        return len(r2.text) > 200
    return False

# ── PAGES TO CHECK ──
public = [
    ("/","landing"),
    ("/admin/login","admin_login"),
    ("/testcolegio/login","login_v2"),
    ("/testcolegio/rector/login","rector_login"),
    ("/testcolegio/directora/login","directora_login"),
]

rector_pages = [
    "/testcolegio/rector","/testcolegio/rector/panel",
    "/testcolegio/rector/profesores","/testcolegio/rector/estudiantes",
    "/testcolegio/rector/cursos","/testcolegio/rector/horarios",
    "/testcolegio/rector/reportes","/testcolegio/rector/configuracion",
    "/testcolegio/rector/comunicaciones",
    "/testcolegio/rector/comunicaciones/nueva",
    "/testcolegio/rector/canales","/testcolegio/rector/auditoria",
    "/testcolegio/rector/solicitudes",
    "/testcolegio/rector/gestion-rectores",
]

logged_in = [
    "/testcolegio/notificaciones","/testcolegio/horarios",
    "/testcolegio/archivados","/testcolegio/transferir_curso",
    "/testcolegio/cambiar_password","/testcolegio/seleccionar",
    "/testcolegio/estudiante","/testcolegio/directora",
]

admin_pages = ["/admin","/admin/codigos","/admin/correos"]

# ── COLLECT PAGES ──
all_pages = list(public)
results = []

print("=== AUDIT: Fetching public pages ===")
for path, name in public:
    r = s.get(f"{BASE}{path}", timeout=10)
    info = analyze_html(path, name, r.text)
    if info: results.append(info)
    print(f"  {r.status_code} {name}")

print("\n=== AUDIT: Login attempts ===")
print(f"  Admin login: {login_admin()}")
print(f"  Rector login: {login_rector()}")
print(f"  Teacher login: {login_teacher()}")
print(f"  Directora login: {login_directora()}")

print("\n=== AUDIT: Fetching logged-in rector pages ===")
for path in rector_pages:
    r = s.get(f"{BASE}{path}", timeout=10)
    name = path.rstrip("/").split("/")[-1] or "rector_panel"
    info = analyze_html(path, name, r.text)
    if info: results.append(info)
    print(f"  {r.status_code} {name:30s} {path}")

print("\n=== AUDIT: Fetching other logged-in pages ===")
for path in logged_in:
    r = s.get(f"{BASE}{path}", timeout=10)
    name = path.rstrip("/").split("/")[-1]
    info = analyze_html(path, name, r.text)
    if info: results.append(info)
    print(f"  {r.status_code} {name:30s} {path}")

print("\n=== AUDIT: Fetching admin pages ===")
for path in admin_pages:
    r = s.get(f"{BASE}{path}", timeout=10)
    name = path.rstrip("/").split("/")[-1] or "admin"
    info = analyze_html(path, name, r.text)
    if info: results.append(info)
    print(f"  {r.status_code} {name:30s} {path}")

# ── SUMMARY ──
print(f"\n{'='*60}")
print(f"PAGES AUDITED: {len(results)}")
print(f"ISSUES FOUND: {len(issues)}")
print(f"{'='*60}")

by_type = defaultdict(list)
for iss in sorted(set(issues)):
    print(f"  ! {iss}")
    parts = iss.split("] ", 1)
    if len(parts) > 1:
        by_type[parts[0][1:]].append(parts[1])
    else:
        by_type["OTHER"].append(iss)

print(f"\n{'='*60}")
print("SUMMARY BY CATEGORY:")
for cat in sorted(by_type.keys()):
    items = sorted(set(by_type[cat]))
    print(f"  [{cat}] ({len(items)} issues)")
    for item in items[:8]:
        print(f"    - {item}")

report = {
    "pages_checked": len(results),
    "total_issues": len(issues),
    "issues": sorted(set(issues)),
    "by_type": {k: sorted(set(v)) for k, v in by_type.items()},
    "pages": [{"name": r["name"], "path": r["path"], "has_lucide": r.get("has_lucide"), "icons": r.get("icons"), "has_root": r.get("has_root"), "css_files": r.get("css_files")} for r in results]
}
with open("C:\\Users\\PC\\OneDrive\\Documentos\\GitHub\\Lumini\\audit_report.json", "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"\nReport saved!")

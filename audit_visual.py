import requests, re, sys, json, os
from bs4 import BeautifulSoup
from collections import defaultdict

BASE = "http://127.0.0.1:5050"
s = requests.Session()

PAGES = [
    ("/", "landing"),
    ("/admin/login", "admin_login"),
    ("/testcolegio/login", "login_v2"),
    ("/testcolegio/rector/login", "rector_login"),
    ("/testcolegio/directora/login", "directora_login"),
]

def login_admin():
    r = s.post(f"{BASE}/admin", data={"clave":"admin","_csrf_token":"x"}, allow_redirects=False)
    # Try with the real password via page fetch + parse
    r = s.get(f"{BASE}/admin")
    if "Panel Admin" in r.text or "Dashboard" in r.text or "admin_panel" in r.text:
        return True
    # Try direct login
    r = s.post(f"{BASE}/admin", data={"clave":"admin123","_csrf_token":"x"}, allow_redirects=False)
    if r.status_code in (302, 303):
        r = s.get(f"{BASE}/admin")
        return "admin_panel" in r.text
    return False

def login_rector():
    r = s.get(f"{BASE}/testcolegio/rector/login")
    soup = BeautifulSoup(r.text, 'html.parser')
    token = soup.find("input", {"name": "_csrf_token"})
    tok = token["value"] if token else "x"
    r = s.post(f"{BASE}/testcolegio/rector/login", data={
        "username": "rector", "password": "12345678", "_csrf_token": tok
    }, allow_redirects=False)
    if r.status_code in (302, 303):
        loc = r.headers.get("Location","")
        if "rector" in loc or "panel" in loc:
            r = s.get(f"{BASE}/testcolegio/rector")
            return True
    return False

def login_teacher():
    r = s.get(f"{BASE}/testcolegio/login")
    soup = BeautifulSoup(r.text, 'html.parser')
    token = soup.find("input", {"name": "_csrf_token"})
    tok = token["value"] if token else "x"
    r = s.post(f"{BASE}/testcolegio/login", data={
        "username": "profesor", "password": "12345678", "_csrf_token": tok
    }, allow_redirects=False)
    for r2 in [s.get(f"{BASE}/testcolegio/"), s.get(f"{BASE}/testcolegio")]:
        if "Bienvenido" in r2.text or "estudiante" in r2.text.lower():
            return True
    return False

REWORD_PAGES = ["/testcolegio/rector/panel","/testcolegio/rector/profesores","/testcolegio/rector/estudiantes",
    "/testcolegio/rector/cursos","/testcolegio/rector/horarios","/testcolegio/rector/reportes",
    "/testcolegio/rector/configuracion","/testcolegio/rector/comunicaciones","/testcolegio/rector/comunicaciones/nueva",
    "/testcolegio/rector/canales","/testcolegio/rector/auditoria","/testcolegio/rector/solicitudes",
    "/testcolegio/rector/gestion-rectores","/testcolegio/notificaciones","/testcolegio/horarios",
    "/testcolegio/archivados","/testcolegio/transferir_curso","/testcolegio/cambiar_password",
    "/testcolegio/seleccionar","/testcolegio/estudiante","/testcolegio/directora",
    "/admin","/admin/codigos","/admin/correos",
]

def get_important_pages():
    pages = []
    for path, name in PAGES:
        pages.append((path, name))
    # Logged-in rector pages
    if login_rector():
        for path in REWORD_PAGES:
            if "rector" in path or "notificaciones" in path or "horarios" in path or "archivados" in path or "transferir" in path or "cambiar" in path or "seleccionar" in path:
                pages.append((path, path.rstrip("/").split("/")[-1]))
    # Teacher
    if login_teacher():
        pages.append(("/testcolegio/", "index_profesor"))
        pages.append(("/testcolegio/horarios", "horarios_profesor"))
    # Admin
    if login_admin():
        for p in ["/admin","/admin/codigos","/admin/correos"]:
            pages.append((p, p.strip("/").replace("/","_")))
    # Directora
    r = s.get(f"{BASE}/testcolegio/directora/login")
    soup = BeautifulSoup(r.text, 'html.parser')
    token = soup.find("input", {"name": "_csrf_token"})
    tok = token["value"] if token else "x"
    r = s.post(f"{BASE}/testcolegio/directora/login", data={
        "username": "directora", "password": "12345678", "_csrf_token": tok
    }, allow_redirects=False)
    if r.status_code in (302, 303):
        pages.append(("/testcolegio/directora", "directora_panel"))
    return pages

issues = []
checked = set()

def analyze_html(path, name, html):
    if not html or len(html) < 100:
        issues.append(f"[MISSING] {name} ({path}): Empty/too short HTML")
        return
    key = f"{path}:{hash(html)%10000}"
    if key in checked:
        return
    checked.add(key)
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # 1. Has lucide script
    lucide_scripts = soup.find_all("script", src=lambda x: x and "lucide" in x.lower())
    if not lucide_scripts:
        issues.append(f"[ICONS] {name} ({path}): Missing lucide.js script tag")
    
    # 2. Has CSS files
    css_links = [l["href"] for l in soup.find_all("link", rel="stylesheet") if l.get("href")]
    if not any("lumini.css" in c for c in css_links):
        issues.append(f"[CSS] {name} ({path}): Missing lumini.css")
    if not any("enhanced.css" in c for c in css_links):
        issues.append(f"[CSS] {name} ({path}): Missing enhanced.css")
    
    # 3. Has :root CSS variables
    style_tags = soup.find_all("style")
    all_css = "\n".join(st.get_text() for st in style_tags)
    if ":root" not in all_css:
        issues.append(f"[VARS] {name} ({path}): NO :root CSS variables in inline style!")
    
    # 4. Check key CSS variables present in :root
    var_checks = ["--bg", "--bg2", "--accent", "--text", "--muted", "--border", "--rsm"]
    for var in var_checks:
        if f"{var}:" not in all_css:
            issues.append(f"[VAR] {name} ({path}): Missing {var} in CSS")
    
    # 5. Check responsive meta viewport
    viewport = soup.find("meta", attrs={"name": "viewport"})
    if not viewport:
        issues.append(f"[RESP] {name} ({path}): Missing viewport meta tag")
    
    # 6. Find classes used but check if they might be missing
    used_classes = set()
    for tag in soup.find_all(class_=True):
        for cls in tag.get("class", []):
            used_classes.add(cls)
    
    # Check for classes known to need definition
    known_needed = ["overlay", "modal", "modal-title", "close-btn", "badge-ok", "badge-off",
                    "btn-red", "btn-green", "btn-yellow", "btn-ghost", "codigo-box", "pass-wrap",
                    "eye-btn", "scroll-top", "toast", "actions-cell", "logo-preview",
                    "prof-chip", "codigo-badge", "hamburger", "sidebar-overlay"]
    for cls in known_needed:
        if cls in used_classes:
            # Check if defined in any style tag or external CSS (we can only check inline)
            if f".{cls}" not in all_css:
                issues.append(f"[MISSING-CLASS] {name} ({path}): class '{cls}' used but NOT defined in inline CSS")
    
    # 7. Check for <i data-lucide="..."> tags (icons)
    lucide_icons = soup.find_all("i", attrs={"data-lucide": True})
    if lucide_icons:
        # Check that lucide.createIcons is called
        all_scripts = "\n".join(s.get_text() for s in soup.find_all("script") if s.get_text())
        if "lucide.createIcons" not in all_scripts:
            issues.append(f"[ICONS] {name} ({path}): Has {len(lucide_icons)} lucide icons but no lucide.createIcons() call")
        
        # Check for common icon name errors
        for icon in lucide_icons:
            name = icon.get("data-lucide", "")
            if not name or not re.match(r'^[a-z][a-z0-9-]*$', name):
                issues.append(f"[ICON-NAME] {name} ({path}): Invalid icon name '{name}'")
    
    # 8. Check for horizontal scroll issues (elements with fixed widths that may overflow)
    for tag in soup.find_all(style=True):
        style = tag.get("style", "")
        if "overflow-x" in style and "hidden" not in style and "auto" not in style:
            pass  # might cause scroll
        if "white-space: nowrap" in style and "overflow" not in style:
            issues.append(f"[SCROLL] {name} ({path}): 'white-space:nowrap' without overflow handling")
    
    # 9. Check for balanced tags
    # Count open/close div tags roughly
    open_divs = html.count("<div ") + html.count("<div>")
    close_divs = html.count("</div>")
    if abs(open_divs - close_divs) > 0:
        issues.append(f"[HTML] {name} ({path}): Unbalanced divs (open={open_divs}, close={close_divs})")
    
    # 10. Check body has proper display
    body_style = ""
    for tag in soup.find_all("style"):
        text = tag.get_text()
        m = re.search(r'body\s*\{([^}]+)\}', text)
        if m:
            body_style = m.group(1)
    if body_style and "display" not in body_style:
        issues.append(f"[LAYOUT] {name} ({path}): body CSS missing 'display' property")
    
    return {
        "path": path,
        "name": name,
        "css_links": css_links,
        "has_lucide_script": bool(lucide_scripts),
        "lucide_icon_count": len(lucide_icons),
        "used_classes": used_classes,
        "has_root_vars": ":root" in all_css,
        "has_viewport": bool(viewport),
    }

pages_to_check = get_important_pages()
print(f"Fetching {len(pages_to_check)} pages...")
results = []
for path, name in pages_to_check:
    try:
        r = s.get(f"{BASE}{path}", timeout=10)
        info = analyze_html(path, name, r.text)
        if info:
            results.append(info)
        print(f"  {r.status_code} {name:40s} {path}")
    except Exception as e:
        issues.append(f"[FETCH] {name} ({path}): {e}")
        print(f"  ERROR {name:40s} {path}: {e}")

# Summary
print(f"\n{'='*60}")
print(f"PAGES CHECKED: {len(results)}")
print(f"ISSUES FOUND: {len(issues)}")
print(f"{'='*60}")
for iss in sorted(set(issues)):
    print(f"  ! {iss}")

# Group issues by type
by_type = defaultdict(list)
for iss in issues:
    parts = iss.split("] ", 1)
    if len(parts) > 1:
        by_type[parts[0][1:]].append(parts[1])
    else:
        by_type["OTHER"].append(iss)

print(f"\n{'='*60}")
print("ISSUES BY CATEGORY:")
for cat, items in sorted(by_type.items()):
    print(f"\n [{cat}] ({len(items)}):")
    for item in sorted(set(items))[:10]:
        print(f"    - {item}")

# Save report
report = {"pages_checked": len(results), "total_issues": len(issues), "issues": sorted(set(issues)), "by_type": {k: sorted(set(v)) for k,v in by_type.items()}}
with open(os.path.join(os.path.dirname(__file__),"audit_report.json"), "w") as f:
    json.dump(report, f, indent=2)
print(f"\nReport saved to audit_report.json")

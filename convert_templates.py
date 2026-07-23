"""Convert standalone templates to extend base.html"""
import os
import re

TEMPLATES_DIR = r"C:\Users\PC\OneDrive\Documentos\GitHub\Lumini\templates"
SKIP_FILES = {"base.html", "components.html", "rector_panel.html"}

# Files that don't have sidebar nav (login, public, etc.)
NO_SIDEBAR = {
    "login_v2.html", "rector_login.html", "directora_login.html",
    "admin_login.html", "recuperar.html", "cambiar_password.html",
    "error.html", "seleccionar_jornada.html", "index.html",
    "index_root.html", "admin_correos.html", "admin_codigos.html",
}

def get_end(filepath):
    """Read end of file to handle closing divs and scripts"""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    # Find the last few closing divs before <script> tags
    # Pattern: we need to identify what's the .main closing div
    return content

def convert_template(filepath):
    basename = os.path.basename(filepath)
    print(f"Converting {basename}...")

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    original = content

    # Extract title
    title_match = re.search(r"<title>(.*?)</title>", content)
    title = title_match.group(1) if title_match else "LUMINI"

    # Extract page-specific CSS (between <style> and </style>)
    style_match = re.search(r"<style>(.*?)</style>", content, re.DOTALL)
    extra_styles = ""
    if style_match:
        css = style_match.group(1)
        # Remove the base variables (root and [data-theme]) that base.html provides
        css_lines = css.split("\n")
        filtered = []
        for line in css_lines:
            stripped = line.strip()
            if stripped.startswith(":root{--bg:") or stripped == ":root{--bg:#080B14;--bg2:#0F172A;--bg3:#1E293B;--bg4:#334155;--border:rgba(255,255,255,.06);{{ accent_css(colegio) }}--blue:#2563EB;--text:#F8FAFC;--muted:#94A3B8;--sub:#64748B;--green:#22C55E;--red:#EF4444;--rsm:6px;--rmd:10px;--rlg:14px;--tr:.2s cubic-bezier(.4,0,.2,1);--sidebar:210px;}":
                continue
            if stripped.startswith(":root{"):
                continue
            if stripped.startswith("[data-theme"):
                continue
            if stripped.startswith("*{box-sizing"):
                continue
            if stripped.startswith("body{font-family"):
                continue
            if stripped in [".sidebar{position:fixed;top:0;left:0;width:var(--sidebar);height:100vh;background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:100;}", ".sidebar{position:fixed;top:0;left:0;width:var(--sidebar);height:100vh;background:var(--bg2);border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:100;transition:transform .25s cubic-bezier(.4,0,.2,1);}"]:
                continue
            if stripped.startswith(".sidebar{position"):
                continue
            if stripped in [".sidebar-header{padding:16px 14px 12px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;}", ".sidebar-header{padding:16px 14px 12px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;flex-shrink:0;}"]:
                continue
            if stripped.startswith(".sidebar-header{"):
                continue
            if stripped in [".sidebar-logo{width:32px;height:32px;border-radius:8px;object-fit:cover;flex-shrink:0;}", ".sidebar-logo{width:32px;height:32px;border-radius:8px;object-fit:cover;}"]:
                continue
            if stripped.startswith(".sidebar-logo{"):
                continue
            if stripped in [".sidebar-brand{font-size:14px;font-weight:800;letter-spacing:2px;background:linear-gradient(135deg,#fff 40%,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}"]:
                continue
            if stripped.startswith(".sidebar-brand{"):
                continue
            if stripped in [".sidebar-sub{font-size:9px;color:var(--muted);letter-spacing:1px;text-transform:uppercase;margin-top:1px;}"]:
                continue
            if stripped.startswith(".sidebar-sub{"):
                continue
            if stripped in [".sidebar-nav{flex:1;padding:8px 6px;overflow-y:auto;}"]:
                continue
            if stripped.startswith(".sidebar-nav{"):
                continue
            if stripped in [".sidebar-section{font-size:9px;color:var(--sub);text-transform:uppercase;letter-spacing:1px;padding:8px 10px 4px;font-weight:600;}", ".sidebar-section{font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;padding:12px 10px 4px;font-weight:600;}"]:
                continue
            if stripped.startswith(".sidebar-section{"):
                continue
            if stripped in [".sidebar-item{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:var(--rsm);color:var(--muted);text-decoration:none;font-size:12px;font-weight:500;transition:all var(--tr);margin-bottom:1px;cursor:pointer;position:relative;}", ".sidebar-item{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:var(--rsm);font-size:12px;font-weight:500;color:var(--text);text-decoration:none;cursor:pointer;position:relative;transition:all var(--tr);}"]:
                continue
            if stripped.startswith(".sidebar-item{"):
                continue
            if stripped.startswith(".sidebar-item:hover"):
                continue
            if stripped.startswith(".sidebar-item.active"):
                continue
            if stripped.startswith(".sidebar-item .icon"):
                continue
            if stripped.startswith(".badge-count"):
                continue
            if stripped.startswith(".sidebar-user"):
                continue
            if stripped.startswith(".main{flex"):
                continue
            if stripped.startswith(".hamburger"):
                continue
            if stripped.startswith(".sidebar-overlay"):
                continue
            if stripped.startswith("@media"):
                continue
            filtered.append(line)
        extra_styles = "\n".join(filtered).strip()

    # Determine if this template has sidebar
    has_sidebar = basename not in NO_SIDEBAR and "sidebar" in content

    # Find the sidebar nav and main content
    new_content = '{% extends "base.html" %}\n'
    if has_sidebar:
        new_content += '{% from "components.html" import sidebar_item %}\n'
    new_content += '{% block title %}' + title + '{% endblock %}\n'
    new_content += '{% block extra_css %}<link rel="stylesheet" href="/static/css/sidebar.css">{% endblock %}\n'
    new_content += '{% block accent_css %}{{ accent_css(colegio) }}{% endblock %}\n'

    if extra_styles:
        new_content += '{% block extra_styles %}\n' + extra_styles + '\n{% endblock %}\n\n'

    # Extract sidebar nav (between <nav class="sidebar" and </nav>)
    if has_sidebar:
        sidebar_match = re.search(
            r'(<nav class="sidebar"[^>]*>.*?</nav>)',
            content, re.DOTALL
        )
        if sidebar_match:
            sidebar_html = sidebar_match.group(1)
            # Simple fixes: class renames and header restructure
            # Replace old sidebar classes and fix header structure
            sidebar_html = sidebar_html.replace('class="sidebar-logo"', 'class="logo"')
            sidebar_html = sidebar_html.replace('class="sidebar-brand"', 'class="brand-name"')
            sidebar_html = sidebar_html.replace('class="sidebar-sub"', 'class="brand-sub"')
            # Convert: <div class="sidebar-header">...<div>\n<div class="brand-name">
            # To:      <div class="sidebar-header">...<div class="brand-text">\n<div class="brand-name">
            sidebar_html = re.sub(
                r'(<div class="sidebar-header">.*?)<div>\s*\n(\s*)<div class="brand-name">',
                r'\1<div class="brand-text">\n\2<div class="brand-name">',
                sidebar_html, flags=re.DOTALL
            )
            # Remove the extra </div> that was wrapping the old <div> around brand
            # Pattern: </div></div></div></a> → </div></div></a>
            sidebar_html = re.sub(
                r'(<div class="brand-sub">.*?</div>)\s*</div>\s*</div>\s*</a>',
                r'\1</div></div></a>',
                sidebar_html, flags=re.DOTALL
            )
            new_content += '{% block sidebar %}\n'
            new_content += sidebar_html + '\n'
            new_content += '{% endblock %}\n\n'

    # Extract main content (between <div class="main"> and the closing </div> before scripts)
    new_content += '{% block content %}\n'

    # Remove everything before <div class="main"> or before <div class="topbar">
    # Some templates have inline CSS in the head section that uses different patterns
    # Get content after </style> or after <body>
    body_match = re.search(r'<body[^>]*>(.*?)(?:</body>|$)', content, re.DOTALL)
    if body_match:
        body_content = body_match.group(1)
    else:
        body_content = content

    # Remove sidebar-overlay div
    body_content = re.sub(
        r'<div class="sidebar-overlay"[^>]*>.*?</div>\s*',
        '', body_content, flags=re.DOTALL
    )

    # Remove hamburger button
    body_content = re.sub(
        r'<button class="hamburger"[^>]*>.*?</button>\s*',
        '', body_content, flags=re.DOTALL
    )

    # Remove theme toggle button
    body_content = re.sub(
        r'<button onclick="toggleTheme\(\)"[^>]*>.*?</button>\s*',
        '', body_content, flags=re.DOTALL
    )

    # Extract main content area
    main_match = re.search(r'<div class="main"[^>]*>(.*)</div>\s*(?:<script|</body|\s*$)', body_content, re.DOTALL)
    if main_match:
        main_content = main_match.group(1).strip()
    else:
        # Try to get everything after </style> and before <script>
        main_content = re.sub(r'^.*?</style>\s*', '', body_content, flags=re.DOTALL)
        main_content = re.sub(r'<script>.*$', '', main_content, flags=re.DOTALL)
        main_content = main_content.strip()

    # Remove lucide script
    main_content = re.sub(
        r'<script src="https://unpkg\.com/lucide[^<]*</script>\s*',
        '', main_content, flags=re.DOTALL
    )

    # Remove lumini.js script
    main_content = re.sub(
        r'<script src="/static/js/lumini\.js"[^>]*></script>\s*',
        '', main_content, flags=re.DOTALL
    )

    # Remove theme toggle script
    main_content = re.sub(
        r'<script>function toggleTheme.*?</script>\s*',
        '', main_content, flags=re.DOTALL
    )

    main_content = main_content.strip()
    new_content += main_content + '\n'
    new_content += '{% endblock %}\n'

    if new_content.strip() != original.strip():
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  Converted ({len(new_content)} chars, was {len(original)})")
    else:
        print("  Skipped (no changes)")


for fname in sorted(os.listdir(TEMPLATES_DIR)):
    if not fname.endswith(".html"):
        continue
    if fname in SKIP_FILES:
        continue
    fpath = os.path.join(TEMPLATES_DIR, fname)
    convert_template(fpath)

print("Done!")

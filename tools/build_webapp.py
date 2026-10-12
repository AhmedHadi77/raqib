"""Build the browser/PWA version of the mobile app into backend/webapp (served at http://<server>:8000).

    python tools/build_webapp.py        (needs: cd mobile && npm install)
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "webapp"
npx = "npx.cmd" if sys.platform == "win32" else "npx"
if OUT.exists():
    shutil.rmtree(OUT)
subprocess.run([npx, "expo", "export", "--platform", "web", "--output-dir", str(OUT)], cwd=ROOT / "mobile", check=True)

# keep only the icon fonts the app uses (smaller download)
fonts = OUT / "assets" / "node_modules" / "@expo" / "vector-icons" / "build" / "vendor" / "react-native-vector-icons" / "Fonts"
if fonts.exists():
    for f in fonts.iterdir():
        if not f.name.startswith(("MaterialCommunityIcons.", "MaterialIcons.")):
            f.unlink()

# keep only the text font weights the app uses (see mobile/src/theme.ts)
USED = ("Archivo_800ExtraBold.", "Archivo_700Bold.", "Archivo_600SemiBold.",
        "PublicSans_400Regular.", "PublicSans_500Medium.", "PublicSans_600SemiBold.")
gf = OUT / "assets" / "node_modules" / "@expo-google-fonts"
if gf.exists():
    for f in list(gf.rglob("*.ttf")):
        if not f.name.startswith(USED):
            f.unlink()
    for d in sorted(gf.rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

# installable web app (Add to Home Screen)
index = OUT / "index.html"
html = index.read_text(encoding="utf-8")
head = ('<link rel="manifest" href="/manifest.json"><meta name="theme-color" content="#0D1530">'
        '<link rel="apple-touch-icon" href="/icon-192.png"><meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Raqib">')
if "manifest.json" not in html:
    html = re.sub(r"</head>", head + "</head>", html, count=1)
index.write_text(html, encoding="utf-8")
print("Web app built ->", OUT)

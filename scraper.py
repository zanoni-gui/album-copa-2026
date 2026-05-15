#!/usr/bin/env python3
"""
scraper.py  –  Panini World Cup 2026 – downloader de figurinhas
Usa Playwright (Chromium real) para passar o Cloudflare Managed Challenge.

Uso:
    pip install playwright beautifulsoup4
    python -m playwright install chromium
    python scraper.py           # normal
    python scraper.py --debug   # salva HTML das páginas
"""

import sys, os, re, time, argparse, json
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── UTF-8 no terminal Windows ─────────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Configuração ──────────────────────────────────────────────────────────────
BASE_URL  = "https://www.laststicker.com"
ALBUM_URL = "https://www.laststicker.com/cards/panini_world_cup_2026/"
OUT_DIR   = Path("players")
OUT_JS    = Path("players.js")
DEBUG_DIR = Path("_debug_html")
DELAY     = 1.0   # segundos entre páginas (não sobrecarregar o servidor)

# ── Cookies opcionais ─────────────────────────────────────────────────────────
# Se você tiver um cf_clearance válido (gerado há menos de 2h no mesmo IP),
# cole aqui para pular o challenge automaticamente. Caso contrário, deixe "".
CF_CLEARANCE = ""

EXTRA_COOKIES = [
    # {"name": "guest", "value": "1",          "domain": ".laststicker.com", "path": "/"},
    # {"name": "fv",    "value": "1778812472", "domain": ".laststicker.com", "path": "/"},
]

# ── Mapa slug → código FIFA ───────────────────────────────────────────────────
SLUG_TO_CODE = {
    "brazil":"BRA","brasil":"BRA","argentina":"ARG","uruguay":"URU",
    "colombia":"COL","ecuador":"ECU","chile":"CHI","peru":"PER",
    "venezuela":"VEN","bolivia":"BOL","paraguay":"PAR","mexico":"MEX",
    "usa":"USA","united-states":"USA","canada":"CAN","costa-rica":"CRC",
    "panama":"PAN","honduras":"HON","el-salvador":"SLV","jamaica":"JAM",
    "haiti":"HAI","curacao":"CUW",
    "france":"FRA","germany":"GER","spain":"ESP","portugal":"POR",
    "england":"ENG","netherlands":"NED","italy":"ITA","belgium":"BEL",
    "croatia":"CRO","serbia":"SRB","poland":"POL","denmark":"DEN",
    "switzerland":"SUI","austria":"AUT","ukraine":"UKR","scotland":"SCO",
    "czech-republic":"CZE","czechia":"CZE","slovakia":"SVK","norway":"NOR",
    "sweden":"SWE","turkey":"TUR","albania":"ALB","georgia":"GEO",
    "bosnia-and-herzegovina":"BIH","bosnia":"BIH","qatar":"QAT",
    "south-korea":"KOR","korea-republic":"KOR","japan":"JPN",
    "australia":"AUS","iran":"IRN","saudi-arabia":"KSA","uzbekistan":"UZB",
    "iraq":"IRQ","jordan":"JOR","indonesia":"IDN","bahrain":"BHR",
    "new-zealand":"NZL",
    "morocco":"MAR","senegal":"SEN","egypt":"EGY","ghana":"GHA",
    "nigeria":"NGA","cameroon":"CMR","ivory-coast":"CIV","cote-d-ivoire":"CIV",
    "mali":"MLI","tunisia":"TUN","algeria":"ALG","south-africa":"RSA",
    "dr-congo":"COD","congo-dr":"COD","democratic-republic-congo":"COD",
    "cape-verde":"CPV","cabo-verde":"CPV",
    # páginas especiais → ignorar
    "stickers":None,"base":None,"special":None,"legend":None,"legends":None,
    "stadium":None,"stadiums":None,"cover":None,"introduction":None,
    "world-cup":None,"world_cup":None,"logo":None,"logos":None,
}

def slug_to_code(slug):
    key = slug.lower().strip("/").replace("_","-")
    if key in SLUG_TO_CODE:
        return SLUG_TO_CODE[key]
    return key[:3].upper()


# ── Funções de parsing ────────────────────────────────────────────────────────
def parse_sections(html):
    soup = BeautifulSoup(html, "html.parser")
    sections = []
    seen = set()
    pat = re.compile(r"^/cards/panini_world_cup_2026/([^/]+)/?$")
    for a in soup.find_all("a", href=True):
        m = pat.match(a["href"])
        if not m:
            continue
        slug = m.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        code = slug_to_code(slug)
        if code is None:
            print(f"   [skip] pagina especial: {slug}")
            continue
        sections.append((urljoin(BASE_URL, a["href"]), code, slug))
    return sections

def img_src(tag):
    for attr in ("src","data-src","data-lazy-src","data-original"):
        v = tag.get(attr,"").strip()
        if v and not v.startswith("data:"):
            return v
    return ""

def extract_number(text):
    nums = re.findall(r"\b(\d{1,4})\b", text)
    return nums[0] if nums else None

def parse_stickers(html, code):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    # Estratégia A: containers com classe contendo "sticker","card","item"
    containers = []
    for pat in (r"\bsticker\b", r"\bcard\b", r"\bfigurinha\b", r"\bitem\b"):
        found = soup.find_all(["div","li","span","article"],
                              class_=re.compile(pat, re.I))
        if found:
            containers = found
            break

    def process_img(img, context_text="", context_href=""):
        src = img_src(img)
        if not src or src in seen:
            return
        num = None
        for attr in ("alt","title"):
            num = extract_number(img.get(attr,""))
            if num: break
        if not num and context_href:
            num = extract_number(context_href)
        if not num:
            num = extract_number(context_text)
        if not num:
            m = re.search(r"[/_-](\d{1,4})\.(jpg|jpeg|png|webp)", src, re.I)
            if m: num = m.group(1)
        if num:
            key = f"{code}_{num}"
            if key not in seen:
                seen.add(key); seen.add(src)
                img_url = urljoin(BASE_URL, src) if src.startswith("/") else src
                results.append((key, img_url))

    if containers:
        for el in containers:
            img = el.find("img")
            if not img: continue
            parent = img.find_parent("a")
            href = parent.get("href","") if parent else ""
            process_img(img, el.get_text(" ", strip=True), href)
    else:
        skip = re.compile(r"logo|icon|banner|ad[_-]|avatar|spinner|placeholder", re.I)
        for img in soup.find_all("img"):
            src = img_src(img)
            if not src or skip.search(src): continue
            parent = img.find_parent("a")
            href = parent.get("href","") if parent else ""
            process_img(img, "", href)

    return results


# ── Main ──────────────────────────────────────────────────────────────────────
def main(debug=False):
    OUT_DIR.mkdir(exist_ok=True)
    if debug:
        DEBUG_DIR.mkdir(exist_ok=True)

    print("=" * 60)
    print("  Album Copa 2026 - Downloader de Figurinhas (Playwright)")
    print(f"  Destino: {OUT_DIR}/  |  {OUT_JS}")
    if debug:
        print(f"  DEBUG: HTML salvo em {DEBUG_DIR}/")
    print("=" * 60)

    cookies = [
        {"name": "cf_clearance", "value": CF_CLEARANCE,
         "domain": ".laststicker.com", "path": "/",
         "httpOnly": False, "secure": True, "sameSite": "None"},
    ] + EXTRA_COOKIES

    with sync_playwright() as pw:
        # Roda visível (headless=False) — Cloudflare Turnstile detecta headless e bloqueia
        browser = pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1280,800",
            ]
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="pt-BR",
            extra_http_headers={"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8"},
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()

        # Remove rastros de automação do navigator
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins',   {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR','pt','en-US','en']});
            window.chrome = { runtime: {} };
        """)

        # ── PASSO 1: página principal ────────────────────────────────────────
        print("\n[1/3] Abrindo album principal...")
        print("      >>> Uma janela Chrome vai aparecer. NAO feche ela. <<<")
        print("      Se aparecer 'Verificar que voce e humano', CLIQUE no botao.")
        try:
            page.goto(ALBUM_URL, wait_until="domcontentloaded", timeout=40000)
        except PWTimeout:
            print("   [X] Timeout. Verifique sua conexao.")
            browser.close()
            return

        # Aguarda Cloudflare Turnstile resolver (auto ou com clique do usuário)
        print("   Aguardando Cloudflare... (pode levar até 60s)")
        solved = False
        for tick in range(60):
            title = page.title()
            url   = page.url
            if "Um momento" not in title and "Just a moment" not in title:
                solved = True
                print(f"   OK! Titulo: {title[:60]}")
                break
            # Detecta se challenge foi resolvido (success text visível)
            try:
                if page.locator("#challenge-success-text").is_visible(timeout=500):
                    print("   Verificacao bem-sucedida! Aguardando redirect...")
                    page.wait_for_url(lambda u: "challenge" not in u and "__cf_chl" not in u,
                                      timeout=10000)
                    solved = True
                    break
            except Exception:
                pass
            if tick in (20, 40):
                print(f"   Ainda verificando ({tick}s)... Se tiver um botao no browser, clique.")
            time.sleep(1)

        if not solved:
            print("\n[X] Cloudflare nao liberou em 60s.")
            print("    -> No browser aberto, clique em 'Verificar' ou resolva o CAPTCHA")
            print("    -> Depois rode o script novamente")
            try:
                time.sleep(5)
            except Exception:
                pass
            browser.close()
            return

        html = page.content()
        title = page.title()
        print(f"   Titulo: {title}")

        if debug:
            (DEBUG_DIR / "album_index.html").write_text(html, encoding="utf-8", errors="replace")
            print(f"   HTML salvo em {DEBUG_DIR}/album_index.html")

        if "Just a moment" in title or "Error" in title:
            print("\n[X] Cloudflare ainda bloqueando.")
            print("    O cf_clearance pode ter expirado. Siga os passos:")
            print("    1. Abra laststicker.com no Chrome")
            print("    2. F12 -> Application -> Cookies")
            print("    3. Copie o valor NOVO de cf_clearance")
            print("    4. Cole em CF_CLEARANCE no topo deste script")
            browser.close()
            return

        sections = parse_sections(html)
        if not sections:
            print("\n[!] Nenhuma secao encontrada. Verifique o HTML salvo.")
            if not debug:
                (DEBUG_DIR / "album_index.html").write_text(html, encoding="utf-8", errors="replace")
                print(f"    HTML salvo para diagnostico em {DEBUG_DIR}/album_index.html")
            browser.close()
            return

        print(f"\n   {len(sections)} secoes encontradas:")
        for _, code, slug in sections:
            print(f"      {code:6s} <- {slug}")

        # ── PASSO 2: cada seção ──────────────────────────────────────────────
        print(f"\n[2/3] Baixando imagens...\n")
        players = {}
        stats   = {"ok": 0, "skip": 0, "err": 0, "no_img": 0}

        for i, (sec_url, code, slug) in enumerate(sections, 1):
            print(f"  [{i:02d}/{len(sections):02d}]  {code}  ({slug})")

            try:
                page.goto(sec_url, wait_until="domcontentloaded", timeout=25000)
                time.sleep(DELAY)
            except PWTimeout:
                print(f"         [X] Timeout")
                stats["err"] += 1
                continue

            sec_html = page.content()
            if debug:
                (DEBUG_DIR / f"section_{code}.html").write_text(
                    sec_html, encoding="utf-8", errors="replace")

            stickers = parse_stickers(sec_html, code)
            if not stickers:
                print(f"         [!] Nenhuma figurinha encontrada")
                if debug:
                    print(f"             Inspecione {DEBUG_DIR}/section_{code}.html")
                stats["no_img"] += 1
                continue

            print(f"         {len(stickers)} figurinhas")

            for key, img_url in stickers:
                ext = "jpg"
                m = re.search(r"\.(png|webp|jpe?g)(\?|$)", img_url, re.I)
                if m:
                    ext = m.group(1).lower().replace("jpeg","jpg")
                filename  = f"{key}.{ext}"
                dest_path = OUT_DIR / filename
                rel_path  = f"players/{filename}"

                if dest_path.exists():
                    players[key] = rel_path
                    stats["skip"] += 1
                    continue

                print(f"         -> {key}  {img_url[:65]}")
                try:
                    time.sleep(DELAY)
                    resp = page.request.get(img_url, timeout=20000)
                    if resp.ok:
                        dest_path.write_bytes(resp.body())
                        players[key] = rel_path
                        stats["ok"] += 1
                    else:
                        print(f"            HTTP {resp.status}")
                        stats["err"] += 1
                except Exception as e:
                    print(f"            ERRO: {e}")
                    stats["err"] += 1

        browser.close()

    # ── PASSO 3: players.js ──────────────────────────────────────────────────
    print(f"\n[3/3] Gerando {OUT_JS}...")
    lines = ["const PLAYERS = {"]
    for key in sorted(players):
        lines.append(f"  '{key}': '{players[key]}',")
    lines.append("};")
    lines.append("")
    OUT_JS.write_text("\n".join(lines), encoding="utf-8")

    # ── PASSO 4: sticker_map.js ──────────────────────────────────────────────
    from collections import defaultdict
    code_nums = defaultdict(list)
    for key in sorted(players):
        parts = key.split("_", 1)
        if len(parts) == 2:
            code_nums[parts[0]].append(int(parts[1]))
    map_lines = ["// stickerNums para colar no TEAMS do index.html",
                 "const STICKER_MAP = {"]
    for code in sorted(code_nums):
        nums = sorted(code_nums[code])
        map_lines.append(f"  '{code}': {nums},")
    map_lines.append("};")
    map_lines.append("")
    Path("sticker_map.js").write_text("\n".join(map_lines), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"  OK: {stats['ok']:4d}  SKIP: {stats['skip']:4d}  ERRO: {stats['err']:4d}")
    if stats['no_img']:
        print(f"  Secoes sem imagem: {stats['no_img']}")
    print(f"  players.js: {len(players)} entradas")
    print(f"  sticker_map.js gerado")
    print(f"{'='*60}")

    if stats["err"] or stats["no_img"]:
        print("\n[!] Alguns itens falharam. Rode com --debug para diagnostico.")

    # Imprime template de stickerNums
    if code_nums:
        print("\n--- Template stickerNums para index.html ---")
        for c in sorted(code_nums):
            nums = sorted(code_nums[c])
            print(f"  {c}: {nums}")
        print("--------------------------------------------")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true",
                    help="Salva HTML das páginas para diagnóstico")
    args = ap.parse_args()
    main(debug=args.debug)

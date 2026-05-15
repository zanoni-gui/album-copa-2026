#!/usr/bin/env python3
"""
parse_html.py  —  Extrai figurinhas do HTML baixado do laststicker.com
Saídas:
  sticker_data.json   dados completos
  teams_snippet.js    trecho pronto para colar em index.html
  sticker_urls.txt    URLs das páginas de cada figurinha (para baixar imagens depois)
"""
import sys, json, re
from pathlib import Path
from bs4 import BeautifulSoup
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HTML_FILE = (
    r"C:\Users\Fartech Gamer\Downloads"
    r"\Swap stickers, checklist and photos for album Panini FIFA World Cup 2026."
    r" Standard Edition - laststicker.com (15_05_2026 00：33：13).html"
)

# Código laststicker → código FIFA usado no index.html
CODE_MAP = {
    "alg":"ALG","arg":"ARG","aus":"AUS","aut":"AUT","bel":"BEL",
    "bih":"BIH","bra":"BRA","can":"CAN","cpv":"CPV","col":"COL",
    "cod":"COD","cro":"CRO","cuw":"CUW","cze":"CZE","ecu":"ECU",
    "egy":"EGY","eng":"ENG","fra":"FRA","ger":"GER","gha":"GHA",
    "hai":"HAI","irn":"IRN","irq":"IRQ","civ":"CIV","jpn":"JPN",
    "jor":"JOR","mex":"MEX","mar":"MAR","ned":"NED","nzl":"NZL",
    "nor":"NOR","pan":"PAN","par":"PAR","por":"POR","qat":"QAT",
    "ksa":"KSA","sco":"SCO","sen":"SEN","rsa":"RSA","kor":"KOR",
    "esp":"ESP","swe":"SWE","sui":"SUI","tun":"TUN","tur":"TUR",
    "usa":"USA","uru":"URU","uzb":"UZB","ven":"VEN",
}

# Grupo e flag de cada time (para preencher no teams_snippet)
TEAM_INFO = {
    "MEX":("A","🇲🇽","México"),        "RSA":("A","🇿🇦","África do Sul"),
    "KOR":("A","🇰🇷","Coreia do Sul"),  "CZE":("A","🇨🇿","Tchéquia"),
    "CAN":("B","🇨🇦","Canadá"),         "BIH":("B","🇧🇦","Bósnia"),
    "QAT":("B","🇶🇦","Catar"),          "SUI":("B","🇨🇭","Suíça"),
    "BRA":("C","🇧🇷","Brasil"),          "MAR":("C","🇲🇦","Marrocos"),
    "HAI":("C","🇭🇹","Haiti"),           "SCO":("C","🏴󠁧󠁢󠁳󠁣󠁴󠁿","Escócia"),
    "USA":("D","🇺🇸","EUA"),             "PAR":("D","🇵🇾","Paraguai"),
    "AUS":("D","🇦🇺","Austrália"),       "TUR":("D","🇹🇷","Turquia"),
    "GER":("E","🇩🇪","Alemanha"),        "CUW":("E","🇨🇼","Curaçao"),
    "CIV":("E","🇨🇮","Costa do Marfim"),"ECU":("E","🇪🇨","Equador"),
    "NED":("F","🇳🇱","Holanda"),         "JPN":("F","🇯🇵","Japão"),
    "SWE":("F","🇸🇪","Suécia"),          "TUN":("F","🇹🇳","Tunísia"),
    "BEL":("G","🇧🇪","Bélgica"),         "EGY":("G","🇪🇬","Egito"),
    "IRN":("G","🇮🇷","Irã"),             "NZL":("G","🇳🇿","Nova Zelândia"),
    "ESP":("H","🇪🇸","Espanha"),         "CPV":("H","🇨🇻","Cabo Verde"),
    "ALG":("H","🇩🇿","Argélia"),         "ARG":("H","🇦🇷","Argentina"),
    "AUT":("I","🇦🇹","Áustria"),         "COL":("I","🇨🇴","Colômbia"),
    "COD":("I","🇨🇩","Congo DR"),        "CRO":("I","🇭🇷","Croácia"),
    "FRA":("J","🇫🇷","França"),          "GHA":("J","🇬🇭","Gana"),
    "IRQ":("J","🇮🇶","Iraque"),          "JOR":("J","🇯🇴","Jordânia"),
    "NOR":("K","🇳🇴","Noruega"),         "PAN":("K","🇵🇦","Panamá"),
    "POR":("K","🇵🇹","Portugal"),        "KSA":("K","🇸🇦","Arábia Saudita"),
    "SEN":("L","🇸🇳","Senegal"),         "URU":("L","🇺🇾","Uruguai"),
    "VEN":("L","🇻🇪","Venezuela"),       "UZB":("L","🇺🇿","Uzbequistão"),
}

def parse():
    p = Path(HTML_FILE)
    if not p.exists():
        print(f"[X] Arquivo nao encontrado:\n    {HTML_FILE}")
        return

    print(f"[.] Lendo HTML ({p.stat().st_size//1024} KB)...")
    html = p.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")

    # ── Extrai todos os links <a rel="..."> que correspondem a figurinhas ────
    # Padrão: rel="bra1", rel="fwc3", rel="00", etc.
    sticker_pattern = re.compile(r"^([a-z]{2,4})(\d+)$|^(fwc\d+)$|^(00)$", re.I)

    stickers = []
    seen_ids = set()

    for a in soup.find_all("a", href=True):
        rel_list = a.get("rel", [])
        rel = rel_list[0] if rel_list else ""
        if not rel:
            # Tenta extrair do href
            m = re.search(r"/panini_world_cup_2026/([^/]+)/?$", a.get("href", ""))
            if m:
                rel = m.group(1)

        if not rel or rel in seen_ids:
            continue
        seen_ids.add(rel)

        name = a.get_text(strip=True)
        href = a.get("href", "")

        # Extrai código e número
        m = re.match(r"^([a-z]{2,4})(\d+)$", rel.lower())
        if m:
            raw_code   = m.group(1)
            sticker_num = int(m.group(2))
        elif rel.lower().startswith("fwc"):
            raw_code    = "fwc"
            sticker_num = int(rel[3:]) if rel[3:].isdigit() else 0
        else:
            raw_code    = rel.lower()
            sticker_num = 0

        fifa_code = CODE_MAP.get(raw_code, raw_code.upper())

        stickers.append({
            "id":          rel,
            "num":         sticker_num,
            "name":        name,
            "raw_code":    raw_code,
            "fifa_code":   fifa_code,
            "href":        href,
        })

    # Filtra apenas figurinhas de times (2-4 letras + número)
    team_stickers = [s for s in stickers if re.match(r"^[a-z]{2,4}$", s["raw_code"])]

    print(f"[.] {len(stickers)} IDs únicos encontrados")
    print(f"[.] {len(team_stickers)} figurinhas de times\n")

    # ── Salva JSON ───────────────────────────────────────────────────────────
    Path("sticker_data.json").write_text(
        json.dumps(stickers, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── Agrupa por time e ordena por número ──────────────────────────────────
    by_team = defaultdict(list)
    for s in team_stickers:
        by_team[s["raw_code"]].append(s)

    for code in by_team:
        by_team[code].sort(key=lambda x: x["num"])

    # ── Mostra resumo ────────────────────────────────────────────────────────
    print(f"{'Code':6s} {'FIFA':6s} {'#fig':5s}  Jogadores (1-5...)")
    print("─" * 70)
    for raw in sorted(by_team.keys()):
        items = by_team[raw]
        fifa  = CODE_MAP.get(raw, raw.upper())
        names = [i["name"] for i in items[:5]]
        print(f"{raw:6s} {fifa:6s} {len(items):3d}    {', '.join(names)[:55]}")

    # ── Gera teams_snippet.js ────────────────────────────────────────────────
    lines = [
        "// Cole dentro do array TEAMS no index.html",
        "// (substitui o TEAMS inteiro pelo conteúdo abaixo)",
        "const TEAMS = [",
    ]

    tid = 0
    # Ordena por grupo (A→L) usando TEAM_INFO
    def sort_key(raw):
        fifa = CODE_MAP.get(raw, "ZZZ")
        info = TEAM_INFO.get(fifa, ("Z", "", ""))
        return (info[0], fifa)

    for raw in sorted(by_team.keys(), key=sort_key):
        items  = by_team[raw]
        fifa   = CODE_MAP.get(raw, raw.upper())
        info   = TEAM_INFO.get(fifa, ("?", "🏳", raw.upper()))
        grp, flag, pt_name = info

        players = [s["name"] for s in items]
        # Garante 20 slots
        while len(players) < 20:
            players.append(f"Figurinha {len(players)+1}")
        players = players[:20]

        # Formata como array JS curto
        pl_json = json.dumps(players, ensure_ascii=False)
        lines.append(
            f'  {{id:{tid}, code:"{fifa}", name:"{pt_name}", group:"{grp}", '
            f'flag:"{flag}", stickerNums:null, players:{pl_json}}},'
        )
        tid += 1

    lines.append("];")
    Path("teams_snippet.js").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[OK] teams_snippet.js — {tid} times")

    # ── Gera lista de URLs das páginas de figurinha ─────────────────────────
    # (cada página tem a imagem thumbnail — útil para download futuro)
    urls = []
    for s in sorted(stickers, key=lambda x: (x["raw_code"], x["num"])):
        if s["href"] and "laststicker.com" in s["href"]:
            urls.append(s["href"])

    Path("sticker_urls.txt").write_text("\n".join(urls), encoding="utf-8")
    print(f"[OK] sticker_urls.txt — {len(urls)} URLs")
    print(f"[OK] sticker_data.json — {len(stickers)} entradas")

    print(f"""
─────────────────────────────────────────────
  Próximos passos:
  1. Abra teams_snippet.js
  2. Copie o conteúdo e substitua o array TEAMS
     inteiro no index.html
  3. Para imagens: abra cada URL de sticker_urls.txt
     e inspecione o src da imagem thumbnail
─────────────────────────────────────────────""")


if __name__ == "__main__":
    parse()

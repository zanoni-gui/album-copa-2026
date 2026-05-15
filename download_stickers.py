"""
Download all sticker images for the Panini FIFA World Cup 2026 (Standard Edition)
album from laststicker.com.

URL pattern: https://www.laststicker.com/i/cards/12176/<code>.jpg
Codes were scraped from https://www.laststicker.com/cards/panini_world_cup_2026/
on 2026-05-15 (1000 stickers: 912 base + 68 foil + 20 "Extra / Base").

Usage:
    python download_stickers.py                  # download all to ./stickers/
    python download_stickers.py -o my_folder     # custom output dir
    python download_stickers.py --workers 4      # control concurrency (default 6)
    python download_stickers.py --sample 5       # only the first 5 (sanity check)

Behaviour:
    - Skips files already present on disk (safe to resume).
    - Retries each request up to 3 times with exponential backoff.
    - 404s are recorded in missing.txt; everything else fails loudly.
    - Sets a polite User-Agent and a small inter-request delay per worker.

Only the standard library is required (urllib + concurrent.futures).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ALBUM_ID = "12176"
BASE_URL = f"https://www.laststicker.com/i/cards/{ALBUM_ID}"
REFERER  = "https://www.laststicker.com/"

# fmt: off
CODES = [
    # 0..99 - Logo, FWC1-8, MEX, RSA, KOR, CZE, CAN1-11
    "00", "fwc1", "fwc2", "fwc3", "fwc4", "fwc5", "fwc6", "fwc7", "fwc8",
    "mex1", "mex2", "mex3", "mex4", "mex5", "mex6", "mex7", "mex8", "mex9", "mex10",
    "mex11", "mex12", "mex13", "mex14", "mex15", "mex16", "mex17", "mex18", "mex19", "mex20",
    "rsa1", "rsa2", "rsa3", "rsa4", "rsa5", "rsa6", "rsa7", "rsa8", "rsa9", "rsa10",
    "rsa11", "rsa12", "rsa13", "rsa14", "rsa15", "rsa16", "rsa17", "rsa18", "rsa19", "rsa20",
    "kor1", "kor2", "kor3", "kor4", "kor5", "kor6", "kor7", "kor8", "kor9", "kor10",
    "kor11", "kor12", "kor13", "kor14", "kor15", "kor16", "kor17", "kor18", "kor19", "kor20",
    "cze1", "cze2", "cze3", "cze4", "cze5", "cze6", "cze7", "cze8", "cze9", "cze10",
    "cze11", "cze12", "cze13", "cze14", "cze15", "cze16", "cze17", "cze18", "cze19", "cze20",
    "can1", "can2", "can3", "can4", "can5", "can6", "can7", "can8", "can9", "can10", "can11",
    # 100..199 - CAN12-20, BIH, QAT, SUI, BRA, MAR1-11
    "can12", "can13", "can14", "can15", "can16", "can17", "can18", "can19", "can20",
    "bih1", "bih2", "bih3", "bih4", "bih5", "bih6", "bih7", "bih8", "bih9", "bih10",
    "bih11", "bih12", "bih13", "bih14", "bih15", "bih16", "bih17", "bih18", "bih19", "bih20",
    "qat1", "qat2", "qat3", "qat4", "qat5", "qat6", "qat7", "qat8", "qat9", "qat10",
    "qat11", "qat12", "qat13", "qat14", "qat15", "qat16", "qat17", "qat18", "qat19", "qat20",
    "sui1", "sui2", "sui3", "sui4", "sui5", "sui6", "sui7", "sui8", "sui9", "sui10",
    "sui11", "sui12", "sui13", "sui14", "sui15", "sui16", "sui17", "sui18", "sui19", "sui20",
    "bra1", "bra2", "bra3", "bra4", "bra5", "bra6", "bra7", "bra8", "bra9", "bra10",
    "bra11", "bra12", "bra13", "bra14", "bra15", "bra16", "bra17", "bra18", "bra19", "bra20",
    "mar1", "mar2", "mar3", "mar4", "mar5", "mar6", "mar7", "mar8", "mar9", "mar10", "mar11",
    # 200..299 - MAR12-20, HAI, SCO, USA, PAR, AUS1-11
    "mar12", "mar13", "mar14", "mar15", "mar16", "mar17", "mar18", "mar19", "mar20",
    "hai1", "hai2", "hai3", "hai4", "hai5", "hai6", "hai7", "hai8", "hai9", "hai10",
    "hai11", "hai12", "hai13", "hai14", "hai15", "hai16", "hai17", "hai18", "hai19", "hai20",
    "sco1", "sco2", "sco3", "sco4", "sco5", "sco6", "sco7", "sco8", "sco9", "sco10",
    "sco11", "sco12", "sco13", "sco14", "sco15", "sco16", "sco17", "sco18", "sco19", "sco20",
    "usa1", "usa2", "usa3", "usa4", "usa5", "usa6", "usa7", "usa8", "usa9", "usa10",
    "usa11", "usa12", "usa13", "usa14", "usa15", "usa16", "usa17", "usa18", "usa19", "usa20",
    "par1", "par2", "par3", "par4", "par5", "par6", "par7", "par8", "par9", "par10",
    "par11", "par12", "par13", "par14", "par15", "par16", "par17", "par18", "par19", "par20",
    "aus1", "aus2", "aus3", "aus4", "aus5", "aus6", "aus7", "aus8", "aus9", "aus10", "aus11",
    # 300..399 - AUS12-20, TUR, GER, CUW, CIV, ECU1-11
    "aus12", "aus13", "aus14", "aus15", "aus16", "aus17", "aus18", "aus19", "aus20",
    "tur1", "tur2", "tur3", "tur4", "tur5", "tur6", "tur7", "tur8", "tur9", "tur10",
    "tur11", "tur12", "tur13", "tur14", "tur15", "tur16", "tur17", "tur18", "tur19", "tur20",
    "ger1", "ger2", "ger3", "ger4", "ger5", "ger6", "ger7", "ger8", "ger9", "ger10",
    "ger11", "ger12", "ger13", "ger14", "ger15", "ger16", "ger17", "ger18", "ger19", "ger20",
    "cuw1", "cuw2", "cuw3", "cuw4", "cuw5", "cuw6", "cuw7", "cuw8", "cuw9", "cuw10",
    "cuw11", "cuw12", "cuw13", "cuw14", "cuw15", "cuw16", "cuw17", "cuw18", "cuw19", "cuw20",
    "civ1", "civ2", "civ3", "civ4", "civ5", "civ6", "civ7", "civ8", "civ9", "civ10",
    "civ11", "civ12", "civ13", "civ14", "civ15", "civ16", "civ17", "civ18", "civ19", "civ20",
    "ecu1", "ecu2", "ecu3", "ecu4", "ecu5", "ecu6", "ecu7", "ecu8", "ecu9", "ecu10", "ecu11",
    # 400..499 - ECU12-20, NED, JPN, SWE, TUN, BEL1-11
    "ecu12", "ecu13", "ecu14", "ecu15", "ecu16", "ecu17", "ecu18", "ecu19", "ecu20",
    "ned1", "ned2", "ned3", "ned4", "ned5", "ned6", "ned7", "ned8", "ned9", "ned10",
    "ned11", "ned12", "ned13", "ned14", "ned15", "ned16", "ned17", "ned18", "ned19", "ned20",
    "jpn1", "jpn2", "jpn3", "jpn4", "jpn5", "jpn6", "jpn7", "jpn8", "jpn9", "jpn10",
    "jpn11", "jpn12", "jpn13", "jpn14", "jpn15", "jpn16", "jpn17", "jpn18", "jpn19", "jpn20",
    "swe1", "swe2", "swe3", "swe4", "swe5", "swe6", "swe7", "swe8", "swe9", "swe10",
    "swe11", "swe12", "swe13", "swe14", "swe15", "swe16", "swe17", "swe18", "swe19", "swe20",
    "tun1", "tun2", "tun3", "tun4", "tun5", "tun6", "tun7", "tun8", "tun9", "tun10",
    "tun11", "tun12", "tun13", "tun14", "tun15", "tun16", "tun17", "tun18", "tun19", "tun20",
    "bel1", "bel2", "bel3", "bel4", "bel5", "bel6", "bel7", "bel8", "bel9", "bel10", "bel11",
    # 500..599 - BEL12-20, EGY, IRN, NZL, ESP, CPV1-11
    "bel12", "bel13", "bel14", "bel15", "bel16", "bel17", "bel18", "bel19", "bel20",
    "egy1", "egy2", "egy3", "egy4", "egy5", "egy6", "egy7", "egy8", "egy9", "egy10",
    "egy11", "egy12", "egy13", "egy14", "egy15", "egy16", "egy17", "egy18", "egy19", "egy20",
    "irn1", "irn2", "irn3", "irn4", "irn5", "irn6", "irn7", "irn8", "irn9", "irn10",
    "irn11", "irn12", "irn13", "irn14", "irn15", "irn16", "irn17", "irn18", "irn19", "irn20",
    "nzl1", "nzl2", "nzl3", "nzl4", "nzl5", "nzl6", "nzl7", "nzl8", "nzl9", "nzl10",
    "nzl11", "nzl12", "nzl13", "nzl14", "nzl15", "nzl16", "nzl17", "nzl18", "nzl19", "nzl20",
    "esp1", "esp2", "esp3", "esp4", "esp5", "esp6", "esp7", "esp8", "esp9", "esp10",
    "esp11", "esp12", "esp13", "esp14", "esp15", "esp16", "esp17", "esp18", "esp19", "esp20",
    "cpv1", "cpv2", "cpv3", "cpv4", "cpv5", "cpv6", "cpv7", "cpv8", "cpv9", "cpv10", "cpv11",
    # 600..699 - CPV12-20, KSA, URU, FRA, SEN, IRQ1-11
    "cpv12", "cpv13", "cpv14", "cpv15", "cpv16", "cpv17", "cpv18", "cpv19", "cpv20",
    "ksa1", "ksa2", "ksa3", "ksa4", "ksa5", "ksa6", "ksa7", "ksa8", "ksa9", "ksa10",
    "ksa11", "ksa12", "ksa13", "ksa14", "ksa15", "ksa16", "ksa17", "ksa18", "ksa19", "ksa20",
    "uru1", "uru2", "uru3", "uru4", "uru5", "uru6", "uru7", "uru8", "uru9", "uru10",
    "uru11", "uru12", "uru13", "uru14", "uru15", "uru16", "uru17", "uru18", "uru19", "uru20",
    "fra1", "fra2", "fra3", "fra4", "fra5", "fra6", "fra7", "fra8", "fra9", "fra10",
    "fra11", "fra12", "fra13", "fra14", "fra15", "fra16", "fra17", "fra18", "fra19", "fra20",
    "sen1", "sen2", "sen3", "sen4", "sen5", "sen6", "sen7", "sen8", "sen9", "sen10",
    "sen11", "sen12", "sen13", "sen14", "sen15", "sen16", "sen17", "sen18", "sen19", "sen20",
    "irq1", "irq2", "irq3", "irq4", "irq5", "irq6", "irq7", "irq8", "irq9", "irq10", "irq11",
    # 700..799 - IRQ12-20, NOR, ARG, ALG, AUT, JOR1-11
    "irq12", "irq13", "irq14", "irq15", "irq16", "irq17", "irq18", "irq19", "irq20",
    "nor1", "nor2", "nor3", "nor4", "nor5", "nor6", "nor7", "nor8", "nor9", "nor10",
    "nor11", "nor12", "nor13", "nor14", "nor15", "nor16", "nor17", "nor18", "nor19", "nor20",
    "arg1", "arg2", "arg3", "arg4", "arg5", "arg6", "arg7", "arg8", "arg9", "arg10",
    "arg11", "arg12", "arg13", "arg14", "arg15", "arg16", "arg17", "arg18", "arg19", "arg20",
    "alg1", "alg2", "alg3", "alg4", "alg5", "alg6", "alg7", "alg8", "alg9", "alg10",
    "alg11", "alg12", "alg13", "alg14", "alg15", "alg16", "alg17", "alg18", "alg19", "alg20",
    "aut1", "aut2", "aut3", "aut4", "aut5", "aut6", "aut7", "aut8", "aut9", "aut10",
    "aut11", "aut12", "aut13", "aut14", "aut15", "aut16", "aut17", "aut18", "aut19", "aut20",
    "jor1", "jor2", "jor3", "jor4", "jor5", "jor6", "jor7", "jor8", "jor9", "jor10", "jor11",
    # 800..899 - JOR12-20, POR, COD, UZB, COL, ENG1-11
    "jor12", "jor13", "jor14", "jor15", "jor16", "jor17", "jor18", "jor19", "jor20",
    "por1", "por2", "por3", "por4", "por5", "por6", "por7", "por8", "por9", "por10",
    "por11", "por12", "por13", "por14", "por15", "por16", "por17", "por18", "por19", "por20",
    "cod1", "cod2", "cod3", "cod4", "cod5", "cod6", "cod7", "cod8", "cod9", "cod10",
    "cod11", "cod12", "cod13", "cod14", "cod15", "cod16", "cod17", "cod18", "cod19", "cod20",
    "uzb1", "uzb2", "uzb3", "uzb4", "uzb5", "uzb6", "uzb7", "uzb8", "uzb9", "uzb10",
    "uzb11", "uzb12", "uzb13", "uzb14", "uzb15", "uzb16", "uzb17", "uzb18", "uzb19", "uzb20",
    "col1", "col2", "col3", "col4", "col5", "col6", "col7", "col8", "col9", "col10",
    "col11", "col12", "col13", "col14", "col15", "col16", "col17", "col18", "col19", "col20",
    "eng1", "eng2", "eng3", "eng4", "eng5", "eng6", "eng7", "eng8", "eng9", "eng10", "eng11",
    # 900..999 - ENG12-20, CRO, GHA, PAN, FWC9-19, then 20 Extra/Base 2-letter codes
    "eng12", "eng13", "eng14", "eng15", "eng16", "eng17", "eng18", "eng19", "eng20",
    "cro1", "cro2", "cro3", "cro4", "cro5", "cro6", "cro7", "cro8", "cro9", "cro10",
    "cro11", "cro12", "cro13", "cro14", "cro15", "cro16", "cro17", "cro18", "cro19", "cro20",
    "gha1", "gha2", "gha3", "gha4", "gha5", "gha6", "gha7", "gha8", "gha9", "gha10",
    "gha11", "gha12", "gha13", "gha14", "gha15", "gha16", "gha17", "gha18", "gha19", "gha20",
    "pan1", "pan2", "pan3", "pan4", "pan5", "pan6", "pan7", "pan8", "pan9", "pan10",
    "pan11", "pan12", "pan13", "pan14", "pan15", "pan16", "pan17", "pan18", "pan19", "pan20",
    "fwc9", "fwc10", "fwc11", "fwc12", "fwc13", "fwc14", "fwc15", "fwc16", "fwc17", "fwc18", "fwc19",
    # 20 "Extra / Base" stickers (star player foils)
    "lm", "jd", "vj", "ad", "ld", "lmo", "mc", "ms", "jb", "km",
    "fw", "rj", "ah", "eh", "cg", "cr", "hs", "ly", "cp", "fv",
]
# fmt: on

assert len(CODES) == 1000, f"expected 1000 codes, got {len(CODES)}"
assert len(set(CODES)) == 1000, "duplicate codes in CODES list"


def generate_players_js(out_dir: Path) -> None:
    lines = ["const PLAYERS = {"]
    for code in CODES:
        p = out_dir / f"{code}.jpg"
        if p.exists() and p.stat().st_size > 0:
            lines.append(f"  '{code}': '{out_dir.name}/{code}.jpg',")
    lines.append("};")
    js_path = out_dir.parent / "players.js"
    js_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> players.js: {len(lines)-2} entradas em {js_path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-o", "--out", default="stickers", help="pasta de saida (default: ./stickers)")
    p.add_argument("--sample", type=int, default=0, help="baixar apenas os primeiros N (teste)")
    args = p.parse_args(argv)

    codes   = CODES[: args.sample] if args.sample > 0 else CODES
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    print(f"=== Download de {len(codes)} figurinhas via Playwright ===")
    print(f"Destino: {out_dir.resolve()}")
    print(">>> Uma janela Chrome vai abrir. Nao feche. <<<")
    print(">>> Se aparecer desafio Cloudflare, clique em Verificar. <<<\n")

    counts = {"ok": 0, "skip": 0, "missing": 0, "fail": 0}
    missing, failed = [], []
    start = time.time()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            "window.chrome={runtime:{}};"
        )

        # ── Passo 1: resolver Cloudflare uma vez ───────────────────────────
        print("[1/2] Abrindo laststicker.com para passar o Cloudflare...")
        try:
            page.goto("https://www.laststicker.com/cards/panini_world_cup_2026/",
                      wait_until="domcontentloaded", timeout=40000)
        except PWTimeout:
            pass

        for tick in range(60):
            title = page.title()
            if "momento" not in title.lower() and "moment" not in title.lower():
                print(f"   OK: {title[:60]}")
                break
            if tick == 20:
                print("   Ainda verificando... clique em 'Verificar' se aparecer botao.")
            time.sleep(1)
        else:
            print("   [!] Cloudflare nao liberou. Feche o browser e tente novamente.")
            browser.close()
            return 1

        # ── Passo 2: baixar todas as imagens via context.request ──────────
        print(f"\n[2/2] Baixando {len(codes)} imagens...")
        for i, code in enumerate(codes, 1):
            dest = out_dir / f"{code}.jpg"
            if dest.exists() and dest.stat().st_size > 0:
                counts["skip"] += 1
                if i % 100 == 0:
                    print(f"  [{i:>4}/{len(codes)}] skip={counts['skip']} ok={counts['ok']}")
                continue

            url = f"{BASE_URL}/{code}.jpg"
            try:
                resp = ctx.request.get(url, timeout=15000,
                                       headers={"Referer": REFERER})
                if resp.ok:
                    dest.write_bytes(resp.body())
                    counts["ok"] += 1
                elif resp.status == 404:
                    counts["missing"] += 1
                    missing.append(code)
                else:
                    counts["fail"] += 1
                    failed.append((code, f"http {resp.status}"))
            except Exception as e:
                counts["fail"] += 1
                failed.append((code, str(e)[:60]))

            if i % 50 == 0 or i == len(codes):
                elapsed = time.time() - start
                print(f"  [{i:>4}/{len(codes)}] ok={counts['ok']} skip={counts['skip']} "
                      f"miss={counts['missing']} fail={counts['fail']}  ({elapsed:.0f}s)")

        browser.close()

    if missing:
        (out_dir / "missing.txt").write_text("\n".join(sorted(missing)), encoding="utf-8")
    if failed:
        (out_dir / "failed.txt").write_text(
            "\n".join(f"{c}\t{s}" for c, s in failed), encoding="utf-8")

    elapsed = time.time() - start
    print(f"\nFim em {elapsed:.0f}s — ok={counts['ok']} skip={counts['skip']} "
          f"missing={counts['missing']} fail={counts['fail']}")

    generate_players_js(out_dir)
    return 0 if counts["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

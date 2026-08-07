#!/usr/bin/env python3
"""
Prospecção de clientes B2B por nicho + raio de distância, usando apenas
fontes públicas e gratuitas:

  1. Nominatim (OpenStreetMap)  -> geocodifica o endereço/cidade de referência
  2. Overpass API (OpenStreetMap) -> lista empresas do nicho dentro do raio
  3. BrasilAPI (dados abertos da Receita Federal) -> quando o CNPJ da empresa
     é encontrado no próprio site dela, busca razão social, sócios/
     administradores (QSA) e telefone/e-mail institucionais cadastrados
  4. Gera (opcional) um link de busca no LinkedIn por decisor encontrado,
     sem fazer login ou scraping do LinkedIn (isso violaria os Termos de
     Uso deles) — é só um link pronto para você clicar e conferir.

Uso:
    python3 buscar_leads.py --nicho "contador" --local "Osasco, SP" \
        --raio 5 --limite 30 --saida leads.csv --enriquecer-cnpj --gerar-linkedin
"""

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

CONTATO_PADRAO = "cosmuscontabil@gmail.com"
USER_AGENT = f"ProspeccaoEscritorioContabil/1.0 (contato: {CONTATO_PADRAO})"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
BRASILAPI_CNPJ_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

CNPJ_RE = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

NICHOS_PATH = Path(__file__).parent / "nichos.json"


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower().strip())
    return "".join(c for c in texto if not unicodedata.combining(c))


def http_get_json(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_text(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="ignore")


def geocodificar(local):
    params = urllib.parse.urlencode({"q": local, "format": "json", "limit": 1, "countrycodes": "br"})
    resultados = http_get_json(f"{NOMINATIM_URL}?{params}")
    if not resultados:
        raise SystemExit(f"Não consegui localizar '{local}'. Tente ser mais específico (ex: 'Osasco, SP').")
    return float(resultados[0]["lat"]), float(resultados[0]["lon"])


def carregar_tags_do_nicho(nicho):
    mapa = json.loads(NICHOS_PATH.read_text(encoding="utf-8"))
    chave = normalizar(nicho)
    for k, v in mapa.items():
        if normalizar(k) == chave:
            return v
    return None


def montar_query_overpass(lat, lon, raio_m, nicho):
    tags = carregar_tags_do_nicho(nicho)
    filtros = []
    if tags:
        for chave, valor in tags:
            filtros.append(f'node["{chave}"="{valor}"](around:{raio_m},{lat},{lon});')
            filtros.append(f'way["{chave}"="{valor}"](around:{raio_m},{lat},{lon});')
    else:
        # sem mapeamento conhecido: procura pelo termo no nome do estabelecimento
        termo = nicho.replace('"', "")
        filtros.append(f'node["name"~"{termo}",i](around:{raio_m},{lat},{lon});')
        filtros.append(f'way["name"~"{termo}",i](around:{raio_m},{lat},{lon});')
    corpo = "\n  ".join(filtros)
    return f"[out:json][timeout:60];\n(\n  {corpo}\n);\nout center tags;"


def buscar_empresas_osm(lat, lon, raio_km, nicho, limite):
    query = montar_query_overpass(lat, lon, int(raio_km * 1000), nicho)
    dados = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=dados, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as resp:
        resultado = json.loads(resp.read().decode("utf-8"))

    empresas = []
    vistos = set()
    for el in resultado.get("elements", []):
        tags = el.get("tags", {})
        nome = tags.get("name")
        if not nome or nome in vistos:
            continue
        vistos.add(nome)

        endereco_partes = [
            tags.get("addr:street"),
            tags.get("addr:housenumber"),
            tags.get("addr:suburb"),
            tags.get("addr:city"),
        ]
        endereco = ", ".join(p for p in endereco_partes if p)

        empresas.append({
            "empresa": nome,
            "endereco": endereco,
            "telefone": tags.get("phone") or tags.get("contact:phone") or "",
            "email": tags.get("email") or tags.get("contact:email") or "",
            "website": tags.get("website") or tags.get("contact:website") or "",
            "cnpj": "",
            "decisores": "",
            "cargo_decisores": "",
            "fonte": "OpenStreetMap",
        })
        if len(empresas) >= limite:
            break
    return empresas


def tentar_achar_cnpj_no_site(website):
    if not website:
        return None
    try:
        html = http_get_text(website)
    except Exception:
        return None
    m = CNPJ_RE.search(html)
    if not m:
        return None
    return re.sub(r"\D", "", m.group())


def tentar_achar_email_no_site(website):
    if not website:
        return None
    try:
        html = http_get_text(website)
    except Exception:
        return None
    m = EMAIL_RE.search(html)
    return m.group() if m else None


def enriquecer_com_cnpj(empresa):
    cnpj = tentar_achar_cnpj_no_site(empresa["website"])
    if not cnpj:
        return empresa
    try:
        dados = http_get_json(BRASILAPI_CNPJ_URL.format(cnpj=cnpj))
    except Exception:
        empresa["cnpj"] = cnpj
        return empresa

    empresa["cnpj"] = cnpj
    if not empresa["telefone"] and dados.get("ddd_telefone_1"):
        empresa["telefone"] = dados["ddd_telefone_1"]
    if not empresa["email"] and dados.get("email"):
        empresa["email"] = dados["email"]

    qsa = dados.get("qsa") or []
    nomes = [socio.get("nome_socio", "") for socio in qsa if socio.get("nome_socio")]
    cargos = [socio.get("qualificacao_socio", "") for socio in qsa if socio.get("nome_socio")]
    empresa["decisores"] = "; ".join(nomes)
    empresa["cargo_decisores"] = "; ".join(cargos)
    return empresa


def gerar_link_linkedin(nome_decisor, empresa):
    termo = f"{nome_decisor} {empresa}"
    return "https://www.linkedin.com/search/results/people/?keywords=" + urllib.parse.quote(termo)


def montar_links_linkedin(empresa):
    nomes = [n.strip() for n in empresa["decisores"].split(";") if n.strip()]
    links = [gerar_link_linkedin(nome, empresa["empresa"]) for nome in nomes]
    return " | ".join(links)


def main():
    ap = argparse.ArgumentParser(description="Prospecção de clientes por nicho + raio, com dados públicos.")
    ap.add_argument("--nicho", required=True, help='Ex: "contador", "restaurante", "clinica medica"')
    ap.add_argument("--local", required=True, help='Endereço ou cidade de referência, ex: "Osasco, SP"')
    ap.add_argument("--raio", type=float, default=5, help="Raio de busca em km (padrão: 5)")
    ap.add_argument("--limite", type=int, default=30, help="Máximo de empresas a retornar (padrão: 30)")
    ap.add_argument("--saida", default="leads.csv", help="Caminho do CSV de saída")
    ap.add_argument("--enriquecer-cnpj", action="store_true",
                     help="Tenta achar o CNPJ no site de cada empresa e buscar sócios/telefone/e-mail na Receita (BrasilAPI)")
    ap.add_argument("--gerar-linkedin", action="store_true",
                     help="Gera um link de busca no LinkedIn para cada decisor encontrado (não faz scraping)")
    args = ap.parse_args()

    print(f"Localizando '{args.local}'...", file=sys.stderr)
    lat, lon = geocodificar(args.local)

    print(f"Buscando '{args.nicho}' num raio de {args.raio} km...", file=sys.stderr)
    empresas = buscar_empresas_osm(lat, lon, args.raio, args.nicho, args.limite)
    print(f"{len(empresas)} empresa(s) encontrada(s) no OpenStreetMap.", file=sys.stderr)

    if args.enriquecer_cnpj:
        for i, empresa in enumerate(empresas, 1):
            print(f"  Enriquecendo {i}/{len(empresas)}: {empresa['empresa']}...", file=sys.stderr)
            enriquecer_com_cnpj(empresa)
            if not empresa["email"]:
                email_site = tentar_achar_email_no_site(empresa["website"])
                if email_site:
                    empresa["email"] = email_site
            time.sleep(0.5)  # não sobrecarregar os sites/APIs públicas

    campos = ["empresa", "endereco", "telefone", "email", "website", "cnpj",
              "decisores", "cargo_decisores"]
    if args.gerar_linkedin:
        campos.append("busca_linkedin")
        for empresa in empresas:
            empresa["busca_linkedin"] = montar_links_linkedin(empresa) if empresa["decisores"] else ""

    campos.append("fonte")
    with open(args.saida, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(empresas)

    print(f"\nPronto! {len(empresas)} lead(s) salvos em {args.saida}", file=sys.stderr)


if __name__ == "__main__":
    main()

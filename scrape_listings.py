import json
import csv
import re
import os
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

CONFIG_PATH = "scraper_config.json"

# Teléfonos “bonitos” tipo 323 2925350, 601 1234567, etc. (10 dígitos)
PHONE_REGEX_MAIN = re.compile(r"\b\d{2,3}\s*\d{3}\s*\d{4}\b")
# Cualquier cosa que pueda parecer teléfono (mínimo 7 dígitos en total)
PHONE_REGEX_ANY = re.compile(r"\d[\d\s\.\-]{4,}")


def load_specialties(path: str = "specialties.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_specialties_limit(config_path: str = CONFIG_PATH, default_limit: int = 1) -> int:
    """
    Lee el límite de especialidades desde scraper_config.json.
    Si el archivo no existe o está mal, usa default_limit.
    """
    if not os.path.exists(config_path):
        print(f"⚙️  {config_path} no existe. Usando límite por defecto: {default_limit}")
        return default_limit

    try:
        with open(config_path, encoding="utf-8") as f:
            data = json.load(f)
        value = int(data.get("specialties_limit", default_limit))
        if value <= 0:
            print(
                f"⚠️  specialties_limit <= 0 en {config_path}. "
                f"Usando límite por defecto: {default_limit}"
            )
            return default_limit
        print(f"⚙️  Límite de especialidades desde {config_path}: {value}")
        return value
    except Exception as e:
        print(f"⚠️  Error leyendo {config_path}: {e}. Usando límite {default_limit}")
        return default_limit


def fetch_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.encoding = "utf-8"  # por si acaso
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def get_max_pages(soup: BeautifulSoup) -> int:
    """
    Busca el bloque donde aparece el texto 'Siguiente'
    y toma el número más grande como última página.
    """
    pager = soup.find(
        lambda tag: tag.name in ("ul", "nav", "div")
        and "Siguiente" in tag.get_text()
    )
    if not pager:
        return 1

    numbers = []
    for a in pager.find_all("a"):
        text = a.get_text(strip=True)
        if text.isdigit():
            numbers.append(int(text))

    return max(numbers) if numbers else 1


def clean_specialty_visible(text: str) -> str:
    """
    Limpia el texto visible de la especialidad:
    - normaliza espacios
    - quita el '· Ver más' si aparece
    """
    if not text:
        return ""

    text = " ".join(text.split())
    if "·" in text:
        text = text.split("·", 1)[0].strip()
    return text.strip()


def split_specialty_parentheses(text: str):
    """
    Fallback por si los detalles vienen entre paréntesis
    en el mismo texto:
    'Dermatóloga (Tricología - ...)' -> ('Dermatóloga', 'Tricología - ...')
    """
    if not text:
        return "", ""

    text = " ".join(text.split())

    if "(" in text and ")" in text and text.index("(") < text.rfind(")"):
        start = text.index("(")
        end = text.rfind(")")
        main = text[:start].strip()
        details = text[start + 1 : end].strip()
        return main, details

    return text.strip(), ""


def parse_doctor_cards(soup: BeautifulSoup, base_url: str):
    results = []

    # Cada doctor suele tener un <h3> con un <a> que empieza por Dr / Dra
    for h3 in soup.find_all("h3"):
        link = h3.find("a", href=True)
        if not link:
            continue

        name = link.get_text(strip=True)
        if not name.startswith(("Dr", "Dra")):
            continue

        # 'card' nos sirve para especialidad, pero dirección/precio viven más abajo
        card = h3.parent
        if card.name not in ("div", "article", "section", "li"):
            card = card.parent

        profile_url = urljoin(base_url, link["href"])

        # ---- Especialidad visible en el <h4> ----
        specialty_tag = card.find("h4")
        specialty_visible = ""
        specialty_details = ""

        if specialty_tag:
            specialty_full = specialty_tag.get_text(" ", strip=True)
            specialty_visible = clean_specialty_visible(specialty_full)

        # ---- Detalles en <span class="hide"> (Ver más) ----
        details_span = card.find("span", class_="hide")
        if details_span:
            details_raw = details_span.get_text(" ", strip=True)
            if details_raw.startswith("(") and details_raw.endswith(")"):
                details_raw = details_raw[1:-1]
            specialty_details = details_raw.strip()
        else:
            specialty_visible, specialty_details = split_specialty_parentheses(
                specialty_visible
            )

        # ---- Dirección y precio: buscamos el siguiente div con data-id="result-address-item" ----
        address = ""
        price = ""

        address_block = h3.find_next("div", attrs={"data-id": "result-address-item"})
        if address_block:
            container = address_block.parent  # el div mt-1-5

            street_meta = container.find("meta", attrs={"data-test-id": "street-address"})
            city_meta = container.find("meta", attrs={"data-test-id": "city-address"})
            region_meta = container.find("meta", attrs={"data-test-id": "province-address"})

            street = street_meta.get("content", "").strip() if street_meta else ""
            city = city_meta.get("content", "").strip() if city_meta else ""
            region = region_meta.get("content", "").strip() if region_meta else ""

            parts = [p for p in (street, city, region) if p]
            address = ", ".join(parts)

            # Precio dentro del mismo contenedor
            for text in container.stripped_strings:
                if "$" in text:
                    price = text.strip()
                    break
        else:
            # Fallback por si cambia el HTML
            for p in card.find_all("p"):
                if p.find("a", string=lambda s: s and "Mapa" in s):
                    span = p.find("span")
                    if span:
                        address = span.get_text(" ", strip=True)
                    break
            for text in card.stripped_strings:
                if "$" in text:
                    price = text.strip()
                    break

        results.append(
            {
                "name": name,
                "profile_url": profile_url,
                "specialty": specialty_visible,
                "specialty_details": specialty_details,
                "address": address,
                "price": price,
            }
        )

    return results


def scrape_specialty(specialty: dict):
    base_url = specialty["url"]
    print(f"\n=== {specialty['name']} ===")

    first_soup = fetch_soup(base_url)
    max_pages = get_max_pages(first_soup)
    print(f"Encontradas {max_pages} páginas")

    all_doctors = []

    # Página 1
    all_doctors.extend(parse_doctor_cards(first_soup, base_url))

    # Páginas siguientes
    for page in range(2, max_pages + 1):
        page_url = f"{base_url}?page={page}"
        print(f"Scrapeando página {page}/{max_pages} -> {page_url}")
        soup = fetch_soup(page_url)
        all_doctors.extend(parse_doctor_cards(soup, base_url))

    return all_doctors


def scrape_profile_details(profile_url: str):
    """
    Extrae, desde el perfil:
    - profile_specialty: lista de especialidades del header (sin 'ver más').
    - profile_specialty_details: texto del pop-up 'Más detalles' (Trabajo como / Especialista en).
    - phone_main: teléfonos cerca de 'Número de teléfono'.
    - phone_all: cualquier cosa que parezca teléfono en toda la página.
    """
    soup = fetch_soup(profile_url)

    # -------- 1) Especialidad en perfil (header, sin "ver más") --------
    main_specs = []
    header_span = soup.find("span", attrs={"data-test-id": "doctor-specializations"})
    if header_span:
        for a in header_span.find_all("a"):
            href = a.get("href", "")
            title = a.get("title")
            text = a.get_text(" ", strip=True)

            # Filtramos el "ver más":
            # - suele tener href="#"
            # - no tiene atributo title
            # - texto es "ver más"
            if href == "#" or not title or text.lower().startswith("ver más"):
                continue

            if text:
                main_specs.append(text)

    profile_specialty = ", ".join(main_specs)

    # -------- 2) Especialidad detallada en perfil (pop-up "Más detalles") --------
    profile_specialty_details = ""

    # Buscamos el contenedor más pequeño que tenga ambos textos:
    # "Trabajo como" y "Especialista en"
    candidates = []
    for tag in soup.find_all(lambda t: t.name in ("div", "section", "article")):
        txt = tag.get_text(" ", strip=True)
        if "Trabajo como" in txt and "Especialista en" in txt:
            candidates.append((len(txt), tag))

    if candidates:
        # Elegimos el bloque con menos texto (más probable que sea el pop-up)
        _, details_section = min(candidates, key=lambda x: x[0])

        # Obtenemos líneas limpias
        raw_text = details_section.get_text("\n", strip=True)
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        trabajo_como_items = []
        especialista_en_items = []

        # Identificamos posiciones de "Trabajo como" y "Especialista en"
        idx_trabajo = None
        idx_especialista = None
        for i, line in enumerate(lines):
            low = line.lower()
            if idx_trabajo is None and "trabajo como" in low:
                idx_trabajo = i
            if idx_especialista is None and "especialista en" in low:
                idx_especialista = i

        if (
            idx_trabajo is not None
            and idx_especialista is not None
            and idx_especialista > idx_trabajo
        ):
            # Trabajos: entre "Trabajo como" y "Especialista en"
            trabajo_como_items = lines[idx_trabajo + 1 : idx_especialista]
            # Especialidades: después de "Especialista en"
            especialista_en_items = lines[idx_especialista + 1 :]

        # Armamos el texto final
        tc = "; ".join(trabajo_como_items)
        ee = "; ".join(especialista_en_items)

        parts = []
        if tc:
            parts.append(f"Trabajo como: {tc}")
        if ee:
            parts.append(f"Especialista en: {ee}")

        profile_specialty_details = " | ".join(parts)

    # -------- 3) Teléfonos --------
    phone_main_set = set()
    phone_all_set = set()

    # 3.1 Teléfonos alrededor de "Número de teléfono"
    phone_labels = soup.find_all(
        lambda tag: hasattr(tag, "get_text")
        and "Número de teléfono" in tag.get_text(strip=True)
    )

    for label in phone_labels:
        section = label.parent
        if not hasattr(section, "get_text"):
            continue

        section_text = section.get_text(" ", strip=True)

        # Patrones "bonitos" (10 dígitos)
        for match in PHONE_REGEX_MAIN.findall(section_text):
            norm = " ".join(match.split())
            phone_main_set.add(norm)

        # Miramos hermanos siguientes por si el número está debajo
        for sib in section.next_siblings:
            if getattr(sib, "name", None) in ("h2", "h3", "h4", "section"):
                break

            text = (
                sib.get_text(" ", strip=True)
                if hasattr(sib, "get_text")
                else str(sib)
            )
            for match in PHONE_REGEX_MAIN.findall(text):
                norm = " ".join(match.split())
                phone_main_set.add(norm)

    # 3.2 Teléfonos en todo el HTML (cualquier cosa que parezca teléfono)
    full_text = soup.get_text(" ", strip=True)
    for match in PHONE_REGEX_ANY.findall(full_text):
        digits_only = re.sub(r"\D", "", match)
        if 7 <= len(digits_only) <= 12:
            norm = " ".join(match.split())
            phone_all_set.add(norm)

    # Aseguramos que los "main" también estén en el set amplio
    phone_all_set.update(phone_main_set)

    phone_main = "; ".join(sorted(phone_main_set))
    phone_all = "; ".join(sorted(phone_all_set))

    return profile_specialty, profile_specialty_details, phone_main, phone_all


def save_to_csv(rows, path: str = "doctors.csv"):
    # utf-8-sig -> Excel reconoce bien acentos
    fieldnames = [
        "search_name",
        "name",
        "specialty",
        "specialty_details",
        "address",
        "price",
        "profile_url",
        "profile_specialty",
        "profile_specialty_details",
        "phone_main",
        "phone_all",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nCSV generado: {path} ({len(rows)} filas)")


def main():
    specialties = load_specialties()

    # --- Límite desde archivo de config (hard limit si no existe) ---
    limit = load_specialties_limit()
    specialties = specialties[:limit]
    print(f"🔢 Procesando {len(specialties)} especialidades (de {limit} permitidas)")

    all_results = []

    # 1) Scraping de listados (todas las páginas de cada URL)
    for sp in specialties:
        doctors = scrape_specialty(sp)
        for d in doctors:
            d["search_name"] = sp["name"]
        all_results.extend(doctors)

    # 2) Enriquecer cada doctor con datos del perfil
    total = len(all_results)
    for idx, d in enumerate(all_results, start=1):
        url = d.get("profile_url")
        if not url:
            d["profile_specialty"] = ""
            d["profile_specialty_details"] = ""
            d["phone_main"] = ""
            d["phone_all"] = ""
            continue

        print(f"Perfil {idx}/{total} -> {url}")
        try:
            esp, esp_detalle, phone_main, phone_all = scrape_profile_details(url)
        except Exception as e:
            print(f"  Error leyendo perfil: {e}")
            esp, esp_detalle, phone_main, phone_all = "", "", "", ""

        d["profile_specialty"] = esp
        d["profile_specialty_details"] = esp_detalle
        d["phone_main"] = phone_main
        d["phone_all"] = phone_all

    # 3) Guardar CSV
    save_to_csv(all_results, "doctors.csv")


if __name__ == "__main__":
    main()

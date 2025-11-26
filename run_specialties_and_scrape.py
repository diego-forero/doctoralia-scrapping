import json
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Puedes reutilizar el mismo user-agent
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

BASE_URL = "https://www.doctoralia.co"


def fetch_specialties():
    """
    Lee https://www.doctoralia.co/especialidades-medicas
    y devuelve una lista de:
    { "name": ..., "url": ... }
    filtrando 'ver más' y corrigiendo URLs absolutas/relativas.
    """
    url = f"{BASE_URL}/especialidades-medicas"
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    links = soup.find_all("a", class_="text-muted")

    specialties = []
    seen_urls = set()

    for link in links:
        name = link.get_text(strip=True)
        href = (link.get("href") or "").strip()

        if not name or not href:
            continue

        # Saltar los "ver más"
        if "ver más" in name.lower():
            continue

        # Construimos URL completa de forma segura
        full_url = urljoin(BASE_URL, href)

        # Evitar duplicados
        if full_url in seen_urls:
            continue

        specialties.append(
            {
                "name": name,
                "url": full_url,
            }
        )
        seen_urls.add(full_url)

    return specialties


def save_specialties_json(specialties, path: str = "specialties.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(specialties, f, ensure_ascii=False, indent=2)
    print(f"✅ Guardado specialties.json con {len(specialties)} entradas")


def main():
    from scrape_listings import main as scrape_doctors_main  # import aquí para evitar ciclos

    start_total = time.perf_counter()
    print("⏱️ Inicio del pipeline completo\n")

    # 1) Obtener especialidades y guardar specialties.json
    t0 = time.perf_counter()
    specialties = fetch_specialties()
    t1 = time.perf_counter()
    save_specialties_json(specialties)
    t2 = time.perf_counter()

    print(
        f"📊 Paso 1 - Especialidades:"
        f" {len(specialties)} especialidades obtenidas en {t1 - t0:.1f} s,"
        f" guardado JSON en {t2 - t1:.1f} s"
    )

    # 2) Ejecutar el scraper principal de médicos
    print("\n🚀 Paso 2 - Scraping de médicos usando specialties.json...")
    t3 = time.perf_counter()
    scrape_doctors_main()
    t4 = time.perf_counter()
    print(f"📊 Paso 2 - Scraping de médicos completado en {t4 - t3:.1f} s")

    # 3) Tiempo total
    total = time.perf_counter() - start_total
    print("\n⏰ Tiempo TOTAL del pipeline: "
          f"{total:.1f} segundos (~{total/60:.1f} minutos)")


if __name__ == "__main__":
    main()

# Doctoralia Scraping

Pequeño proyecto en Python para extraer información pública de médicos en [doctoralia.co](https://www.doctoralia.co).

El flujo completo hace dos cosas:

1. Descarga el listado de **especialidades médicas** de Doctoralia Colombia.
2. Para un subconjunto de esas especialidades, recorre las páginas de resultados y los **perfiles** de cada médico y genera un archivo `doctors.csv` con la información principal.

> ⚠️ Usa este código de forma responsable. Respeta los Términos y Condiciones de Doctoralia, limita la frecuencia de consultas y no lo uses para spam.

---

## Requisitos

- Python 3.10+ (recomendado)
- `pip`
- (Opcional pero recomendado) entorno virtual `venv`

Dependencias de Python:

- `requests`
- `beautifulsoup4`

Instalación rápida de dependencias:

```bash
pip install requests beautifulsoup4
```

---

## Estructura principal

- `run_specialties_and_scrape.py`  
  Orquestador. Descarga las especialidades, genera `specialties.json` y luego ejecuta el scraper de médicos. También imprime métricas de tiempo por paso y tiempo total del proceso.

- `scrape_listings.py`  
  Lee `specialties.json`, aplica un límite configurado y:
  - Recorre las páginas de cada especialidad (por ejemplo, `https://www.doctoralia.co/dermatologo/bogota?page=2`).
  - Extrae la información de cada card de médico.
  - Entra al perfil de cada médico para completar detalles adicionales (especialidades, teléfonos, etc.).
  - Genera el archivo `doctors.csv`.

- `specialties.json`  
  Archivo generado automáticamente con la lista de especialidades a procesar.  
  Cada item tiene la forma:

  ```json
  {
    "name": "Dermatólogo Bogotá",
    "url": "https://www.doctoralia.co/dermatologo/bogota"
  }
  ```

- `scraper_config.json`  
  Archivo de configuración para limitar cuántas especialidades se procesan en cada ejecución.

---

## Configuración: límite de especialidades

Para evitar probar con cientos de URLs, el límite se configura en `scraper_config.json`.

Ejemplo de archivo (en la raíz del repo):

```json
{
  "specialties_limit": 4
}
```

- Si `scraper_config.json` **no existe**, el código usa un límite por defecto de **10** especialidades.
- Si el valor es inválido o menor/igual a 0, también se usa el valor por defecto (10).

Este límite solo afecta **cuántas especialidades** del `specialties.json` se procesan, empezando por las primeras.

---

## Campos generados en `doctors.csv`

El archivo `doctors.csv` se genera en la raíz del repo con codificación `utf-8-sig` (amigable con Excel) y contiene, entre otras, las siguientes columnas:

- `search_name` – Nombre de la especialidad/ciudad con la que se hizo la búsqueda (por ejemplo, `"Dermatólogo Bogotá"`).
- `name` – Nombre del médico (por ejemplo, `"Dra. Alejandra Téllez"`).
- `specialty` – Especialidad visible en el listado (texto principal del card).
- `specialty_details` – Detalle de la especialidad que aparece entre paréntesis en el card (si aplica).
- `address` – Dirección normalizada a partir de los metadatos del listado (calle, ciudad, región).
- `price` – Precio de la consulta que aparece en el card (por ejemplo, `$ 220.000`).
- `profile_url` – URL del perfil del médico.

Datos extraídos desde el **perfil**:

- `profile_specialty` – Lista de especialidades en el encabezado del perfil (por ejemplo: `Dermatólogo, Médico estético`), sin incluir el enlace de “ver más”.
- `profile_specialty_details` – Texto del bloque “Más detalles”, en el formato:

  ```text
  Trabajo como: Dermatólogo; Médico estético | Especialista en: Dermatología Pediátrica; Láser Dermocosmético; ...
  ```

Teléfonos:

- `phone_main` – Números cerca del bloque de “Número de teléfono” en el perfil (normalmente los más relevantes).
- `phone_all` – Cualquier texto que parezca número de teléfono dentro del HTML del perfil.

---

## Cómo ejecutar el proyecto

### 1. Clonar el repositorio

```bash
git clone https://github.com/diego-forero/doctoralia-scrapping.git
cd doctoralia-scrapping
```

### 2. (Opcional) Crear y activar un entorno virtual

En macOS / Linux:

```bash
python -m venv .venv
source .venv/bin/activate
```

En Windows (Git Bash):

```bash
python -m venv .venv
source .venv/Scripts/activate
```

### 3. Instalar dependencias

```bash
pip install requests beautifulsoup4
```

### 4. Configurar el límite de especialidades (opcional)

Crear/editar `scraper_config.json` en la raíz:

```json
{
  "specialties_limit": 4
}
```

Si lo omites, se usará el límite por defecto de 10.

### 5. Ejecutar el pipeline completo

Desde la raíz del repo:

```bash
python run_specialties_and_scrape.py
```

Este comando hará:

1. Descargar `https://www.doctoralia.co/especialidades-medicas`.
2. Generar/actualizar `specialties.json`.
3. Leer `scraper_config.json` para determinar cuántas especialidades procesar.
4. Scrappear las páginas de resultados y los perfiles de los médicos.
5. Generar `doctors.csv` con toda la información consolidada.
6. Mostrar métricas de tiempo por paso y tiempo total del pipeline.

Durante la ejecución verás logs tipo:

- Especialidades encontradas y guardadas.
- Cuántas especialidades se van a procesar según el límite.
- Progreso por página y por perfil.
- Métricas de tiempo por paso y tiempo total en segundos y minutos.

---

## Notas y buenas prácticas

- No aumentes `specialties_limit` a valores muy grandes sin probar antes con pocos (por ejemplo 2–4), ya que el número de perfiles puede ser alto.
- Respeta las políticas de uso de Doctoralia:
  - No dispares el scraper con demasiada frecuencia.
  - No distribuyas los datos de forma que viole sus términos.
- Este proyecto es únicamente con fines educativos / internos.

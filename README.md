# InstaFlow ⚡ — Dashboard Profesional de Scraping y Análisis de Instagram

**InstaFlow** es una aplicación integral, modular y profesional desarrollada en **Python (Flask)** y **Selenium**, diseñada para la extracción, visualización y análisis de perfiles y publicaciones públicas o autorizadas de Instagram. Su interfaz de usuario moderna, oscura y reactiva está inspirada en la experiencia visual de **n8n**.

---

## 🚀 Características Principales

- **Diseño visual inspirado en n8n:**
  - Lienzo oscuro (`#0b0c13`), tarjetas modulares con bordes sutiles y acentos violetas (`#8936FF`), azules (`#3F8CFF`) y esmeralda (`#00C49F`).
  - Pipeline interactivo que desglosa en tiempo real las **16 etapas** de la extracción con duraciones y estados.
  - Consola terminal en vivo para registrar eventos de red y progreso.
  - Tarjetas de métricas independientes que distinguen rigurosamente entre valores reales (incluido el `0`) y datos desconocidos (`No disponible`), sin inventar datos.
- **Galería de publicaciones interactiva:**
  - Tarjetas cuadradas con miniaturas reales en alta resolución extraídas del atributo `srcset`.
  - Detección diferenciada de tipos de contenido: **Fotografía**, **Carrusel multi-imagen**, **Vídeo** y **Reel**.
  - Filtros instantáneos por tipo de medio, buscador por texto en pie de foto y lightbox modal para zoom de imágenes.
  - Paginación progresiva para garantizar rendimiento fluido sin saturar la memoria del navegador.
- **Gestión de imágenes y medios:**
  - Descarga de imágenes únicamente desde dominios autorizados de Meta (`cdninstagram.com`, `fbcdn.net`) con protección contra SSRF.
  - Validación de integridad con **Pillow** (`Image.verify()`), conversión a JPEG optimizado y asignación de nombres únicos con hashes SHA-256.
  - Generación opcional de captura de pantalla en PNG del encabezado del perfil analizado.
- **Arquitectura asíncrona sin bloqueos:**
  - Gestor de trabajos en segundo plano (`JobManager`) basado en hilos (`threading`), con identificadores únicos UUIDv4.
  - El hilo principal de Flask nunca se congela; el frontend sondea el progreso mediante la API REST (`/api/jobs/<job_id>`).
  - Soporte de cancelación segura cooperativa en cualquier etapa de la extracción.
- **Persistencia y exportación multiformato:**
  - Almacenamiento completo de cada ejecución en archivos **JSON** UTF-8 (`data/results/`).
  - Exportación tabular a **CSV** mediante **Pandas**, con codificación UTF-8 con BOM (`utf-8-sig`) para compatibilidad directa con Microsoft Excel en Windows (conservando tildes y emojis).
  - Base de datos relacional **SQLite** (`data/database/instaflow.db`) para registro histórico de ejecuciones, perfiles y publicaciones.
- **Cumplimiento ético y seguridad:**
  - Uso exclusivo de métodos autorizados y navegación estándar de Chrome mediante Selenium Manager.
  - Sin elusión de CAPTCHA, sin bypass de 2FA y sin evasión de restricciones.
  - Cookies de autenticación separadas en `cookies.json` y excluidas de Git.

---

## 🛠️ Tecnologías Utilizadas

| Componente | Tecnología | Propósito |
| :--- | :--- | :--- |
| **Backend / API** | Python 3.11+ / Flask 3.1+ | Servidor web local y API REST asíncrona |
| **Automatización** | Selenium 4.20+ / Selenium Manager | Control de Google Chrome y navegación DOM |
| **Datos / Exportación** | Pandas 2.2+ | Generación de reportes tabulares y CSV |
| **Validación de Imagen**| Pillow 10.3+ | Verificación de integridad y optimización de medios |
| **Parser HTML** | BeautifulSoup4 | Extracción de metadatos Open Graph y JSON-LD |
| **Persistencia** | SQLite 3 / JSON / CSV | Almacenamiento histórico y caché local |
| **Frontend** | HTML5 / CSS3 / Vanilla JavaScript | Dashboard n8n-style sin dependencias pesadas |
| **Pruebas** | pytest 8.0+ | Pruebas unitarias automatizadas |

---

## 📁 Estructura del Proyecto

```text
instagram-dashboard/
├── app.py                     # Servidor Flask y endpoints de la API REST
├── config.py                  # Configuración centralizada de la aplicación
├── requirements.txt           # Dependencias de Python fijadas
├── README.md                  # Manual completo de instalación y uso
├── .gitignore                 # Exclusiones de Git (cookies, media, datos locales)
├── cookies.example.json       # Plantilla de ejemplo para cookies autorizadas
├── scraper/
│   ├── __init__.py
│   ├── browser.py             # Controlador Selenium y gestión de Chrome
│   ├── session_manager.py     # Manejo de sesión y cookies autorizadas
│   ├── profile_extractor.py   # Extracción multiescalonada de perfil (OG, DOM, JSON-LD)
│   ├── post_extractor.py      # Extracción de cuadrícula, srcset y tipos de medio
│   ├── image_downloader.py    # Descarga segura y validación Pillow
│   ├── scraper_service.py     # Orquestador de las 16 etapas de extracción
│   ├── job_manager.py         # Administrador de tareas en segundo plano
│   ├── validators.py          # Validadores de username, contadores y sanitización
│   └── exceptions.py          # Excepciones estructuradas del sistema
├── storage/
│   ├── __init__.py
│   ├── json_storage.py        # Almacenamiento y carga de resultados JSON
│   ├── csv_storage.py         # Exportación tabular con Pandas (UTF-8 BOM)
│   └── database.py            # Gestor de base de datos SQLite histórica
├── templates/
│   ├── index.html             # Vista principal del Dashboard
│   ├── profile.html           # Vista detallada de perfil almacenado
│   └── settings.html          # Panel de diagnóstico y configuración
├── static/
│   ├── css/
│   │   ├── dashboard.css      # Sistema de diseño n8n (variables, layout, timeline)
│   │   └── gallery.css        # Estilos de la cuadrícula de publicaciones y tarjetas
│   ├── js/
│   │   ├── api.js             # Cliente HTTP REST asíncrono
│   │   ├── dashboard.js       # Controlador de eventos, métricas y sondeo de tareas
│   │   └── gallery.js         # Filtros, búsqueda, lightbox y paginación
│   └── img/
│       └── placeholder.svg    # Imagen de respaldo con gradiente oscuro
├── data/
│   ├── results/               # Resultados exportados en JSON y CSV
│   └── database/              # Archivo de base de datos instaflow.db
├── media/
│   ├── profiles/              # Fotos de perfil descargadas
│   └── posts/                 # Miniaturas e imágenes de publicaciones
├── screenshots/               # Capturas PNG de perfiles analizados
└── tests/
    ├── test_validators.py     # Pruebas de validación y contadores
    ├── test_profile_extractor.py # Pruebas de extracción de perfiles
    ├── test_post_extractor.py # Pruebas de cuadrícula y tipos de medios
    ├── test_storage.py        # Pruebas de persistencia JSON, CSV y SQLite
    └── test_api_endpoints.py  # Pruebas de endpoints Flask
```

---

## 💻 Instalación y Ejecución en Windows

### Requisitos previos
1. **Python 3.11 o superior** instalado y agregado al PATH de Windows.
2. **Google Chrome** instalado en su ruta estándar (`C:\Program Files\Google\Chrome\Application\chrome.exe`).
3. PowerShell de Windows.

### Paso 1: Abrir PowerShell y ubicarse en el proyecto
```powershell
cd C:\Users\ASUS\.gemini\antigravity\scratch\instagram-dashboard
```

### Paso 2: Crear el entorno virtual
```powershell
python -m venv .venv
```

### Paso 3: Activar el entorno virtual
Si PowerShell muestra un error de directiva de ejecución (`ExecutionPolicy`), habilite la ejecución para la sesión actual mediante:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Paso 4: Instalar las dependencias
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 5: Iniciar la aplicación
```powershell
python app.py
```

### Paso 6: Abrir el dashboard en su navegador
Una vez iniciado, acceda a:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 🔑 Configuración de Sesión y Cookies Autorizadas

Para consultar cuentas accesibles mediante su sesión autorizada sin introducir contraseñas en la aplicación:

1. Inicie sesión en Instagram desde su navegador habitual (Google Chrome o Firefox).
2. Abra las Herramientas de Desarrollador (**F12**) y diríjase a la pestaña **Application** (o **Almacenamiento** en Firefox) -> **Cookies** -> `https://www.instagram.com`.
3. Copie las cookies principales de sesión: `sessionid`, `ds_user_id` y `csrftoken`.
4. Copie el archivo de ejemplo `cookies.example.json` como `cookies.json`:
   ```powershell
   Copy-Item cookies.example.json cookies.json
   ```
5. Edite `cookies.json` colocando sus valores reales:
   ```json
   [
     {
       "name": "sessionid",
       "value": "su_valor_sessionid_aqui",
       "domain": ".instagram.com",
       "path": "/",
       "secure": true,
       "httpOnly": true
     },
     {
       "name": "ds_user_id",
       "value": "su_id_de_usuario_aqui",
       "domain": ".instagram.com",
       "path": "/",
       "secure": true,
       "httpOnly": false
     },
     {
       "name": "csrftoken",
       "value": "su_csrftoken_aqui",
       "domain": ".instagram.com",
       "path": "/",
       "secure": true,
       "httpOnly": false
     }
   ]
   ```
6. Al reiniciar o refrescar la aplicación, el badge de sesión en la cabecera mostrará **«Cookies Configuradas»**.
7. Si no desea configurar cookies, la aplicación funcionará de forma automática en **Modo Público**, extrayendo la información pública accesible.

> [!NOTE]
> `cookies.json` está explícitamente excluido en `.gitignore` para garantizar que sus credenciales nunca se suban a un repositorio.

---

## ⚙️ Configuración Centralizada (`config.py`)

Todas las opciones del sistema están centralizadas y documentadas en `config.py`:

- `HEADLESS`: `True` para ejecutar Chrome de fondo sin ventana visible; `False` para ver la ventana de Chrome durante la ejecución.
- `PAGE_LOAD_TIMEOUT`: Tiempo máximo de carga de páginas (30 segundos).
- `ELEMENT_TIMEOUT`: Tiempo de espera explícita `WebDriverWait` (12 segundos).
- `DEFAULT_POSTS_LIMIT`: Cantidad de publicaciones predeterminada (12).
- `MAX_POSTS_LIMIT`: Límite máximo configurable de publicaciones (100).
- `MAX_SCROLL_ATTEMPTS`: Límite de desplazamientos para prevenir bucles infinitos (15).
- `DOWNLOAD_IMAGES`: Habilitar/deshabilitar la descarga local de imágenes en disco.
- `CAPTURE_SCREENSHOT`: Habilitar/deshabilitar la captura PNG del perfil.
- `MAX_CONCURRENT_JOBS`: Límite de tareas simultáneas (2).

---

## 🔄 Las 16 Etapas del Pipeline de Scraping

Cada ejecución se ejecuta a través de 16 etapas sincronizadas y cronometradas en tiempo real:

1. **Validar el nombre de usuario:** Normalización y validación sintáctica de la entrada.
2. **Inicializar Chrome:** Apertura del WebDriver con Selenium Manager y optimizaciones de rendimiento.
3. **Comprobar la sesión y el estado de acceso:** Verificación e inyección de cookies autorizadas.
4. **Abrir el perfil solicitado:** Navegación a la URL oficial del perfil.
5. **Esperar a que el contenido relevante esté disponible:** Espera explícita de hidratación del DOM.
6. **Capturar la información básica:** Nombre completo, biografía con emojis y contadores.
7. **Capturar la fotografía de perfil:** Obtención de URL y descarga local del avatar.
8. **Detectar el número total de publicaciones:** Detección del contador oficial de la cabecera.
9. **Identificar los enlaces de publicaciones:** Detección de nodos `/p/` y `/reel/` en la cuadrícula.
10. **Recopilar los metadatos disponibles:** Clasificación de fotos, carruseles, vídeos y reels.
11. **Obtener las miniaturas:** Selección de la URL de mayor resolución en `srcset`.
12. **Descargar las imágenes autorizadas:** Descarga HTTP segura con gestión de errores por post.
13. **Validar los archivos:** Validación estricta de formato e integridad con Pillow.
14. **Guardar los resultados:** Persistencia simultánea en JSON, CSV y base de datos SQLite.
15. **Actualizar el dashboard:** Transmisión de métricas y estados finales.
16. **Generar un resumen de la ejecución:** Cálculo del tiempo total transcurrido y tasa de éxito.

---

## 🧪 Ejecución de Pruebas Automatizadas

El proyecto incluye una completa suite de pruebas unitarias que no dependen de la red ni de Instagram en vivo:

```powershell
python -m pytest tests -v
```

Resultado verificado:
```text
tests/test_api_endpoints.py::TestAPIEndpoints::test_health_endpoint PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_settings_endpoint PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_scrape_validation_invalid_username PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_scrape_valid_launch PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_job_not_found PASSED
tests/test_api_endpoints.py::TestAPIEndpoints::test_cancel_non_existent_job PASSED
tests/test_post_extractor.py::TestPostExtractor::test_parse_single_photo_post PASSED
tests/test_post_extractor.py::TestPostExtractor::test_parse_carousel_post PASSED
tests/test_post_extractor.py::TestPostExtractor::test_parse_reel_post PASSED
tests/test_post_extractor.py::TestPostExtractor::test_extract_best_from_srcset PASSED
tests/test_post_extractor.py::TestPostExtractor::test_clean_caption_accessibility_prefix PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_extract_from_open_graph_spanish PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_extract_from_open_graph_english PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_extract_from_json_ld PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_detect_profile_not_found PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_detect_private_account PASSED
tests/test_profile_extractor.py::TestProfileExtractor::test_empty_biography_handling PASSED
tests/test_storage.py::TestStorage::test_json_storage_save_and_load PASSED
tests/test_storage.py::TestStorage::test_csv_storage_profile_and_posts PASSED
tests/test_storage.py::TestStorage::test_sqlite_database_operations PASSED
tests/test_validators.py::TestValidators::test_normalize_username_with_at PASSED
tests/test_validators.py::TestValidators::test_normalize_username_from_url PASSED
tests/test_validators.py::TestValidators::test_validate_username_valid PASSED
tests/test_validators.py::TestValidators::test_validate_username_invalid PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_explicit_zero PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_unknown_or_empty PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_millions PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_thousands PASSED
tests/test_validators.py::TestValidators::test_parse_count_string_formatted_numbers PASSED
tests/test_validators.py::TestValidators::test_sanitize_filename PASSED
tests/test_validators.py::TestValidators::test_is_safe_image_url PASSED

============================= 31 passed in 4.27s ==============================
```

---

## ⚠️ Limitaciones Conocidas y Uso Ético

1. **Límites de acceso y tasa (Rate Limits):** Instagram aplica límites de frecuencia de solicitudes. Se recomienda espaciar las extracciones consecutivas y utilizar límites moderados de publicaciones (ej. 12 a 50 publicaciones).
2. **Cuentas privadas:** Si una cuenta es privada y la sesión configurada no la sigue con aprobación previa, Instagram no expondrá sus publicaciones; la aplicación detectará el estado privado y concluirá la etapa informándolo claramente.
3. **Persistencia de URLs de CDN:** Las URLs de imágenes en CDN de Instagram contienen firmas con tiempo de expiración. InstaFlow descarga y valida localmente las imágenes para garantizar que permanezcan accesibles permanentemente en el dashboard.
4. **Uso autorizado:** Esta herramienta ha sido diseñada para análisis de cuentas propias, investigación autorizada y auditoría de perfiles accesibles legítimamente. No debe ser utilizada con fines abusivos ni para eludir medidas de seguridad de la plataforma.

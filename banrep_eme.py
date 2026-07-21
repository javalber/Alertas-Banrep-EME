"""
Monitor de la Encuesta Mensual de Expectativas de Analistas Económicos (EME)
del Banco de la República de Colombia.

Qué hace
--------
Cada vez que se ejecuta:

1. Detecta automáticamente el último informe EME publicado. No hay que decirle
   qué mes buscar: parte del mes actual y retrocede hasta 12 meses probando la
   URL de cada período hasta encontrar una que exista (ver
   `obtener_ultimo_publicado`).
2. Compara el período detectado con el último notificado, guardado en
   `ultimo_periodo.txt` (el "estado").
3. Si es un período nuevo, envía un correo de alerta y actualiza el estado.

El script NO necesita mantenimiento mensual: la detección es automática. Lo que
sí debe funcionar es que el estado (`ultimo_periodo.txt`) se persista entre
ejecuciones; en GitHub Actions eso lo hace el paso de commit del workflow
(.github/workflows/monitor_banrep_eme.yml), que requiere `permissions: contents:
write`. Si ese push falla, el estado no se guarda y se reenvían correos
duplicados.

Cómo detecta un período no publicado
-------------------------------------
BanRep publica cada informe en una URL predecible:
    {BASE_URL}{SLUG_PREFIX}{mes}-{anio}
Si el período aún no existe, esa URL devuelve 404 o una página de "no
encontrada". `existe_publicacion` distingue ambos casos (ver esa función). Si
BanRep cambia el patrón de sus URLs, esta es la parte que habría que ajustar.

Ejecución
---------
    GMAIL_APP_PASSWORD=<clave-de-aplicacion-gmail> python banrep_eme.py

Efectos secundarios al detectar un período nuevo:
- Envía correo a los destinatarios de DESTINOS.
- Sobrescribe `ultimo_periodo.txt` con el período detectado.
- Crea `changed.flag`, señal que el workflow usa para saber que debe commitear
  el nuevo estado.
"""

import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ================= CONFIG =================
# Remitente Gmail. La contraseña es una "App Password" de Gmail (no la clave
# normal de la cuenta) y se inyecta por variable de entorno / secret, nunca se
# hardcodea.
GMAIL_USER = "javalber2@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

DESTINOS = [
    "jflor35@bancodebogota.com.co",
]

ARCHIVO_ESTADO = "ultimo_periodo.txt"

BASE_URL = "https://www.banrep.gov.co/es/"
SLUG_PREFIX = "resultado-encuesta-mensual-expectativas-analistas-economicos-eme-"

MESES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


# ================= HELPERS =================
def construir_url(year, month):
    """Devuelve (url, periodo) para un año/mes dados.

    - url: dirección de BanRep donde se publicaría ese informe.
    - periodo: etiqueta legible tipo "Junio 2026", usada como estado y en el
      correo.
    """
    mes = MESES[month]
    url = f"{BASE_URL}{SLUG_PREFIX}{mes}-{year}"
    periodo = f"{mes.capitalize()} {year}"
    return url, periodo


def leer_estado():
    """Lee el último período notificado desde `ultimo_periodo.txt`.

    Devuelve None si el archivo no existe o está vacío (primera ejecución).
    """
    if not os.path.exists(ARCHIVO_ESTADO):
        return None
    with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
        val = f.read().strip()
    return val if val else None


def guardar_estado(periodo):
    """Persiste el período notificado en `ultimo_periodo.txt`.

    Evita reenviar el mismo aviso en corridas posteriores. En CI, este archivo
    debe commitearse de vuelta al repo para que el estado sobreviva entre
    ejecuciones.
    """
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        f.write(periodo)


def enviar_correo(periodo, url):
    """Envía por SMTP (Gmail, STARTTLS) el correo de alerta de nuevo informe."""
    asunto = f"[Alerta BanRep EME] Publicado: {periodo}"
    cuerpo = (
        f"Se publicó la EME correspondiente a {periodo}.\n\n"
        f"URL:\n{url}\n"
    )

    msg = MIMEText(cuerpo, _charset="utf-8")
    msg["Subject"] = asunto
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(DESTINOS)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, DESTINOS, msg.as_string())


def existe_publicacion(url):
    """Indica si la URL corresponde a un informe realmente publicado.

    BanRep no siempre responde 404 para un período inexistente: a veces
    devuelve 200 con una página de "Página no encontrada". Por eso se revisan
    ambas señales: el código HTTP y el <title> de la página.

    NOTA: si BanRep cambia el texto de su página de error o el patrón de la URL,
    esta función es lo que hay que ajustar.
    """
    r = requests.get(url, timeout=20)

    if r.status_code == 404:
        return False

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""

    if "Página no encontrada" in title or "Page not found" in title:
        return False

    return True


def obtener_ultimo_publicado():
    """Detecta el último informe EME publicado.

    Parte del mes actual (UTC) y retrocede mes a mes, probando la URL de cada
    período, hasta encontrar uno publicado. Devuelve (periodo, url) del más
    reciente, o (None, None) si no encuentra nada en 12 meses.

    Esta es la razón por la que el script NO necesita configurarse cada mes: el
    mes objetivo se descubre solo.
    """
    fecha = datetime.utcnow()

    for _ in range(12):  # máximo retrocede 12 meses
        year = fecha.year
        month = fecha.month

        url, periodo = construir_url(year, month)

        if existe_publicacion(url):
            return periodo, url

        fecha -= relativedelta(months=1)

    return None, None


# ================= MAIN =================
def main():
    """Orquesta: detectar → comparar con estado → notificar si es nuevo."""
    periodo_detectado, url = obtener_ultimo_publicado()

    if not periodo_detectado:
        print("No se encontró ninguna publicación.")
        return

    print(f"Último publicado detectado: {periodo_detectado}")

    estado = leer_estado()

    if estado == periodo_detectado:
        print("Ya notificado previamente.")
        return

    enviar_correo(periodo_detectado, url)
    guardar_estado(periodo_detectado)

    # Señal para el workflow: hubo cambio de estado, hay que commitear
    # ultimo_periodo.txt de vuelta al repo.
    with open("changed.flag", "w") as f:
        f.write("changed")

    print("Notificación enviada.")


if __name__ == "__main__":
    main()

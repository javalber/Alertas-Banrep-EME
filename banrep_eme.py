import os
import re
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import unicodedata

# =========================
# Configuración
# =========================
GMAIL_USER = "javalber2@gmail.com"
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
DESTINOS = [
    "jflor35@bancodebogota.com.co",
    # Puedes agregar más correos del equipo aquí:
    # "alguien@bancodebogota.com.co",
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

TITULO_ESPERADO_PREFIX = "Resultado de la Encuesta mensual de expectativas de analistas económicos (EME) -"


# =========================
# Helpers
# =========================
def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.strip()


def leer_estado() -> str | None:
    if not os.path.exists(ARCHIVO_ESTADO):
        return None
    with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
        val = f.read().strip()
    return val if val else None


def guardar_estado(periodo: str) -> None:
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        f.write(periodo)


def enviar_correo(periodo: str, url: str, title: str) -> None:
    asunto = f"[Alerta BanRep EME] Publicado: {periodo}"
    cuerpo = (
        "Hola,\n\n"
        "Se detectó una nueva publicación del BanRep:\n"
        "Resultado de la Encuesta mensual de expectativas de analistas económicos (EME)\n\n"
        f"Periodo publicado: {periodo}\n"
        f"Título detectado: {title}\n"
        f"URL: {url}\n\n"
        "Saludos,\n"
        "Bot de alertas (GitHub Actions)\n"
    )

    msg = MIMEText(cuerpo, _charset="utf-8")
    msg["Subject"] = asunto
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(DESTINOS)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, DESTINOS, msg.as_string())


def periodo_objetivo(modo: str = "current") -> tuple[int, int]:
    """
    modo="current": revisa el mes actual (recomendado si el BanRep publica 'el mes' vigente)
    modo="next": revisa el mes siguiente (si tú quieres anticiparte y esperar que aparezca)
    """
    now = datetime.utcnow()
    year, month = now.year, now.month

    if modo == "current":
        month += 1
        if month == 13:
            month = 1
            year += 1

    return year, month


def construir_url(year: int, month: int) -> tuple[str, str]:
    mes_nombre = MESES[month]  # ya va en minúscula sin acentos
    slug = f"{SLUG_PREFIX}{mes_nombre}-{year}"
    url = f"{BASE_URL}{slug}"
    periodo = f"{mes_nombre.capitalize()} {year}"
    return url, periodo


def esta_publicado(title: str, year: int, month: int) -> bool:
    title_norm = normalizar(title)

    # Si contiene "Página no encontrada"
    if "Página no encontrada" in title_norm or "Page not found" in title_norm:
        return False

    # Validación del patrón esperado + mes/año en el título
    mes_nombre = MESES[month]
    patron = re.compile(
        rf"^{re.escape(TITULO_ESPERADO_PREFIX)}\s*-\s*{mes_nombre}\s+de\s+{year}$",
        re.IGNORECASE
    )

    return bool(patron.match(title_norm))


# =========================
# Main
# =========================
def main():
    # Ajusta el modo aquí:
    # - "current" revisa el mes actual
    # - "next" revisa el mes siguiente
    modo = "current"  # <-- cámbialo a "current" si eso se adapta mejor a tu necesidad

    year, month = periodo_objetivo(modo=modo)
    url, periodo = construir_url(year, month)

    print(f"Revisando URL: {url}")

    r = requests.get(url, timeout=30)
    status = r.status_code

    # Si el servidor responde 404, no está publicado
    if status == 404:
        print("No publicado (404).")
        return

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""
    print(f"Title: {title}")

    if not title:
        print("No se pudo leer <title>.")
        return

    if not esta_publicado(title, year, month):
        print("No publicado (por título).")
        return

    # Publicado. Evitar duplicados:
    estado = leer_estado()
    if estado == periodo:
        print(f"Ya notificado anteriormente: {periodo}")
        return

    # Notificar y guardar estado
    enviar_correo(periodo, url, title)
    guardar_estado(periodo)

    # Bandera para commit
    with open("changed.flag", "w", encoding="utf-8") as f:
        f.write("changed")

    print(f"Notificación enviada y estado actualizado: {periodo}")


if __name__ == "__main__":
    main()
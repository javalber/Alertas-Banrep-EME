import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from dateutil.relativedelta import relativedelta

# ================= CONFIG =================
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
    mes = MESES[month]
    url = f"{BASE_URL}{SLUG_PREFIX}{mes}-{year}"
    periodo = f"{mes.capitalize()} {year}"
    return url, periodo


def leer_estado():
    if not os.path.exists(ARCHIVO_ESTADO):
        return None
    with open(ARCHIVO_ESTADO, "r", encoding="utf-8") as f:
        val = f.read().strip()
    return val if val else None


def guardar_estado(periodo):
    with open(ARCHIVO_ESTADO, "w", encoding="utf-8") as f:
        f.write(periodo)


def enviar_correo(periodo, url):
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
    r = requests.get(url, timeout=20)

    if r.status_code == 404:
        return False

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else ""

    if "Página no encontrada" in title or "Page not found" in title:
        return False

    return True


def obtener_ultimo_publicado():
    """
    Busca hacia atrás desde el mes actual
    hasta encontrar el último publicado.
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

    with open("changed.flag", "w") as f:
        f.write("changed")

    print("Notificación enviada.")


if __name__ == "__main__":
    main()

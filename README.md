# Alertas BanRep EME

Aviso automático por correo cuando el Banco de la República publica un nuevo
informe de la **Encuesta Mensual de Expectativas de Analistas Económicos (EME)**.

## Cómo funciona

`banrep_eme.py` se ejecuta dos veces al día desde GitHub Actions y:

1. **Detecta solo** el último informe publicado: parte del mes actual y
   retrocede hasta 12 meses probando la URL de cada período en el sitio de
   BanRep. No hay que decirle qué mes buscar.
2. Compara ese período con el último notificado, guardado en
   `ultimo_periodo.txt`.
3. Si es nuevo → envía correo a los destinatarios y actualiza el estado.

No requiere mantenimiento mensual. El mes se descubre automáticamente.

## Archivos

| Archivo | Rol |
|---|---|
| `banrep_eme.py` | Lógica de detección y envío de correo. |
| `ultimo_periodo.txt` | Estado: último período ya notificado (p. ej. `Junio 2026`). |
| `.github/workflows/monitor_banrep_eme.yml` | Cron (08:00 y 14:00 hora Colombia) y commit del estado. |
| `requirements.txt` | Dependencias de Python. |

## Configuración

- **Destinatarios**: editar la lista `DESTINOS` en `banrep_eme.py`.
- **Remitente / clave**: `GMAIL_USER` en el script; la clave es una
  [App Password de Gmail](https://myaccount.google.com/apppasswords) (no la
  contraseña normal), cargada como secret `GMAIL_APP_PASSWORD` en el
  environment del repo en GitHub.

## Ejecutar localmente

```bash
pip install -r requirements.txt
GMAIL_APP_PASSWORD=tu_app_password python banrep_eme.py
```

## Por qué antes tocaba actualizarlo a mano

El workflow guarda el estado (`ultimo_periodo.txt`) haciendo `git push` de
vuelta al repo. Eso necesita `permissions: contents: write` en el workflow; sin
ese permiso el `GITHUB_TOKEN` es de solo lectura, el push falla y el estado
nunca se persiste, por lo que el script vuelve a detectar el mismo período como
"nuevo" y reenvía correos duplicados hasta que alguien edita
`ultimo_periodo.txt` a mano. Con el permiso ya configurado, el ciclo es
totalmente automático.

## Si algún día deja de detectar informes

BanRep publica cada informe en una URL con patrón fijo. Si cambian ese patrón o
el texto de su página de error, ajustar `construir_url` y/o
`existe_publicacion` en `banrep_eme.py` (ambas están documentadas en el código).

"""
WhatsApp Image Agent
====================
Sube una imagen local y la reenvía a un grupo de WhatsApp
usando Twilio for WhatsApp API.

Requisitos:
    pip install twilio requests python-dotenv

Uso:
    python agent.py --image foto.jpg --caption "Mira esta imagen"
    python agent.py --image foto.png   (sin caption, envía solo la imagen)

Variables de entorno necesarias en .env:
    TWILIO_ACCOUNT_SID
    TWILIO_AUTH_TOKEN
    TWILIO_WHATSAPP_FROM      # ej: whatsapp:+14155238886  (número sandbox de Twilio)
    WHATSAPP_GROUP_ID         # ej: whatsapp:+51999999999  (número del destinatario/grupo)
    IMAGE_HOST_URL            # URL pública donde se aloja la imagen (ver README)
"""

import os
import sys
import argparse
import mimetypes
import logging
from pathlib import Path
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# ---------------------------------------------------------------------------
# Configuración de logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE_MB = 5


# ---------------------------------------------------------------------------
# Funciones auxiliares
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """Carga y valida las variables de entorno desde .env."""
    load_dotenv()

    required = [
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_WHATSAPP_FROM",
        "WHATSAPP_GROUP_ID",
        "IMAGE_HOST_URL",
    ]

    config = {}
    missing = []

    for key in required:
        value = os.getenv(key)
        if not value:
            missing.append(key)
        else:
            config[key] = value

    if missing:
        logger.error("Faltan variables de entorno: %s", ", ".join(missing))
        logger.error("Copiá .env.example a .env y completá los valores.")
        sys.exit(1)

    return config


def validate_image(image_path: Path) -> None:
    """
    Valida que el archivo exista, sea un formato soportado
    y no supere el tamaño máximo permitido por WhatsApp.
    """
    if not image_path.exists():
        logger.error("Archivo no encontrado: %s", image_path)
        sys.exit(1)

    if image_path.suffix.lower() not in SUPPORTED_FORMATS:
        logger.error(
            "Formato no soportado: %s. Usá uno de: %s",
            image_path.suffix,
            ", ".join(SUPPORTED_FORMATS),
        )
        sys.exit(1)

    size_mb = image_path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        logger.error(
            "La imagen pesa %.1f MB. El límite es %d MB.", size_mb, MAX_FILE_SIZE_MB
        )
        sys.exit(1)

    logger.info("✔ Imagen válida: %s (%.1f MB)", image_path.name, size_mb)


def build_public_url(image_path: Path, host_url: str) -> str:
    """
    Construye la URL pública de la imagen.

    Twilio necesita una URL pública para enviar la imagen a WhatsApp.
    En desarrollo podés usar ngrok para exponer una carpeta local.
    En producción subí la imagen a S3, Cloudinary, etc.

    Ejemplo con ngrok:
        ngrok http --configuration=ngrok.yml 8080
        → IMAGE_HOST_URL=https://xxxx.ngrok.io/images
    """
    host_url = host_url.rstrip("/")
    return f"{host_url}/{image_path.name}"


def send_whatsapp_image(
    config: dict,
    image_url: str,
    caption: str | None = None,
) -> str:
    """
    Envía la imagen al grupo de WhatsApp vía Twilio.

    Args:
        config:    Diccionario con credenciales y números.
        image_url: URL pública de la imagen.
        caption:   Texto opcional que acompaña la imagen.

    Returns:
        SID del mensaje enviado.
    """
    client = Client(config["TWILIO_ACCOUNT_SID"], config["TWILIO_AUTH_TOKEN"])

    params = {
        "from_": config["TWILIO_WHATSAPP_FROM"],
        "to": config["WHATSAPP_GROUP_ID"],
        "media_url": [image_url],
    }

    if caption:
        params["body"] = caption

    logger.info("Enviando imagen a %s ...", config["WHATSAPP_GROUP_ID"])
    logger.info("URL de la imagen: %s", image_url)

    try:
        message = client.messages.create(**params)
        logger.info("✔ Mensaje enviado! SID: %s | Estado: %s", message.sid, message.status)
        return message.sid

    except TwilioRestException as e:
        logger.error("Error de Twilio (código %s): %s", e.code, e.msg)
        logger.error("Documentación: %s", e.uri)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agente Python que envía una imagen a WhatsApp vía Twilio.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--image",
        required=True,
        type=Path,
        help="Ruta local de la imagen (ej: foto.jpg)",
    )
    parser.add_argument(
        "--caption",
        type=str,
        default=None,
        help="Texto opcional que acompaña la imagen",
    )
    return parser.parse_args()


def main():
    logger.info("=== WhatsApp Image Agent ===")

    args = parse_args()
    config = load_config()

    # 1. Validar imagen
    validate_image(args.image)

    # 2. Construir URL pública
    image_url = build_public_url(args.image, config["IMAGE_HOST_URL"])

    # 3. Enviar a WhatsApp
    send_whatsapp_image(config, image_url, caption=args.caption)

    logger.info("=== Proceso finalizado ===")


if __name__ == "__main__":
    main()

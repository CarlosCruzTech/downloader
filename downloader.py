import logging
import os
import shutil
import subprocess
import sys
from logging.handlers import RotatingFileHandler

BASE = os.path.dirname(os.path.abspath(__file__))
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

handler = RotatingFileHandler(
    os.path.join(BASE, "downloader.log"),
    maxBytes=500_000,
    backupCount=2,
    encoding="utf-8",
)
handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[handler])

ALTURAS = {"Melhor": None, "1080p": 1080, "720p": 720, "480p": 480}


class LogYtdlp:
    """Impede o yt-dlp de escrever no console (que não existe com pythonw)."""
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): logging.warning(msg)
    def error(self, msg): logging.error(msg)


def atualizar_ytdlp():
    """Atualiza o yt-dlp sem abrir janela. Retorna True se deu certo."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp[default]"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=120,
        )
        return r.returncode == 0
    except Exception:
        logging.exception("Falha ao atualizar o yt-dlp")
        return False


def verificar_dependencias():
    avisos = []
    if shutil.which("deno") is None:
        avisos.append("Deno não encontrado (winget install DenoLand.Deno)")
    if shutil.which("ffmpeg") is None:
        avisos.append("FFmpeg não encontrado: qualidade limitada e sem MP3 (winget install Gyan.FFmpeg)")
    return avisos


def normalizar_url(url):
    url = url.strip()
    if url.startswith("tps://"):
        url = url.replace("tps://", "https://")
    elif url and not url.startswith("http"):
        url = "https://" + url
    return url


def baixar(url, pasta, qualidade, so_audio, ao_progresso):
    # Import tardio: garante usar a versão recém atualizada do yt-dlp
    import yt_dlp

    tem_ffmpeg = shutil.which("ffmpeg") is not None

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                ao_progresso(d["downloaded_bytes"] / total * 100)
        elif d["status"] == "finished":
            ao_progresso(100)

    opcoes = {
        "outtmpl": os.path.join(pasta, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": LogYtdlp(),
        "progress_hooks": [hook],
    }

    cookies = os.path.join(BASE, "cookies.txt")
    if os.path.isfile(cookies):
        opcoes["cookiefile"] = cookies

    if so_audio:
        if not tem_ffmpeg:
            raise RuntimeError("Para baixar só o áudio em MP3 é preciso instalar o FFmpeg.")
        opcoes["format"] = "ba/b"
        opcoes["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    elif tem_ffmpeg:
        altura = ALTURAS.get(qualidade)
        if altura:
            opcoes["format"] = f"bv*[height<={altura}]+ba/b[height<={altura}]/bv*+ba/b"
        else:
            opcoes["format"] = "bv*+ba/b"
        opcoes["format_sort"] = ["vcodec:h264", "res", "acodec:aac"]
        opcoes["merge_output_format"] = "mp4"
    else:
        opcoes["format"] = "b/best"

    logging.info("Iniciando download: %s", url)
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        ydl.download([url])
    logging.info("Download concluído: %s", url)


def traduzir_erro(msg):
    m = msg.lower()
    if "failed to resolve" in m or "getaddrinfo" in m:
        return "O endereço do link não existe. Confira se o link foi copiado corretamente."
    if "incomplete youtube id" in m or "is not a valid url" in m:
        return "O link parece incompleto ou inválido."
    if "video unavailable" in m or "private video" in m:
        return "O vídeo está indisponível ou é privado."
    if "sign in to confirm" in m:
        return "O YouTube pediu login. Use um cookies.txt de uma conta logada."
    if "requested format is not available" in m:
        return "Formato indisponível. Atualize o yt-dlp e confira se o Deno está instalado."
    if "ffmpeg" in m:
        return "FFmpeg não encontrado. Instale com: winget install Gyan.FFmpeg"
    if "unable to download" in m or "timed out" in m:
        return "Falha de conexão. Verifique sua internet e tente de novo."
    if "unsupported url" in m:
        return "O link está incompleto ou não é de um vídeo compatível. Copie o link direto do vídeo."
    return "Não foi possível baixar este vídeo. Detalhes no arquivo downloader.log."
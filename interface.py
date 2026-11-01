import json
import logging
import os
import sys
import threading
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

import downloader

# Com pythonw não existe console; evita erro se algo tentar imprimir
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

BASE = os.path.dirname(os.path.abspath(__file__))
ARQ_CONFIG = os.path.join(BASE, "config.json")


def carregar_config():
    try:
        with open(ARQ_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_config():
    try:
        with open(ARQ_CONFIG, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        logging.exception("Não foi possível salvar a configuração")


config = carregar_config()

root = tk.Tk()
root.title("Downloader Estratégico")
root.geometry("460x360")
root.resizable(False, False)


def ui(funcao):
    """Toda alteração de tela vinda de thread passa por aqui."""
    root.after(0, funcao)


def selecionar_pasta():
    caminho = filedialog.askdirectory()
    if caminho:
        entrada_pasta.delete(0, tk.END)
        entrada_pasta.insert(0, caminho)


def abrir_pasta():
    pasta = entrada_pasta.get().strip()
    if os.path.isdir(pasta):
        os.startfile(pasta)


def iniciar_download():
    url = downloader.normalizar_url(entrada_url.get())
    pasta = entrada_pasta.get().strip()

    if not url or not pasta:
        messagebox.showwarning("Atenção", "Preencha o link e a pasta de destino.")
        return
    if not os.path.isdir(pasta):
        messagebox.showwarning("Atenção", "A pasta de destino não existe.")
        return

    config["pasta"] = pasta
    salvar_config()

    botao_baixar.config(state=tk.DISABLED)
    barra.config(value=0)
    label_status.config(text="Status: Baixando...")

    qualidade = combo_qualidade.get()
    so_audio = var_audio.get()

    def tarefa():
        try:
            downloader.baixar(
                url, pasta, qualidade, so_audio,
                lambda p: ui(lambda: barra.config(value=p)),
            )
            ui(lambda: label_status.config(text="Status: Concluído com sucesso!"))
        except Exception as e:
            msg = downloader.traduzir_erro(str(e))
            logging.exception("Erro no download")
            ui(lambda: label_status.config(text="Status: Erro no download (veja downloader.log)"))
            ui(lambda: messagebox.showerror("Erro", msg))
        finally:
            ui(lambda: botao_baixar.config(state=tk.NORMAL))

    threading.Thread(target=tarefa, daemon=True).start()


def preparar_em_segundo_plano():
    hoje = date.today().isoformat()
    if config.get("ultima_atualizacao") != hoje:
        ui(lambda: label_status.config(text="Status: Verificando atualizações do yt-dlp..."))
        if downloader.atualizar_ytdlp():
            config["ultima_atualizacao"] = hoje
            salvar_config()

    avisos = downloader.verificar_dependencias()

    def liberar():
        label_status.config(text="Status: Pronto")
        label_avisos.config(text="\n".join(avisos))
        botao_baixar.config(state=tk.NORMAL)

    ui(liberar)


# Layout
tk.Label(root, text="URL do Vídeo:").pack(pady=(15, 0))
entrada_url = tk.Entry(root, width=55)
entrada_url.pack(pady=5)

tk.Label(root, text="Pasta de Destino:").pack()
frame_pasta = tk.Frame(root)
frame_pasta.pack(pady=5)
entrada_pasta = tk.Entry(frame_pasta, width=38)
entrada_pasta.insert(0, config.get("pasta", os.path.join(os.path.expanduser("~"), "Downloads")))
entrada_pasta.pack(side=tk.LEFT, padx=(0, 5))
tk.Button(frame_pasta, text="Procurar", command=selecionar_pasta).pack(side=tk.LEFT, padx=(0, 5))
tk.Button(frame_pasta, text="Abrir", command=abrir_pasta).pack(side=tk.LEFT)

frame_opcoes = tk.Frame(root)
frame_opcoes.pack(pady=8)
tk.Label(frame_opcoes, text="Qualidade:").pack(side=tk.LEFT)
combo_qualidade = ttk.Combobox(
    frame_opcoes, values=list(downloader.ALTURAS), state="readonly", width=8
)
combo_qualidade.set("Melhor")
combo_qualidade.pack(side=tk.LEFT, padx=(5, 15))
var_audio = tk.BooleanVar(value=False)
tk.Checkbutton(frame_opcoes, text="Só áudio (MP3)", variable=var_audio).pack(side=tk.LEFT)

botao_baixar = tk.Button(
    root, text="Iniciar Download", command=iniciar_download,
    bg="black", fg="white", state=tk.DISABLED,
)
botao_baixar.pack(pady=10)

barra = ttk.Progressbar(root, length=380, maximum=100)
barra.pack(pady=5)

label_status = tk.Label(root, text="Status: Iniciando...", fg="gray")
label_status.pack()
label_avisos = tk.Label(root, text="", fg="#b00020", wraplength=420, justify="left")
label_avisos.pack(pady=5)

threading.Thread(target=preparar_em_segundo_plano, daemon=True).start()
root.mainloop()
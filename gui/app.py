import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
from core.youtube import download_mp3, download_mp4, DEFAULT_DOWNLOAD_DIR


def run_app():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("Converterw")
    app.geometry("520x480")
    app.resizable(False, False)

    def browse_folder():
        path = filedialog.askdirectory()
        if path:
            out_entry.delete(0, "end")
            out_entry.insert(0, path)

    def set_buttons(state):
        mp3_btn.configure(state=state)
        mp4_btn.configure(state=state)

    def show_progress():
        progress_bar.set(0)
        progress_bar.pack(pady=10)
        info_label.pack()

    def hide_progress():
        progress_bar.pack_forget()
        info_label.pack_forget()

    def update_progress(data):
        def _update():
            progress_bar.set(data["percent"])
            info_label.configure(
                text=f"{int(data['percent']*100)}% | {data['size']} | {data['speed']} | ETA {data['eta']}"
            )
        app.after(0, _update)

    def start_download(func, label):
        url = url_entry.get().strip()
        out = out_entry.get().strip()

        if not url:
            messagebox.showwarning("Missing URL", "Please enter a YouTube URL.")
            return

        def task():
            try:
                app.after(0, lambda: set_buttons("disabled"))
                app.after(0, lambda: status.configure(text=label))
                app.after(0, show_progress)

                func(url, out, progress_callback=update_progress)

                app.after(0, lambda: status.configure(text="Done! File saved."))
            except Exception as e:
                # capture e now so the lambda doesn't close over a changed variable
                app.after(0, lambda err=str(e): messagebox.showerror("Error", err))
                app.after(0, lambda: status.configure(text=""))
            finally:
                app.after(0, lambda: set_buttons("normal"))
                app.after(0, hide_progress)

        threading.Thread(target=task, daemon=True).start()

    # ===== UI =====
    ctk.CTkLabel(app, text="YouTube URL", font=ctk.CTkFont(size=14)).pack(pady=(20, 5))
    url_entry = ctk.CTkEntry(app, width=450)
    url_entry.pack()

    ctk.CTkLabel(app, text="Output Folder", font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
    out_entry = ctk.CTkEntry(app, width=450)
    out_entry.pack()
    out_entry.insert(0, DEFAULT_DOWNLOAD_DIR)

    ctk.CTkButton(app, text="Browse", command=browse_folder).pack(pady=8)

    mp3_btn = ctk.CTkButton(
        app,
        text="Download MP3",
        width=200,
        command=lambda: start_download(download_mp3, "Downloading MP3..."),
    )
    mp3_btn.pack(pady=(10, 5))

    mp4_btn = ctk.CTkButton(
        app,
        text="Download MP4",
        width=200,
        command=lambda: start_download(download_mp4, "Downloading MP4..."),
    )
    mp4_btn.pack(pady=5)

    progress_bar = ctk.CTkProgressBar(app)
    progress_bar.set(0)

    info_label = ctk.CTkLabel(app, text="", font=ctk.CTkFont(size=12))

    status = ctk.CTkLabel(app, text="", font=ctk.CTkFont(size=12))
    status.pack(pady=10)

    app.mainloop()

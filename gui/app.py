import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
from core.youtube import download_mp3, download_mp4, DEFAULT_DOWNLOAD_DIR

def run_app():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("YouTube Converter")
    app.geometry("520x420")
    app.resizable(False, False)

    # ===== Functions =====
    def browse_folder():
        path = filedialog.askdirectory()
        if path:
            out_entry.delete(0, "end")
            out_entry.insert(0, path)

    def set_buttons_state(state):
        mp3_button.configure(state=state)
        mp4_button.configure(state=state)

    def start_progress():
        progress_bar.start()
        progress_bar.pack(pady=10)

    def stop_progress():
        progress_bar.stop()
        progress_bar.pack_forget()

    def download_mp3_click():
        def task():
            try:
                set_buttons_state("disabled")
                status_label.configure(text="Downloading MP3...")
                app.after(0, start_progress)

                download_mp3(url_entry.get(), out_entry.get())

                status_label.configure(text="MP3 download finished")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                status_label.configure(text="")
            finally:
                app.after(0, stop_progress)
                set_buttons_state("normal")

        threading.Thread(target=task, daemon=True).start()

    def download_mp4_click():
        def task():
            try:
                set_buttons_state("disabled")
                status_label.configure(text="Downloading MP4...")
                app.after(0, start_progress)

                download_mp4(url_entry.get(), out_entry.get())

                status_label.configure(text="MP4 download finished")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                status_label.configure(text="")
            finally:
                app.after(0, stop_progress)
                set_buttons_state("normal")

        threading.Thread(target=task, daemon=True).start()

    # ===== UI =====
    ctk.CTkLabel(app, text="YouTube URL", font=ctk.CTkFont(size=14)).pack(pady=(20, 5))
    url_entry = ctk.CTkEntry(app, width=450)
    url_entry.pack()

    ctk.CTkLabel(app, text="Output Folder", font=ctk.CTkFont(size=14)).pack(pady=(15, 5))
    out_entry = ctk.CTkEntry(app, width=450)
    out_entry.pack()
    out_entry.insert(0, DEFAULT_DOWNLOAD_DIR)  # Pre-fill with default Downloads path

    ctk.CTkButton(app, text="Browse", command=browse_folder).pack(pady=8)

    mp3_button = ctk.CTkButton(app, text="Download MP3", command=download_mp3_click, width=200)
    mp3_button.pack(pady=(10, 5))

    mp4_button = ctk.CTkButton(app, text="Download MP4", command=download_mp4_click, width=200)
    mp4_button.pack(pady=5)

    progress_bar = ctk.CTkProgressBar(app, mode="indeterminate")
    progress_bar.set(0)

    status_label = ctk.CTkLabel(app, text="", font=ctk.CTkFont(size=12))
    status_label.pack(pady=10)

    app.mainloop()
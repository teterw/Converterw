import customtkinter as ctk
from tkinter import filedialog, messagebox
from core.youtube import download_mp3, download_mp4

def run_app():
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")

    app = ctk.CTk()
    app.title("YouTube Converter")
    app.geometry("500x300")

    def browse_folder():
        path = filedialog.askdirectory()
        if path:
            out_entry.delete(0, "end")
            out_entry.insert(0, path)

    def download_mp3_click():
        try:
            download_mp3(url_entry.get(), out_entry.get())
            status_label.configure(text="MP3 download finished")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def download_mp4_click():
        try:
            download_mp4(url_entry.get(), out_entry.get())
            status_label.configure(text="MP4 download finished")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    ctk.CTkLabel(app, text="YouTube URL").pack(pady=(10, 0))
    url_entry = ctk.CTkEntry(app, width=400)
    url_entry.pack()

    ctk.CTkLabel(app, text="Output Folder").pack(pady=(10, 0))
    out_entry = ctk.CTkEntry(app, width=400)
    out_entry.pack()

    ctk.CTkButton(app, text="Browse", command=browse_folder).pack(pady=5)

    ctk.CTkButton(app, text="Download MP3", command=download_mp3_click).pack(pady=5)
    ctk.CTkButton(app, text="Download MP4", command=download_mp4_click).pack(pady=5)

    status_label = ctk.CTkLabel(app, text="")
    status_label.pack(pady=10)

    app.mainloop()

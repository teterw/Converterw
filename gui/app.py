import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import customtkinter as ctk  # noqa: E402
from tkinter import filedialog, messagebox  # noqa: E402

from core import config, engine  # noqa: E402
from core.version import APP_NAME, __version__  # noqa: E402
from core.youtube import (  # noqa: E402
    AUDIO_BITRATES,
    AUDIO_FORMATS,
    COOKIE_BROWSERS,
    VIDEO_CONTAINERS,
    VIDEO_QUALITY_LABELS,
    Cancelled,
    Downloader,
    format_duration,
    probe,
)

PAD = 12
MIN_WIDTH = 720


class ConverterwApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.settings = config.load()
        self.downloader = None
        self.download_thread = None
        self.pending_engine_version = None

        ctk.set_appearance_mode(self.settings["appearance"])
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} {__version__}")

        self._build_widgets()
        self._load_settings_into_widgets()
        self._measure_tabs()
        self._resize_tabs()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(300, self._start_engine_check)

    # ----------------------------------------------------------------- layout

    def _build_widgets(self):
        self.grid_columnconfigure(0, weight=1)

        self._build_engine_banner()
        self._build_url_row()
        self._build_output_row()
        self._build_tabs()
        self._build_actions()
        self._build_log()

    def _build_engine_banner(self):
        banner = ctk.CTkFrame(self)
        banner.pack(fill="x", padx=PAD, pady=(PAD, 0))
        banner.grid_columnconfigure(0, weight=1)

        self.engine_label = ctk.CTkLabel(
            banner, text="Checking downloader engine...", anchor="w",
            font=ctk.CTkFont(size=12),
        )
        self.engine_label.grid(row=0, column=0, sticky="ew", padx=PAD, pady=8)

        self.engine_button = ctk.CTkButton(banner, text="", width=130, command=self._engine_action)
        self.engine_button.grid(row=0, column=1, padx=(0, PAD), pady=8)
        self.engine_button.grid_remove()

    def _build_url_row(self):
        ctk.CTkLabel(self, text="YouTube URL", anchor="w", font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(fill="x", padx=PAD, pady=(PAD, 4))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=PAD)
        row.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(row, placeholder_text="https://www.youtube.com/watch?v=...")
        self.url_entry.grid(row=0, column=0, sticky="ew")
        self.url_entry.bind("<Return>", lambda _event: self._start_download("video"))

        ctk.CTkButton(row, text="Paste", width=70, command=self._paste_url
                      ).grid(row=0, column=1, padx=(8, 0))
        self.info_button = ctk.CTkButton(row, text="Info", width=70, command=self._fetch_info)
        self.info_button.grid(row=0, column=2, padx=(8, 0))

        self.info_label = ctk.CTkLabel(
            self, text="", anchor="w", justify="left", text_color=("gray35", "gray65"),
            font=ctk.CTkFont(size=12),
        )
        self.info_label.pack(fill="x", padx=PAD, pady=(4, 0))

    def _build_output_row(self):
        ctk.CTkLabel(self, text="Save to", anchor="w", font=ctk.CTkFont(size=14, weight="bold")
                     ).pack(fill="x", padx=PAD, pady=(PAD, 4))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=PAD)
        row.grid_columnconfigure(0, weight=1)

        self.out_entry = ctk.CTkEntry(row)
        self.out_entry.grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(row, text="Browse", width=70, command=self._browse_folder
                      ).grid(row=0, column=1, padx=(8, 0))
        ctk.CTkButton(row, text="Open", width=70, command=self._open_folder
                      ).grid(row=0, column=2, padx=(8, 0))

    def _fit_window(self):
        """Size the window to exactly what the widgets need, so no dead space is
        left under the tabs.

        CustomTkinter defers part of its relayout, so the requested height right
        after a change can still be the old one. Each full update lets a bit more
        of that work run, so this converges instead of measuring once.
        """
        for _ in range(4):
            self.update()
            height = self.winfo_reqheight()
            width = max(self.winfo_width(), MIN_WIDTH)
            self.minsize(MIN_WIDTH, height)
            if abs(height - self.winfo_height()) <= 2 and width == self.winfo_width():
                break
            self.geometry(f"{width}x{height}")

    def _build_tabs(self):
        # No fixed height and no expand: the tabview asks for exactly as much
        # room as its tallest tab needs, and _fit_window sizes the window to it.
        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="x", padx=PAD, pady=(PAD, 0))
        self._tab_names = ("Video", "Audio", "Options", "Advanced")
        for name in self._tab_names:
            self.tabs.add(name)

        self._build_video_tab(self.tabs.tab("Video"))
        self._build_audio_tab(self.tabs.tab("Audio"))
        self._build_options_tab(self.tabs.tab("Options"))
        self._build_advanced_tab(self.tabs.tab("Advanced"))

        # Otherwise every tab is padded out to the height of the tallest one.
        self.tabs.configure(command=self._resize_tabs)

    def _measure_tabs(self):
        """Record how tall each tab's content is, once, while it is on screen.

        All four tabs share one grid cell, so after a tall tab has been shown the
        short ones start reporting its height too - measuring on the fly would
        keep the window stuck at the tallest tab's size.
        """
        active = self.tabs.get()
        self._tab_heights = {}
        for name in self._tab_names:
            self.tabs.set(name)
            self.update()
            self._tab_heights[name] = self.tabs.tab(name).winfo_reqheight()
        self.tabs.set(active)
        self.update()

    def _resize_tabs(self, *_):
        """Shrink the tab area to whatever the visible tab actually needs."""
        self.tabs.configure(height=self._tab_heights[self.tabs.get()] + PAD)
        self._fit_window()

    @staticmethod
    def _dropdown(parent, row, label, values, variable, hint=None):
        parent.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(parent, text=label, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, PAD), pady=6
        )
        menu = ctk.CTkOptionMenu(parent, values=values, variable=variable, width=200)
        menu.grid(row=row, column=1, sticky="w", pady=6)
        if hint:
            ctk.CTkLabel(parent, text=hint, anchor="w", text_color=("gray40", "gray60"),
                         font=ctk.CTkFont(size=11)).grid(row=row, column=2, sticky="w", padx=PAD)
        return menu

    def _build_video_tab(self, tab):
        self.quality_var = ctk.StringVar()
        self.container_var = ctk.StringVar()
        self._dropdown(tab, 0, "Quality", VIDEO_QUALITY_LABELS, self.quality_var,
                       "Falls back to the next best if unavailable")
        self._dropdown(tab, 1, "Container", VIDEO_CONTAINERS, self.container_var,
                       "mp4 is the most compatible")

    def _build_audio_tab(self, tab):
        self.audio_format_var = ctk.StringVar()
        self.audio_bitrate_var = ctk.StringVar()
        self._dropdown(tab, 0, "Format", AUDIO_FORMATS, self.audio_format_var,
                       "flac and wav are lossless")
        self._dropdown(tab, 1, "Bitrate", AUDIO_BITRATES, self.audio_bitrate_var,
                       "Ignored for flac and wav")

    def _build_options_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)

        self.embed_thumbnail_var = ctk.BooleanVar()
        self.embed_metadata_var = ctk.BooleanVar()
        self.embed_subtitles_var = ctk.BooleanVar()
        self.remove_sponsors_var = ctk.BooleanVar()
        self.download_playlist_var = ctk.BooleanVar()
        self.playlist_subfolder_var = ctk.BooleanVar()
        self.skip_existing_var = ctk.BooleanVar()
        self.subtitle_languages_var = ctk.StringVar()
        self.playlist_items_var = ctk.StringVar()

        checks = [
            ("Embed cover art / thumbnail", self.embed_thumbnail_var),
            ("Embed title, artist and chapters", self.embed_metadata_var),
            ("Embed subtitles (video only)", self.embed_subtitles_var),
            ("Remove sponsor segments (SponsorBlock)", self.remove_sponsors_var),
            ("Download whole playlist when the URL has one", self.download_playlist_var),
            ("Put playlists in their own folder", self.playlist_subfolder_var),
            ("Skip videos already downloaded to this folder", self.skip_existing_var),
        ]
        for row, (text, variable) in enumerate(checks):
            ctk.CTkCheckBox(tab, text=text, variable=variable).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=4
            )

        row = len(checks)
        ctk.CTkLabel(tab, text="Subtitle languages", anchor="w").grid(
            row=row, column=0, sticky="w", pady=6
        )
        ctk.CTkEntry(tab, textvariable=self.subtitle_languages_var, width=160,
                     placeholder_text="en,es").grid(row=row, column=1, sticky="w", pady=6)

        ctk.CTkLabel(tab, text="Playlist items", anchor="w").grid(
            row=row + 1, column=0, sticky="w", pady=6
        )
        ctk.CTkEntry(tab, textvariable=self.playlist_items_var, width=160,
                     placeholder_text="e.g. 1-5,8").grid(row=row + 1, column=1, sticky="w", pady=6)

    def _build_advanced_tab(self, tab):
        tab.grid_columnconfigure(1, weight=1)

        self.cookies_var = ctk.StringVar()
        self.fragments_var = ctk.StringVar()
        self.appearance_var = ctk.StringVar()
        self.auto_update_var = ctk.BooleanVar()

        self._dropdown(tab, 0, "Cookies from browser", COOKIE_BROWSERS, self.cookies_var,
                       "Helps with age-restricted or members-only videos")
        self._dropdown(tab, 1, "Parallel fragments", ["1", "2", "4", "8", "16"],
                       self.fragments_var, "Higher is faster, but heavier on the network")
        self._dropdown(tab, 2, "Appearance", ["System", "Light", "Dark"], self.appearance_var,
                       None).configure(command=self._change_appearance)

        ctk.CTkCheckBox(tab, text="Automatically keep the downloader engine up to date",
                        variable=self.auto_update_var).grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(12, 4)
        )

        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=4, column=0, columnspan=3, sticky="w", pady=8)
        ctk.CTkButton(buttons, text="Update engine now", width=150,
                      command=lambda: self._update_engine(force=True)).pack(side="left")
        ctk.CTkButton(buttons, text="Reset engine", width=110, fg_color="gray40",
                      hover_color="gray30", command=self._reset_engine).pack(side="left", padx=8)
        ctk.CTkButton(buttons, text="Open data folder", width=140, fg_color="gray40",
                      hover_color="gray30", command=self._open_data_folder).pack(side="left")

        ctk.CTkLabel(
            tab,
            text=f"{APP_NAME} {__version__}   -   github.com/teterw/Converterw",
            anchor="w", text_color=("gray40", "gray60"), font=ctk.CTkFont(size=11),
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(12, 0))

    def _build_actions(self):
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=PAD, pady=(PAD, 0))
        actions.grid_columnconfigure((0, 1), weight=1)

        self.video_button = ctk.CTkButton(
            actions, text="Download Video", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._start_download("video"),
        )
        self.video_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.audio_button = ctk.CTkButton(
            actions, text="Download Audio", height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._start_download("audio"),
        )
        self.audio_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.cancel_button = ctk.CTkButton(
            actions, text="Cancel", height=40, fg_color="#b3261e", hover_color="#8c1d18",
            font=ctk.CTkFont(size=14, weight="bold"), command=self._cancel_download,
        )

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=(8, 0))

    def _build_log(self):
        self.log_toggle = ctk.CTkButton(
            self, text="Show log", width=100, height=24, fg_color="transparent",
            text_color=("gray30", "gray70"), hover_color=("gray85", "gray25"),
            command=self._toggle_log,
        )
        self.log_toggle.pack(pady=(4, 0))

        self.log_box = ctk.CTkTextbox(self, height=140, font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.configure(state="disabled")

    # --------------------------------------------------------------- settings

    def _load_settings_into_widgets(self):
        s = self.settings
        self.out_entry.insert(0, s["output_dir"])
        self.quality_var.set(s["quality"])
        self.container_var.set(s["container"])
        self.audio_format_var.set(s["audio_format"])
        self.audio_bitrate_var.set(s["audio_bitrate"])
        self.embed_thumbnail_var.set(s["embed_thumbnail"])
        self.embed_metadata_var.set(s["embed_metadata"])
        self.embed_subtitles_var.set(s["embed_subtitles"])
        self.remove_sponsors_var.set(s["remove_sponsors"])
        self.download_playlist_var.set(s["download_playlist"])
        self.playlist_subfolder_var.set(s["playlist_subfolder"])
        self.skip_existing_var.set(s["skip_existing"])
        self.subtitle_languages_var.set(s["subtitle_languages"])
        self.playlist_items_var.set(s["playlist_items"])
        self.cookies_var.set(s["cookies_browser"])
        self.fragments_var.set(str(s["concurrent_fragments"]))
        self.appearance_var.set(s["appearance"])
        self.auto_update_var.set(s["auto_update_engine"])
        if s["show_log"]:
            self._toggle_log()

    def _collect_settings(self):
        try:
            fragments = int(self.fragments_var.get())
        except ValueError:
            fragments = 4
        return {
            "output_dir": self.out_entry.get().strip(),
            "quality": self.quality_var.get(),
            "container": self.container_var.get(),
            "audio_format": self.audio_format_var.get(),
            "audio_bitrate": self.audio_bitrate_var.get(),
            "embed_thumbnail": self.embed_thumbnail_var.get(),
            "embed_metadata": self.embed_metadata_var.get(),
            "embed_subtitles": self.embed_subtitles_var.get(),
            "remove_sponsors": self.remove_sponsors_var.get(),
            "download_playlist": self.download_playlist_var.get(),
            "playlist_subfolder": self.playlist_subfolder_var.get(),
            "skip_existing": self.skip_existing_var.get(),
            "subtitle_languages": self.subtitle_languages_var.get(),
            "playlist_items": self.playlist_items_var.get(),
            "cookies_browser": self.cookies_var.get(),
            "concurrent_fragments": fragments,
            "appearance": self.appearance_var.get(),
            "auto_update_engine": self.auto_update_var.get(),
            "show_log": self.log_box.winfo_ismapped(),
            "mode": self.settings.get("mode", "video"),
        }

    # ---------------------------------------------------------------- helpers

    def _log(self, message):
        def append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message.rstrip() + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, append)

    def _toggle_log(self):
        if self.log_box.winfo_ismapped():
            self.log_box.pack_forget()
            self.log_toggle.configure(text="Show log")
        else:
            self.log_box.pack(fill="both", expand=True, padx=PAD, pady=(4, PAD))
            self.log_toggle.configure(text="Hide log")
        self._fit_window()

    def _change_appearance(self, value):
        ctk.set_appearance_mode(value)

    def _paste_url(self):
        try:
            text = self.clipboard_get().strip()
        except Exception:
            return
        if text:
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text)

    def _browse_folder(self):
        path = filedialog.askdirectory(initialdir=self.out_entry.get().strip() or None)
        if path:
            self.out_entry.delete(0, "end")
            self.out_entry.insert(0, path)

    def _open_folder(self):
        self._open_path(self.out_entry.get().strip())

    def _open_data_folder(self):
        from core.paths import app_data_dir

        self._open_path(str(app_data_dir()))

    def _open_path(self, path):
        if not path or not os.path.isdir(path):
            messagebox.showwarning("Folder not found", f"{path or 'No folder'} does not exist yet.")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            else:
                import subprocess

                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", path])
        except OSError as error:
            messagebox.showerror("Could not open folder", str(error))

    # ------------------------------------------------------------ video info

    def _fetch_info(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a YouTube link first.")
            return

        self.info_button.configure(state="disabled")
        self.info_label.configure(text="Loading video details...")

        def task():
            try:
                info = probe(url)
            except Exception as error:
                message = str(error).splitlines()[0] if str(error) else "Could not read that URL"
                self.after(0, lambda: self.info_label.configure(text=message))
            else:
                if info["is_playlist"]:
                    text = (f"Playlist: {info['title']}  -  {info['count']} videos  -  "
                            f"{format_duration(info['duration'])} total")
                else:
                    text = (f"{info['title']}  -  {info['uploader']}  -  "
                            f"{format_duration(info['duration'])}")
                self.after(0, lambda: self.info_label.configure(text=text))
            finally:
                self.after(0, lambda: self.info_button.configure(state="normal"))

        threading.Thread(target=task, daemon=True).start()

    # -------------------------------------------------------------- download

    def _set_busy(self, busy):
        if busy:
            self.video_button.grid_remove()
            self.audio_button.grid_remove()
            self.cancel_button.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.progress_bar.set(0)
            self.progress_bar.pack(fill="x", padx=PAD, pady=(8, 0), before=self.status_label)
        else:
            self.cancel_button.grid_remove()
            self.video_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            self.audio_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))
            self.progress_bar.pack_forget()
        # The progress bar appearing changes how tall the window needs to be.
        self._fit_window()

    def _update_progress(self, data):
        def apply():
            self.progress_bar.set(data["percent"])
            if data["status"] == "processing":
                self.status_label.configure(text=f"Converting {data['filename']}...")
            else:
                self.status_label.configure(
                    text=f"{int(data['percent'] * 100)}%  -  {data['size']}  -  "
                         f"{data['speed']}  -  ETA {data['eta']}"
                )

        self.after(0, apply)

    def _start_download(self, mode):
        if self.download_thread and self.download_thread.is_alive():
            return

        url = self.url_entry.get().strip()
        out_dir = self.out_entry.get().strip()
        if not url:
            messagebox.showwarning("Missing URL", "Paste a YouTube link first.")
            return
        if not out_dir:
            messagebox.showwarning("Missing folder", "Choose a folder to save into.")
            return

        self.settings = self._collect_settings()
        self.settings["mode"] = mode
        config.save(self.settings)

        options = config.to_options(self.settings)
        options.mode = mode

        self.downloader = Downloader(
            progress_callback=self._update_progress, log_callback=self._log
        )

        self._set_busy(True)
        self.status_label.configure(text="Starting...")
        self._log(f"--- {mode} download: {url}")

        def task():
            try:
                result = self.downloader.run(url, out_dir, options)
            except Cancelled:
                self.after(0, lambda: self.status_label.configure(text="Cancelled."))
                self._log("--- cancelled")
            except Exception as error:
                message = str(error)
                self._log(f"--- failed: {message.splitlines()[0] if message else 'unknown error'}")
                self.after(0, lambda: messagebox.showerror("Download failed", message))
                self.after(0, lambda: self.status_label.configure(text="Failed."))
            else:
                self.after(0, lambda: self._finish(result))
            finally:
                self.after(0, lambda: self._set_busy(False))

        self.download_thread = threading.Thread(target=task, daemon=True)
        self.download_thread.start()

    def _finish(self, result):
        count = result["completed"]
        errors = result["errors"]
        noun = "file" if count == 1 else "files"
        if errors:
            self.status_label.configure(text=f"Done - {count} {noun}, {len(errors)} skipped.")
            self._log(f"--- finished with {len(errors)} error(s); see above")
        else:
            self.status_label.configure(text=f"Done - {count} {noun} saved.")
            self._log("--- finished")

    def _cancel_download(self):
        if self.downloader:
            self.downloader.cancel()
            self.status_label.configure(text="Cancelling...")

    # ---------------------------------------------------------------- engine

    def _set_engine_banner(self, text, button_text=None):
        self.engine_label.configure(text=text)
        if button_text:
            self.engine_button.configure(text=button_text)
            self.engine_button.grid()
        else:
            self.engine_button.grid_remove()

    def _start_engine_check(self):
        current = engine.current_version() or "unknown"
        self._set_engine_banner(f"Downloader engine: yt-dlp {current}")

        def task():
            latest, available = engine.update_available(timeout=8)
            if latest is None:
                self.after(0, lambda: self._set_engine_banner(
                    f"Downloader engine: yt-dlp {current}  (offline - could not check for updates)"
                ))
                return
            if not available:
                self.after(0, lambda: self._set_engine_banner(
                    f"Downloader engine: yt-dlp {current}  (up to date)"
                ))
                return
            if self.auto_update_var.get():
                self._update_engine(version=latest)
            else:
                self.after(0, lambda: self._set_engine_banner(
                    f"yt-dlp {latest} is available - updating fixes most download errors",
                    "Update",
                ))

        threading.Thread(target=task, daemon=True).start()

    def _engine_action(self):
        if self.pending_engine_version:
            self._restart()
        else:
            self._update_engine(force=True)

    def _update_engine(self, version=None, force=False):
        if self.pending_engine_version:
            self._restart()
            return

        self.after(0, lambda: self._set_engine_banner("Downloading yt-dlp update..."))

        def task():
            try:
                staged = engine.download_update(version=version)
            except Exception as error:
                message = str(error)
                self.after(0, lambda: self._set_engine_banner(
                    f"Engine update failed: {message[:80]}", "Retry"
                ))
                if force:
                    self.after(0, lambda: messagebox.showerror("Engine update failed", message))
                return

            self.pending_engine_version = staged
            self.after(0, lambda: self._set_engine_banner(
                f"yt-dlp {staged} downloaded - restart to start using it", "Restart now"
            ))

        threading.Thread(target=task, daemon=True).start()

    def _reset_engine(self):
        if not messagebox.askyesno(
            "Reset engine",
            "Remove the downloaded yt-dlp and go back to the version bundled with "
            f"{APP_NAME}?\n\nYou can update again at any time.",
        ):
            return
        engine.reset()
        self.pending_engine_version = "bundled"
        self._set_engine_banner(
            f"Engine reset to the version bundled with {APP_NAME} - restart to apply",
            "Restart now",
        )

    def _restart(self):
        config.save(self._collect_settings())
        engine.restart_app()
        self.destroy()

    # ----------------------------------------------------------------- close

    def _on_close(self):
        if self.download_thread and self.download_thread.is_alive():
            if not messagebox.askyesno("Quit", "A download is still running. Stop it and quit?"):
                return
            if self.downloader:
                self.downloader.cancel()
        config.save(self._collect_settings())
        self.destroy()


def run_app():
    ConverterwApp().mainloop()

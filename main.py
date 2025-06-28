import os
import sqlite3
import subprocess
from tkinter import Tk, Frame, Label, Scrollbar, Canvas, Entry, Button
from PIL import Image, ImageTk
from collections import OrderedDict
import io

class ThumbnailCache:
    def __init__(self, max_size):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, video_file):
        if video_file in self.cache:
            img = self.cache.pop(video_file)
            self.cache[video_file] = img
            return img
        else:
            img = self.create_thumbnail(video_file)
            if img:
                self.cache[video_file] = img
                if len(self.cache) > self.max_size:
                    self.cache.popitem(last=False)
            return img

    def create_thumbnail(self, video_file):
        try:
            command = [
                "ffmpeg", "-i", video_file, "-ss", "00:00:01.000", 
                "-vframes", "1", "-f", "image2pipe", "-vcodec", "png", "pipe:1"
            ]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                print(f"Error generating thumbnail: {stderr.decode()}")
                return None
            
            img = Image.open(io.BytesIO(stdout))
            img.thumbnail((160, 90))
            return ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Error creating thumbnail for {video_file}: {e}")
            return None

class ThumbnailGallery:
    def __init__(self, master, max_cache_size=5, columns=5):
        self.master = master
        self.master.title("Video Thumbnail Gallery")
        
        self.cache = ThumbnailCache(max_cache_size)
        self.columns = columns
        self.video_files = []
        self.current_page = 0
        self.videos_per_page = 25
        
        self.frame = Frame(self.master)
        self.frame.pack(fill="both", expand=True)

        self.search_entry = Entry(self.frame)
        self.search_entry.pack(side="left", padx=5, pady=5)
        self.search_entry.bind("<Return>", self.search_videos)

        self.search_button = Button(self.frame, text="Search", command=self.search_videos)
        self.search_button.pack(side="left", padx=5, pady=5)

        self.canvas = Canvas(self.frame)
        self.scroll_y = Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="n")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll_y.pack(side="right", fill="y")

        self.load_videos()
        self.display_videos()

        self.page_frame = Frame(self.master)
        self.page_frame.pack(side="bottom", pady=5)

        self.page_buttons = []
        self.create_page_buttons()

    def load_videos(self):
        self.conn = sqlite3.connect('videos.db')
        cursor = self.conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS video_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL
            )
        ''')

        if cursor.execute('SELECT COUNT(*) FROM video_files').fetchone()[0] == 0:
            video_files = []
            for root, dirs, files in os.walk("./"):
                for file in files:
                    if file.endswith(('.mp4', '.avi', '.mov', '.mkv')):
                        video_files.append(os.path.join(root, file))
            
            for video_file in video_files:
                cursor.execute('INSERT INTO video_files (path) VALUES (?)', (video_file,))
            self.conn.commit()

        self.video_files = cursor.execute('SELECT path FROM video_files').fetchall()
        self.conn.close()

    def display_videos(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        start_index = self.current_page * self.videos_per_page
        end_index = start_index + self.videos_per_page
        video_subset = self.video_files[start_index:end_index]

        for i, (video_file,) in enumerate(video_subset):
            thumbnail = self.cache.get(video_file)
            row = i // self.columns
            column = i % self.columns
            
            frame = Frame(self.scrollable_frame, bd=2, relief="groove", width=170, height=100)
            frame.grid(row=row, column=column, padx=5, pady=5)

            label = Label(frame, image=thumbnail, width=160, height=90)
            label.image = thumbnail
            label.pack(expand=True)
            
            label.bind("<Button-3>", lambda e, vf=video_file: self.show_video_details(vf))
            label.bind("<Button-1>", lambda e, vf=video_file: self.open_video(vf))

    def create_page_buttons(self):
        for button in self.page_buttons:
            button.destroy()
        self.page_buttons.clear()

        num_pages = (len(self.video_files) + self.videos_per_page - 1) // self.videos_per_page
        for i in range(num_pages):
            button = Button(self.page_frame, text=str(i + 1), command=lambda page=i: self.change_page(page))
            button.pack(side="left", padx=2)
            self.page_buttons.append(button)
    
    def change_page(self, page):
        self.current_page = page
        self.display_videos()

    def search_videos(self, event=None):
        search_query = self.search_entry.get().lower()
        self.conn = sqlite3.connect('videos.db')
        cursor = self.conn.cursor()

        self.video_files = cursor.execute(
            'SELECT path FROM video_files WHERE path LIKE ?',
            (f'%{search_query}%',)
        ).fetchall()

        self.conn.close()
        self.current_page = 0
        self.create_page_buttons()
        self.display_videos()

    def show_video_details(self, video_file):
        details_window = Tk()
        details_window.title("Video Details")
        Label(details_window, text=f"Details for: {video_file}").pack()
        details_window.mainloop()

    def open_video(self, video_file):
        subprocess.Popen(["/usr/bin/vlc", video_file])  # Open video in VLC

if __name__ == "__main__":
    root = Tk()
    gallery = ThumbnailGallery(root)
    root.geometry("1000x800")
    root.mainloop()

"""Compact Tk interface for the shared ellipse simulation."""

import time
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk

if __package__:
    from .ellipse_demo import (DEFAULT_ECCENTRICITY, DEFAULT_MAX_BALLS, MAX_BALLS,
                              MAX_LAUNCH_AMOUNT, RasterRenderer, Simulation)
    from .ellipse_sound import SoundPlayer
else:
    from ellipse_demo import (DEFAULT_ECCENTRICITY, DEFAULT_MAX_BALLS, MAX_BALLS,
                             MAX_LAUNCH_AMOUNT, RasterRenderer, Simulation)
    from ellipse_sound import SoundPlayer


class EllipseApp:
    def __init__(self, root):
        self.root = root
        self.running = False
        self.simulation = Simulation()
        self.sounds = SoundPlayer()
        self.renderer = RasterRenderer()
        self.frame_photo = None
        self.row_cache = {}
        self.last_tick = time.perf_counter()
        self.last_status_update = 0.0
        self.geometry_pending = False
        self.scale_track_presses = set()
        self.eccentricity = tk.DoubleVar(value=DEFAULT_ECCENTRICITY)
        self.count = tk.StringVar(value='1')
        self.last_start_count = 1
        self.max_count = tk.StringVar(value=str(DEFAULT_MAX_BALLS))
        self.amount_slider = tk.DoubleVar(value=1)
        self.limit_slider = tk.DoubleVar(value=DEFAULT_MAX_BALLS)
        self.synchronizing_counts = False
        self.speed = tk.DoubleVar(value=1.0)
        self.duplicate_balls = tk.BooleanVar(value=True)
        self.sound_muted = tk.BooleanVar(value=not self.sounds.available)
        self.sounds.set_enabled(True)
        bg, foreground, muted = '#101820', '#edf5fc', '#a6b8c9'
        root.title('Ellipse focus simulation')
        width = max(780, min(1920, root.winfo_screenwidth()-80))
        height = max(620, min(1080, root.winfo_screenheight()-100))
        root.geometry(f'{width}x{height}')
        root.minsize(780, 620)
        root.configure(background=bg)
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('TFrame', background=bg)
        style.configure('TLabel', background=bg, foreground=foreground, font=('Segoe UI', 10))
        style.configure('Muted.TLabel', foreground=muted)
        style.configure('Hint.TLabel', foreground=muted, font=('Segoe UI', 9))
        style.configure('Title.TLabel', font=('Segoe UI', 20, 'bold'))
        style.configure('Tagline.TLabel', foreground='#ffda89', font=('Segoe UI', 14, 'italic'))
        style.configure('TButton', font=('Segoe UI', 10, 'normal'), padding=(24, 12))
        style.configure('TCheckbutton', background=bg, foreground=foreground, font=('Segoe UI', 10))
        style.map('TCheckbutton', background=[('active', bg)])
        style.configure('Settings.TLabelframe', background=bg, bordercolor='#2a3944')
        style.configure('Settings.TLabelframe.Label', background=bg, foreground=muted,
                        font=('Segoe UI', 10, 'bold'))
        self.configure_sliders(style)
        outer = ttk.Frame(root, padding=22)
        outer.pack(fill='both', expand=True)
        title = ttk.Label(outer, text='Ellipse focus simulation',
                          style='Title.TLabel', justify='left', wraplength=900)
        title.pack(anchor='w', fill='x')
        title.bind('<Configure>', lambda event: title.configure(wraplength=event.width))
        ttk.Label(outer, text='- Every Direction. One destination',
                  style='Tagline.TLabel').pack(anchor='w', pady=(3, 7))
        ttk.Label(outer, text='Launch a group of balls, or click the ellipse to shoot one.',
                  style='Muted.TLabel').pack(anchor='w', pady=(4, 12))
        self.canvas = tk.Canvas(outer, background=self.renderer.background_color,
                                highlightthickness=0, height=370)
        self.canvas.pack(fill='both', expand=True)
        self.frame_item = self.canvas.create_image(0, 0, anchor='nw')
        self.canvas.bind('<Configure>', lambda event: self.draw_scene())
        self.canvas.bind('<Button-1>', self.shoot)
        self.status = ttk.Label(outer, text='')
        self.status.pack(anchor='w', pady=(6, 7))
        self.settings = ttk.Frame(outer)
        self.settings.pack(fill='x', pady=(0, 5))
        self.settings_columns = None
        self.setting_panels = [ttk.LabelFrame(self.settings, text=title, padding=(10, 8),
                                               style='Settings.TLabelframe')
                               for title in ('Playback', 'Balls', 'Shape')]
        playback, balls, shape = self.setting_panels

        def row(parent):
            frame = ttk.Frame(parent)
            frame.pack(fill='x', pady=3)
            return frame

        toolbar = row(playback)
        playback_buttons = ttk.Frame(toolbar)
        playback_buttons.pack(anchor='center')
        self.pause_button = ttk.Button(playback_buttons, text='Run', width=10, command=self.toggle)
        self.pause_button.pack(side='left', padx=(0, 10))
        ttk.Button(playback_buttons, text='Clear', width=10, command=self.clear).pack(side='left')
        speed_row = row(playback)
        speed_label = ttk.Label(speed_row)
        speed_label.pack(side='left', padx=(0, 6))
        self.speed_scale = ttk.Scale(speed_row, from_=0.25, to=4.0, variable=self.speed, length=150,
                                     style='Visible.Horizontal.TScale', command=self.change_speed)
        self.speed_scale.pack(side='left', fill='x', expand=True)
        self.configure_scale_steps(self.speed_scale, 0.25)
        ttk.Checkbutton(row(playback), text='Mute sound', variable=self.sound_muted,
                        command=lambda: self.sounds.set_enabled(not self.sound_muted.get()),
                        state='normal' if self.sounds.available else 'disabled').pack(side='left')

        ttk.Button(row(balls), text='Launch', width=10, command=self.launch).pack(anchor='center')
        ball_sliders = row(balls)
        ball_sliders.columnconfigure(1, weight=1)
        start_label = ttk.Label(ball_sliders)
        start_label.grid(row=0, column=0, sticky='w', padx=(0, 6), pady=3)
        self.amount_scale = ttk.Scale(ball_sliders, from_=1, to=MAX_LAUNCH_AMOUNT,
                                       variable=self.amount_slider, length=140,
                                       style='Visible.Horizontal.TScale', command=self.change_amount)
        self.amount_scale.grid(row=0, column=1, sticky='ew', pady=3)
        self.limit_label = ttk.Label(ball_sliders)
        self.limit_label.grid(row=1, column=0, sticky='w', padx=(0, 6), pady=3)
        self.limit_scale = ttk.Scale(ball_sliders, from_=1, to=MAX_BALLS,
                                      variable=self.limit_slider, length=140,
                                      style='Visible.Horizontal.TScale', command=self.change_limit)
        self.limit_scale.grid(row=1, column=1, sticky='ew', pady=3)
        ttk.Checkbutton(row(balls), text='Duplicate each pass',
                        variable=self.duplicate_balls, command=self.update_status).pack(side='left')

        shape_row = row(shape)
        eccentricity_label = ttk.Label(shape_row)
        eccentricity_label.pack(side='left', padx=(0, 6))
        self.eccentricity_scale = ttk.Scale(shape_row, from_=0.01, to=0.99,
                                            variable=self.eccentricity, length=140,
                                            style='Visible.Horizontal.TScale', command=self.change_geometry)
        self.eccentricity_scale.pack(side='left', fill='x', expand=True)
        self.configure_scale_steps(self.eccentricity_scale, 0.01)
        ttk.Label(row(shape), text='Changing shape clears the scene',
                  style='Muted.TLabel').pack(side='left')

        self.control_labels = [eccentricity_label, start_label, speed_label]
        self.settings.bind('<Configure>', self.layout_settings)
        self.layout_settings()
        ttk.Label(outer, text='Click: add a ball    Space: launch    R: run / pause    C: clear    Escape: close',
                  style='Muted.TLabel').pack(anchor='w', pady=(1, 0))
        self.install_shortcuts()
        root.bind('<Escape>', lambda event: self.close())
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.update_labels()
        self.update_status()
        root.after(16, self.tick)

    def configure_sliders(self, style):
        """Keep native slider behavior with a clear, generously sized thumb."""
        self.slider_images = []
        for fill, outline in (('#ffce66', '#fff0bd'), ('#ffe29a', '#fff7df'),
                              ('#ffb83f', '#fff0bd')):
            image = Image.new('RGBA', (56, 52))
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((2, 2, 53, 49), radius=10, fill=fill,
                                   outline=outline, width=3)
            draw.line((28, 15, 28, 36), fill='#6a4b1b', width=3)
            image = image.resize((28, 26), Image.Resampling.LANCZOS)
            self.slider_images.append(ImageTk.PhotoImage(image, master=self.root))
        normal, hover, pressed = self.slider_images
        style.element_create('Visible.Scale.slider', 'image', normal,
                             ('pressed', pressed), ('active', hover), border=0)
        style.layout('Visible.Horizontal.TScale', [
            ('Horizontal.Scale.trough', {'sticky': 'we', 'children': [
                ('Visible.Scale.slider', {'side': 'left', 'sticky': ''})
            ]})
        ])
        style.configure('Visible.Horizontal.TScale', troughcolor='#243746',
                        bordercolor='#486276', lightcolor='#243746', darkcolor='#243746')

    def configure_scale_steps(self, scale, step):
        # Use explicit steps for track clicks and native behavior for handle drags.
        scale.bind('<Button-1>', lambda event: self.scale_press(event, scale, step))
        scale.bind('<B1-Motion>', lambda event: 'break' if scale in self.scale_track_presses else None)
        scale.bind('<ButtonRelease-1>', lambda event: self.scale_release(scale))
        for key, direction in (('<Left>', -1), ('<Down>', -1), ('<Right>', 1), ('<Up>', 1)):
            scale.bind(key, lambda event, direction=direction: self.step_scale(scale, direction*step))

    def step_scale(self, scale, delta):
        lower, upper = float(scale.cget('from')), float(scale.cget('to'))
        scale.set(round(max(lower, min(upper, scale.get()+delta)), 2))
        return 'break'

    def scale_press(self, event, scale, step):
        self.scale_track_presses.discard(scale)
        element = scale.identify(event.x, event.y)
        if element.endswith('slider'):
            return  # Preserve the native handle drag.
        if element.endswith(('trough', 'track')):
            self.scale_track_presses.add(scale)
            scale.focus_set()
            direction = -1 if scale.get(event.x, event.y) < scale.get() else 1
            return self.step_scale(scale, direction*step)

    def scale_release(self, scale):
        if scale in self.scale_track_presses:
            self.scale_track_presses.discard(scale)
            return 'break'

    def layout_settings(self, event=None):
        width = event.width if event is not None else self.settings.winfo_width()
        minimum = max(panel.winfo_reqwidth() for panel in self.setting_panels)+10
        columns = 3 if width >= minimum*3 else 2 if width >= minimum*2 else 1
        if columns == self.settings_columns:
            return
        self.settings_columns = columns
        for column in range(3):
            self.settings.columnconfigure(column, weight=1 if column < columns else 0,
                                           uniform='settings' if column < columns else '')
        for index, panel in enumerate(self.setting_panels):
            span = columns if index == len(self.setting_panels)-1 and index % columns == 0 else 1
            panel.grid(row=index//columns, column=index % columns, sticky='nsew',
                       columnspan=span,
                       padx=(0, 10 if index % columns+span < columns else 0), pady=(0, 8))

    def update_labels(self):
        self.control_labels[0].configure(text=f'Eccentricity: {self.eccentricity.get():.2f}')
        self.control_labels[1].configure(text=f'Amount: {self.last_start_count:,}')
        self.limit_label.configure(text=f'Max: {self.simulation.limit:,}')
        self.control_labels[2].configure(text=f'Speed: {self.speed.get():.2f}×')

    def finish_count_edit(self, _=None):
        value = self.count.get().strip()
        if value.isascii() and value.isdigit() and len(value) <= 3 and 1 <= int(value) <= MAX_LAUNCH_AMOUNT:
            self.last_start_count = int(value)
        else:
            self.count.set(str(self.last_start_count))
        self.sync_count_sliders()

    def sync_count_sliders(self):
        self.synchronizing_counts = True
        try:
            self.amount_slider.set(self.last_start_count)
            self.limit_slider.set(self.simulation.limit)
        finally:
            self.synchronizing_counts = False
        self.update_labels()

    def change_amount(self, value):
        if self.synchronizing_counts:
            return
        self.last_start_count = max(1, min(MAX_LAUNCH_AMOUNT, round(float(value))))
        self.count.set(str(self.last_start_count))
        self.sync_count_sliders()

    def change_limit(self, value):
        if self.synchronizing_counts:
            return
        self.max_count.set(str(max(1, min(MAX_BALLS, round(float(value))))))
        self.finish_limit_edit()

    def finish_limit_edit(self, _=None):
        value = self.max_count.get().strip()
        if value.isascii() and value.isdigit() and len(value) <= 5 and 1 <= int(value) <= MAX_BALLS:
            self.simulation.set_limit(int(value))
        else:
            self.max_count.set(str(self.simulation.limit))
        self.sync_count_sliders()
        self.update_status()

    def change_geometry(self, _=None):
        self.eccentricity.set(round(max(0.01, min(0.99, self.eccentricity.get())), 2))
        if not self.geometry_pending:
            self.geometry_pending = True
            self.root.after_idle(self.clear)

    def change_speed(self, _=None):
        self.speed.set(max(0.25, min(4.0, round(self.speed.get()/0.25)*0.25)))
        self.update_labels()
        self.update_status()

    def sync_rows(self):
        rows = []
        for batch in self.simulation.batches:
            key = id(batch)
            cached = self.row_cache.get(key)
            if cached is None or cached[0] != batch.revision:
                batch_rows = [self.renderer.prepare_ray(ray, color)
                              for ray, color in zip(batch.rays, batch.colors)]
                cached = (batch.revision, batch_rows)
                self.row_cache[key] = cached
            rows.extend(cached[1])
        self.renderer.rows = rows

    def begin(self):
        if not self.running:
            self.last_tick = time.perf_counter()
        self.running = True
        self.canvas.focus_set()
        if self.renderer.background is not None:
            self.sync_rows()
            self.draw_particles()
        self.update_status()

    def launch(self):
        self.finish_limit_edit()
        self.finish_count_edit()
        if self.simulation.launch(self.last_start_count):
            self.sounds.emit(focus=len(self.simulation.batches[-1].rays))
            self.begin()
        else:
            self.show_limit()

    def shoot(self, event):
        if self.renderer.background is None:
            return
        self.finish_limit_edit()
        target = self.renderer.world_point(event.x, event.y)
        if self.simulation.shoot(target):
            self.sounds.emit(focus=1)
            self.begin()
        elif self.simulation.count >= self.simulation.limit:
            self.show_limit()

    def show_limit(self):
        self.update_status()

    def clear(self, _=None):
        self.geometry_pending = False
        self.running = False
        self.simulation = Simulation(self.eccentricity.get(), limit=self.simulation.limit)
        self.row_cache.clear()
        self.last_tick = time.perf_counter()
        self.update_labels()
        self.draw_scene()
        self.update_status()

    def draw_scene(self):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        if w < 10 or h < 10:
            return
        self.renderer.prepare([], [], w, h, self.eccentricity.get())
        self.row_cache.clear()
        self.sync_rows()
        self.draw_particles()

    def draw_particles(self):
        if self.renderer.background is None:
            return
        batches = self.simulation.batches
        if len(batches) == 1:
            batch = batches[0]
            frame = self.renderer.render(batch.distance, batch.arrival_hold)
        else:
            frame = self.renderer.render(0, states=self.simulation.states())
        if self.frame_photo is None or (self.frame_photo.width(), self.frame_photo.height()) != frame.size:
            self.frame_photo = ImageTk.PhotoImage(frame, master=self.canvas)
            self.canvas.itemconfigure(self.frame_item, image=self.frame_photo)
        else:
            self.frame_photo.paste(frame)

    def update_status(self):
        self.last_status_update = time.perf_counter()
        count = self.simulation.count
        state = ('Running' if self.running else 'Paused') if count else 'Ready'
        duplicate = 'On' if self.duplicate_balls.get() else 'Off'
        text = (f'{state} · {count:,} / {self.simulation.limit:,} balls · '
                f'Speed {self.speed.get():.2f}× · Duplicate: {duplicate}')
        if count >= self.simulation.limit:
            text += ' · Limit reached'
        self.status.configure(text=text)
        self.pause_button.configure(text=('Pause' if self.running else 'Resume') if count else 'Run')

    def install_shortcuts(self):
        tag = 'EllipseSimulationShortcuts'
        for key, action in (('<space>', self.launch), ('<r>', self.toggle), ('<R>', self.toggle),
                            ('<c>', self.clear), ('<C>', self.clear)):
            self.root.bind_class(tag, key, lambda event, action=action: self.handle_shortcut(event, action))
        widgets = [self.root]
        while widgets:
            widget = widgets.pop()
            widget.bindtags((tag,)+tuple(widget.bindtags()))
            widgets.extend(widget.winfo_children())

    def handle_shortcut(self, event, action):
        if event.widget.winfo_class() in ('TSpinbox', 'Spinbox', 'TEntry', 'Entry', 'Text', 'TCombobox'):
            return
        action()
        return 'break'

    def toggle(self):
        if not self.simulation.count:
            self.launch()
            return
        self.running = not self.running
        self.last_tick = time.perf_counter()
        self.update_status()

    def close(self):
        self.sounds.close()
        self.root.destroy()

    def tick(self):
        now = time.perf_counter()
        dt, self.last_tick = min(now-self.last_tick, 0.25), now
        if self.running:
            if self.simulation.advance(dt, self.speed.get(), self.duplicate_balls.get(),
                                       collect_events=self.sounds.enabled):
                self.sync_rows()
            wall_hits, focus_launches = self.simulation.last_events
            self.sounds.emit(wall=wall_hits, focus=focus_launches)
            self.draw_particles()
            if now-self.last_status_update >= 0.12:
                self.update_status()
        spent_ms = (time.perf_counter()-now)*1000
        self.root.after(max(1, round(1000/60-spent_ms)), self.tick)


def run_demo():
    root = tk.Tk()
    EllipseApp(root)
    root.mainloop()

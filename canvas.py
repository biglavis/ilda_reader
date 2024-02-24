import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import threading
import time
from time import perf_counter_ns
import glob
import ilda

SERIAL_TIMEOUT = 1

def wait_us(delay):
    target = perf_counter_ns() + delay * 1000
    while perf_counter_ns() < target:
        pass

class Canvas(tk.Frame):

    def __init__(self, master, ser = None, size = 600, speed = 30):
        super().__init__(master)
        self.grid(row=0, column=0, sticky="EW")
        self.columnconfigure(0, weight=1)

        self.ser = ser

        self.size = size
        self.scale = 1

        self.speed = speed
        self.max_speed = 1000

        self.frame_count = 0
        self.point_count = 0
        self.start = 0

        self.files = [[],[]]

        self.data = None

        #-------------------------------------------------- menu --------------------------------------------------#
        self.menu = tk.Frame(self)
        self.menu.grid(row=0, column=0, pady=4, sticky='EW')
        self.menu.columnconfigure(0, weight=8)
        self.menu.columnconfigure(3, minsize=100)
        self.menu.columnconfigure(4, weight=1)
        self.menu.columnconfigure(6, minsize=40)
        self.menu.columnconfigure(7, weight=1)

        # file menu
        self.file_cbox = ttk.Combobox(self.menu, state='readonly', postcommand=self.get_files)
        self.file_cbox.grid(row=0, column=0, padx=4, sticky='EW')

        self.file_cbox.bind('<<ComboboxSelected>>', lambda _: self.open_file(self.file_cbox.get()))

        # browse
        self.browse_button = tk.Button(self.menu, text='Browse', command=self.browse_files)
        self.browse_button.grid(row=0, column=1)

        # close
        self.close_button = tk.Button(self.menu, text=' X ', command=self.close_file)
        self.close_button.grid(row=0, column=2)

        # speed
        self.speed_label = tk.Label(self.menu, text='Speed')
        self.speed_label.grid(row=0, column=3, sticky="E")

        self.speed_entry = tk.Entry(self.menu, width=5)
        self.speed_entry.grid(row=0, column=5, padx=4)

        self.speed_entry.bind('<Return>', self.update_speed)

        self.speed_scale = ttk.Scale(self.menu, orient='horizontal', from_=1, to=self.max_speed, length=50, command=self.set_speed)
        self.speed_scale.set(self.speed)
        self.speed_scale.grid(row=0, column=4, sticky='EW')

        # scale
        self.scale_label = tk.Label(self.menu, text='Scale')
        self.scale_label.grid(row=0, column=6, sticky="E")

        self.scale_entry = tk.Entry(self.menu, width=5)
        self.scale_entry.grid(row=0, column=8, padx=4)

        self.scale_entry.bind('<Return>', self.update_scale)

        self.scale_scale = ttk.Scale(self.menu, orient='horizontal', from_=1, to=100, length=50, command=self.set_scale)
        self.scale_scale.set(self.scale * 100)
        self.scale_scale.grid(row=0, column=7, sticky='EW')

        #-------------------------------------------------- canvas --------------------------------------------------#
        self.canvas = tk.Canvas(self, height=self.size, width=self.size, borderwidth=0, highlightthickness=0, background='black')
        self.canvas.grid(row=1, column=0)

        #-------------------------------------------------- counters --------------------------------------------------#
        self.misc = tk.Frame(self, width=self.size, height=21)
        self.misc.grid(row=2, column=0)
        self.misc.columnconfigure(0, minsize=130)
        self.misc.columnconfigure(2, weight=1)
        self.misc.grid_propagate(0)

        self.frame_counter = tk.Label(self.misc, text="Frame: -- / --")
        self.frame_counter.grid(row=0, column=0, padx=(4,0),sticky="W")

        self.fps_pps_counter = tk.Label(self.misc, text="-- / --")
        self.fps_pps_counter.grid(row=0, column=1, sticky="W")

        #-------------------------------------------------- options --------------------------------------------------#
        self.enable_print_label = tk.Label(self.misc, text="Print Response")
        self.enable_print_label.grid(row=0, column=2, sticky="E")

        self.enable_print_value = tk.BooleanVar(value=True)
        self.enable_print_button = tk.Checkbutton(self.misc, borderwidth=0, highlightthickness=0, state='disabled', var=self.enable_print_value, command=self.enable_print)
        self.enable_print_button.grid(row=0, column=3, sticky="E")

        self.preview_label = tk.Label(self.misc, text="Preview Only")
        self.preview_label.grid(row=0, column=4, sticky="E")

        self.preview_value = tk.BooleanVar(value=True)
        self.preview_button = tk.Checkbutton(self.misc, borderwidth=0, highlightthickness=0, state='disabled', var=self.preview_value, command=self.set_preview_only)
        self.preview_button.grid(row=0, column=5, sticky="E")

        #-------------------------------------------------- draw --------------------------------------------------#
        # flags
        self.new_data = False
        self.transmit = False

        # draw
        self.drawer = threading.Thread(target=self.wait)
        self.drawer.daemon = True
        self.drawer.start()

    def wait(self):
        while True:
            if self.data:
                self.new_data = False
                self.draw()

            else:
                time.sleep(0.1)

    def draw(self):
        for i, frame in enumerate(self.data):
            self.update_frame_counter(i + 1, len(self.data))

            # update fps/pps
            if (end := time.time()) - self.start > 1:
                threading.Thread(target=self.update_fps_pps_counter, args=(self.start, end)).start()
                self.start = time.time()

            # draw frame
            if frame:
                self.draw_frame(frame)
                self.clear()

            self.frame_count += 1

            # new data available
            if self.new_data:
                return
            
    def draw_frame(self, frame, px_size=3):
        prev_pos = None

        for pos in frame:
            if pos[2]:
                x = round((pos[0] * self.scale + 32768) / 65535 * self.size)
                y = round((32767 - pos[1] * self.scale) / 65535 * self.size)
                self.canvas.create_rectangle(x, y, x+px_size, y+px_size, fill='red', outline='red', state='disabled')

            # not transmitting
            if not self.transmit:
                wait_us(1000000/(self.speed*len(frame)))
                self.point_count += 1

            # transmitting - only send command if current position != previous position
            elif pos != prev_pos:
                norm_x = ((pos[0] + 32768) / 65535 * 2 - 1) * self.scale
                norm_y = ((pos[1] + 32768) / 65535 * 2 - 1) * self.scale

                if self.ser.laser != pos[2]:
                    if pos[2]:
                        self.ser.send(f'laser on\n')
                        self.ser.ready.wait(timeout=SERIAL_TIMEOUT)
                        self.ser.laser = True   
                    else:
                        self.ser.send(f'laser off\n')
                        self.ser.ready.wait(timeout=SERIAL_TIMEOUT)
                        self.ser.laser = False

                self.ser.send(f'move {norm_x} {norm_y}\n')
                self.ser.ready.wait(timeout=SERIAL_TIMEOUT)

                self.point_count += 1

            # new data available
            if self.new_data:
                break

            prev_pos = pos

    def clear(self):
        self.canvas.delete('all')

    #-------------------------------------------------- file methods --------------------------------------------------#
    def get_files(self):
        self.files[0] = glob.glob('*.ild')
        self.file_cbox['values'] = self.files[0] + self.files[1]

    def browse_files(self):
        file = filedialog.askopenfilename(filetypes=(('ILDA', '*.ild'), ('All Files', '*.*')))
        if file:
            if file not in self.files:
                self.files[1].append(file)
                self.file_cbox['values'] = self.files[0] + self.files[1]
                self.file_cbox.current(len(self.file_cbox['values']) - 1)
                self.open_file(file)

    def open_file(self, file):
        self.data = ilda.filter_frames(ilda.unpack_ilda(file, head = False))
        self.new_data = True

    def close_file(self):
        self.data = None
        self.new_data = True
        self.file_cbox.set('')

    #-------------------------------------------------- scale methods --------------------------------------------------#
    def update_scale(self, event):
        scale = int(self.scale_entry.get())
        if scale < 1:
            scale = 1
        elif scale > 100:
            scale = 100

        self.scale_scale.set(scale)
        self.set_scale(scale)

    def set_scale(self, value):
        scale = round(float(value))
        self.scale = scale / 100
        self.scale_entry.delete(0, 'end')
        self.scale_entry.insert(0, scale)

    #-------------------------------------------------- speed methods --------------------------------------------------#
    def update_speed(self, event):
        speed = int(self.speed_entry.get())

        if speed < 1:
            speed = 1
        elif speed > self.max_speed:
            speed = self.max_speed

        self.speed_scale.set(speed)
        self.set_speed(speed)

    def set_speed(self, value):
        self.speed = round(float(value))
        self.speed_entry.delete(0, 'end')
        self.speed_entry.insert(0, self.speed)

    def enable_speed(self):
        self.speed_scale.config(state='normal')
        self.speed_entry.config(state='normal')

    def disable_speed(self):
        self.speed_scale.config(state='disabled')
        self.speed_entry.config(state='disabled')

    #-------------------------------------------------- counter methods --------------------------------------------------#
    def update_frame_counter(self, current, total):
        self.frame_counter.config(text = f'Frame: {current} / {total}')

    def update_fps_pps_counter(self, start, end):
        fps = self.frame_count / (end - start)
        pps = self.point_count / (end - start)
        self.fps_pps_counter.config(text = f'{round(fps, 1)} / {round(pps,1)}')

        self.frame_count = 0
        self.point_count = 0

    #-------------------------------------------------- button methods --------------------------------------------------#
    def enable_print(self):
        if self.ser:
            if self.enable_print_value.get():
                self.ser.ready.wait()
                self.ser.enable_print = True
            else:
                self.ser.enable_print = False

    def set_preview_only(self):
        if self.preview_value.get():
            self.transmit = False
            self.enable_speed()

            self.enable_print_value.set(True)
            self.enable_print()

        else:
            self.enable_print_value.set(False)
            self.enable_print()

            self.transmit = True
            self.disable_speed()
    
    def enable_buttons(self, en: bool):
        if en:
            self.enable_print_button.config(state='normal')
            self.preview_button.config(state='normal')
        else:
            self.transmit = False
            self.preview_value.set(True)
            self.set_preview_only()
            self.enable_print_button.config(state='disabled')
            self.preview_button.config(state='disabled')

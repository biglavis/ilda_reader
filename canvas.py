import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import threading
import time
from time import perf_counter_ns
import math
import glob
import ilda

SERIAL_TIMEOUT = 1

def wait_us(delay):
    target = perf_counter_ns() + delay * 1000
    while perf_counter_ns() < target:
        time.sleep(0)

class Canvas(tk.Frame):

    def __init__(self, master, ser = None, size = 600):
        super().__init__(master)
        self.grid(row=0, column=0, sticky="EW")
        self.columnconfigure(0, weight=1)

        self.ser = ser

        self.size = size
        self.scale = 1

        self.speed = 0
        self.play_speed = 0

        self.fps = 0
        self.settled = False

        self.frame_count = 0
        self.point_count = 0
        self.start = 0

        self.files = [[],[]]

        self.data = None

        #-------------------------------------------------- menu --------------------------------------------------#
        self.menu = tk.Frame(self)
        self.menu.grid(row=0, column=0, pady=4, sticky='EW')
        self.menu.columnconfigure(0, weight=2)
        self.menu.columnconfigure(3, minsize=100)
        self.menu.columnconfigure(4, weight=1)
        self.menu.columnconfigure(6, minsize=40)
        self.menu.columnconfigure(7, weight=1)

        # file menu
        self.file_cbox = ttk.Combobox(self.menu, state='readonly', postcommand=self.get_files)
        self.file_cbox.grid(row=0, column=0, padx=4, sticky='EW')

        self.file_cbox.bind('<<ComboboxSelected>>', lambda _: self.open_file(self.file_cbox.get()))

        # browse button
        self.browse_button = tk.Button(self.menu, text='Browse', command=self.browse_files)
        self.browse_button.grid(row=0, column=1)

        # close button
        self.close_button = tk.Button(self.menu, text=' X ', command=self.close_file)
        self.close_button.grid(row=0, column=2)

        # speed slider/entry
        self.speed_label = tk.Label(self.menu, text='Speed')
        self.speed_label.grid(row=0, column=3, sticky="E")

        self.speed_entry = tk.Entry(self.menu, width=5)
        self.speed_entry.grid(row=0, column=5, padx=4)

        self.speed_entry.bind('<Return>', self.entry_set_speed)

        self.speed_slider = ttk.Scale(self.menu, orient='horizontal', from_=0, to=100, length=50, command=self.slider_set_speed)
        self.speed_slider.set(50)
        self.speed_slider.grid(row=0, column=4, sticky='EW')

        # scale slider/entry
        self.scale_label = tk.Label(self.menu, text='Scale')
        self.scale_label.grid(row=0, column=6, sticky="E")

        self.scale_entry = tk.Entry(self.menu, width=5)
        self.scale_entry.grid(row=0, column=8, padx=4)

        self.scale_entry.bind('<Return>', self.entry_set_scale)

        self.scale_slider = ttk.Scale(self.menu, orient='horizontal', from_=1, to=100, length=50, command=self.slider_set_scale)
        self.scale_slider.set(self.scale * 100)
        self.scale_slider.grid(row=0, column=7, sticky='EW')

        #-------------------------------------------------- canvas --------------------------------------------------#
        self.canvas = tk.Canvas(self, height=self.size, width=self.size, borderwidth=0, highlightthickness=0, background='black')
        self.canvas.grid(row=1, column=0)

        #-------------------------------------------------- counters --------------------------------------------------#
        self.misc = tk.Frame(self, width=self.size, height=21)
        self.misc.grid(row=2, column=0)
        self.misc.columnconfigure(0, minsize=130)
        self.misc.columnconfigure(2, weight=1)
        self.misc.grid_propagate(0)

        # frame counter
        self.frame_counter = tk.Label(self.misc, text="Frame: -- / --")
        self.frame_counter.grid(row=0, column=0, padx=(4,0),sticky="W")

        # fps/pps counter
        self.fps_pps_counter = tk.Label(self.misc, text="-- / --")
        self.fps_pps_counter.grid(row=0, column=1, sticky="W")

        #-------------------------------------------------- options --------------------------------------------------#
        # print response button
        self.enable_print_label = tk.Label(self.misc, text="Print Response")
        self.enable_print_label.grid(row=0, column=2, sticky="E")

        self.enable_print_value = tk.BooleanVar(value=True)
        self.enable_print_button = tk.Checkbutton(self.misc, borderwidth=0, highlightthickness=0, state='disabled', var=self.enable_print_value, command=self.set_print)
        self.enable_print_button.grid(row=0, column=3, sticky="E")

        # preview only button
        self.preview_label = tk.Label(self.misc, text="Preview Only")
        self.preview_label.grid(row=0, column=4, sticky="E")

        self.preview_value = tk.BooleanVar(value=True)
        self.preview_button = tk.Checkbutton(self.misc, borderwidth=0, highlightthickness=0, state='disabled', var=self.preview_value, command=self.set_preview_only)
        self.preview_button.grid(row=0, column=5, sticky="E")

        #-------------------------------------------------- draw --------------------------------------------------#
        # flags
        self.new_data = False
        self.transmit = False

        # start drawing
        self.drawer = threading.Thread(target=self.wait)
        self.drawer.daemon = True
        self.drawer.start()

    def wait(self):
        while True:
            if self.data:
                if self.new_data:
                    self.new_data = False
                    self.start = time.time()
                self.draw()

            else:
                time.sleep(0.1)

    def draw(self):
        """
        Draws ILDA data from `self.data`. 
        """
                
        while True:
            # get frame
            index, total, frame = next(self.data)

            # update frame counter
            self.update_frame_counter(index + 1, total)

            # update fps/pps
            if (end := time.time()) - self.start > 1:
                self.update_fps_pps_counter(self.start, end)
                self.start = time.time()

            # draw frame
            self.draw_frame(frame)
            self.clear()

            self.frame_count += 1

            # new data available
            if self.new_data:
                return
            
    def draw_frame(self, frame, px_size=3):
        """
        Draws frame on canvas. If `self.transmit` is true, writes frame to serial.
        """

        for point in frame:
            # draw point on canvas
            if point[2]:
                x = round((point[0] * self.scale + 32768) / 65535 * self.size)
                y = round((32767 - point[1] * self.scale) / 65535 * self.size)
                self.canvas.create_rectangle(x, y, x+px_size, y+px_size, fill='red', outline='red', state='disabled')

            # not transmitting - wait delay
            if not self.transmit:
                wait_us(1000000/(self.play_speed*len(frame)))
                self.point_count += 1

            # transmitting - write to serial
            else:
                norm_x = ((point[0] + 32768) / 65535 * 2 - 1) * self.scale
                norm_y = ((point[1] + 32768) / 65535 * 2 - 1) * self.scale

                if self.ser.laser != point[2]:
                    if point[2]:
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
                return

    #-------------------------------------------------- canvas methods --------------------------------------------------#
    def clear(self):
        """
        Clears the canvas.
        """

        self.canvas.delete('all')

    #-------------------------------------------------- file methods --------------------------------------------------#
    def get_files(self):
        """
        Gets ILDA files in the current directory and subdirectories.
        """

        self.files[0] = glob.glob('**/*.ild', recursive=True)
        self.file_cbox['values'] = self.files[0] + self.files[1]

    def browse_files(self):
        """
        Opens file explorer.
        """

        file = filedialog.askopenfilename(filetypes=(('ILDA', '*.ild'), ('All Files', '*.*')))
        if file:
            if file not in self.files:
                self.files[1].append(file)
                self.file_cbox['values'] = self.files[0] + self.files[1]
                self.file_cbox.current(len(self.file_cbox['values']) - 1)
                self.open_file(file)

    def open_file(self, file):
        """
        Opens `file` and returns a generator object to `self.data`. Resets speed and counters.
        """

        self.play_speed = self.speed
        self.settled = False

        self.frame_count = 0
        self.point_count = 0

        self.data = ilda.unpack_ilda(file, filter = True)
        self.new_data = True

    def close_file(self):
        """
        Sets `self.data` = `None`. Clears counters.
        """

        self.data = None
        self.new_data = True

        self.file_cbox.set('')
        self.frame_counter.config(text = "Frame: -- / --")
        self.fps_pps_counter.config(text = "-- / --")

    #-------------------------------------------------- speed methods --------------------------------------------------#
    def entry_set_speed(self, event):
        """
        Sets the speed.
        """

        value = int(self.speed_entry.get())

        if value < 1:
            value = 1
        elif value > 300:
            value = 300

        value = math.log((value + 2.49) / 3.49) / math.log(1.045632)

        self.speed_slider.set(value)

    def slider_set_speed(self, value = None):
        """
        Sets the speed.
        """

        speed = round(3.49 * pow(1.045632, float(value)) - 2.49)
        self.speed = speed
        self.play_speed = speed

        self.settled = False

        self.speed_entry.delete(0, 'end')
        self.speed_entry.insert(0, self.speed)

    def adjust_speed(self):
        """
        Tries to adjust speed to match requested fps within 5%
        """

        if self.fps < self.speed * 0.95 and self.play_speed < 1000:
            if self.fps < self.speed * 0.8:
                self.play_speed = self.play_speed * 1.5
            else:
                self.play_speed = self.play_speed * 1.1

        elif self.fps > self.speed * 1.05:
            if self.fps > self.speed * 1.2:
                self.play_speed = self.play_speed * 0.67
            else:
                self.play_speed = self.play_speed * 0.91

    def enable_speed(self):
        """
        Enables speed slider/entry.
        """

        self.speed_slider.config(state='normal')
        self.speed_entry.config(state='normal')

    def disable_speed(self):
        """
        Disables speed slider/entry.
        """
        
        self.speed_slider.config(state='disabled')
        self.speed_entry.config(state='disabled')

    #-------------------------------------------------- scale methods --------------------------------------------------#
    def entry_set_scale(self, event):
        """
        Updates scale slider/entry and sets the scale.
        """

        scale = int(self.scale_entry.get())
        if scale < 1:
            scale = 1
        elif scale > 100:
            scale = 100

        self.scale_slider.set(scale)

    def slider_set_scale(self, value):
        """
        Sets the scale.
        """

        scale = round(float(value))
        self.scale = scale / 100
        self.scale_entry.delete(0, 'end')
        self.scale_entry.insert(0, scale)

    #-------------------------------------------------- counter methods --------------------------------------------------#
    def update_frame_counter(self, current, total):
        """
        Updates frame counter.
        """

        self.frame_counter.config(text = f'Frame: {current} / {total}')

    def update_fps_pps_counter(self, start, end):
        """
        Updates fps/pps counters and adjusts speed.
        """

        self.fps = round(self.frame_count / (end - start), 1)
        pps = round(self.point_count / (end - start), 1)
        self.fps_pps_counter.config(text = f'{self.fps} / {pps}')

        if self.settled:
            self.adjust_speed()
        else:
            self.settled = True

        self.frame_count = 0
        self.point_count = 0

    #-------------------------------------------------- button methods --------------------------------------------------#
    def set_print(self):
        """
        Enable/disable serial to write to console.
        """

        if self.ser:
            if self.enable_print_value.get():
                self.ser.ready.wait()
                self.ser.enable_print = True
            else:
                self.ser.enable_print = False

    def set_preview_only(self):
        """
        Enable/disable preview only mode.
        """

        if self.preview_value.get():
            self.transmit = False
            self.enable_speed()

            self.enable_print_value.set(True)
            self.set_print()

        else:
            self.enable_print_value.set(False)
            self.set_print()

            self.transmit = True
            self.disable_speed()
    
    def enable_buttons(self):
        """
        Enables print/preview buttons.
        """

        self.enable_print_button.config(state='normal')
        self.preview_button.config(state='normal')

    def disable_buttons(self):
        """
        Disables print/preview buttons.
        """       

        self.transmit = False
        self.preview_value.set(True)
        self.set_preview_only()
        self.enable_print_button.config(state='disabled')
        self.preview_button.config(state='disabled')

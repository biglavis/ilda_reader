import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk
import threading
import canvas
import console

SERIAL_TIMEOUT = 1

class App(tk.Tk):
    def __init__(self, title, size = 600):
        super().__init__()

        self.title(title)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.canvas = canvas.Canvas(self, size=size)
        self.console = console.Console(self)
        self.ser = _serial(console=self.console, canvas=self.canvas)

        self.canvas.ser = self.ser
        self.console.ser = self.ser

        self.minsize(size, size + 55)

        # run
        self.mainloop()

class _serial(serial.Serial):
    def __init__(self, console, canvas, port = None, baudrate = None):
        super().__init__()

        self.port = port
        if baudrate:
            self.baudrate = baudrate

        self.console = console
        self.canvas = canvas

        self.serial_listener_thread = threading.Thread(target=self.serial_listener)
        self.serial_listener_thread.daemon = True
        self.serial_listener_thread.start()

        self.ready = threading.Event()
        self.ready.set()

        self.laser = None
        self.enable_print = True

    def serial_listener(self):
        """
        Checks if serial connection is active. Prints recieved data to console.
        """

        while True:
            # get available serial ports
            available_ports = [port.device for port in serial.tools.list_ports.comports()]

            # if serial is open
            if self.is_open:

                # close serial if port is unavailable
                if self.port not in available_ports:
                    self.close()
                    self.console.print(f'DISCONNECTED FROM {self.port}', 'error')
                    self.canvas.disable_buttons()
                    self.laser = None

                # read incoming data
                response = ''
                try:
                    if self.in_waiting:
                        if response := self.readline().decode('utf-8'):
                            self.ready.set()

                            # print recieved data if enabled
                            if self.enable_print:
                                if 'invalid' in response:
                                    self.console.print(response, 'error')
                                else:
                                    self.console.print(response, 'response')
                except:
                    pass
            
            # open serial if port is available
            elif self.port in available_ports:
                self.open()
                self.console.print(f'CONNECTED TO {self.port}', 'status')
                self.canvas.enable_buttons()

    def send(self, string: str):
        """
        Writes `string` ended by `'\\n'` to serial.
        """

        if self.is_open:
            self.ready.wait(timeout=SERIAL_TIMEOUT)
            
            if not string.endswith('\n'):
                string += '\n'
            
            try:
                self.write(string.encode('utf-8'))
                self.ready.clear()
            except:
                pass

if __name__ == '__main__':
    App('ILDA Reader')

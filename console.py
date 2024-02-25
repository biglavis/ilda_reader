import serial
import serial.tools.list_ports
import tkinter as tk
from tkinter import ttk

class Console(tk.Frame):
    def __init__(self, master, ser = None):
        super().__init__(master, width=600)
        self.grid(row=1, column=0, sticky='NSEW')
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        baudrates = [f'{rate} baud' for rate in [9600, 1000000]]

        self.ser = ser

        #-------------------------------------------------- command line --------------------------------------------------#
        self.command = tk.Frame(self, height=21)
        self.command.grid(row=0, column=0, columnspan=2, padx=4, pady=4, sticky='EW')
        self.command.columnconfigure(0, weight=8)
        self.command.columnconfigure(1, weight=1)
        self.command.columnconfigure(2, weight=1)
        self.command.grid_propagate(0)

        # command entry
        self.entry = tk.Entry(self.command)
        self.entry.grid(row=0, column=0, padx=2, sticky='EW')

        self.entry.bind('<Return>', self.send)

        # port menu
        self.port_cbox = ttk.Combobox(self.command, state='readonly', width=10, postcommand=self.get_ports)
        self.port_cbox.grid(row=0, column=1, padx=2, sticky='EW')

        self.port_cbox.bind('<<ComboboxSelected>>', self.set_port)

        # baudrate menu
        self.baudrate_cbox = ttk.Combobox(self.command, values=baudrates, width=10)
        self.baudrate_cbox.current(0)
        self.baudrate_cbox.grid(row=0, column=2, padx=2, sticky='EW')

        self.baudrate_cbox.bind('<<ComboboxSelected>>', self.set_baudrate)
        self.baudrate_cbox.bind('<Return>', self.set_baudrate)

        #-------------------------------------------------- console --------------------------------------------------#
        
        # scrollbar
        style = ttk.Style(master)
        style.layout(   'arrowless.Vertical.TScrollbar', 
                        [('Vertical.Scrollbar.trough', {'children': [('Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})], 'sticky': 'ns'})]    )

        self.scrollbar = ttk.Scrollbar(self, orient='vertical', style='arrowless.Vertical.TScrollbar')
        self.scrollbar.grid(row=1, column=1, sticky='NS')

        # console
        self.console = tk.Text(self, height=6, width=1, spacing1=2, spacing3=2, state='disabled', yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.console.yview)
        self.console.grid(row=1, column=0, sticky='NSEW')

        # console tags
        self.console.tag_config('status', foreground='green')
        self.console.tag_config('response', foreground='blue')
        self.console.tag_config('error', foreground='red')

    def get_ports(self):
        """
        Gets available serial ports.
        """

        ports = [f'{port.device}: {port.description.partition(" (COM")[0]}' for port in serial.tools.list_ports.comports()]
        self.port_cbox['values'] = ports

    def set_port(self, event):
        """
        Sets the serial port.
        """

        if self.ser:
            port = self.port_cbox.get().partition(':')[0]

            if port == self.ser.port:
                return

            if self.ser.is_open:
                self.ser.close()

            self.ser.port = port
            self.print(f'SET: {port}', 'status')

    def set_baudrate(self, event):
        """
        Sets the baudrate.
        """

        if self.ser:
            baudrate = int(self.baudrate_cbox.get().split(' ')[0])

            if baudrate == self.ser.baudrate:
                return
            
            self.ser.baudrate = baudrate
            self.print(f'SET: {baudrate} baud', 'status')

    def send(self, event):
        """
        Writes user command to console/serial.
        """
        
        command = self.entry.get().strip()
        self.entry.delete(0, 'end')

        if command:
            if command == 'clear':
                self.clear()
            else:
                self.print(f'> {command}')
                if self.ser:
                    self.ser.send(command)

    def print(self, string: str, tag=None):
        """
        Writes `string` to console.
        """

        if not string.endswith('\n'):
            string += '\n'

        self.console.configure(state='normal')
        self.console.insert('end', string, tag)
        self.console.configure(state='disabled')

        self.console.see('end')

    def clear(self):
        """
        Clears the console.
        """

        self.console.configure(state='normal')
        self.console.delete(1.0, 'end')
        self.console.configure(state='disabled')

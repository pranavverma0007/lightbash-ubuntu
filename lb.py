			import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import os
import sys
import re
import threading
import shlex

class BashEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LightBash IDE")
        self.geometry("1000x700")
        
        self.font_family = "Courier"
        self.font_size = 10
        self.tabs = {} 
        self.current_tab_id = None
        self.tab_counter = 0
        self.running_process = None

        self._build_ui()
        self._bind_shortcuts()
        self.bind_class("Text", "<<Paste>>", self._replace_on_paste)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_ui(self):
        self.toolbar = tk.Frame(self, bg="#333", pady=2)
        self.toolbar.pack(fill=tk.X, side=tk.TOP)
        
        tk.Button(self.toolbar, text="Open", command=self.open_file, relief=tk.FLAT, bg="#555", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="Save", command=self.save_file, relief=tk.FLAT, bg="#555", fg="white").pack(side=tk.LEFT, padx=2)
        tk.Button(self.toolbar, text="Run", command=self.run_script, relief=tk.FLAT, bg="#2e7d32", fg="white").pack(side=tk.LEFT, padx=2)

        self.main_paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=5, bg="#444")
        self.main_paned.pack(fill=tk.BOTH, expand=1)

        self.left_container = tk.Frame(self.main_paned, width=800)
        self.main_paned.add(self.left_container, stretch="always")
        
        self.tab_bar = tk.Frame(self.left_container, bg="#222", height=25)
        self.tab_bar.pack(fill=tk.X)
        
        self.editor_container = tk.Frame(self.left_container)
        self.editor_container.pack(fill=tk.BOTH, expand=1)

        self.right_paned = tk.PanedWindow(self.main_paned, orient=tk.VERTICAL, sashwidth=5, bg="#444")
        self.main_paned.add(self.right_paned, width=200)

        self.input_frame = tk.Frame(self.right_paned, height=210)
        tk.Label(self.input_frame, text="Script Arguments:", anchor="w").pack(fill=tk.X)
        self.input_area = tk.Text(self.input_frame, height=5, font=(self.font_family, self.font_size), insertbackground="black")
        self.input_area.pack(fill=tk.BOTH, expand=1)
        self.right_paned.add(self.input_frame)

        self.output_frame = tk.Frame(self.right_paned, height=490)
        self.right_paned.add(self.output_frame, stretch="always")
        
        self.btn_clear = tk.Button(self.output_frame, text="Clear Output", command=lambda: self.output_area.delete(1.0, tk.END))
        self.btn_clear.pack(fill=tk.X)
        
        self.output_area = tk.Text(self.output_frame, bg="#1e1e1e", fg="#00ff00", font=(self.font_family, self.font_size), insertbackground="white")
        self.output_area.pack(fill=tk.BOTH, expand=1)
        self.output_area.tag_configure("error", foreground="#ff6666")
        
        # Interactive Terminal Bindings
        self.output_area.bind('<Return>', self._on_output_enter)
        self.output_area.bind('<BackSpace>', self._on_output_backspace)
        self.output_area.mark_set("input_start", tk.END)

    def _bind_shortcuts(self):
        self.bind('<Control-s>', self.save_file)
        self.bind('<Control-o>', self.open_file)
        self.bind('<Control-r>', self.run_script)
        self.bind('<Control-a>', self._select_all)
        self.bind('<Control-plus>', self.zoom_in)
        self.bind('<Control-equal>', self.zoom_in)
        self.bind('<Control-minus>', self.zoom_out)
        self.bind('<Control-Button-4>', self.zoom_in)
        self.bind('<Control-Button-5>', self.zoom_out)

    def _select_all(self, event=None):
        widget = self.focus_get()
        if isinstance(widget, tk.Text):
            widget.tag_add(tk.SEL, "1.0", tk.END)
            widget.mark_set(tk.INSERT, "1.0")
            widget.see(tk.INSERT)
            return 'break'

    def apply_fonts(self):
        base_font = (self.font_family, self.font_size)
        bold_font = (self.font_family, self.font_size, "bold")
        italic_font = (self.font_family, self.font_size, "italic")

        self.input_area.configure(font=base_font)
        self.output_area.configure(font=base_font)

        for tab in self.tabs.values():
            tab['text'].configure(font=base_font)
            tab['lines'].configure(font=base_font)
            tab['text'].tag_configure("keyword", font=bold_font, foreground="#0000ff")
            tab['text'].tag_configure("comment", font=italic_font, foreground="#008000")
            tab['text'].tag_configure("string", font=base_font, foreground="#a31515")

    def zoom_in(self, event=None):
        self.font_size += 1
        self.apply_fonts()
        return "break"

    def zoom_out(self, event=None):
        if self.font_size > 6:
            self.font_size -= 1
            self.apply_fonts()
        return "break"

    def new_tab(self, filename, content="", filepath=None):
        if len(self.tabs) >= 5:
            messagebox.showwarning("Limit Reached", "Maximum of 5 files allowed.")
            return

        self.tab_counter += 1
        tab_id = self.tab_counter
        
        frame = tk.Frame(self.editor_container)
        
        line_numbers = tk.Text(frame, width=4, padx=3, takefocus=0, border=0, bg='#e0e0e0', state='disabled')
        line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        
        text_area = tk.Text(frame, undo=True, wrap=tk.NONE, tabs=('1c',), insertbackground="black")
        text_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=1)
        text_area.insert(1.0, content)
        
        text_area.bind('<Return>', lambda e, t=text_area: self.auto_indent(e, t))
        text_area.bind('<KeyRelease>', lambda e, tid=tab_id: self.on_text_change(e, tid))

        tab_btn_frame = tk.Frame(self.tab_bar, bg="#555", bd=1, relief=tk.RAISED)
        tab_btn_frame.pack(side=tk.LEFT, padx=1, pady=1)
        
        lbl = tk.Label(tab_btn_frame, text=filename, bg="#555", fg="white", cursor="hand2")
        lbl.pack(side=tk.LEFT, padx=5)
        lbl.bind('<Button-1>', lambda e, tid=tab_id: self.switch_tab(tid))
        
        btn_close = tk.Label(tab_btn_frame, text="X", bg="#555", fg="#ff6666", cursor="hand2")
        btn_close.pack(side=tk.RIGHT, padx=2)
        btn_close.bind('<Button-1>', lambda e, tid=tab_id: self.request_close_tab(tid))

        self.tabs[tab_id] = {
            'path': filepath,
            'frame': frame,
            'text': text_area,
            'lines': line_numbers,
            'tab_btn': tab_btn_frame,
            'lbl': lbl,
            'dirty': False,
            'filename': filename
        }
        
        self.apply_fonts()
        self.switch_tab(tab_id)
        self.tabs[tab_id]['text'].edit_modified(False)

    def on_text_change(self, event, tab_id):
        self.update_ui()
        if not self.tabs[tab_id]['dirty'] and self.tabs[tab_id]['text'].edit_modified():
            self.tabs[tab_id]['dirty'] = True
            self.tabs[tab_id]['lbl'].config(text=f"*{self.tabs[tab_id]['filename']}")

    def switch_tab(self, tab_id):
        if tab_id not in self.tabs: return
        
        for tid, data in self.tabs.items():
            data['frame'].pack_forget()
            data['tab_btn'].configure(bg="#555")
            data['lbl'].configure(bg="#555")
            
        self.current_tab_id = tab_id
        active = self.tabs[tab_id]
        active['frame'].pack(fill=tk.BOTH, expand=1)
        active['tab_btn'].configure(bg="#777")
        active['lbl'].configure(bg="#777")
        active['text'].focus_set()
        
        self.title(f"LightBash IDE - {active['path'] or 'Untitled.sh'}")
        self.update_ui()

    def request_close_tab(self, tab_id):
        if tab_id not in self.tabs: return
        
        active = self.tabs[tab_id]
        if active['dirty']:
            response = messagebox.askyesnocancel("Unsaved Changes", f"Save changes to {active['filename']} before closing?")
            if response is None: return
            if response is True:
                self.switch_tab(tab_id)
                self.save_file()
                if self.tabs[tab_id]['dirty']: return 

        self.close_tab(tab_id)

    def close_tab(self, tab_id):
        self.tabs[tab_id]['frame'].destroy()
        self.tabs[tab_id]['tab_btn'].destroy()
        del self.tabs[tab_id]
        
        if self.tabs:
            self.switch_tab(list(self.tabs.keys())[-1])
        else:
            self.current_tab_id = None
            self.title("LightBash IDE")

    def auto_indent(self, event, text_widget):
        current_line = text_widget.get("insert linestart", "insert lineend")
        indent = len(current_line) - len(current_line.lstrip())
        base_space = " " * indent
        
        if current_line.strip().endswith(("then", "do", "{")) or current_line.strip().startswith("case "):
            base_space += "    "
            
        text_widget.insert(tk.INSERT, "\n" + base_space)
        self.update_ui()
        return "break"

    def update_ui(self):
        if not self.current_tab_id or self.current_tab_id not in self.tabs: return
        
        active = self.tabs[self.current_tab_id]
        text_area = active['text']
        line_numbers = active['lines']

        line_count = text_area.index('end-1c').split('.')[0]
        lines = "\n".join(str(i) for i in range(1, int(line_count) + 1))
        line_numbers.config(state='normal')
        line_numbers.delete(1.0, tk.END)
        line_numbers.insert(1.0, lines)
        line_numbers.config(state='disabled')

        for tag in ["keyword", "string", "comment"]:
            text_area.tag_remove(tag, "1.0", tk.END)
        
        text_content = text_area.get("1.0", "end-1c")
        rules = [
            ("keyword", r'\b(echo|if|fi|then|elif|else|for|while|do|done|case|esac|sudo|grep|awk|sed|read|return|function)\b'),
            ("string", r'\"[^\"]*\"|\'[^\']*\''),
            ("comment", r'#.*$')
        ]

        for tag, pattern in rules:
            for match in re.finditer(pattern, text_content, re.MULTILINE):
                start = f"1.0 + {match.start()} chars"
                end = f"1.0 + {match.end()} chars"
                text_area.tag_add(tag, start, end)

    def _replace_on_paste(self, event):
        try:
            clipboard_content = self.clipboard_get()
            if event.widget.tag_ranges(tk.SEL):
                event.widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            event.widget.insert(tk.INSERT, clipboard_content)
            
            if self.current_tab_id and event.widget == self.tabs[self.current_tab_id]['text']:
                self.on_text_change(None, self.current_tab_id)
            return 'break'
        except tk.TclError:
            return 'break'

    def load_file(self, path):
        abs_path = os.path.abspath(path)
        
        if os.path.getsize(abs_path) > 5 * 1024 * 1024:
            messagebox.showerror("File too large", "Cannot open files larger than 5MB.")
            return

        for tid, data in self.tabs.items():
            if data['path'] and os.path.abspath(data['path']) == abs_path:
                self.switch_tab(tid)
                return

        try:
            with open(abs_path, 'r', encoding='utf-8') as file:
                content = file.read()
            self.new_tab(os.path.basename(abs_path), content, abs_path)
        except UnicodeDecodeError:
            messagebox.showerror("Invalid File", "This appears to be a binary file. Only text/script files are supported.")
        except Exception as e:
            messagebox.showerror("Error Reading File", str(e))

    def open_file(self, event=None):
        path = filedialog.askopenfilename(filetypes=[("Bash Scripts", "*.sh")])
        if path: self.load_file(path)

    def save_file(self, event=None):
        if not self.current_tab_id: return
        active = self.tabs[self.current_tab_id]
        
        if not active['path']:
            path = filedialog.asksaveasfilename(defaultextension=".sh", initialfile="Untitled.sh")
            if not path: return
            active['path'] = path
            active['filename'] = os.path.basename(path)
            
        try:
            with open(active['path'], 'w', encoding='utf-8') as file:
                file.write(active['text'].get(1.0, "end-1c"))
            
            active['dirty'] = False
            active['text'].edit_modified(False)
            active['lbl'].config(text=active['filename'])
            self.title(f"LightBash IDE - {active['path']}")
            os.chmod(active['path'], 0o755)
        except PermissionError:
            messagebox.showerror("Permission Denied", f"You do not have write permissions for:\n{active['path']}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # --- Interactive Terminal Handling ---
    def _on_output_backspace(self, event):
        # Prevent users from deleting script output text
        if self.output_area.compare(tk.INSERT, "<=", "input_start"):
            return 'break'

    def _on_output_enter(self, event):
        if self.running_process and self.running_process.poll() is None:
            user_input = self.output_area.get("input_start", "end-1c")
            try:
                self.running_process.stdin.write(user_input + "\n")
                self.running_process.stdin.flush()
            except BrokenPipeError:
                pass
            
            self.output_area.insert(tk.END, "\n")
            self.output_area.mark_set("input_start", tk.END)
            return 'break'
        return None

    def _publish_char(self, char, tag=None):
        self.output_area.insert(tk.END, char, tag)
        self.output_area.see(tk.END)
        self.output_area.mark_set("input_start", tk.END)

    def _stream_reader(self, stream, tag=None):
        try:
            for char in iter(lambda: stream.read(1), ''):
                self.after(0, self._publish_char, char, tag)
        except ValueError:
            pass

    def kill_process(self):
        if self.running_process and self.running_process.poll() is None:
            self.running_process.terminate()
            try:
                self.running_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.running_process.kill()

    def run_script(self, event=None):
        if not self.current_tab_id: return
        self.save_file()
        
        active = self.tabs[self.current_tab_id]
        if not active['path'] or active['dirty']: return 

        self.kill_process()
        self.output_area.delete(1.0, tk.END)
        
        raw_args = self.input_area.get("1.0", "end-1c").strip()
        try:
            args = shlex.split(raw_args) 
        except ValueError as e:
            self.output_area.insert(tk.END, f"[System Error]: Invalid arguments format.\n{e}\n")
            return

        command = ["bash", active['path']] + args
        
        self.output_area.insert(tk.END, f"$ {' '.join(command)}\n{'-'*40}\n")
        self.output_area.mark_set("input_start", tk.END)
        cwd = os.path.dirname(active['path'])

        try:
            # Enable STDIN piping, unbuffered byte parsing (bufsize=1)
            self.running_process = subprocess.Popen(
                command, cwd=cwd, 
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                text=True, bufsize=1
            )
            
            # Spawn daemon threads to continuously read streams byte-by-byte
            threading.Thread(target=self._stream_reader, args=(self.running_process.stdout,), daemon=True).start()
            threading.Thread(target=self._stream_reader, args=(self.running_process.stderr, "error"), daemon=True).start()
        except Exception as e:
            self.output_area.insert(tk.END, f"Execution failed: {str(e)}\n", "error")

    def on_closing(self):
        unsaved = [data['filename'] for data in self.tabs.values() if data['dirty']]
        if unsaved:
            files_str = "\n".join(unsaved)
            if not messagebox.askyesno("Unsaved Changes", f"The following files have unsaved changes:\n\n{files_str}\n\nAre you sure you want to exit without saving?"):
                return
        
        self.kill_process() 
        self.destroy()

if __name__ == "__main__":
    args = sys.argv[1:]
    
    if '-h' in args or '--help' in args:
        print("Usage: lb [file1.sh] [file2.sh] ... (Max 5)")
        print("Lightweight Bash IDE for CentOS.")
        sys.exit(0)

    if len(args) > 5:
        print("Error: A maximum of 5 files can be passed via command line.", file=sys.stderr)
        sys.exit(1)
        
    # Pre-flight Validation
    valid_files = []
    for f in args:
        if not f.endswith('.sh'):
            print(f"Error: '{f}' is not a valid extension. Only .sh files are supported.", file=sys.stderr)
            sys.exit(1)
        
        abs_path = os.path.abspath(f)
        if not os.path.exists(abs_path):
            print(f"Error: Target file '{f}' does not exist.", file=sys.stderr)
            sys.exit(1)
            
        valid_files.append(abs_path)

    app = BashEditor()
    
    if valid_files:
        for f in valid_files:
            app.load_file(f)
        if app.tabs:
            app.switch_tab(list(app.tabs.keys())[0])
    else:
        app.new_tab("Untitled.sh")
        
    app.mainloop()

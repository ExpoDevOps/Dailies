import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui
from datetime import datetime
import os

# Base directory for sessions
BASE_DIR = r"G:\expo\Software\Dailies\Dailies\dailies\sessions"
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)


class DailiesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("dailies")
        self.root.geometry("350x275")

        # Set up today's session folder
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.session_dir = os.path.join(BASE_DIR, self.today)
        os.makedirs(self.session_dir, exist_ok=True)

        # Task buttons frame
        self.task_frame = tk.Frame(root)
        self.task_frame.pack(pady=10)

        self.tasks = ["code", "research", "building", "meeting", "field", "social"]
        self.task_buttons = {}
        self.current_task = tk.StringVar(value="default")
        for task in self.tasks:
            btn = tk.Button(self.task_frame, text=task,
                            command=lambda t=task: self.set_task(t),
                            bg="lightgrey", activebackground="lightgrey")
            btn.pack(side=tk.LEFT, padx=5)
            self.task_buttons[task] = btn

        # Text field for notes
        self.note_label = tk.Label(root, text="speak puny mortal")
        self.note_label.pack(pady=10)

        self.note_text = tk.Text(root, height=5, width=40)
        self.note_text.pack(pady=10)

        # Save button
        self.save_button = tk.Button(root, text="save", command=self.save_note)
        self.save_button.pack(pady=5)

        # Report button
        self.report_button = tk.Button(root, text="generate report", command=self.generate_report)
        self.report_button.pack(pady=5)

        # Track prompt state
        self.prompt_active = False
        self.prompt_time = None

        # Start the periodic prompting
        self.running = True
        self.prompt_thread = threading.Thread(target=self.prompt_periodically)
        self.prompt_thread.daemon = True
        self.prompt_thread.start()

    def set_task(self, task):
        self.current_task.set(task)
        for btn_task, btn in self.task_buttons.items():
            btn.config(bg="lightgrey")
        self.task_buttons[task].config(bg="lightgreen")

    def prompt_periodically(self):
        while self.running:
            time.sleep(15 * 60)  # 15 minutes in seconds
            if self.running:
                self.root.after(0, self.show_prompt)
                self.prompt_active = True
                self.prompt_time = time.time()
                threading.Thread(target=self.check_prompt_timeout, daemon=True).start()

    def show_prompt(self):
        self.root.lift()
        self.root.attributes('-topmost', True)
        messagebox.showinfo("Note Time", "Time to add a note and take a screenshot!")
        self.root.attributes('-topmost', False)

    def check_prompt_timeout(self):
        time.sleep(3 * 60)  # Wait 3 minutes
        if self.prompt_active and self.note_text.get("1.0", tk.END).strip() == "":
            self.save_auto_note()

    def save_note(self):
        note = self.note_text.get("1.0", tk.END).strip()
        task = self.current_task.get()
        if note:
            self.save_to_task(task, note)
            self.prompt_active = False
        else:
            messagebox.showwarning("empty note", "please stop trolling.")

    def save_auto_note(self):
        auto_note = "user did not leave note - leaving auto-note for timestamp and time summation"
        self.save_to_task("default", auto_note)
        self.prompt_active = False

    def save_to_task(self, task, note):
        task_dir = os.path.join(self.session_dir, task)
        os.makedirs(task_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%H:%M:%S")

        # HTML format
        note_filename_html = os.path.join(task_dir, f"{task}_notes.html")
        html_entry = f'<div class="note"><p><strong>{timestamp}</strong>: {note}</p></div>\n'
        if not os.path.exists(note_filename_html):
            with open(note_filename_html, "w") as f:
                f.write('<html><body>\n')
        with open(note_filename_html, "a") as f:
            f.write(html_entry)

        # XML format
        note_filename_xml = os.path.join(task_dir, f"{task}_notes.xml")
        xml_entry = f'  <note timestamp="{timestamp}">{note}</note>\n'
        if not os.path.exists(note_filename_xml):
            with open(note_filename_xml, "w") as f:
                f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<notes task="{task}">\n')
        with open(note_filename_xml, "a") as f:
            f.write(xml_entry)

        # Screenshot
        try:
            screenshot = pyautogui.screenshot()
            screenshot_filename = os.path.join(task_dir, f"screenshot_{task}_{timestamp.replace(':', '-')}.png")
            screenshot.save(screenshot_filename)
        except Exception as e:
            messagebox.showwarning("Screenshot Failed", f"Note saved but screenshot failed: {str(e)}")

        self.note_text.delete("1.0", tk.END)
        messagebox.showinfo("saved", f"note and screenshot saved for {task}!")

    def generate_report(self):
        report_dir = self.session_dir
        timestamp = self.today

        # HTML Report
        report_filename_html = os.path.join(report_dir, f"report_{timestamp}.html")
        with open(report_filename_html, "w") as report:
            report.write('<html><body>\n<h1>Daily Report</h1>\n')
            self._write_html_report(report)
            report.write('</body></html>\n')

        # XML Report
        report_filename_xml = os.path.join(report_dir, f"report_{timestamp}.xml")
        with open(report_filename_xml, "w") as report:
            report.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<report date="{timestamp}">\n')
            self._write_xml_report(report)
            report.write('</report>\n')

        messagebox.showinfo("report generated", f"Reports saved in HTML and XML formats in {report_dir}")

    def _write_html_report(self, report):
        report.write(f'<h2>Date: {self.today}</h2>\n')
        total_time = 0
        afk_time = 0
        all_tasks = self.tasks + ["default"]
        for task in all_tasks:
            task_dir = os.path.join(self.session_dir, task)
            note_file = os.path.join(task_dir, f"{task}_notes.xml")  # Using XML as source
            if os.path.exists(note_file):
                report.write(f'<h3>{task.upper()}</h3>\n<ul>\n')
                with open(note_file, "r") as f:
                    lines = f.readlines()
                    notes = [line.strip() for line in lines if "<note" in line]
                    for note in notes:
                        timestamp = note.split('timestamp="')[1].split('"')[0]
                        content = note.split(">")[1].split("</")[0]
                        report.write(f'<li>[{timestamp}] {content}</li>\n')
                note_count = len(notes)
                task_time = note_count * 15
                if task == "default" and any("auto-note" in n for n in notes):
                    afk_time += task_time
                else:
                    total_time += task_time
                report.write(f'</ul>\n<p>Estimated Time: {task_time} minutes</p>\n')
                screenshots = [f for f in os.listdir(task_dir) if f.startswith(f"screenshot_{task}")]
                if screenshots:
                    report.write('<p>Screenshots:</p>\n<ul>\n')
                    for shot in screenshots:
                        report.write(f'<li>{shot}</li>\n')
                    report.write('</ul>\n')
        report.write(f'<p><strong>Total Productive Time:</strong> {total_time} minutes</p>\n')
        report.write(f'<p><strong>Total AFK Time:</strong> {afk_time} minutes</p>\n')
        report.write(f'<p><strong>Grand Total Time:</strong> {total_time + afk_time} minutes</p>\n')

    def _write_xml_report(self, report):
        total_time = 0
        afk_time = 0
        all_tasks = self.tasks + ["default"]
        for task in all_tasks:
            task_dir = os.path.join(self.session_dir, task)
            note_file = os.path.join(task_dir, f"{task}_notes.xml")
            if os.path.exists(note_file):
                report.write(f'  <task name="{task}">\n')
                with open(note_file, "r") as f:
                    lines = f.readlines()
                    notes = [line.strip() for line in lines if "<note" in line]
                    for note in notes:
                        report.write(f'    {note}\n')
                note_count = len(notes)
                task_time = note_count * 15
                if task == "default" and any("auto-note" in n for n in notes):
                    afk_time += task_time
                else:
                    total_time += task_time
                report.write(f'    <time>{task_time}</time>\n')
                screenshots = [f for f in os.listdir(task_dir) if f.startswith(f"screenshot_{task}")]
                if screenshots:
                    report.write('    <screenshots>\n')
                    for shot in screenshots:
                        report.write(f'      <screenshot>{shot}</screenshot>\n')
                    report.write('    </screenshots>\n')
                report.write('  </task>\n')
        report.write(f'  <totals>\n')
        report.write(f'    <productive>{total_time}</productive>\n')
        report.write(f'    <afk>{afk_time}</afk>\n')
        report.write(f'    <grand>{total_time + afk_time}</grand>\n')
        report.write(f'  </totals>\n')

    def on_closing(self):
        self.running = False
        # Close open XML files properly
        for task in self.tasks + ["default"]:
            xml_file = os.path.join(self.session_dir, task, f"{task}_notes.xml")
            if os.path.exists(xml_file):
                with open(xml_file, "a") as f:
                    f.write("</notes>\n")
        # Close open HTML files
        for task in self.tasks + ["default"]:
            html_file = os.path.join(self.session_dir, task, f"{task}_notes.html")
            if os.path.exists(html_file):
                with open(html_file, "a") as f:
                    f.write("</body></html>\n")
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = DailiesApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
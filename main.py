import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui
from datetime import datetime
import os
import logging
import webbrowser

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AgentX")

# Base directory for sessions
BASE_DIR = r"G:\expo\Software\Dailies\Dailies\dailies\sessions"
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

class DailiesApp:
    def __init__(self, root):
        self.root = root
        self.root.title("dailies")
        self.root.geometry("350x300")

        self.today = datetime.now().strftime("%Y-%m-%d")
        self.session_dir = os.path.join(BASE_DIR, self.today)
        os.makedirs(self.session_dir, exist_ok=True)
        logger.debug("Agent X: Base of operations established at %s", self.session_dir)
        logger.info("Session directory initialized: %s", self.session_dir)

        # Store notes in memory
        self.notes = []

        # Task colors (rainbow + gray for default)
        self.task_colors = {
            "code": "#ff0000",      # Red
            "research": "#ff8000",  # Orange
            "building": "#ffff00",  # Yellow
            "meeting": "#00ff00",   # Green
            "field": "#0000ff",     # Blue
            "social": "#800080",    # Purple
            "default": "#808080"    # Gray
        }

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

        self.note_label = tk.Label(root, text="speak puny mortal")
        self.note_label.pack(pady=10)

        self.note_text = tk.Text(root, height=5, width=40)
        self.note_text.pack(pady=10)

        self.save_button = tk.Button(root, text="save", command=self.save_note)
        self.save_button.pack(pady=5)

        self.status_label = tk.Label(root, text="", fg="cyan")
        self.status_label.pack(pady=5)

        self.report_button = tk.Button(root, text="generate report", command=self.generate_report)
        self.report_button.pack(pady=5)

        self.prompt_active = False
        self.prompt_time = None

        self.running = True
        self.prompt_thread = threading.Thread(target=self.prompt_periodically)
        self.prompt_thread.daemon = True
        self.prompt_thread.start()
        logger.debug("Agent X: Surveillance thread activated. Monitoring commencing.")
        logger.info("Prompt thread started")

    def set_task(self, task):
        self.current_task.set(task)
        for btn_task, btn in self.task_buttons.items():
            btn.config(bg="lightgrey")
        self.task_buttons[task].config(bg="lightgreen")
        logger.debug("Agent X: Mission target switched to %s. Eyes on the prize!", task)

    def prompt_periodically(self):
        while self.running:
            time.sleep(15 * 60)
            if self.running:
                self.root.after(0, self.show_prompt)
                self.prompt_active = True
                self.prompt_time = time.time()
                logger.debug("Agent X: HQ checking in. Time to report, operative!")
                threading.Thread(target=self.check_prompt_timeout, daemon=True).start()

    def show_prompt(self):
        self.root.lift()
        self.root.attributes('-topmost', True)
        messagebox.showinfo("Note Time", "Time to add a note and take a screenshot!")
        self.root.attributes('-topmost', False)

    def check_prompt_timeout(self):
        time.sleep(3 * 60)
        if self.prompt_active and self.note_text.get("1.0", tk.END).strip() == "":
            self.save_auto_note()
            logger.debug("Agent X: Operative gone dark. Deploying auto-note protocol.")

    def save_note(self):
        note = self.note_text.get("1.0", tk.END).strip()
        task = self.current_task.get()
        if note:
            self.save_to_task(task, note)
            self.prompt_active = False
        else:
            messagebox.showwarning("empty note", "please stop trolling.")
            logger.debug("Agent X: Empty intel detected. This is no time for games, rookie!")

    def save_auto_note(self):
        auto_note = "user did not leave note - leaving auto-note for timestamp and time summation"
        self.save_to_task("default", auto_note)
        self.prompt_active = False

    def save_to_task(self, task, note):
        task_dir = os.path.join(self.session_dir, task)
        os.makedirs(task_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%H:%M:%S")
        logger.debug("Agent X: Securing intel drop in %s sector.", task)

        # Store note in memory
        self.notes.append({"task": task, "timestamp": timestamp, "content": note})

        # Write all notes to HTML
        note_filename_html = os.path.join(self.session_dir, "notes.html")
        with open(note_filename_html, "w") as f:
            f.write('<html><head><style>')
            f.write('body { font-family: Arial, sans-serif; margin: 20px; }')
            f.write('h2 { color: #666; }')
            f.write('.note { margin: 5px 0; padding: 10px; border-radius: 4px; color: #333; background: #fff; }')
            for task_name, color in self.task_colors.items():
                f.write(f'.note-{task_name} {{ border-left: 4px solid {color}; }}')
            f.write('@media (max-width: 600px) { .note { padding: 8px; font-size: 14px; } }')
            f.write(f'</style></head><body>\n<h2>Notes for {self.today}</h2>\n')
            for n in self.notes:
                f.write(f'<div class="note note-{n["task"]}" data-task="{n["task"]}"><p><strong>{n["timestamp"]}</strong> [{n["task"]}]: {n["content"]}</p></div>\n')
            f.write('</body></html>\n')
            logger.info("Updated HTML file with %d notes: %s", len(self.notes), note_filename_html)

        # Write all notes to XML
        note_filename_xml = os.path.join(self.session_dir, "notes.xml")
        with open(note_filename_xml, "w") as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<notes date="{self.today}">\n')
            for n in self.notes:
                f.write(f'  <note task="{n["task"]}" timestamp="{n["timestamp"]}">{n["content"]}</note>\n')
            f.write('</notes>\n')
            logger.info("Updated XML file with %d notes: %s", len(self.notes), note_filename_xml)

        # Screenshot
        try:
            screenshot = pyautogui.screenshot()
            screenshot_filename = os.path.join(task_dir, f"screenshot_{task}_{timestamp.replace(':', '-')}.png")
            screenshot.save(screenshot_filename)
            logger.debug("Agent X: Snapshot acquired. Evidence locked in at %s.", screenshot_filename)
            logger.info("Screenshot saved: %s", screenshot_filename)
        except Exception as e:
            messagebox.showwarning("Screenshot Failed", f"Note saved but screenshot failed: {str(e)}")
            logger.error("Screenshot failed: %s", str(e))

        self.note_text.delete("1.0", tk.END)
        self.status_label.config(text="note saved!")
        self.root.after(3000, lambda: self.status_label.config(text=""))
        logger.debug("Agent X: Intel successfully stashed for %s. Mission accomplished!", task)

    def generate_report(self):
        report_dir = self.session_dir
        timestamp = self.today

        # HTML Report
        report_filename_html = os.path.join(report_dir, f"report_{timestamp}.html")
        with open(report_filename_html, "w") as report:
            report.write('<html><head><style>')
            report.write('body { font-family: Arial, sans-serif; margin: 20px; background: #f9f9f9; }')
            report.write('h1 { color: #2c3e50; } h2 { color: #34495e; } h3 { color: #7f8c8d; }')
            report.write('.note { margin: 5px 0; padding: 10px; border-radius: 4px; color: #333; background: #fff; }')
            for task_name, color in self.task_colors.items():
                report.write(f'.note-{task_name} {{ border-left: 4px solid {color}; }}')
            report.write('.task-group { margin-bottom: 25px; padding: 10px; background: #ecf0f1; border-radius: 8px; }')
            report.write('.summary { border-collapse: collapse; width: 50%; margin-top: 20px; }')
            report.write('.summary td, .summary th { border: 1px solid #ddd; padding: 8px; text-align: left; }')
            report.write('.summary th { background: #3498db; color: white; }')
            report.write('@media (max-width: 600px) { .note { padding: 8px; font-size: 14px; } }')
            report.write('</style></head><body>\n<h1>Daily Report</h1>\n')
            self._write_html_report(report)
            report.write('</body></html>\n')
            logger.info("Generated HTML report: %s", report_filename_html)
            webbrowser.open(f"file://{report_filename_html}")

        # XML Report
        report_filename_xml = os.path.join(report_dir, f"report_{timestamp}.xml")
        with open(report_filename_xml, "w") as report:
            report.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<report date="{timestamp}">\n')
            self._write_xml_report(report)
            report.write('</report>\n')
            logger.info("Generated XML report: %s", report_filename_xml)

        messagebox.showinfo("report generated", f"Reports saved in HTML and XML formats in {report_dir}")
        logger.debug("Agent X: Debriefing complete. Reports dispatched to %s.", report_dir)

    def _write_html_report(self, report):
        report.write(f'<h2>Date: {self.today}</h2>\n')
        total_time = 0
        afk_time = 0
        all_tasks = self.tasks + ["default"]
        for task in all_tasks:
            task_notes = [n for n in self.notes if n["task"] == task]
            if task_notes:
                report.write(f'<div class="task-group">\n<h3>{task.upper()}</h3>\n<ul>\n')
                for note in task_notes:
                    report.write(f'<li><div class="note note-{task}"><strong>{note["timestamp"]}</strong> [{task}]: {note["content"]}</div></li>\n')
                note_count = len(task_notes)
                task_time = note_count * 15
                if task == "default" and any("auto-note" in n["content"] for n in task_notes):
                    afk_time += task_time
                else:
                    total_time += task_time
                report.write(f'</ul>\n<p>Estimated Time: {task_time} minutes</p>\n')
                screenshots = [f for f in os.listdir(os.path.join(self.session_dir, task)) if f.startswith(f"screenshot_{task}")]
                if screenshots:
                    report.write('<p>Screenshots:</p>\n<ul>\n')
                    for shot in screenshots:
                        report.write(f'<li><a href="{task}/{shot}">{shot}</a></li>\n')
                    report.write('</ul>\n</div>\n')
        report.write('<table class="summary">\n')
        report.write('<tr><th>Metric</th><th>Value</th></tr>\n')
        report.write(f'<tr><td>Total Productive Time</td><td>{total_time} minutes</td></tr>\n')
        report.write(f'<tr><td>Total AFK Time</td><td>{afk_time} minutes</td></tr>\n')
        report.write(f'<tr><td>Grand Total Time</td><td>{total_time + afk_time} minutes</td></tr>\n')
        report.write('</table>\n')

    def _write_xml_report(self, report):
        total_time = 0
        afk_time = 0
        all_tasks = self.tasks + ["default"]
        for task in all_tasks:
            task_notes = [n for n in self.notes if n["task"] == task]
            if task_notes:
                report.write(f'  <task name="{task}">\n')
                for note in task_notes:
                    report.write(f'    <note task="{task}" timestamp="{note["timestamp"]}">{note["content"]}</note>\n')
                note_count = len(task_notes)
                task_time = note_count * 15
                if task == "default" and any("auto-note" in n["content"] for n in task_notes):
                    afk_time += task_time
                else:
                    total_time += task_time
                report.write(f'    <time>{task_time}</time>\n')
                screenshots = [f for f in os.listdir(os.path.join(self.session_dir, task)) if f.startswith(f"screenshot_{task}")]
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
        logger.debug("Agent X: Shutting down operations. Going off the grid.")
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DailiesApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
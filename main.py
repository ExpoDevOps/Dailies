import tkinter as tk
from tkinter import messagebox
import threading
import time
import pyautogui
from datetime import datetime
import os
import logging

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

        # Single HTML file for all notes
        note_filename_html = os.path.join(self.session_dir, "notes.html")
        html_entry = f'<div class="note" data-task="{task}"><p><strong>{timestamp}</strong> [{task}]: {note}</p></div>\n'
        if not os.path.exists(note_filename_html):
            with open(note_filename_html, "w") as f:
                f.write('<html><head><style>')
                f.write('body { font-family: Arial, sans-serif; margin: 20px; }')
                f.write('h2 { color: #666; }')
                f.write('.note { margin: 5px 0; padding: 5px; border-left: 3px solid #00cccc; color: #333; }')
                f.write('.task-group { margin-bottom: 20px; }')
                f.write('</style></head><body>\n<h2>Notes for {self.today}</h2>\n')
                logger.info("Initialized HTML file: %s", note_filename_html)
        with open(note_filename_html, "a") as f:
            f.write(html_entry)
            logger.info("Appended note to HTML: %s (task: %s)", note_filename_html, task)

        # Single XML file for all notes
        note_filename_xml = os.path.join(self.session_dir, "notes.xml")
        xml_entry = f'  <note task="{task}" timestamp="{timestamp}">{note}</note>\n'
        if not os.path.exists(note_filename_xml):
            with open(note_filename_xml, "w") as f:
                f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<notes date="{self.today}">\n')
                logger.info("Initialized XML file: %s", note_filename_xml)
        with open(note_filename_xml, "a") as f:
            f.write(xml_entry)
            logger.info("Appended note to XML: %s (task: %s)", note_filename_xml, task)

        # Screenshot (still task-specific)
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
            report.write('body { font-family: Arial, sans-serif; margin: 20px; }')
            report.write('h1 { color: #333; } h2 { color: #666; } h3 { color: #999; }')
            report.write('.note { margin: 5px 0; padding: 5px; border-left: 3px solid #00cccc; color: #333; }')
            report.write('.task-group { margin-bottom: 20px; }')
            report.write('</style></head><body>\n<h1>Daily Report</h1>\n')
            self._write_html_report(report)
            report.write('</body></html>\n')
            logger.info("Generated HTML report: %s", report_filename_html)

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
        note_file = os.path.join(self.session_dir, "notes.xml")
        if os.path.exists(note_file):
            with open(note_file, "r") as f:
                lines = f.readlines()
                notes = [line.strip() for line in lines if "<note" in line]
                for task in all_tasks:
                    task_notes = [n for n in notes if f'task="{task}"' in n]
                    if task_notes:
                        report.write(f'<div class="task-group">\n<h3>{task.upper()}</h3>\n<ul>\n')
                        for note in task_notes:
                            timestamp = note.split('timestamp="')[1].split('"')[0]
                            content = note.split(">")[1].split("</")[0]
                            report.write(f'<li><div class="note"><strong>{timestamp}</strong> [{task}]: {content}</div></li>\n')
                        note_count = len(task_notes)
                        task_time = note_count * 15
                        if task == "default" and any("auto-note" in n for n in task_notes):
                            afk_time += task_time
                        else:
                            total_time += task_time
                        report.write(f'</ul>\n<p>Estimated Time: {task_time} minutes</p>\n')
                        screenshots = [f for f in os.listdir(os.path.join(self.session_dir, task)) if f.startswith(f"screenshot_{task}")]
                        if screenshots:
                            report.write('<p>Screenshots:</p>\n<ul>\n')
                            for shot in screenshots:
                                report.write(f'<li>{shot}</li>\n')
                            report.write('</ul>\n</div>\n')
        report.write(f'<p><strong>Total Productive Time:</strong> {total_time} minutes</p>\n')
        report.write(f'<p><strong>Total AFK Time:</strong> {afk_time} minutes</p>\n')
        report.write(f'<p><strong>Grand Total Time:</strong> {total_time + afk_time} minutes</p>\n')

    def _write_xml_report(self, report):
        total_time = 0
        afk_time = 0
        all_tasks = self.tasks + ["default"]
        note_file = os.path.join(self.session_dir, "notes.xml")
        if os.path.exists(note_file):
            with open(note_file, "r") as f:
                lines = f.readlines()
                notes = [line.strip() for line in lines if "<note" in line]
                for task in all_tasks:
                    task_notes = [n for n in notes if f'task="{task}"' in n]
                    if task_notes:
                        report.write(f'  <task name="{task}">\n')
                        for note in task_notes:
                            report.write(f'    {note}\n')
                        note_count = len(task_notes)
                        task_time = note_count * 15
                        if task == "default" and any("auto-note" in n for n in task_notes):
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
        xml_file = os.path.join(self.session_dir, "notes.xml")
        if os.path.exists(xml_file):
            with open(xml_file, "r+") as f:
                content = f.read()
                if "</notes>" not in content:
                    f.seek(0, os.SEEK_END)
                    f.write("</notes>\n")
                    logger.info("Closed XML file properly: %s", xml_file)
        html_file = os.path.join(self.session_dir, "notes.html")
        if os.path.exists(html_file):
            with open(html_file, "r+") as f:
                content = f.read()
                if "</body></html>" not in content:
                    f.seek(0, os.SEEK_END)
                    f.write("</body></html>\n")
                    logger.info("Closed HTML file properly: %s", html_file)
        logger.debug("Agent X: Shutting down operations. Going off the grid.")
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = DailiesApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
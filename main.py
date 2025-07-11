import sys
import os
import time
import logging
import webbrowser
from datetime import datetime
from xml.etree import ElementTree as ET
import pyautogui
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QTextEdit, QLabel, QFrame, QMessageBox)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QColor, QPalette

# Set up logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("AgentX")

# Base directory for sessions
BASE_DIR = r"G:\expo\Software\Dailies\Dailies\dailies\sessions"
if not os.path.exists(BASE_DIR):
    os.makedirs(BASE_DIR)

def invert_color(hex_color):
    hex_color = hex_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    inv_r, inv_g, inv_b = 255 - r, 255 - g, 255 - b
    if inv_r + inv_g + inv_b < 100:
        inv_r, inv_g, inv_b = min(inv_r + 50, 255), min(inv_g + 50, 255), min(inv_b + 50, 255)
    return f"#{inv_r:02x}{inv_g:02x}{inv_b:02x}"

class DailiesApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dailies")
        self.setGeometry(100, 100, 800, 600)

        self.today = datetime.now().strftime("%Y-%m-%d")
        self.session_dir = os.path.join(BASE_DIR, self.today)
        os.makedirs(self.session_dir, exist_ok=True)
        logger.debug("Agent X: Base of operations established at %s - The Force is strong with this one!",
                     self.session_dir)

        self.notes = []
        self.task_colors = {
            "code": {"bg": "#ff9999", "fg": "#fff"},
            "research": {"bg": "#ffcc99", "fg": "#fff"},
            "building": {"bg": "#ffffcc", "fg": "#000"},
            "meeting": {"bg": "#99ff99", "fg": "#000"},
            "field": {"bg": "#9999ff", "fg": "#fff"},
            "social": {"bg": "#cc99ff", "fg": "#fff"},
            "default": {"bg": "#e6e6e6", "fg": "#000"}
        }
        self.task_times = {task: 0.0 for task in self.task_colors.keys()}
        self.load_existing_notes()
        self.check_last_shutdown()

        self.current_task_start = time.time()
        self.current_task = "default"

        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # Left panel (tasks and notes)
        self.left_panel = QWidget()
        self.left_layout = QVBoxLayout(self.left_panel)
        self.main_layout.addWidget(self.left_panel, stretch=3)

        # Task buttons
        self.task_frame = QWidget()
        self.task_layout = QHBoxLayout(self.task_frame)
        self.tasks = ["code", "research", "building", "meeting", "field", "social"]
        self.task_buttons = {}
        for task in self.tasks:
            btn = QPushButton(task)
            btn.setStyleSheet(
                f"background-color: {self.task_colors[task]['bg']}; color: {self.task_colors[task]['fg']}")
            btn.clicked.connect(lambda checked, t=task: self.set_task(t))
            self.task_layout.addWidget(btn)
            self.task_buttons[task] = btn
        self.left_layout.addWidget(self.task_frame)

        # Note section
        self.note_label = QLabel("speak puny mortal")
        self.left_layout.addWidget(self.note_label)

        self.note_text = QTextEdit()
        self.note_text.setMinimumHeight(200)
        self.left_layout.addWidget(self.note_text, stretch=1)

        self.save_button = QPushButton("save")
        self.save_button.clicked.connect(self.save_note)
        self.left_layout.addWidget(self.save_button)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: cyan")
        self.left_layout.addWidget(self.status_label)

        self.report_button = QPushButton("generate report")
        self.report_button.clicked.connect(self.generate_report)
        self.left_layout.addWidget(self.report_button)

        # Right panel (tools)
        self.tool_frame = QFrame()
        self.tool_frame.setFrameShape(QFrame.Shape.Box)
        self.tool_layout = QVBoxLayout(self.tool_frame)
        self.main_layout.addWidget(self.tool_frame, stretch=1)
        self.tool_layout.addStretch()

        # Timers
        self.running = True
        self.prompt_timer = QTimer()
        self.prompt_timer.timeout.connect(self.show_prompt)
        self.prompt_timer.start(15 * 60 * 1000)  # 15 minutes

        self.time_log_timer = QTimer()
        self.time_log_timer.timeout.connect(self.log_time_note)
        self.time_log_timer.start(60 * 1000)  # 1 minute

        logger.debug("Agent X: Surveillance and time logging timers activated - Hasta la vista, idle time!")

    def set_task(self, task):
        if self.current_task_start:
            elapsed = (time.time() - self.current_task_start) / 60.0
            self.task_times[self.current_task] += elapsed
            logger.debug("Agent X: Logged %.1f minutes for %s - Time Lord approves!", elapsed, self.current_task)

        self.current_task = task
        self.current_task_start = time.time()
        for btn_task, btn in self.task_buttons.items():
            btn.setStyleSheet(
                f"background-color: {self.task_colors[btn_task]['bg']}; color: {self.task_colors[btn_task]['fg']}")
        self.task_buttons[task].setStyleSheet(
            f"background-color: {invert_color(self.task_colors[task]['bg'])}; color: {self.task_colors[task]['fg']}")
        logger.debug("Agent X: Mission target switched to %s - Engage warp speed!", task)

    def show_prompt(self):
        self.raise_()
        self.activateWindow()
        QMessageBox.information(self, "Note Time", "Time to add a note and take a screenshot!")
        self.prompt_active = True
        self.prompt_time = time.time()
        QTimer.singleShot(3 * 60 * 1000, self.check_prompt_timeout)

    def check_prompt_timeout(self):
        if self.prompt_active and not self.note_text.toPlainText().strip():
            self.save_auto_note()
            logger.debug("Agent X: Operative gone dark - Deploying auto-note protocol, Batman style!")

    def save_note(self):
        note = self.note_text.toPlainText().strip()
        if note:
            self.save_to_task(self.current_task, note)
            self.prompt_active = False
        else:
            QMessageBox.warning(self, "Empty Note", "please stop trolling.")
            logger.debug("Agent X: Empty intel detected - This is not the note you’re looking for!")

    def save_auto_note(self):
        auto_note = "user did not leave note - leaving auto-note for timestamp and time summation"
        self.save_to_task("default", auto_note)
        self.prompt_active = False

    def save_to_task(self, task, note):
        task_dir = os.path.join(self.session_dir, task)
        os.makedirs(task_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%H:%M:%S")

        if self.current_task_start:
            elapsed = (time.time() - self.current_task_start) / 60.0
            self.task_times[task] += elapsed
            logger.debug("Agent X: Logged %.1f minutes for %s - Time logged, Spock says 'Fascinating!'", elapsed, task)
            self.current_task_start = time.time()

        self.notes.append({"task": task, "timestamp": timestamp, "content": note})
        self.update_notes_files()

        try:
            screenshot = pyautogui.screenshot()
            screenshot_filename = os.path.join(task_dir, f"screenshot_{task}_{timestamp.replace(':', '-')}.png")
            screenshot.save(screenshot_filename)
            logger.info("Screenshot saved: %s - Captured the moment, Indiana Jones style!", screenshot_filename)
        except Exception as e:
            QMessageBox.warning(self, "Screenshot Failed", f"Note saved but screenshot failed: {str(e)}")
            logger.error("Screenshot failed: %s - Gremlins ate the screenshot!", str(e))

        self.note_text.clear()
        self.status_label.setText("note saved!")
        QTimer.singleShot(3000, lambda: self.status_label.setText(""))

    def load_existing_notes(self):
        note_filename_xml = os.path.join(self.session_dir, "notes.xml")
        if os.path.exists(note_filename_xml):
            try:
                tree = ET.parse(note_filename_xml)
                root = tree.getroot()
                for note in root.findall("note"):
                    task = note.get("task")
                    timestamp = note.get("timestamp")
                    content = note.text
                    self.notes.append({"task": task, "timestamp": timestamp, "content": content})
                    if content.startswith("Time logged:"):
                        try:
                            minutes = float(content.split(" ")[2])
                            self.task_times[task] += minutes
                        except (IndexError, ValueError):
                            logger.error("Failed to parse time from note: %s - Time travel glitch detected!", content)
                logger.info("Loaded %d notes from %s - The archives are complete, Obi-Wan!", len(self.notes),
                            note_filename_xml)
            except ET.ParseError:
                logger.error("Failed to parse existing notes.xml - XML chaos, Serenity now!")
                self.notes = []
        else:
            logger.debug("No notes.xml found - A new hope begins today!")

    def check_last_shutdown(self):
        note_filename_xml = os.path.join(self.session_dir, "notes.xml")
        if os.path.exists(note_filename_xml):
            try:
                tree = ET.parse(note_filename_xml)
                root = tree.getroot()
                shutdown_notes = [n for n in root.findall("note") if "the program shut down at" in n.text]
                if shutdown_notes:
                    last_shutdown_note = shutdown_notes[-1]
                    last_shutdown = last_shutdown_note.text.split("at ")[1]
                    logger.info("Last shutdown: %s - Found the last log, Sherlock!", last_shutdown)
                    shutdown_dt = datetime.strptime(last_shutdown, "%Y-%m-%d %H:%M:%S")
                    if shutdown_dt.strftime("%Y-%m-%d") == self.today:
                        gap_minutes = (time.time() - shutdown_dt.timestamp()) / 60.0
                        self.task_times["default"] += gap_minutes
                        logger.debug("Added %.1f minutes to default for gap - Time gap bridged, Doctor Who style!",
                                     gap_minutes)
                else:
                    logger.info("No previous shutdown note found - Fresh start, Neo!")
            except (ET.ParseError, ValueError) as e:
                logger.error("Failed to parse shutdown time: %s - Time vortex malfunction!", str(e))

    def log_time_note(self):
        if self.current_task_start:
            elapsed = (time.time() - self.current_task_start) / 60.0
            task = self.current_task
            self.task_times[task] += elapsed
            timestamp = datetime.now().strftime("%H:%M:%S")
            note_content = f"Time logged: {elapsed:.1f} minutes for {task}"
            self.notes.append({"task": task, "timestamp": timestamp, "content": note_content})
            self.update_notes_files()
            logger.debug("Agent X: Auto-logged %.1f minutes for %s - Time tracked, Tony Stark approved!", elapsed, task)
            self.current_task_start = time.time()

    def update_notes_files(self):
        note_filename_xml = os.path.join(self.session_dir, "notes.xml")
        note_filename_html = os.path.join(self.session_dir, "notes.html")

        # Load existing notes from XML to merge with current session
        existing_notes = []
        if os.path.exists(note_filename_xml):
            try:
                tree = ET.parse(note_filename_xml)
                root = tree.getroot()
                for note in root.findall("note"):
                    existing_notes.append({
                        "task": note.get("task"),
                        "timestamp": note.get("timestamp"),
                        "content": note.text
                    })
                logger.debug("Agent X: Retrieved %d existing notes from XML - Memory banks loaded, R2-D2!",
                             len(existing_notes))
            except ET.ParseError:
                logger.error("Agent X: Failed to parse notes.xml for merging - XML rebellion detected!")
                existing_notes = []

        # Merge existing notes with new ones, avoiding duplicates
        all_notes = existing_notes + self.notes
        # Remove duplicates based on task, timestamp, and content
        unique_notes = []
        seen = set()
        for note in all_notes:
            note_key = (note["task"], note["timestamp"], note["content"])
            if note_key not in seen:
                seen.add(note_key)
                unique_notes.append(note)
        logger.debug("Agent X: Merged to %d unique notes - Duplicates zapped, Ghostbusters style!", len(unique_notes))

        # Write to HTML
        with open(note_filename_html, "w") as f:
            f.write('<html><head><style>')
            f.write('body { font-family: Arial, sans-serif; margin: 20px; }')
            f.write('h2 { color: #666; }')
            f.write('.note { margin: 5px 0; padding: 10px; border-radius: 4px; }')
            for task_name, colors in self.task_colors.items():
                f.write(f'.note-{task_name} {{ background: {colors["bg"]}; color: {colors["fg"]}; }}')
            f.write('@media (max-width: 600px) { .note { padding: 8px; font-size: 14px; } }')
            f.write(f'</style></head><body>\n<h2>Notes for {self.today}</h2>\n')
            for n in unique_notes:
                if not n["content"].startswith("Time logged:"):
                    f.write(
                        f'<div class="note note-{n["task"]}" data-task="{n["task"]}"><p><strong>{n["timestamp"]}</strong> [{n["task"]}]: {n["content"]}</p></div>\n')
            f.write('</body></html>\n')
            logger.info("Updated HTML file with %d notes: %s - HTML updated, Spider-Man swings in!", len(unique_notes),
                        note_filename_html)

        # Write to XML
        with open(note_filename_xml, "w") as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<notes date="{self.today}">\n')
            for n in unique_notes:
                f.write(f'  <note task="{n["task"]}" timestamp="{n["timestamp"]}">{n["content"]}</note>\n')
            f.write('</notes>\n')
            logger.info("Updated XML file with %d notes: %s - XML locked, Vault 101 secure!", len(unique_notes),
                        note_filename_xml)

        # Update in-memory notes to reflect the full set
        self.notes = unique_notes

    def generate_report(self):
        report_dir = self.session_dir
        timestamp = self.today

        if self.current_task_start:
            elapsed = (time.time() - self.current_task_start) / 60.0
            self.task_times[self.current_task] += elapsed
            logger.debug("Agent X: Logged %.1f minutes for %s before report - Time logged, Captain Kirk out!", elapsed,
                         self.current_task)
            self.current_task_start = time.time()

        report_filename_html = os.path.join(report_dir, f"report_{timestamp}.html")
        with open(report_filename_html, "w") as report:
            report.write('<!DOCTYPE html>\n<html><head>')
            report.write('<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>')
            report.write('<style>')
            report.write('body { font-family: Arial, sans-serif; margin: 20px; background: #f9f9f9; }')
            report.write('h1 { color: #2c3e50; } h2 { color: #34495e; } h3 { color: #7f8c8d; }')
            report.write('.note { margin: 5px 0; padding: 10px; border-radius: 4px; }')
            for task_name, colors in self.task_colors.items():
                report.write(f'.note-{task_name} {{ background: {colors["bg"]}; color: {colors["fg"]}; }}')
            report.write('.task-group { margin-bottom: 25px; padding: 10px; background: #ecf0f1; border-radius: 8px; }')
            report.write('.summary { border-collapse: collapse; width: 50%; margin-top: 20px; }')
            report.write('.summary td, .summary th { border: 1px solid #ddd; padding: 8px; text-align: left; }')
            report.write('.summary th { background: #3498db; color: white; }')
            report.write('#timeChart { max-width: 500px; margin: 20px auto; }')
            report.write('@media (max-width: 600px) { .note { padding: 8px; font-size: 14px; } }')
            report.write('</style></head><body>\n<h1>Daily Report</h1>\n')
            self._write_html_report(report)
            report.write('<h2>Time Breakdown</h2>\n')
            report.write('<canvas id="timeChart"></canvas>\n')
            report.write('<script>\n')
            report.write('const ctx = document.getElementById("timeChart").getContext("2d");\n')
            report.write('const timeChart = new Chart(ctx, {\n')
            report.write('    type: "pie",\n')
            report.write('    data: {\n')
            report.write('        labels: [')
            labels = [f'"{task.capitalize()}"' for task in self.task_colors.keys()]
            report.write(', '.join(labels) + '],\n')
            report.write('        datasets: [{\n')
            report.write('            data: [')
            times = [f'{self.task_times[task]:.1f}' for task in self.task_colors.keys()]
            report.write(', '.join(times) + '],\n')
            report.write('            backgroundColor: [')
            colors = [f'"{self.task_colors[task]["bg"]}"' for task in self.task_colors.keys()]
            report.write(', '.join(colors) + '],\n')
            report.write('            borderColor: "#fff",\n')
            report.write('            borderWidth: 2\n')
            report.write('        }]\n')
            report.write('    },\n')
            report.write('    options: {\n')
            report.write('        responsive: true,\n')
            report.write('        plugins: {\n')
            report.write('            legend: { position: "top" },\n')
            report.write('            tooltip: {\n')
            report.write('                callbacks: {\n')
            report.write('                    label: function(context) {\n')
            report.write('                        let label = context.label || "";\n')
            report.write('                        if (label) label += ": ";\n')
            report.write('                        label += context.raw + " minutes";\n')
            report.write('                        return label;\n')
            report.write('                    }\n')
            report.write('                }\n')
            report.write('            }\n')
            report.write('        }\n')
            report.write('    }\n')
            report.write('});\n')
            report.write('</script>\n')
            report.write('</body></html>\n')
            logger.info("Generated HTML report with pie chart: %s - Report beamed up, Scotty!", report_filename_html)
            webbrowser.open(f"file://{report_filename_html}")

        report_filename_xml = os.path.join(report_dir, f"report_{timestamp}.xml")
        with open(report_filename_xml, "w") as report:
            report.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<report date="{timestamp}">\n')
            self._write_xml_report(report)
            report.write('</report>\n')
            logger.info("Generated XML report: %s - XML dispatched, Agent 007!", report_filename_xml)

        QMessageBox.information(self, "Report Generated", f"Reports saved in HTML and XML formats in {report_dir}")
        logger.debug("Agent X: Debriefing complete - Reports dispatched to %s, mission accomplished!", report_dir)

    def _write_html_report(self, report):
        report.write(f'<h2>Date: {self.today}</h2>\n')
        total_time = 0
        afk_time = 0
        all_tasks = self.tasks + ["default"]

        for task in all_tasks:
            task_notes = [n for n in self.notes if n["task"] == task and not n["content"].startswith("Time logged:")]
            if task_notes:
                report.write(f'<div class="task-group">\n<h3>{task.upper()}</h3>\n<ul>\n')
                for note in task_notes:
                    report.write(
                        f'<li><div class="note note-{task}"><strong>{note["timestamp"]}</strong> [{task}]: {note["content"]}</div></li>\n')

                task_time = self.task_times[task]
                if task == "default" and any("auto-note" in n["content"] for n in self.notes if n["task"] == task):
                    afk_time += task_time
                else:
                    total_time += task_time

                report.write(f'</ul>\n<p>Tracked Time: {task_time:.1f} minutes</p>\n')
                task_dir = os.path.join(self.session_dir, task)
                if os.path.exists(task_dir):
                    screenshots = [f for f in os.listdir(task_dir) if f.startswith(f"screenshot_{task}")]
                    if screenshots:
                        report.write('<p>Screenshots:</p>\n<ul>\n')
                        for shot in screenshots:
                            report.write(f'<li><a href="{task}/{shot}">{shot}</a></li>\n')
                        report.write('</ul>\n')
                        logger.debug("Agent X: Found %d screenshots for %s - Say cheese, Shutterbug!", len(screenshots),
                                     task)
                    else:
                        logger.debug("Agent X: No screenshots for %s - The camera shy task strikes again!", task)
                else:
                    logger.debug("Agent X: No directory for %s - This task is a ghost, Scooby-Doo!", task)
                report.write('</div>\n')

        report.write('<table class="summary">\n')
        report.write('<tr><th>Metric</th><th>Value</th></tr>\n')
        report.write(f'<tr><td>Total Productive Time</td><td>{total_time:.1f} minutes</td></tr>\n')
        report.write(f'<tr><td>Total AFK Time</td><td>{afk_time:.1f} minutes</td></tr>\n')
        report.write(f'<tr><td>Grand Total Time</td><td>{total_time + afk_time:.1f} minutes</td></tr>\n')
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

                task_time = self.task_times[task]
                if task == "default" and any("auto-note" in n["content"] for n in task_notes):
                    afk_time += task_time
                else:
                    total_time += task_time

                report.write(f'    <time>{task_time:.1f}</time>\n')
                task_dir = os.path.join(self.session_dir, task)
                if os.path.exists(task_dir):
                    screenshots = [f for f in os.listdir(task_dir) if f.startswith(f"screenshot_{task}")]
                    if screenshots:
                        report.write('    <screenshots>\n')
                        for shot in screenshots:
                            report.write(f'      <screenshot>{shot}</screenshot>\n')
                        report.write('    </screenshots>\n')
                        logger.debug("Agent X: XML logged %d screenshots for %s - Snapshot central!", len(screenshots),
                                     task)
                    else:
                        logger.debug("Agent X: No screenshots in XML for %s - Empty gallery, Picasso!", task)
                else:
                    logger.debug("Agent X: No directory for %s in XML - Task vanished, Houdini!", task)
                report.write('  </task>\n')

        report.write(f'  <totals>\n')
        report.write(f'    <productive>{total_time:.1f}</productive>\n')
        report.write(f'    <afk>{afk_time:.1f}</afk>\n')
        report.write(f'    <grand>{total_time + afk_time:.1f}</grand>\n')
        report.write(f'  </totals>\n')

    def closeEvent(self, event):
        if self.current_task_start:
            elapsed = (time.time() - self.current_task_start) / 60.0
            self.task_times[self.current_task] += elapsed
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.notes.append({"task": self.current_task, "timestamp": timestamp,
                               "content": f"Time logged: {elapsed:.1f} minutes for {self.current_task}"})
            logger.debug("Agent X: Logged %.1f minutes for %s on close - Shutdown logged, HAL 9000 out!", elapsed,
                         self.current_task)

        shutdown_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.notes.append({"task": "default", "timestamp": shutdown_time.split(" ")[1],
                           "content": f"the program shut down at {shutdown_time}"})
        self.update_notes_files()

        self.running = False
        logger.debug("Agent X: Shutting down operations - Hasta la vista, baby!")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DailiesApp()
    window.show()
    sys.exit(app.exec())
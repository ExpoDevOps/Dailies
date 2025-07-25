import sys
import os
import time
import logging
import webbrowser
from datetime import datetime, date
from xml.etree import ElementTree as ET
import pyautogui
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
QPushButton, QTextEdit, QLabel, QFrame, QMessageBox, QDateEdit, QDialog, QFormLayout, QComboBox, QCalendarWidget, QLineEdit, QGridLayout, QListWidget, QListWidgetItem, QInputDialog, QCheckBox, QColorDialog)
from PyQt6.QtCore import QTimer, Qt, QDate, QPoint, pyqtSignal
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

def format_minutes(minutes):
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    return f"{hours}h {mins}m"

class EventCalendar(QCalendarWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.event_dates = set() # set of QDate
        self.events = {}  # date_str: list of dicts

    def paintCell(self, painter, rect, date):
        super().paintCell(painter, rect, date)
        date_str = date.toString("yyyy-MM-dd")
        if date_str in self.events:
            events = self.events[date_str][:4]
            dot_radius = 3
            dot_diam = dot_radius * 2
            spacing = 2
            total_width = len(events) * dot_diam + (len(events) - 1) * spacing
            start_x = rect.x() + (rect.width() - total_width) // 2
            y = rect.y() + rect.height() - dot_radius - 2  # near bottom
            for i, event in enumerate(events):
                x = start_x + i * (dot_diam + spacing)
                painter.setBrush(QColor(event.get('color', '#FF0000')))
                painter.drawEllipse(x, y, dot_diam, dot_diam)

class EventItemWidget(QWidget):
    complete_changed = pyqtSignal(bool)
    text_changed = pyqtSignal(str)
    color_changed = pyqtSignal(str)

    def __init__(self, text, complete, color_hex, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(complete)
        self.checkbox.toggled.connect(self.complete_changed.emit)
        self.text_edit = QLineEdit(text)
        self.text_edit.textChanged.connect(self.text_changed.emit)
        self.color_btn = QPushButton()
        self.color_btn.setFixedSize(20, 20)
        self.set_color(color_hex)
        self.color_btn.clicked.connect(self.pick_color)
        self.layout.addWidget(self.checkbox)
        self.layout.addWidget(self.text_edit)
        self.layout.addStretch()
        self.layout.addWidget(self.color_btn)

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.current_color))
        if color.isValid():
            new_color = color.name()
            self.set_color(new_color)
            self.color_changed.emit(new_color)

    def set_color(self, hex_color):
        self.current_color = hex_color
        self.color_btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #000;")

class DailiesApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dailies")
        self.setGeometry(100, 100, 800, 800)

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
        self.current_subtask = ""

        # Shift tracking
        self.shifts = []
        self.clock_in_time = None
        self.clock_in_display_time = None # For display
        self.lunch_start = None
        self.total_lunches = 0.0 # In minutes

        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # Left toolbar
        self.left_toolbar = QFrame()
        self.left_toolbar.setFrameShape(QFrame.Shape.Box)
        self.left_toolbar_layout = QVBoxLayout(self.left_toolbar)
        self.main_layout.addWidget(self.left_toolbar, stretch=1)

        # Task buttons at top, vertical
        self.task_frame = QWidget()
        self.task_layout = QVBoxLayout(self.task_frame)
        self.tasks = ["code", "research", "building", "meeting", "field", "social"]
        self.task_buttons = {}
        for task in self.tasks:
            btn = QPushButton(task)
            btn.setStyleSheet(
                f"background-color: {self.task_colors[task]['bg']}; color: {self.task_colors[task]['fg']}")
            btn.clicked.connect(lambda checked, t=task: self.set_task(t))
            self.task_layout.addWidget(btn)
            self.task_buttons[task] = btn
        self.left_toolbar_layout.addWidget(self.task_frame)

        # Subtask combo box
        self.subtask_combo = QComboBox()
        self.subtask_combo.setEditable(True)
        self.subtask_combo.setPlaceholderText("Enter Subtask")
        self.subtask_combo.currentTextChanged.connect(self.set_subtask)
        self.left_toolbar_layout.addWidget(self.subtask_combo)

        # Middle space
        self.left_toolbar_layout.addStretch()

        # Utility buttons at bottom
        # Save button (light blue)
        self.save_button = QPushButton("Save")
        self.save_button.setStyleSheet("background-color: lightblue;")
        self.save_button.clicked.connect(self.save_note)
        self.left_toolbar_layout.addWidget(self.save_button)

        # Generate Report button (light purple)
        self.report_button = QPushButton("Generate Report")
        self.report_button.setStyleSheet("background-color: #CBC3E3;")
        self.report_button.clicked.connect(self.generate_report)
        self.left_toolbar_layout.addWidget(self.report_button)

        # Generate Past Report button (white)
        self.past_report_button = QPushButton("Generate Past Report")
        self.past_report_button.setStyleSheet("background-color: white;")
        self.past_report_button.clicked.connect(self.generate_past_report)
        self.left_toolbar_layout.addWidget(self.past_report_button)

        # Work buttons
        self.work_in_btn = QPushButton("WORK IN")
        self.work_in_btn.clicked.connect(self.work_in)
        self.left_toolbar_layout.addWidget(self.work_in_btn)

        self.lunch_out_btn = QPushButton("LUNCH OUT")
        self.lunch_out_btn.setEnabled(False)
        self.lunch_out_btn.clicked.connect(self.lunch_out)
        self.left_toolbar_layout.addWidget(self.lunch_out_btn)

        self.lunch_in_btn = QPushButton("LUNCH IN")
        self.lunch_in_btn.setEnabled(False)
        self.lunch_in_btn.clicked.connect(self.lunch_in)
        self.left_toolbar_layout.addWidget(self.lunch_in_btn)

        self.work_out_btn = QPushButton("WORK OUT")
        self.work_out_btn.setEnabled(False)
        self.work_out_btn.clicked.connect(self.work_out)
        self.left_toolbar_layout.addWidget(self.work_out_btn)

        self.shift_status_label = QLabel("Not Clocked In")
        self.shift_status_label.setStyleSheet("color: orange")
        self.left_toolbar_layout.addWidget(self.shift_status_label)

        self.worked_time_label = QLabel("Worked: 0h 0m")
        self.worked_time_label.setStyleSheet("color: green")
        self.left_toolbar_layout.addWidget(self.worked_time_label)

        # Middle panel (notes and log)
        self.note_panel = QWidget()
        self.note_layout = QVBoxLayout(self.note_panel)
        self.main_layout.addWidget(self.note_panel, stretch=2) # Reduced stretch to make room

        # Note section
        self.note_label = QLabel("speak puny mortal")
        self.note_layout.addWidget(self.note_label)

        self.note_text = QTextEdit()
        self.note_text.setMinimumHeight(200)
        self.note_layout.addWidget(self.note_text, stretch=1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: cyan")
        self.note_layout.addWidget(self.status_label)

        # Log window below notes
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(150)
        self.note_layout.addWidget(self.log_text)

        # Right toolbar
        self.right_toolbar = QFrame()
        self.right_toolbar.setFrameShape(QFrame.Shape.Box)
        self.right_toolbar_layout = QVBoxLayout(self.right_toolbar)
        self.main_layout.addWidget(self.right_toolbar, stretch=1)

        # Calendar at top
        self.calendar = EventCalendar()
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.ISOWeekNumbers)
        self.calendar.setStyleSheet("""\
QCalendarWidget QHeaderView::section:vertical {\
border-right: 1px solid black;\
}\
""")
        self.right_toolbar_layout.addWidget(self.calendar)

        # Event list below calendar
        self.event_list = QListWidget()
        self.right_toolbar_layout.addWidget(self.event_list)

        # Buttons for adding and deleting events
        event_buttons_layout = QHBoxLayout()
        add_event_btn = QPushButton("Add Event")
        add_event_btn.clicked.connect(self.add_event)
        event_buttons_layout.addWidget(add_event_btn)
        delete_event_btn = QPushButton("Delete Event")
        delete_event_btn.clicked.connect(self.delete_event)
        event_buttons_layout.addWidget(delete_event_btn)
        self.right_toolbar_layout.addLayout(event_buttons_layout)

        # Events data
        self.events = {} # date_str: list of {'text': str, 'complete': bool}
        self.load_events()
        self.calendar.events = self.events
        self.calendar.event_dates = {QDate.fromString(d, "yyyy-MM-dd") for d in self.events}
        self.calendar.selectionChanged.connect(self.update_event_list)

        # Middle space for right toolbar
        self.right_toolbar_layout.addStretch()

        # Calculator at bottom
        self.expression = ''
        self.calculator = QWidget()
        calc_layout = QVBoxLayout(self.calculator)
        self.display = QLineEdit('0')
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        calc_layout.addWidget(self.display)
        clear_btn = QPushButton('C')
        clear_btn.clicked.connect(self.calc_button_clicked)
        calc_layout.addWidget(clear_btn)
        grid = QGridLayout()
        names = [
            ['7', '8', '9', '/'],
            ['4', '5', '6', '*'],
            ['1', '2', '3', '-'],
            ['0', '.', '=', '+']
        ]
        for i in range(4):
            for j in range(4):
                btn = QPushButton(names[i][j])
                btn.clicked.connect(self.calc_button_clicked)
                grid.addWidget(btn, i, j)
        calc_layout.addLayout(grid)
        self.right_toolbar_layout.addWidget(self.calculator)

        # Load shifts after UI setup
        self.load_work_shifts()

        # Load recent subtasks
        self.load_recent_subtasks()

        # Timers
        self.running = True
        self.prompt_timer = QTimer()
        self.prompt_timer.timeout.connect(self.show_prompt)
        self.prompt_timer.start(15 * 60 * 1000) # 15 minutes

        self.time_log_timer = QTimer()
        self.time_log_timer.timeout.connect(self.log_time_note)
        self.time_log_timer.start(60 * 1000) # 1 minute

        self.worked_timer = QTimer()
        self.worked_timer.timeout.connect(self.update_worked_time)
        self.worked_timer.start(60 * 1000) # Update every minute

        self.update_shift_buttons()
        self.update_worked_time()

        self.update_event_list()

        logger.debug("Agent X: Surveillance and time logging timers activated - Hasta la vista, idle time!")

    def load_events(self):
        self.events = {}
        for date_dir in os.listdir(BASE_DIR):
            if len(date_dir) == 10 and date_dir.count('-') == 2: # Basic check for YYYY-MM-DD format
                session_dir = os.path.join(BASE_DIR, date_dir)
                events_file = os.path.join(session_dir, "events.xml")
                if os.path.exists(events_file):
                    try:
                        tree = ET.parse(events_file)
                        root = tree.getroot()
                        event_list = [{'text': event.text.strip(), 'complete': event.get("complete", "false").lower() == "true", 'color': event.get("color", "#FFFFFF")}
                                      for event in root.findall("event") if event.text and event.text.strip()]
                        if event_list:
                            self.events[date_dir] = event_list
                            logger.info("Loaded events from %s", events_file)
                    except ET.ParseError:
                        logger.error("Failed to parse events.xml for %s", date_dir)

    def save_events(self, date_str):
        event_list = self.events.get(date_str, [])
        session_dir = os.path.join(BASE_DIR, date_str)
        os.makedirs(session_dir, exist_ok=True)
        events_file = os.path.join(session_dir, "events.xml")
        if event_list:
            root = ET.Element("events")
            for event in event_list:
                event_elem = ET.SubElement(root, "event")
                event_elem.set("complete", "true" if event['complete'] else "false")
                event_elem.set("color", event.get('color', "#FFFFFF"))
                event_elem.text = event['text']
            tree = ET.ElementTree(root)
            tree.write(events_file, encoding="utf-8", xml_declaration=True)
            logger.info("Saved events to %s", events_file)
        else:
            if os.path.exists(events_file):
                os.remove(events_file)
            logger.info("Removed empty events.xml for %s", date_str)

    def update_event_list(self):
        date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
        events = self.events.get(date_str, [])
        self.event_list.clear()
        for idx, event in enumerate(events):
            item = QListWidgetItem()
            widget = EventItemWidget(event['text'], event['complete'], event.get('color', '#FFFFFF'))
            widget.complete_changed.connect(lambda checked, i=idx: self.update_event_complete(date_str, i, checked))
            widget.text_changed.connect(lambda text, i=idx: self.update_event_text(date_str, i, text))
            widget.color_changed.connect(lambda col, i=idx: self.update_event_color(date_str, i, col))
            self.event_list.addItem(item)
            self.event_list.setItemWidget(item, widget)
            item.setSizeHint(widget.sizeHint())

    def update_event_complete(self, date_str, idx, checked):
        if date_str in self.events:
            self.events[date_str][idx]['complete'] = checked
            self.save_events(date_str)

    def update_event_text(self, date_str, idx, text):
        if date_str in self.events:
            self.events[date_str][idx]['text'] = text.strip()
            self.save_events(date_str)

    def update_event_color(self, date_str, idx, color):
        if date_str in self.events:
            self.events[date_str][idx]['color'] = color
            self.save_events(date_str)

    def add_event(self):
        date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
        text, ok = QInputDialog.getText(self, "Add Event", "Enter event text:")
        if ok and text.strip():
            if date_str not in self.events:
                self.events[date_str] = []
            self.events[date_str].append({'text': text.strip(), 'complete': False, 'color': '#FFFFFF'})
            self.save_events(date_str)
            qdate = QDate.fromString(date_str, "yyyy-MM-dd")
            self.calendar.event_dates.add(qdate)
            self.calendar.update()
            self.update_event_list()

    def delete_event(self):
        current_row = self.event_list.currentRow()
        if current_row < 0:
            return
        date_str = self.calendar.selectedDate().toString("yyyy-MM-dd")
        if date_str in self.events:
            del self.events[date_str][current_row]
            if not self.events[date_str]:
                del self.events[date_str]
                qdate = QDate.fromString(date_str, "yyyy-MM-dd")
                self.calendar.event_dates.discard(qdate)
                self.calendar.update()
            self.save_events(date_str)
            self.update_event_list()

    def calc_button_clicked(self):
        button = self.sender()
        text = button.text()
        if text == 'C':
            self.expression = ''
            self.display.setText('0')
        elif text == '=':
            try:
                result = eval(self.expression)
                self.display.setText(str(result))
                self.expression = str(result)
            except:
                self.display.setText('Error')
                self.expression = ''
        else:
            self.expression += text
            self.display.setText(self.expression)

    def set_subtask(self, subtask):
        self.current_subtask = subtask.strip()

    def load_recent_subtasks(self):
        subtasks = []
        note_filename_xml = os.path.join(self.session_dir, "notes.xml")
        if os.path.exists(note_filename_xml):
            try:
                tree = ET.parse(note_filename_xml)
                root = tree.getroot()
                for note in sorted(root.findall("note"), key=lambda n: n.get("timestamp"), reverse=True):
                    subtask = note.get("subtask")
                    if subtask and subtask not in subtasks:
                        subtasks.append(subtask)
                    if len(subtasks) == 10:
                        break
            except ET.ParseError:
                logger.error("Failed to parse notes.xml for subtasks")
        for subtask in subtasks:
            self.subtask_combo.addItem(subtask)

    def work_in(self):
        if self.clock_in_time:
            QMessageBox.warning(self, "Already Clocked In", "You are already clocked in.")
            return
        now = datetime.now()
        self.clock_in_time = now.timestamp()
        self.clock_in_display_time = now.strftime("%H:%M")
        self.shifts.append({"type": "work_in", "timestamp": now.strftime("%H:%M:%S")})
        self.update_shifts_file()
        self.update_shift_status()
        self.update_shift_buttons()
        self.log_ui(f"{now.strftime('%Y-%m-%d %H:%M:%S')} - Clocked in")
        logger.debug("Agent X: Worked in - Shift started!")

    def work_out(self):
        if not self.clock_in_time:
            QMessageBox.warning(self, "Not Clocked In", "You must work in first.")
            return
        if self.lunch_start:
            QMessageBox.warning(self, "On Lunch", "End lunch first before working out.")
            return
        now = datetime.now()
        clock_out_time = now.timestamp()
        elapsed = (clock_out_time - self.clock_in_time) / 60.0
        worked = elapsed - self.total_lunches
        self.shifts.append({"type": "work_out", "timestamp": now.strftime("%H:%M:%S"), "worked": worked})
        self.update_shifts_file()
        self.clock_in_time = None
        self.clock_in_display_time = None
        self.lunch_start = None
        self.total_lunches = 0.0
        self.update_shift_status()
        self.update_shift_buttons()
        self.update_worked_time()
        self.log_ui(f"{now.strftime('%Y-%m-%d %H:%M:%S')} - Clocked out (Worked: {format_minutes(worked)})")
        logger.debug("Agent X: Worked out - Shift ended with %.1f minutes worked!", worked)

    def lunch_out(self):
        if self.lunch_start:
            QMessageBox.warning(self, "Already on Lunch", "You are already on lunch.")
            return
        now = datetime.now()
        self.lunch_start = now.timestamp()
        self.shifts.append({"type": "lunch_out", "timestamp": now.strftime("%H:%M:%S")})
        self.update_shifts_file()
        self.prompt_timer.stop() # Disable prompts during lunch
        self.save_to_task("default", f"LUNCH BREAK STARTED at {now.strftime('%H:%M:%S')}")
        self.update_shift_status()
        self.update_shift_buttons()
        self.update_worked_time()
        self.log_ui(f"{now.strftime('%Y-%m-%d %H:%M:%S')} - Lunch started")

    def lunch_in(self):
        if not self.lunch_start:
            QMessageBox.warning(self, "No Lunch Started", "Start lunch first.")
            return
        now = datetime.now()
        elapsed = (now.timestamp() - self.lunch_start) / 60.0
        self.total_lunches += elapsed
        self.shifts.append({"type": "lunch_in", "timestamp": now.strftime("%H:%M:%S"), "duration": elapsed})
        self.update_shifts_file()
        self.prompt_timer.start(15 * 60 * 1000) # Re-enable prompts
        self.save_to_task("default", f"LUNCH BREAK ENDED at {now.strftime('%H:%M:%S')} (Duration: {elapsed:.1f} min)")
        self.lunch_start = None
        self.update_shift_status()
        self.update_shift_buttons()
        self.update_worked_time()
        self.log_ui(f"{now.strftime('%Y-%m-%d %H:%M:%S')} - Lunch ended (Duration: {elapsed:.1f} min)")

    def update_shift_status(self):
        if self.clock_in_time:
            status = f"Clocked In since {self.clock_in_display_time}"
            if self.lunch_start:
                status += " | On Lunch"
            self.shift_status_label.setText(status)
        else:
            self.shift_status_label.setText("Not Clocked In")

    def update_shift_buttons(self):
        clocked_in = bool(self.clock_in_time)
        on_lunch = bool(self.lunch_start)

        self.work_in_btn.setEnabled(not clocked_in)
        self.work_out_btn.setEnabled(clocked_in and not on_lunch)
        self.lunch_out_btn.setEnabled(clocked_in and not on_lunch)
        self.lunch_in_btn.setEnabled(on_lunch)

    def update_worked_time(self):
        if not self.clock_in_time:
            self.worked_time_label.setText("Worked: 0h 0m")
            return
        current_time = time.time()
        total_elapsed = (current_time - self.clock_in_time) / 60.0
        current_lunch = (current_time - self.lunch_start) / 60.0 if self.lunch_start else 0.0
        worked = total_elapsed - self.total_lunches - current_lunch
        if worked < 0:
            worked = 0.0 # Prevent negative
        self.worked_time_label.setText(f"Worked: {format_minutes(worked)}")

    def load_work_shifts(self):
        shifts_filename = os.path.join(self.session_dir, "shifts.xml")
        if os.path.exists(shifts_filename):
            try:
                tree = ET.parse(shifts_filename)
                root = tree.getroot()
                is_clocked_in = False
                is_on_lunch = False
                for shift in root.findall("shift"):
                    shift_type = shift.get("type")
                    timestamp = shift.get("timestamp")
                    duration = float(shift.get("duration", 0))
                    worked = float(shift.get("worked", 0))
                    self.shifts.append({"type": shift_type, "timestamp": timestamp, "duration": duration, "worked": worked})
                    if shift_type == "work_in":
                        is_clocked_in = True
                        self.clock_in_time = datetime.strptime(f"{self.today} {timestamp}", "%Y-%m-%d %H:%M:%S").timestamp()
                        self.clock_in_display_time = timestamp[:5] # HH:MM
                    elif shift_type == "work_out":
                        is_clocked_in = False
                    elif shift_type == "lunch_out":
                        is_on_lunch = True
                        if is_clocked_in and is_on_lunch:
                            self.lunch_start = datetime.strptime(f"{self.today} {timestamp}", "%Y-%m-%d %H:%M:%S").timestamp()
                    elif shift_type == "lunch_in":
                        is_on_lunch = False
                        self.total_lunches += duration
                if not is_clocked_in:
                    self.clock_in_time = None
                    self.clock_in_display_time = None
                if not is_on_lunch:
                    self.lunch_start = None
                logger.info("Loaded %d shifts from %s", len(self.shifts), shifts_filename)
            except ET.ParseError:
                logger.error("Failed to parse shifts.xml")
        self.update_shift_status()
        self.update_shift_buttons()
        self.update_worked_time()
        if self.lunch_start:
            self.prompt_timer.stop() # Disable if loaded on lunch

    def update_shifts_file(self):
        shifts_filename = os.path.join(self.session_dir, "shifts.xml")
        with open(shifts_filename, "w") as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<shifts date="{self.today}">\n')
            for s in self.shifts:
                duration = s.get("duration", 0)
                worked = s.get("worked", 0)
                f.write(f' <shift type="{s["type"]}" timestamp="{s["timestamp"]}" duration="{duration}" worked="{worked}"></shift>\n')
            f.write('</shifts>\n')
        logger.info("Updated shifts XML: %s", shifts_filename)

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

        subtask = self.current_subtask
        if subtask and subtask not in [self.subtask_combo.itemText(i) for i in range(self.subtask_combo.count())]:
            self.subtask_combo.insertItem(0, subtask)
            if self.subtask_combo.count() > 10:
                self.subtask_combo.removeItem(10)

        self.notes.append({"task": task, "timestamp": timestamp, "content": note, "subtask": subtask})
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

        # Log note saved in UI
        now = datetime.now()
        subtask_str = f" /{subtask}" if subtask else ""
        self.log_ui(f"{now.strftime('%Y-%m-%d %H:%M:%S')} - Note saved in [{task}{subtask_str}]")

    def load_existing_notes(self):
        note_filename_xml = os.path.join(self.session_dir, "notes.xml")
        self.notes = []
        if os.path.exists(note_filename_xml):
            try:
                tree = ET.parse(note_filename_xml)
                root = tree.getroot()
                for note in root.findall("note"):
                    task = note.get("task")
                    timestamp = note.get("timestamp")
                    subtask = note.get("subtask", "")
                    content = note.text if note.text is not None else ""
                    self.notes.append({"task": task, "timestamp": timestamp, "subtask": subtask, "content": content})
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

    def check_last_shutdown(self):
        note_filename_xml = os.path.join(self.session_dir, "notes.xml")
        if os.path.exists(note_filename_xml):
            try:
                tree = ET.parse(note_filename_xml)
                root = tree.getroot()
                shutdown_notes = [n for n in root.findall("note") if "the program shut down at" in (n.text or "")]
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
            except (ET.ParseError, ValueError) as e:
                logger.error("Failed to parse shutdown time: %s - Time vortex malfunction!", str(e))
        else:
            logger.info("No previous shutdown note found - Fresh start, Neo!")

    def log_time_note(self):
        if self.current_task_start:
            elapsed = (time.time() - self.current_task_start) / 60.0
            task = self.current_task
            self.task_times[task] += elapsed
            timestamp = datetime.now().strftime("%H:%M:%S")
            note_content = f"Time logged: {elapsed:.1f} minutes for {task}"
            self.notes.append({"task": task, "timestamp": timestamp, "content": note_content, "subtask": ""})
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
                        "subtask": note.get("subtask", ""),
                        "content": note.text if note.text is not None else ""
                    })
                logger.debug("Agent X: Retrieved %d existing notes from XML - Memory banks loaded, R2-D2!",
                             len(existing_notes))
            except ET.ParseError:
                logger.error("Agent X: Failed to parse notes.xml for merging - XML rebellion detected!")

        # Merge existing notes with new ones, avoiding duplicates
        all_notes = existing_notes + self.notes
        # Remove duplicates based on task, timestamp, subtask, and content
        unique_notes = []
        seen = set()
        for note in all_notes:
            note_key = (note["task"], note["timestamp"], note["subtask"], note["content"])
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
                    subtask_str = f" /{n['subtask']}" if n['subtask'] else ""
                    f.write(
                        f'<div class="note note-{n["task"]}" data-task="{n["task"]}"><p><strong>{n["timestamp"]}</strong> [{n["task"]}{subtask_str}]: {n["content"]}</p></div>\n')
            f.write('</body></html>\n')
        logger.info("Updated HTML file with %d notes: %s - HTML updated, Spider-Man swings in!", len(unique_notes),
                    note_filename_html)

        # Write to XML
        with open(note_filename_xml, "w") as f:
            f.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<notes date="{self.today}">\n')
            for n in unique_notes:
                subtask_attr = f' subtask="{n["subtask"]}"' if n["subtask"] else ""
                f.write(f' <note task="{n["task"]}" timestamp="{n["timestamp"]}"{subtask_attr}>{n["content"]}</note>\n')
            f.write('</notes>\n')
        logger.info("Updated XML file with %d notes: %s - XML locked, Vault 101 secure!", len(unique_notes),
                    note_filename_xml)

        # Update in-memory notes to reflect the full set
        self.notes = unique_notes

    def generate_report(self, report_date=None, session_dir=None, notes=None, task_times=None, shifts=None, total_lunches=0.0):
        if report_date is None:
            report_date = self.today
        if session_dir is None:
            session_dir = self.session_dir
        if notes is None:
            notes = self.notes
        if task_times is None:
            task_times = self.task_times
        if shifts is None:
            shifts = self.shifts
        if total_lunches == 0.0:
            total_lunches = self.total_lunches

        if self.current_task_start and notes is self.notes:
            elapsed = (time.time() - self.current_task_start) / 60.0
            self.task_times[self.current_task] += elapsed
            logger.debug("Agent X: Logged %.1f minutes for %s before report - Time logged, Captain Kirk out!", elapsed,
                         self.current_task)
            self.current_task_start = time.time()

        report_filename_html = os.path.join(session_dir, f"report_{report_date}.html")
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
            self._write_html_report(report, report_date, notes, task_times, session_dir)
            report.write('<h2>Time Breakdown</h2>\n')
            report.write('<canvas id="timeChart"></canvas>\n')
            report.write('<script>\n')
            report.write('const ctx = document.getElementById("timeChart").getContext("2d");\n')
            report.write('const timeChart = new Chart(ctx, {\n')
            report.write(' type: "pie",\n')
            report.write(' data: {\n')
            report.write(' labels: [')
            labels = [f'"{task.capitalize()}"' for task in self.task_colors.keys()]
            report.write(', '.join(labels) + '],\n')
            report.write(' datasets: [{\n')
            report.write(' data: [')
            times = [f'{task_times[task]:.1f}' for task in self.task_colors.keys()]
            report.write(', '.join(times) + '],\n')
            report.write(' backgroundColor: [')
            colors = [f'"{self.task_colors[task]["bg"]}"' for task in self.task_colors.keys()]
            report.write(', '.join(colors) + '],\n')
            report.write(' borderColor: "#fff",\n')
            report.write(' borderWidth: 2\n')
            report.write(' }]\n')
            report.write(' },\n')
            report.write(' options: {\n')
            report.write(' responsive: true,\n')
            report.write(' plugins: {\n')
            report.write(' legend: { position: "top" },\n')
            report.write(' tooltip: {\n')
            report.write(' callbacks: {\n')
            report.write(' label: function(context) {\n')
            report.write(' let label = context.label || "";\n')
            report.write(' if (label) label += ": ";\n')
            report.write(' label += context.raw + " minutes";\n')
            report.write(' return label;\n')
            report.write(' }\n')
            report.write(' }\n')
            report.write(' }\n')
            report.write(' }\n')
            report.write(' }\n')
            report.write('});\n')
            report.write('</script>\n')

            # Add shift summary
            report.write('<h2>Shift Summary</h2>\n')
            report.write('<table class="summary">\n')
            report.write('<tr><th>Metric</th><th>Value</th></tr>\n')
            total_worked = sum(s.get("worked", 0) for s in shifts if s["type"] == "work_out")
            report.write(f'<tr><td>Total Worked</td><td>{format_minutes(total_worked)}</td></tr>\n')
            report.write(f'<tr><td>Total Lunch Time</td><td>{format_minutes(total_lunches)}</td></tr>\n')
            report.write('</table>\n')

            report.write('</body></html>\n')
        logger.info("Generated HTML report with pie chart: %s - Report beamed up, Scotty!", report_filename_html)
        webbrowser.open(f"file://{report_filename_html}")

        report_filename_xml = os.path.join(session_dir, f"report_{report_date}.xml")
        with open(report_filename_xml, "w") as report:
            report.write(f'<?xml version="1.0" encoding="UTF-8"?>\n<report date="{report_date}">\n')
            self._write_xml_report(report, report_date, notes, task_times, session_dir)
            report.write('</report>\n')
        logger.info("Generated XML report: %s - XML dispatched, Agent 007!", report_filename_xml)

        QMessageBox.information(self, "Report Generated", f"Reports saved in HTML and XML formats in {session_dir}")
        logger.debug("Agent X: Debriefing complete - Reports dispatched to %s, mission accomplished!", session_dir)

    def _write_html_report(self, report, report_date, notes, task_times, session_dir):
        report.write(f'<h2>Date: {report_date}</h2>\n')
        total_time = 0
        afk_time = 0
        all_tasks = self.tasks + ["default"]

        for task in all_tasks:
            task_notes = [n for n in notes if n["task"] == task and not n["content"].startswith("Time logged:")]
            if task_notes:
                report.write(f'<div class="task-group">\n<h3>{task.upper()}</h3>\n<ul>\n')
                for note in task_notes:
                    subtask_str = f" /{note['subtask']}" if note.get('subtask') else ""
                    report.write(
                        f'<li><div class="note note-{task}"><strong>{note["timestamp"]}</strong> [{task}{subtask_str}]: {note["content"]}</div></li>\n')

                task_time = task_times[task]
                if task == "default" and any("auto-note" in n["content"] for n in notes if n["task"] == task):
                    afk_time += task_time
                else:
                    total_time += task_time

                report.write(f'</ul>\n<p>Tracked Time: {task_time:.1f} minutes</p>\n')
                task_dir = os.path.join(session_dir, task)
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

        events = self.events.get(report_date, [])
        if events:
            report.write('<h2>Events</h2>\n<ul>\n')
            for event in events:
                status = "Completed" if event['complete'] else "Pending"
                color = event.get('color', '#FFFFFF')
                report.write(f'<li style="background-color: {color}; padding: 5px;">{event["text"]} ({status})</li>\n')
            report.write('</ul>\n')

    def _write_xml_report(self, report, report_date, notes, task_times, session_dir):
        total_time = 0
        afk_time = 0
        all_tasks = self.tasks + ["default"]

        for task in all_tasks:
            task_notes = [n for n in notes if n["task"] == task]
            if task_notes:
                report.write(f' <task name="{task}">\n')
                for note in task_notes:
                    subtask_attr = f' subtask="{note["subtask"]}"' if note.get("subtask") else ""
                    report.write(f' <note task="{task}" timestamp="{note["timestamp"]}"{subtask_attr}>{note["content"]}</note>\n')

                task_time = task_times[task]
                if task == "default" and any("auto-note" in n["content"] for n in task_notes):
                    afk_time += task_time
                else:
                    total_time += task_time

                report.write(f' <time>{task_time:.1f}</time>\n')
                task_dir = os.path.join(session_dir, task)
                if os.path.exists(task_dir):
                    screenshots = [f for f in os.listdir(task_dir) if f.startswith(f"screenshot_{task}")]
                    if screenshots:
                        report.write(' <screenshots>\n')
                        for shot in screenshots:
                            report.write(f' <screenshot>{shot}</screenshot>\n')
                        report.write(' </screenshots>\n')
                        logger.debug("Agent X: XML logged %d screenshots for %s - Snapshot central!", len(screenshots),
                                     task)
                    else:
                        logger.debug("Agent X: No screenshots in XML for %s - Empty gallery, Picasso!", task)
                else:
                    logger.debug("Agent X: No directory for %s in XML - Task vanished, Houdini!", task)
                report.write(' </task>\n')

        events = self.events.get(report_date, [])
        if events:
            report.write(' <events>\n')
            for event in events:
                report.write(f' <event complete="{str(event["complete"]).lower()}" color="{event.get("color", "#FFFFFF")}">{event["text"]}</event>\n')
            report.write(' </events>\n')

        report.write(f' <totals>\n')
        report.write(f' <productive>{total_time:.1f}</productive>\n')
        report.write(f' <afk>{afk_time:.1f}</afk>\n')
        report.write(f' <grand>{total_time + afk_time:.1f}</grand>\n')
        report.write(f' </totals>\n')

    def generate_past_report(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Date for Past Report")
        layout = QFormLayout(dialog)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDate(QDate.currentDate().addDays(-1)) # Default to yesterday
        layout.addRow("Select Date:", date_edit)

        generate_btn = QPushButton("Generate")
        generate_btn.clicked.connect(lambda: self._process_past_report(date_edit.date().toPyDate(), dialog))
        layout.addWidget(generate_btn)

        dialog.exec()

    def _process_past_report(self, selected_date, dialog):
        report_date = selected_date.strftime("%Y-%m-%d")
        session_dir = os.path.join(BASE_DIR, report_date)
        if not os.path.exists(session_dir):
            QMessageBox.warning(self, "No Data", f"No session data found for {report_date}.")
            return

        note_filename_xml = os.path.join(session_dir, "notes.xml")
        if not os.path.exists(note_filename_xml):
            QMessageBox.warning(self, "No Notes", f"No notes.xml found for {report_date}.")
            return

        shifts_filename = os.path.join(session_dir, "shifts.xml")
        past_shifts = []
        past_total_lunches = 0.0
        if os.path.exists(shifts_filename):
            try:
                tree = ET.parse(shifts_filename)
                root = tree.getroot()
                for shift in root.findall("shift"):
                    shift_type = shift.get("type")
                    duration = float(shift.get("duration", 0))
                    worked = float(shift.get("worked", 0))
                    past_shifts.append({"type": shift_type, "duration": duration, "worked": worked})
                    if shift_type == "lunch_in":
                        past_total_lunches += duration
            except ET.ParseError:
                logger.error("Failed to parse past shifts.xml for %s", report_date)

        past_notes = []
        past_task_times = {task: 0.0 for task in self.task_colors.keys()}
        if os.path.exists(note_filename_xml):
            try:
                tree = ET.parse(note_filename_xml)
                root = tree.getroot()
                for note in root.findall("note"):
                    task = note.get("task")
                    timestamp = note.get("timestamp")
                    subtask = note.get("subtask", "")
                    content = note.text if note.text is not None else ""
                    past_notes.append({"task": task, "timestamp": timestamp, "subtask": subtask, "content": content})
                    if content.startswith("Time logged:"):
                        try:
                            minutes = float(content.split(" ")[2])
                            past_task_times[task] += minutes
                        except (IndexError, ValueError):
                            logger.error("Failed to parse time from past note: %s", content)
                logger.info("Loaded %d notes for past report on %s", len(past_notes), report_date)
            except ET.ParseError:
                logger.error("Failed to parse past notes.xml for %s", report_date)

        self.generate_report(report_date, session_dir, past_notes, past_task_times, past_shifts, past_total_lunches)
        dialog.close()

    def log_ui(self, message):
        self.log_text.append(message)

    def closeEvent(self, event):
        if self.clock_in_time:
            reply = QMessageBox.question(self, "Still Clocked In", "You are still clocked in. Clock out now?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.work_out()
        if self.lunch_start:
            reply = QMessageBox.question(self, "Still on Lunch", "You are still on lunch. End lunch now?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.lunch_in()

        if self.current_task_start:
            elapsed = (time.time() - self.current_task_start) / 60.0
            self.task_times[self.current_task] += elapsed
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.notes.append({"task": self.current_task, "timestamp": timestamp,
                               "content": f"Time logged: {elapsed:.1f} minutes for {self.current_task}", "subtask": ""})
            logger.debug("Agent X: Logged %.1f minutes for %s on close - Shutdown logged, HAL 9000 out!", elapsed,
                         self.current_task)

        shutdown_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.notes.append({"task": "default", "timestamp": shutdown_time.split(" ")[1],
                           "content": f"the program shut down at {shutdown_time}", "subtask": ""})
        self.update_notes_files()

        # Auto-generate report on close
        self.generate_report()

        self.running = False
        logger.debug("Agent X: Shutting down operations - Hasta la vista, baby!")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DailiesApp()
    window.show()
    sys.exit(app.exec())
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

class NoteApp:
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
        self.current_task = tk.StringVar(value="default")  # Changed from "None" to "default"
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
        # Auto-notes always go to "default"
        auto_note = f"user did not leave note - leaving auto-note for timestamp and time summation"
        self.save_to_task("default", auto_note)
        self.prompt_active = False

    def save_to_task(self, task, note):
        task_dir = os.path.join(self.session_dir, task)
        os.makedirs(task_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%H:%M:%S")
        note_filename = os.path.join(task_dir, f"{task}_notes.txt")
        with open(note_filename, "a") as f:
            f.write(f"[{timestamp}] {note}\n\n")

        screenshot = pyautogui.screenshot()
        screenshot_filename = os.path.join(task_dir, f"screenshot_{task}_{timestamp.replace(':', '-')}.png")
        screenshot.save(screenshot_filename)

        self.note_text.delete("1.0", tk.END)
        messagebox.showinfo("saved", f"note and screenshot saved for {task}!")

    def generate_report(self):
        report_filename = os.path.join(self.session_dir, f"report_{self.today}.txt")
        with open(report_filename, "w") as report:
            report.write(f"Daily Report for {self.today}\n\n")
            total_time = 0
            afk_time = 0

            # Include "default" in the tasks to report
            all_tasks = self.tasks + ["default"]
            for task in all_tasks:
                task_dir = os.path.join(self.session_dir, task)
                note_file = os.path.join(task_dir, f"{task}_notes.txt")
                if os.path.exists(note_file):
                    report.write(f"{task.upper()}:\n")
                    with open(note_file, "r") as f:
                        notes = f.read().strip().split("\n\n")
                        for note in notes:
                            if note:
                                report.write(f"  {note}\n")
                    note_count = len([n for n in notes if n.strip()])
                    task_time = note_count * 15
                    if task == "default" and any("auto-note" in n for n in notes):
                        afk_time += task_time
                    else:
                        total_time += task_time
                    report.write(f"  Estimated Time: {task_time} minutes\n")

                    screenshots = [f for f in os.listdir(task_dir) if f.startswith(f"screenshot_{task}")]
                    if screenshots:
                        report.write("  Screenshots:\n")
                        for shot in screenshots:
                            report.write(f"    {shot}\n")
                    report.write("\n")

            report.write(f"Total Productive Time: {total_time} minutes\n")
            report.write(f"Total AFK Time: {afk_time} minutes\n")
            report.write(f"Grand Total Time: {total_time + afk_time} minutes\n")

        messagebox.showinfo("report generated", f"Report saved as {report_filename}")

    def on_closing(self):
        self.running = False
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NoteApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
import os
import threading
import time
import json
import tkinter as tk
from tkinter import ttk, messagebox
import phonenumbers

PROGRESS_FILE = "progress.json"

def save_progress(state):
    """
    Save the current processing state and input parameters to a JSON file.
    State includes:
      - start: starting number (from the GUI)
      - end: ending number (from the GUI)
      - vcf_batch_size: batch size for each VCF file
      - current: the last processed number
      - batch_index: the current VCF batch index
      - current_batch_count: number of entries in the current VCF file
    """
    with open(PROGRESS_FILE, "w") as f:
        json.dump(state, f)

def load_progress():
    """
    Load the saved progress state from the JSON file.
    Returns the state dict if exists, otherwise None.
    """
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return None

def clear_progress():
    """Remove the progress file."""
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)

# --- Helper Functions ---

def check_mobile_existence(number):
    """
    Uses the phonenumbers library to check if the given 10-digit string (e.g. '9876543210')
    is a valid Indian mobile number.
    """
    try:
        pn = phonenumbers.parse(number, "IN")
        if phonenumbers.is_valid_number(pn):
            num_type = phonenumbers.number_type(pn)
            if num_type in [phonenumbers.NumberType.MOBILE, phonenumbers.NumberType.FIXED_LINE_OR_MOBILE]:
                return True
        return False
    except Exception:
        return False

def generate_vcard(number):
    """
    Generates a vCard string for the given number.
    """
    return f"""BEGIN:VCARD
VERSION:3.0
FN:{number}
TEL;TYPE=CELL:{number}
END:VCARD
"""

def open_new_vcf_file(batch_index, directory='vcf_files', mode="w"):
    """
    Opens a new VCF file (or appends if mode is "a") for writing using the batch_index in the filename.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)
    filename = os.path.join(directory, f"contacts_{batch_index}.vcf")
    return open(filename, mode), filename

# --- Processing Function ---

def process_numbers(start, end, vcf_batch_size, app, resume_state=None):
    """
    Process numbers from 'start' to 'end'. For each number:
      - Format it as a 10-digit string.
      - Check if it is a valid Indian mobile number.
      - If valid, immediately write the vCard to the current VCF file.
      - When the number of entries in the current VCF file reaches the batch size, close it and open a new one.
      - Non-valid numbers are written to 'non_existing_numbers.txt'.
      - The function checks for pause and stop signals.
    If a stop is requested, the current state (including GUI inputs) is saved to a JSON file.
    """
    count = resume_state.get("current", start) if resume_state else start
    batch_index = resume_state.get("batch_index", 1) if resume_state else 1
    current_batch_count = resume_state.get("current_batch_count", 0) if resume_state else 0

    # Open the current VCF file (append if resuming with an incomplete batch)
    mode = "a" if resume_state and current_batch_count > 0 else "w"
    current_vcf_file, current_filename = open_new_vcf_file(batch_index, mode=mode)
    app.log_message(f"Using VCF file: {current_filename}\n")
    
    for i in range(count, end + 1):
        # Check if a stop was requested.
        if app.stop_requested:
            state = {
                "start": start,
                "end": end,
                "vcf_batch_size": vcf_batch_size,
                "current": i,
                "batch_index": batch_index,
                "current_batch_count": current_batch_count
            }
            save_progress(state)
            app.log_message("Stop requested. Progress saved.\n")
            messagebox.showinfo("Stopped", "Processing stopped. Progress saved to progress.json")
            current_vcf_file.close()
            return

        # Check for pause and wait if needed.
        while app.paused:
            time.sleep(0.1)

        number = str(i).zfill(10)
        if check_mobile_existence(number):
            with open("existing_numbers.txt", "a") as exist_file:
                exist_file.write(number + "\n")
            vcard = generate_vcard(number)
            current_vcf_file.write(vcard + "\n")
            current_batch_count += 1
        else:
            with open("non_existing_numbers.txt", "a") as non_exist_file:
                non_exist_file.write(number + "\n")
        
        # Update progress (both label and progress bar)
        app.update_progress(i - start + 1, end - start + 1)
        app.log_message(f"Processed: {number}\n")

        # Check if current VCF file reached the batch limit.
        if current_batch_count >= vcf_batch_size:
            current_vcf_file.close()
            app.log_message(f"Closed VCF file: {current_filename}\n")
            batch_index += 1
            current_batch_count = 0
            current_vcf_file, current_filename = open_new_vcf_file(batch_index)
            app.log_message(f"Opened new VCF file: {current_filename}\n")
    
    if current_batch_count > 0:
        current_vcf_file.close()
        app.log_message(f"Closed final VCF file: {current_filename}\n")
    clear_progress()
    app.log_message("Processing complete.\n")
    messagebox.showinfo("Done", "Processing is complete.")

# --- GUI Application ---

class MobileCheckerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Indian Mobile Number Checker")
        self.geometry("600x450")
        self.paused = False           # Controls pause/resume
        self.stop_requested = False   # Controls stopping the processing thread
        self.create_widgets()

    def create_widgets(self):
        # Frame for input parameters
        frame = ttk.Frame(self)
        frame.pack(pady=10)

        ttk.Label(frame, text="Start Number (as integer):").grid(row=0, column=0, sticky="e")
        self.start_entry = ttk.Entry(frame, width=20)
        self.start_entry.grid(row=0, column=1, padx=5)
        self.start_entry.insert(0, "1")

        ttk.Label(frame, text="End Number (as integer):").grid(row=1, column=0, sticky="e")
        self.end_entry = ttk.Entry(frame, width=20)
        self.end_entry.grid(row=1, column=1, padx=5)
        self.end_entry.insert(0, "100")

        ttk.Label(frame, text="VCF Batch Size:").grid(row=2, column=0, sticky="e")
        self.batch_entry = ttk.Entry(frame, width=20)
        self.batch_entry.grid(row=2, column=1, padx=5)
        self.batch_entry.insert(0, "500")

        # Frame for buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        self.start_button = ttk.Button(btn_frame, text="Start Processing", command=self.start_processing)
        self.start_button.grid(row=0, column=0, padx=5)

        self.pause_button = ttk.Button(btn_frame, text="Pause", command=self.toggle_pause)
        self.pause_button.grid(row=0, column=1, padx=5)

        self.stop_button = ttk.Button(btn_frame, text="Stop", command=self.request_stop)
        self.stop_button.grid(row=0, column=2, padx=5)

        # Progress label and progress bar
        self.progress_label = ttk.Label(self, text="Progress: 0%")
        self.progress_label.pack(pady=5)
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", mode="determinate", length=400)
        self.progress_bar.pack(pady=5)

        # Log Text Widget
        self.log_text = tk.Text(self, height=10)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)

    def log_message(self, message):
        """Append messages to the log widget."""
        self.log_text.insert(tk.END, message)
        self.log_text.see(tk.END)
        self.update_idletasks()

    def update_progress(self, current, total):
        """Update the progress label and progress bar."""
        percent = (current / total) * 100 if total else 0
        self.progress_label.config(text=f"Progress: {percent:.2f}%")
        self.progress_bar['value'] = percent
        self.update_idletasks()

    def toggle_pause(self):
        """Toggle the pause state."""
        self.paused = not self.paused
        state = "Paused" if self.paused else "Resumed"
        self.pause_button.config(text="Resume" if self.paused else "Pause")
        self.log_message(f"Processing {state}.\n")

    def request_stop(self):
        """Set the stop flag."""
        self.stop_requested = True
        self.log_message("Stop requested.\n")

    def start_processing(self):
        """Read inputs and start (or resume) the processing thread."""
        try:
            start_num = int(self.start_entry.get())
            end_num = int(self.end_entry.get())
            vcf_batch_size = int(self.batch_entry.get())
        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid integer values.")
            return

        if start_num > end_num:
            messagebox.showerror("Input Error", "Start number must be less than or equal to end number.")
            return

        resume_state = load_progress()
        if resume_state:
            response = messagebox.askyesno("Resume Progress", 
                                           "A previous progress file was found. Do you want to resume from where you left off?")
            if response:
                start_num = resume_state.get("current", start_num)
                self.start_entry.delete(0, tk.END)
                self.start_entry.insert(0, str(resume_state.get("start", start_num)))
                self.end_entry.delete(0, tk.END)
                self.end_entry.insert(0, str(resume_state.get("end", end_num)))
                self.batch_entry.delete(0, tk.END)
                self.batch_entry.insert(0, str(resume_state.get("vcf_batch_size", vcf_batch_size)))
                self.log_message(f"Resuming from number: {str(start_num).zfill(10)}\n")
            else:
                clear_progress()
                resume_state = None

        self.stop_requested = False
        self.log_message(f"Starting processing from {str(start_num).zfill(10)} to {str(end_num).zfill(10)} with VCF batch size {vcf_batch_size}.\n")
        self.start_button.config(state="disabled")
        thread = threading.Thread(target=process_numbers, args=(start_num, end_num, vcf_batch_size, self, resume_state))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    app = MobileCheckerApp()
    app.mainloop()

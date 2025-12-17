import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import csv
import datetime
import threading
import os
import json
from playwright.sync_api import sync_playwright

# Dojo List from User
DOJOS = {
    "Gowrie - Gowrie Primary School": "a0B30000006HGr5EAG",
    "Amaroo - Amaroo School": "a0B4X00000qM3p7UAC",
    "Aranda - Aranda Scouts": "a0B4X00000qLlQKUA0",
    "Belconnen - Lake Ginninderra College": "a0B30000006HGqxEAG",
    "Braddon - Ainslie School": "a0B4X00000qM3pCUAS",
    "Calwell - Calwell Primary School": "a0B30000006HGqyEAG",
    "Conder - Charles Conder Primary School": "a0B30000006HGqzEAG",
    "Cooma - Cooma Public School": "a0B30000006HGr0EAG",
    "Coombs - Charles Weston School": "a0B4X0000167ITVUA2",
    "Denman Prospect - Evelyn Scott School": "a0BPg000003ZaN3MAK",
    "Evatt - St Monica's Primary School": "a0B30000006HGr1EAG",
    "Fraser - Fraser Primary School": "a0B30000006HGr3EAG",
    "Gold Creek - Gold Creek Senior School": "a0B4X00000qLXapUAG",
    "Harrison - Harrison School": "a0B4X000014QRpKUAW",
    "Holt - Kingsford Smith School": "a0B1300000ZkTkiEAF",
    "Jerrabomberra - Jerrabomberra Public School": "a0B30000006HGr8EAG",
    "Kaleen - Kaleen Community Hall": "a0B1300000hZt5aEAC",
    "Kambah - Namadgi School": "a0B30000006HGr9EAG",
    "Karabar - Karabar High School": "a0BPg000003ZaQHMA0",
    "Queanbeyan - Queanbeyan South Primary School": "a0B30000006HGrDEAW",
    "Radford - Radford College": "a0BPg000000kN1dMAE",
    "Region 16 Test Dojo - Test Dojo Primary School": "a0B4X00000qLBddUAG",
    "Taylor - Margaret Hendry School": "a0B4X000016jUUwUAM",
    "Tuggeranong - Lake Tuggeranong College": "a0B30000006HGrEEAW",
    "Weston Creek - Weston Creek Community Centre": "a0B4X00000qLpvQUAS",
    "Woden Prime - Woden Prime": "a0BPg000000Kh5dMAC",
    "Yass - Berinba Public School": "a0B30000006HGrHEAW"
}

DAYS = {
    "Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3, 
    "Friday": 4, "Saturday": 5, "Sunday": 6
}

class ScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GKR Dojo Scraper")
        self.root.geometry("600x650")
        
        self.config_file = "gkr_scraper_config.json"

        # --- Login Frame ---
        login_frame = ttk.LabelFrame(root, text="Login Details", padding=10)
        login_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(login_frame, text="Username:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.username_var = tk.StringVar()
        ttk.Entry(login_frame, textvariable=self.username_var, width=30).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(login_frame, text="Password:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.password_var = tk.StringVar()
        ttk.Entry(login_frame, textvariable=self.password_var, show="*", width=30).grid(row=1, column=1, padx=5, pady=5)
        
        self.remember_var = tk.BooleanVar()
        ttk.Checkbutton(login_frame, text="Remember Me", variable=self.remember_var).grid(row=2, column=1, sticky="w", padx=5)

        # --- Config Frame ---
        config_frame = ttk.LabelFrame(root, text="Configuration", padding=10)
        config_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(config_frame, text="Dojo Location:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.dojo_var = tk.StringVar(value="Gowrie - Gowrie Primary School")
        dojo_cb = ttk.Combobox(config_frame, textvariable=self.dojo_var, values=list(DOJOS.keys()), width=40, state="readonly")
        dojo_cb.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(config_frame, text="Day of Week:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.day_var = tk.StringVar(value="Wednesday")
        day_cb = ttk.Combobox(config_frame, textvariable=self.day_var, values=list(DAYS.keys()), state="readonly")
        day_cb.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        ttk.Label(config_frame, text="Year:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.year_var = tk.StringVar(value="2025")
        ttk.Entry(config_frame, textvariable=self.year_var, width=10).grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        self.show_browser = tk.BooleanVar(value=False)
        ttk.Checkbutton(config_frame, text="Show Browser (Headful)", variable=self.show_browser).grid(row=3, column=1, sticky="w", padx=5)

        # --- Action ---
        btn_frame = ttk.Frame(root, padding=10)
        btn_frame.pack(fill="x", padx=10)
        
        self.run_btn = ttk.Button(btn_frame, text="Start Extraction", command=self.start_thread)
        self.run_btn.pack(side="left")
        
        self.status_lbl = ttk.Label(btn_frame, text="Ready")
        self.status_lbl.pack(side="left", padx=10)

        # --- Log ---
        self.log_area = scrolledtext.ScrolledText(root, state='disabled', height=15)
        self.log_area.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.username_var.set(config.get("username", ""))
                    self.password_var.set(config.get("password", ""))
                    self.remember_var.set(config.get("remember", False))
                    self.dojo_var.set(config.get("dojo", "Gowrie - Gowrie Primary School"))
                    self.day_var.set(config.get("day", "Wednesday"))
                    self.year_var.set(config.get("year", "2025"))
            except:
                pass

    def save_config(self):
        if self.remember_var.get():
            config = {
                "username": self.username_var.get(),
                "password": self.password_var.get(),
                "remember": True,
                "dojo": self.dojo_var.get(),
                "day": self.day_var.get(),
                "year": self.year_var.get()
            }
            try:
                with open(self.config_file, 'w') as f:
                    json.dump(config, f)
            except Exception as e:
                print(f"Failed to save config: {e}")
        else:
            if os.path.exists(self.config_file):
                try:
                    os.remove(self.config_file)
                except:
                    pass

    def log(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def start_thread(self):
        if not self.username_var.get() or not self.password_var.get():
            messagebox.showerror("Error", "Please enter username and password")
            return
        
        self.save_config()
        
        self.run_btn.config(state="disabled")
        t = threading.Thread(target=self.run_scraper)
        t.daemon = True
        t.start()

    def run_scraper(self):
        try:
            username = self.username_var.get()
            password = self.password_var.get()
            dojo_name = self.dojo_var.get()
            dojo_id = DOJOS[dojo_name]
            target_day_name = self.day_var.get()
            target_day_idx = DAYS[target_day_name]
            year = int(self.year_var.get())
            headless = not self.show_browser.get()

            self.log(f"Starting scraper for {dojo_name} ({year})...")

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                page = browser.new_page()

                # Login
                self.log("Navigating to login...")
                # Try explicit login path found in investigation
                page.goto("https://dojomanager.gkrkarate.com/users/sign_in")
                
                # Check where we ended up
                if "sign_in" in page.url:
                    page.fill("#user_email", username)
                    page.fill("#user_password", password)
                    page.click("input.btn-primary")
                elif "dashboard" in page.url or "events" in page.url:
                    self.log("Already logged in?")
                
                # Wait for navigation
                try:
                    page.wait_for_url("**/dashboard", timeout=10000)
                    self.log("Login successful!")
                except:
                   if "sign_in" in page.url:
                       self.log("Login failed. Check credentials.")
                       self.root.after(0, lambda: self.run_btn.config(state="normal"))
                       return

                # Calculate Dates
                start_date = datetime.date(year, 1, 1)
                today = datetime.date.today()
                
                while start_date.weekday() != target_day_idx:
                    start_date += datetime.timedelta(days=1)

                dates_to_scrape = []
                current = start_date
                while current <= today:
                    dates_to_scrape.append(current)
                    current += datetime.timedelta(weeks=1)

                dates_to_scrape.reverse() 
                self.log(f"Found {len(dates_to_scrape)} weeks to check.")

                student_stats = {}

                for d in dates_to_scrape:
                    date_str = d.strftime("%Y-%m-%d")
                    url = f"https://dojomanager.gkrkarate.com/events?event[location]={dojo_id}&event[date]={date_str}"
                    self.log(f"Checking {date_str}...")
                    
                    try:
                        page.goto(url)
                        # Wait for potentially dynamic content
                        page.wait_for_selector('body', timeout=5000)
                        
                        class_links = page.eval_on_selector_all("a.btn-card", "elements => elements.map(e => ({href: e.href, text: e.innerText}))")
                        
                        if not class_links:
                            self.log(f"  No classes found for {date_str}")
                            continue

                        # We only care about the first two classes (chronologically / list order)
                        # idx 0 = First Class, idx 1 = Second Class.
                        for idx, cls in enumerate(class_links):
                            if idx > 1:
                                break # Ignore 3rd+ classes if any

                            link = cls['href']
                            class_name = cls['text'].replace("\n", " ")
                            self.log(f"  Scraping Class {idx+1}: {class_name}")
                            
                            page.goto(link)
                            
                            try:
                                page.wait_for_selector("#student-list", timeout=5000)
                                student_names = page.eval_on_selector_all("#student-list a.to-student-info", "els => els.map(e => e.innerText)")
                                
                                for name in student_names:
                                    clean_name = name.strip()
                                    if clean_name not in student_stats:
                                        student_stats[clean_name] = [0, 0] # [First Class Count, Second Class Count]
                                    
                                    student_stats[clean_name][idx] += 1
                                    
                                self.log(f"    Found {len(student_names)} students.")

                            except Exception as e:
                                self.log(f"    Error extracting students: {str(e)}")
                                # Go back to events page for safety if needed, but next loop gets new URL anyway

                    except Exception as e:
                        self.log(f"  Error on {date_str}: {e}")

                browser.close()

                # Save CSV
                output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"student_counts_{year}_{target_day_name}.csv")
                
                if student_stats:
                    with open(output_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(["STUDENT NAMES", "FIRST CLASS COUNT", "SECOND CLASS COUNT"])
                        
                        # Sort by name for nicer output
                        for name in sorted(student_stats.keys()):
                            counts = student_stats[name]
                            writer.writerow([name, counts[0], counts[1]])
                    
                    self.log(f"DONE! Saved to: {output_file}")
                    messagebox.showinfo("Success", f"Extraction complete.\nSaved to {output_file}")
                else:
                    self.log("No student records found.")
                    messagebox.showwarning("No Data", "No student records were found.")

        except Exception as e:
            self.log(f"CRITICAL ERROR: {str(e)}")
            messagebox.showerror("Error", str(e))
        
        finally:
            self.root.after(0, lambda: self.run_btn.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = ScraperApp(root)
    root.mainloop()

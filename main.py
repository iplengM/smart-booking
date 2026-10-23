"""
Smart Campus Resource Booking System

Runs with: python main.py
Uses only Python's standard library (Tkinter + SQLite).
Demo logins:
  System Operator: operator / operator123
  Campus Admin:    admin / admin123
  Lecturer:        lecturer / lecturer123
"""
import sqlite3
import hashlib
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

DB_NAME = "campus_booking.db"


CAMPUS_POLICIES = {
    "Johannesburg": {"max_hours": 4, "open": 8, "close": 18},
    "Durban":       {"max_hours": 3, "open": 9, "close": 17},
    "Cape Town":    {"max_hours": 2, "open": 8, "close": 16},
}


def hash_password(password):
    """Hash a password before storing it.
    NOTE: SHA-256 without a per-user salt is a demonstration only.
    Use bcrypt/scrypt/argon2 in a production system.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class Database:
    """Creates tables and provides the basic database operations."""
    def __init__(self, filename=DB_NAME):
        self.conn = sqlite3.connect(filename)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
        self.seed_demo_data()

    def create_tables(self):
        self.conn.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE COLLATE NOCASE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('Lecturer','Campus Administrator','System Operator')),
            campus TEXT
        );
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_code TEXT NOT NULL,
            name TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            campus TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resource_id INTEGER NOT NULL,
            campus TEXT NOT NULL,
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            duration_hours INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Active',
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(resource_id) REFERENCES resources(id)
        );
        """)
        self.conn.commit()

    def seed_demo_data(self):
        if self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            demo_users = [
                ("operator", "operator123", "Demo Operator", "System Operator", None),
                ("admin", "admin123", "Demo Administrator", "Campus Administrator", "Johannesburg"),
                ("lecturer", "lecturer123", "Demo Lecturer", "Lecturer", "Johannesburg"),
            ]
            self.conn.executemany(
                "INSERT INTO users(username,password_hash,full_name,role,campus) VALUES(?,?,?,?,?)",
                [(u, hash_password(p), n, r, c) for u,p,n,r,c in demo_users])
        if self.conn.execute("SELECT COUNT(*) FROM resources").fetchone()[0] == 0:
            resources = [
                ("JHB-LAB1","Computer Lab 1","Computer Lab","Johannesburg"),
                ("JHB-PROJ1","Projector 1","Projector","Johannesburg"),
                ("DBN-ROOM1","Seminar Room 1","Seminar Room","Durban"),
                ("CPT-LAB1","Computer Lab 1","Computer Lab","Cape Town"),
            ]
            self.conn.executemany(
                "INSERT INTO resources(resource_code,name,resource_type,campus) VALUES(?,?,?,?)",
                resources)
        self.conn.commit()

    def login(self, username, password):
        return self.conn.execute(
        "SELECT * FROM users WHERE LOWER(username)=LOWER(?) AND password_hash=?",
        (username.strip(), hash_password(password))).fetchone()

    def register_lecturer(self, username, password, full_name, campus):
        if not username.strip() or not password or not full_name.strip():
            raise ValueError("Please complete all fields.")
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters.")
        self.conn.execute(
            "INSERT INTO users(username,password_hash,full_name,role,campus) VALUES(?,?,?,?,?)",
            (username.strip(), hash_password(password), full_name.strip(), "Lecturer", campus))
        self.conn.commit()

    def resources_for(self, campus):
        return self.conn.execute("SELECT * FROM resources WHERE campus=? ORDER BY name", (campus,)).fetchall()

    def add_resource(self, code, name, kind, campus):
        if not all(x.strip() for x in (code, name, kind)):
            raise ValueError("Enter a resource code, name and type.")
        self.conn.execute("INSERT INTO resources(resource_code,name,resource_type,campus) VALUES(?,?,?,?)",
                          (code.strip().upper(), name.strip(), kind.strip(), campus))
        self.conn.commit()

    def delete_resource(self, resource_id):
        count = self.conn.execute("SELECT COUNT(*) FROM bookings WHERE resource_id=? AND status='Active'",
                                  (resource_id,)).fetchone()[0]
        if count:
            raise ValueError("This resource has an active booking and cannot be removed.")
        self.conn.execute("DELETE FROM resources WHERE id=?", (resource_id,))
        self.conn.commit()

    def bookings(self, campus=None, user_id=None):
        sql = """SELECT b.*, r.resource_code, r.name AS resource_name, u.full_name, u.username
                 FROM bookings b JOIN resources r ON r.id=b.resource_id
                 JOIN users u ON u.id=b.user_id"""
        clauses, params = [], []
        if campus:
            clauses.append("b.campus=?"); params.append(campus)
        if user_id:
            clauses.append("b.user_id=?"); params.append(user_id)
        if clauses: sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY b.booking_date DESC, b.start_time DESC"
        return self.conn.execute(sql, params).fetchall()

    def create_booking(self, user_id, resource_id, campus, date, start, duration):
        policy = CAMPUS_POLICIES[campus]
        try:
            booking_start = datetime.strptime(f"{date} {start}", "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError("Use date YYYY-MM-DD and time HH:MM (24-hour clock).")
        if booking_start <= datetime.now():
            raise ValueError("Choose a future date and time.")
        if not 1 <= duration <= policy["max_hours"]:
            raise ValueError(f"{campus} allows bookings of 1 to {policy['max_hours']} hour(s).")
        booking_end = booking_start + timedelta(hours=duration)
        if booking_end.date() != booking_start.date():
            raise ValueError("Bookings must end on the same day.")
        if booking_start.hour < policy["open"] or booking_end.hour > policy["close"] or \
            (booking_end.hour == policy["close"] and booking_end.minute > 0):
            raise ValueError(f"{campus} booking hours are {policy['open']:02d}:00–{policy['close']:02d}:00.")
        if booking_start.minute != 0:
            raise ValueError("Start time must be on the hour (HH:00).")
        
        res = self.conn.execute(
            "SELECT campus FROM resources WHERE id=?", (resource_id,)).fetchone()
        if not res:
            raise ValueError("Resource not found.")
        if res["campus"] != campus:
            raise ValueError("That resource does not belong to the selected campus.")
        
        for old in self.conn.execute(
            "SELECT start_time,duration_hours FROM bookings WHERE resource_id=? AND booking_date=? AND status='Active'",
            (resource_id, date)):
            old_start = datetime.strptime(f"{date} {old['start_time']}", "%Y-%m-%d %H:%M")
            old_end = old_start + timedelta(hours=old["duration_hours"])
            if booking_start < old_end and old_start < booking_end:
                raise ValueError("That resource is already booked during the selected time.")
        self.conn.execute("""INSERT INTO bookings
            (user_id,resource_id,campus,booking_date,start_time,duration_hours,status,created_at)
            VALUES(?,?,?,?,?,?,?,?)""",
            (user_id, resource_id, campus, date, start, duration, "Active", datetime.now().isoformat(timespec="seconds")))
        self.conn.commit()

        def cancel_booking(self, booking_id, user_id, override=False):
            row = self.conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
            if not row:
                raise ValueError("Booking not found.")
            if not override and row["user_id"] != user_id:
                raise ValueError("You can only cancel your own booking.")
            start = datetime.strptime(f"{row['booking_date']} {row['start_time']}", "%Y-%m-%d %H:%M")
            if start <= datetime.now():
                raise ValueError("Only future bookings can be cancelled.")
            if row["status"] != "Active":
                raise ValueError("This booking is already cancelled.")
            self.conn.execute("UPDATE bookings SET status='Cancelled' WHERE id=?", (booking_id,))
            self.conn.commit()

    def report_rows(self):
        return self.conn.execute("""
      SELECT campus, COUNT(*) AS total, ROUND(AVG(duration_hours),2) AS avg_hours
      FROM bookings WHERE status='Active' GROUP BY campus ORDER BY campus
    """).fetchall()

    def most_used(self, campus):
        row = self.conn.execute("""
          SELECT r.name, COUNT(b.id) AS total FROM resources r
          LEFT JOIN bookings b ON b.resource_id=r.id AND b.status='Active'
          WHERE r.campus=? GROUP BY r.id ORDER BY total DESC, r.name LIMIT 1
        """, (campus,)).fetchone()
        return row if row else {"name": "None", "total": 0}


class User:
    """Base class demonstrating inheritance and encapsulation."""
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.full_name = row["full_name"]
        self.role = row["role"]
        self.campus = row["campus"]


class Lecturer(User):
    pass


class CampusAdministrator(User):
    pass


class SystemOperator(User):
    pass


class BookingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Campus Resource Booking System")
        self.root.geometry("1000x650")
        self.root.minsize(850, 560)
        self.db = Database()
        self.user = None
        self.active_campus = "Johannesburg"
        self.style = ttk.Style()
        try: self.style.theme_use("clam")
        except tk.TclError: pass
        self.style.configure("Title.TLabel", font=("Arial", 18, "bold"))
        self.style.configure("Treeview", rowheight=26)
        self.show_login()

    def clear(self):
        for widget in self.root.winfo_children(): widget.destroy()

    def show_login(self):
        self.clear()
        frame = ttk.Frame(self.root, padding=35)
        frame.pack(expand=True)
        ttk.Label(frame, text="Smart Campus", style="Title.TLabel").pack(pady=(0,4))
        ttk.Label(frame, text="Resource Booking System").pack(pady=(0,20))
        ttk.Label(frame, text="Username").pack(anchor="w")
        username = ttk.Entry(frame, width=35); username.pack(pady=(2,10))
        ttk.Label(frame, text="Password").pack(anchor="w")
        password = ttk.Entry(frame, show="*", width=35); password.pack(pady=(2,14))
        def do_login():
            row = self.db.login(username.get(), password.get())
            if not row:
                messagebox.showerror("Login failed", "Username or password is incorrect.")
                return
            cls = {"Lecturer": Lecturer, "Campus Administrator": CampusAdministrator,
                   "System Operator": SystemOperator}[row["role"]]
            self.user = cls(row)
            self.active_campus = self.user.campus or "Johannesburg"
            self.show_dashboard()
        ttk.Button(frame, text="Log in", command=do_login).pack(fill="x", pady=4)
        ttk.Button(frame, text="Register lecturer account", command=self.show_register).pack(fill="x", pady=4)
        ttk.Separator(frame).pack(fill="x", pady=16)
        ttk.Label(frame, text="Demo: lecturer/lecturer123  |  admin/admin123  |  operator/operator123",
                  wraplength=370).pack()
        username.focus()

    def show_register(self):
        win = tk.Toplevel(self.root); win.title("Register Lecturer"); win.resizable(False, False)
        frm = ttk.Frame(win, padding=20); frm.pack()
        entries = {}
        for i, label in enumerate(("Full name", "Username", "Password")):
            ttk.Label(frm, text=label).grid(row=i, column=0, sticky="w", pady=5)
            ent = ttk.Entry(frm, show="*" if label == "Password" else "", width=28)
            ent.grid(row=i, column=1, pady=5); entries[label] = ent
        ttk.Label(frm, text="Home campus").grid(row=3, column=0, sticky="w", pady=5)
        campus = ttk.Combobox(frm, values=list(CAMPUS_POLICIES), state="readonly", width=25)
        campus.current(0); campus.grid(row=3, column=1, pady=5)
        def register():
            try:
                self.db.register_lecturer(entries["Username"].get(), entries["Password"].get(),
                                          entries["Full name"].get(), campus.get())
                messagebox.showinfo("Registered", "Account created. You can now log in.", parent=win)
                win.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Registration failed", "That username is already in use.", parent=win)
            except ValueError as e:
                messagebox.showerror("Registration failed", str(e), parent=win)
        ttk.Button(frm, text="Create account", command=register).grid(row=4, column=0, columnspan=2, sticky="ew", pady=12)

    def show_dashboard(self):
        self.clear()
        top = ttk.Frame(self.root, padding=(18,12)); top.pack(fill="x")
        ttk.Label(top, text="Smart Campus Resource Booking System", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text=f"Signed in: {self.user.full_name} ({self.user.role})").pack(anchor="w", pady=(5,0))
        controls = ttk.Frame(self.root, padding=(18,0,18,12)); controls.pack(fill="x")
        ttk.Label(controls, text="Active campus:").pack(side="left")
        self.campus_box = ttk.Combobox(controls, values=list(CAMPUS_POLICIES), state="readonly", width=18)
        if self.user.role == "Campus Administrator" and self.user.campus:
            self.campus_box["values"] = [self.user.campus]
        if self.user.role == "Lecturer" and self.user.campus:
            self.campus_box.set(self.user.campus)
        else:
            self.campus_box.set(self.active_campus)
        self.campus_box.pack(side="left", padx=8)
        self.campus_box.bind("<<ComboboxSelected>>", self.change_campus)
        self.policy_label = ttk.Label(controls, text="")
        self.policy_label.pack(side="left", padx=10)
        ttk.Button(controls, text="Log out", command=self.logout).pack(side="right")
        self.tabs = ttk.Notebook(self.root); self.tabs.pack(fill="both", expand=True, padx=18, pady=(0,18))
        self.resource_tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.resource_tab, text="Resources")
        self.build_resources_tab()
        if self.user.role == "Lecturer":
            self.booking_tab = ttk.Frame(self.tabs, padding=12); self.tabs.add(self.booking_tab, text="Book a resource")
            self.history_tab = ttk.Frame(self.tabs, padding=12); self.tabs.add(self.history_tab, text="My bookings")
            self.build_booking_tab(); self.build_history_tab()
        if self.user.role in ("Campus Administrator", "System Operator"):
            self.manage_tab = ttk.Frame(self.tabs, padding=12); self.tabs.add(self.manage_tab, text="Manage resources")
            self.all_bookings_tab = ttk.Frame(self.tabs, padding=12); self.tabs.add(self.all_bookings_tab, text="Bookings")
            self.build_manage_tab(); self.build_all_bookings_tab()
        if self.user.role == "System Operator":
            self.report_tab = ttk.Frame(self.tabs, padding=12); self.tabs.add(self.report_tab, text="Reports")
            self.build_reports_tab()
        self.update_policy()

    def change_campus(self, _event=None):
        if self.user and self.user.role == "Campus Administrator":
            self.campus_box.set(self.user.campus)
            return
        self.active_campus = self.campus_box.get()
        self.refresh_all()
        self.update_policy()

    def update_policy(self):
        p = CAMPUS_POLICIES[self.active_campus]
        self.policy_label.config(text=f"Policy: max {p['max_hours']}h, {p['open']:02d}:00–{p['close']:02d}:00")
        if hasattr(self, "duration_box"):
            allowed = list(range(1, p["max_hours"] + 1))
            self.duration_box["values"] = allowed
            if int(self.duration_box.get() or 1) > p["max_hours"]:
                self.duration_box.set(str(p["max_hours"]))
        if hasattr(self, "resource_tree"): self.refresh_resources()
        if hasattr(self, "booking_resource"): self.refresh_booking_resources()

    def refresh_all(self):
        self.refresh_resources()
        if hasattr(self, "booking_resource"): self.refresh_booking_resources()
        if hasattr(self, "all_tree"): self.refresh_all_bookings()
        if hasattr(self, "report_text"): self.refresh_reports()

    def make_tree(self, parent, columns, headings):
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading); tree.column(col, width=135, anchor="w")
        tree.pack(fill="both", expand=True, pady=8)
        return tree

    def build_resources_tab(self):
        ttk.Label(self.resource_tab, text="Resources available at the selected campus").pack(anchor="w")
        self.resource_tree = self.make_tree(self.resource_tab, ("code","name","type","campus"),
                                             ("Resource code","Resource name","Type","Campus"))
        self.refresh_resources()

    def refresh_resources(self):
        if not hasattr(self, "resource_tree"): return
        self.resource_tree.delete(*self.resource_tree.get_children())
        if self.user and self.user.role == "System Operator":
            rows = self.db.conn.execute("SELECT * FROM resources ORDER BY campus, name").fetchall()
        else:
            rows = self.db.resources_for(self.active_campus)
        for r in rows:
            self.resource_tree.insert("", "end", values=(r["resource_code"],r["name"],r["resource_type"],r["campus"]))

    def build_booking_tab(self):
        frm = ttk.LabelFrame(self.booking_tab, text="Create a booking", padding=12); frm.pack(fill="x")
        ttk.Label(frm, text="Resource").grid(row=0,column=0,sticky="w",padx=5,pady=5)
        self.booking_resource = ttk.Combobox(frm, state="readonly", width=35); self.booking_resource.grid(row=0,column=1,sticky="w",padx=5,pady=5)
        ttk.Label(frm, text="Date (YYYY-MM-DD)").grid(row=1,column=0,sticky="w",padx=5,pady=5)
        self.date_entry = ttk.Entry(frm,width=38); self.date_entry.insert(0,(datetime.now()+timedelta(days=1)).strftime("%Y-%m-%d")); self.date_entry.grid(row=1,column=1,padx=5,pady=5)
        ttk.Label(frm, text="Start time (HH:MM)").grid(row=2,column=0,sticky="w",padx=5,pady=5)
        self.time_entry = ttk.Entry(frm,width=38); self.time_entry.insert(0,"10:00"); self.time_entry.grid(row=2,column=1,padx=5,pady=5)
        ttk.Label(frm, text="Duration (hours)").grid(row=3,column=0,sticky="w",padx=5,pady=5)
        self.duration_box = ttk.Combobox(frm, values=[1], state="readonly", width=35); self.duration_box.set("1"); self.duration_box.grid(row=3,column=1,padx=5,pady=5)
        ttk.Button(frm,text="Confirm booking",command=self.submit_booking).grid(row=4,column=1,sticky="w",padx=5,pady=10)
        ttk.Label(self.booking_tab,text="The selected campus policy is shown above. The system checks the time limit and overlapping bookings.").pack(anchor="w",pady=8)
        self.refresh_booking_resources()

    def refresh_booking_resources(self):
        if not hasattr(self,"booking_resource"): return
        self.resource_choices = self.db.resources_for(self.active_campus)
        self.booking_resource["values"] = [f"{r['resource_code']} — {r['name']}" for r in self.resource_choices]
        if self.resource_choices: self.booking_resource.current(0)
        else: self.booking_resource.set("")

    def submit_booking(self):
        selected = self.booking_resource.current()
        if selected < 0:
            messagebox.showerror("Booking failed","There are no resources at this campus."); return
        try:
            self.db.create_booking(self.user.id, self.resource_choices[selected]["id"], self.active_campus,
                                   self.date_entry.get().strip(), self.time_entry.get().strip(),
                                   int(self.duration_box.get()))
            messagebox.showinfo("Booking confirmed","Your booking has been saved.")
            self.refresh_history(); self.refresh_all_bookings()
        except (ValueError, sqlite3.Error) as e:
            messagebox.showerror("Booking failed",str(e))

    def build_history_tab(self):
        ttk.Label(self.history_tab,text="Your bookings (active and cancelled)").pack(anchor="w")
        self.history_tree = self.make_tree(self.history_tab,("id","date","time","duration","resource","campus","status"),
                                           ("ID","Date","Start","Hours","Resource","Campus","Status"))
        ttk.Button(self.history_tab,text="Cancel selected future booking",command=self.cancel_my_booking).pack(anchor="w")
        self.refresh_history()

    def refresh_history(self):
        if not hasattr(self,"history_tree"): return
        self.history_tree.delete(*self.history_tree.get_children())
        for b in self.db.bookings(user_id=self.user.id):
            self.history_tree.insert("","end",iid=str(b["id"]),values=(b["id"],b["booking_date"],b["start_time"],b["duration_hours"],b["resource_name"],b["campus"],b["status"]))

    def cancel_my_booking(self):
        selected = self.history_tree.selection()
        if not selected: messagebox.showwarning("Select booking","Select a booking first."); return
        try:
            self.db.cancel_booking(int(selected[0]), self.user.id); self.refresh_history(); self.refresh_all_bookings()
            messagebox.showinfo("Cancelled","The booking was cancelled.")
        except ValueError as e: messagebox.showerror("Cannot cancel",str(e))

    def build_manage_tab(self):
        frm = ttk.LabelFrame(self.manage_tab,text="Add a resource",padding=10); frm.pack(fill="x")
        self.code_entry = ttk.Entry(frm,width=14); self.name_entry = ttk.Entry(frm,width=20); self.type_entry = ttk.Entry(frm,width=18)
        for i,(label,entry) in enumerate((("Unique code",self.code_entry),("Name",self.name_entry),("Type",self.type_entry))):
            ttk.Label(frm,text=label).grid(row=0,column=i,sticky="w",padx=4); entry.grid(row=1,column=i,padx=4,pady=5)
        ttk.Button(frm,text="Add resource",command=self.add_resource).grid(row=1,column=3,padx=6)
        self.manage_tree = self.make_tree(self.manage_tab,("id","code","name","type","campus"),("ID","Code","Name","Type","Campus"))
        ttk.Button(self.manage_tab,text="Remove selected resource",command=self.remove_resource).pack(anchor="w")
        self.refresh_manage()

    def refresh_manage(self):
        if not hasattr(self,"manage_tree"): return
        self.manage_tree.delete(*self.manage_tree.get_children())
        for r in self.db.resources_for(self.active_campus):
            self.manage_tree.insert("","end",iid=str(r["id"]),values=(r["id"],r["resource_code"],r["name"],r["resource_type"],r["campus"]))

    def add_resource(self):
        try:
            self.db.add_resource(self.code_entry.get(),self.name_entry.get(),self.type_entry.get(),self.active_campus)
            self.code_entry.delete(0,"end"); self.name_entry.delete(0,"end"); self.type_entry.delete(0,"end")
            self.refresh_manage(); self.refresh_resources(); self.refresh_booking_resources()
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate code","That resource code already exists. Choose a unique code.")
        except ValueError as e: messagebox.showerror("Cannot add resource",str(e))

    def remove_resource(self):
        selected=self.manage_tree.selection()
        if not selected: messagebox.showwarning("Select resource","Select a resource first."); return
        try:
            self.db.delete_resource(int(selected[0])); self.refresh_manage(); self.refresh_resources(); self.refresh_booking_resources()
        except ValueError as e: messagebox.showerror("Cannot remove resource",str(e))

    def build_all_bookings_tab(self):
        ttk.Label(self.all_bookings_tab,text="Bookings for the active campus").pack(anchor="w")
        self.all_tree=self.make_tree(self.all_bookings_tab,("id","lecturer","resource","date","time","hours","status"),
                                     ("ID","Lecturer","Resource","Date","Start","Hours","Status"))
        self.refresh_all_bookings()

    def refresh_all_bookings(self):
        if not hasattr(self,"all_tree"): return
        self.all_tree.delete(*self.all_tree.get_children())
        campus = None if self.user.role == "System Operator" else self.active_campus
        for b in self.db.bookings(campus=campus):
            self.all_tree.insert("","end",values=(b["id"],b["full_name"],b["resource_name"],b["booking_date"],b["start_time"],b["duration_hours"],b["status"]))

    def build_reports_tab(self):
        ttk.Label(self.report_tab,text="Campus comparison report").pack(anchor="w")
        self.report_text=tk.Text(self.report_tab,height=15,wrap="word",font=("Consolas",10))
        self.report_text.pack(fill="both",expand=True,pady=8)
        self.refresh_reports()

    def refresh_reports(self):
        if not hasattr(self,"report_text"): return
        self.report_text.delete("1.0","end")
        self.report_text.insert("end","CAMPUS USAGE SUMMARY\n"+"="*55+"\n")
        for campus in CAMPUS_POLICIES:
            rows=self.db.conn.execute("SELECT COUNT(*) FROM bookings WHERE campus=? AND status='Active'",(campus,)).fetchone()[0]
            avg=self.db.conn.execute("SELECT AVG(duration_hours) FROM bookings WHERE campus=? AND status='Active'",(campus,)).fetchone()[0]
            most=self.db.most_used(campus)
            self.report_text.insert("end",f"\n{campus}\n  Active bookings: {rows}\n  Average duration: {round(avg,2) if avg else 0} hour(s)\n  Most-used resource: {most['name'] if most else 'None'} ({most['total'] if most else 0} bookings)\n")
        self.report_text.insert("end","\nNote: reports are calculated from saved SQLite booking records.")
        self.report_text.config(state="disabled")

    def logout(self):
        self.user=None; self.show_login()

if __name__ == "__main__":
    root=tk.Tk()
    app=BookingApp(root)
    root.mainloop()

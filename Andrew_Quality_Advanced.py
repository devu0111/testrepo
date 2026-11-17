r"""
NPI Quality Management System
Products: BSA, Helix, MWS
Modules per project: Build Report, DFMEA, PFMEA

Configuration: \\atgv1pfss03\Users\BSA ENGINEERING\DEVU\QUALITY SYSTEM\Configure
Default plant roots: QUALITY SYSTEM\IN13 and QUALITY SYSTEM\CN10
Default company logo: QUALITY SYSTEM\logo.JPG
Project records are saved as JSON with project-local image attachments.
"""
import json
import getpass
import os
import re
import shutil
import hashlib
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

APP_TITLE = "NPI Quality Management System"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(APP_DIR, "andrew_company_logo.ico")
SHARED_ROOT = r"\\atgv1pfss03\Users\BSA ENGINEERING\DEVU\QUALITY SYSTEM"
CONFIG_DIR = os.path.join(SHARED_ROOT, "Configure")
PLANTS = ["IN13", "CN10"]
PRODUCTS = ["BSA", "Helix", "MWS"]
PLANT_DATA_ROOTS = {
    "IN13": os.path.join(SHARED_ROOT, "IN13"),
    "CN10": os.path.join(SHARED_ROOT, "CN10"),
}
PLANT_CONFIG_FILE = os.path.join(CONFIG_DIR, "plant_paths.json")
LOGO_CONFIG_FILE = os.path.join(CONFIG_DIR, "logo_path.json")
DEFAULT_LOGO_PATH = os.path.join(SHARED_ROOT, "logo.JPG")
DEFAULT_ADMIN = "dd1093"
ADMIN_FILE = os.path.join(CONFIG_DIR, "admins.json")

BUILD_FIELDS = [
    "Item No.", "Stage", "Category", "Severity", "Issue Description",
    "Issue Related Picture", "Action Taken / Proposed Solution",
    "Action Related Pictures", "Responsible Person", "Status", "Target Date", "Remark"
]
# DFMEA/PFMEA include Build Report linkage fields so issue descriptions and photo references
# can be pulled into the analysis using the "Link Build Report" button.
FMEA_FIELDS = [
    "Process Step", "Potential Failure Mode", "Potential Effect", "Severity No.",
    "Prevention Control", "Occurrence No.", "Detection Controls", "Detection No.",
    "RPN No.", "Potential Cause", "Recommended Actions", "Action Taken",
    "Revised Severity No.", "Revised Occurrence No.", "Revised Detection No.",
    "Revised RPN No.", "Action Owner", "Status",
    "Failure Mode Related Photos", "Action Related Photos",
    "Source Build Report Item No.", "Source Build Issue Description",
    "Source Build Issue Photos", "Source Build Action Taken", "Source Build Action Photos"
]
PROJECT_FIELDS = ["Project Name", "EAO No.", "Antenna Model", "Team Members", "Project Status"]


def safe_name(value):
    """Convert a label to a Windows-safe, stable folder/file name."""
    value = re.sub(r'[<>:"/\\|?*]+', "_", str(value).strip())
    value = re.sub(r"\s+", "_", value)
    value = value.rstrip(" .")
    return value[:100] or "Untitled_Project"


class NPIQualityApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x820")
        self.company_logo = None
        self.header_logo = None
        self.landing_logo = None
        try:
            if os.path.isfile(ICON_PATH):
                self.root.iconbitmap(ICON_PATH)
        except tk.TclError:
            pass
        self.logo_source_path = self.load_logo_path()
        self._load_company_logo()
        self.root.minsize(1000, 680)
        self.current_path = None
        self._loaded_signature = None
        self.current_user = self.get_current_windows_user()
        self.admins = self.load_admins()
        self.is_current_admin = self.username_key(self.current_user) in {self.username_key(a) for a in self.admins}
        self.project_data = self.empty_project()
        self.active_module = "Build Report"
        self.module_rows = {"Build Report": [], "DFMEA": [], "PFMEA": []}
        self.row_edit_index = None
        self.field_vars = {}
        self.project_vars = {}
        self.project_entries = {}
        # Create plant selection state before building the landing page, which reads it.
        self.plant_var = tk.StringVar(value="")
        self.product_var = tk.StringVar(value=PRODUCTS[0])
        self._build_ui()
        self.refresh_project_list()

    def get_current_windows_user(self):
        """Return the current Windows account name; use environment/getpass fallbacks."""
        username = os.environ.get("USERNAME") or getpass.getuser()
        domain = os.environ.get("USERDOMAIN")
        if domain and username:
            return f"{domain}\\{username}"
        return username or "Unknown User"

    @staticmethod
    def username_key(value):
        # Windows may report DOMAIN\username; compare the account part case-insensitively.
        return str(value or "").strip().split("\\")[-1].casefold()

    def load_admins(self):
        # dd1093 is the bootstrap administrator. The shared file allows this admin to add more.
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            if os.path.isfile(ADMIN_FILE):
                with open(ADMIN_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                admins = data.get("admins", []) if isinstance(data, dict) else []
                return sorted(set([DEFAULT_ADMIN] + [str(x).strip() for x in admins if str(x).strip()]), key=str.casefold)
            data = {"admins": [DEFAULT_ADMIN], "updated_at": datetime.now().isoformat(timespec="seconds")}
            with open(ADMIN_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except (OSError, json.JSONDecodeError):
            # Keep the bootstrap account recognized even if the network is unavailable.
            pass
        return [DEFAULT_ADMIN]

    def save_admins(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            temp = ADMIN_FILE + ".tmp"
            with open(temp, "w", encoding="utf-8") as f:
                json.dump({"admins": self.admins, "updated_at": datetime.now().isoformat(timespec="seconds"),
                           "updated_by": self.current_user}, f, indent=2)
            os.replace(temp, ADMIN_FILE)
            return True
        except OSError as exc:
            messagebox.showerror("Admin list not saved", f"Could not save administrator list to the shared folder:\n\n{exc}")
            return False

    def require_admin(self, action="perform this action"):
        if not self.is_current_admin:
            messagebox.showerror("Administrator access required", f"Only an administrator can {action}.")
            return False
        return True

    def open_admin_panel(self):
        if not self.require_admin("open the Admin Panel"):
            return
        win = tk.Toplevel(self.root)
        win.title("NPI Quality Management System — Admin Panel")
        win.geometry("620x540")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Administrator Console", font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=18, pady=(16, 4))
        ttk.Label(win, text=f"Signed in as {self.current_user}. Only administrators can create projects or add administrators.",
                  wraplength=550).pack(anchor="w", padx=18, pady=(0, 14))
        actions = ttk.Frame(win, padding=(18, 0))
        actions.pack(fill="x")
        ttk.Button(actions, text="Create Project", command=lambda: (win.destroy(), self.new_project_dialog())).pack(fill="x", pady=4)
        ttk.Button(actions, text="Add Administrator", command=self.add_admin_dialog).pack(fill="x", pady=4)
        ttk.Button(actions, text="Remove Selected Administrator", command=lambda: self.remove_admin_dialog(box, win)).pack(fill="x", pady=4)
        ttk.Button(actions, text="Configure Plant Links and Logo", command=self.edit_plant_links_dialog).pack(fill="x", pady=4)
        ttk.Label(win, text="Current administrators (select one to remove)", font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18, pady=(12, 6))
        box = tk.Listbox(win, height=7, exportselection=False)
        box.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        for admin in self.admins:
            label = f"{admin}  (protected primary administrator)" if self.username_key(admin) == self.username_key(DEFAULT_ADMIN) else admin
            box.insert("end", label)
        ttk.Label(win, text="dd1093 is the protected primary administrator and cannot be removed. Administrator changes are stored in the shared configuration folder; other running PCs may need a restart to refresh access.",
                  wraplength=570).pack(anchor="w", padx=18, pady=(0, 12))

    def load_plant_links(self):
        """Load configured roots; defaults are initialized on first run, never silently shared."""
        links = dict(PLANT_DATA_ROOTS)
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            if os.path.isfile(PLANT_CONFIG_FILE):
                with open(PLANT_CONFIG_FILE, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                if isinstance(stored, dict):
                    for plant in PLANTS:
                        if plant in stored:
                            links[plant] = str(stored[plant] or "").strip()
            else:
                with open(PLANT_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump(links, f, indent=2)
        except (OSError, json.JSONDecodeError, TypeError):
            # Defaults remain visible, but project operations still validate the selected path.
            pass
        return links

    def load_logo_path(self):
        path = DEFAULT_LOGO_PATH
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            if os.path.isfile(LOGO_CONFIG_FILE):
                with open(LOGO_CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("logo_path"):
                    path = str(data["logo_path"]).strip()
            else:
                with open(LOGO_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump({"logo_path": path}, f, indent=2)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        return path

    def _make_logo_thumbnail(self, max_width=180, max_height=80):
        """Create a resized logo image compatible with both Pillow and Tk PhotoImage."""
        if not self.company_logo:
            return None
        # Pillow's ImageTk.PhotoImage does not implement Tk's subsample() method.
        try:
            from PIL import Image, ImageTk
            with Image.open(self.logo_source_path) as source:
                image = source.convert("RGBA")
                image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image)
        except Exception:
            # For Tk-native formats, subsample is available; only reduce, never enlarge.
            try:
                factor = max(1, (self.company_logo.width() + max_width - 1) // max_width,
                             (self.company_logo.height() + max_height - 1) // max_height)
                return self.company_logo.subsample(factor, factor)
            except (AttributeError, tk.TclError):
                return self.company_logo

    def _load_company_logo(self):
        """Load JPG/JPEG through Pillow, with Tk-supported image formats as fallback."""
        self.company_logo = None
        if not self.logo_source_path or not os.path.isfile(self.logo_source_path):
            return
        try:
            from PIL import Image, ImageTk
            image = Image.open(self.logo_source_path)
            image.thumbnail((220, 100))
            self.company_logo = ImageTk.PhotoImage(image)
        except ImportError:
            try:
                self.company_logo = tk.PhotoImage(file=self.logo_source_path)
            except tk.TclError:
                self.company_logo = None
        except Exception:
            self.company_logo = None
        if self.company_logo is not None:
            try:
                self.root.iconphoto(True, self.company_logo)
            except tk.TclError:
                pass

    def edit_plant_links_dialog(self):
        if not self.require_admin("edit plant data links and logo path"):
            return
        links = self.load_plant_links()
        win = tk.Toplevel(self.root)
        win.title("Admin — Plant Data Links and Logo")
        win.geometry("820x330")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Plant-specific project data locations", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=18, pady=(16, 6))
        ttk.Label(win, text="IN13 and CN10 must use separate folders. A blank or unavailable path blocks project operations.", wraplength=770).pack(anchor="w", padx=18, pady=(0, 10))
        form = ttk.Frame(win, padding=(18, 0))
        form.pack(fill="x")
        vars_ = {}
        for row, plant in enumerate(PLANTS):
            ttk.Label(form, text=f"{plant} data folder").grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)
            vars_[plant] = tk.StringVar(value=links.get(plant, ""))
            ttk.Entry(form, textvariable=vars_[plant], width=72).grid(row=row, column=1, sticky="ew", pady=6)
            ttk.Button(form, text="Browse", command=lambda p=plant: self._browse_folder_into(vars_[p])).grid(row=row, column=2, padx=(6, 0))
        form.columnconfigure(1, weight=1)
        logo_var = tk.StringVar(value=self.logo_source_path or DEFAULT_LOGO_PATH)
        ttk.Label(form, text="Company logo file").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=6)
        ttk.Entry(form, textvariable=logo_var, width=72).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Button(form, text="Browse", command=lambda: self._browse_logo_into(logo_var)).grid(row=2, column=2, padx=(6, 0))

        def save_links():
            data = {plant: vars_[plant].get().strip() for plant in PLANTS}
            if any(not value for value in data.values()):
                messagebox.showerror("Missing plant path", "Both IN13 and CN10 folder paths are required.", parent=win)
                return
            if os.path.normcase(os.path.abspath(data["IN13"])) == os.path.normcase(os.path.abspath(data["CN10"])):
                messagebox.showerror("Plant paths must be separate", "IN13 and CN10 cannot use the same folder.", parent=win)
                return
            logo_path = logo_var.get().strip()
            if not logo_path or not os.path.isfile(logo_path):
                messagebox.showerror("Logo not found", "Select an existing logo image file.", parent=win)
                return
            try:
                os.makedirs(CONFIG_DIR, exist_ok=True)
                temp = PLANT_CONFIG_FILE + ".tmp"
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                os.replace(temp, PLANT_CONFIG_FILE)
                temp = LOGO_CONFIG_FILE + ".tmp"
                with open(temp, "w", encoding="utf-8") as f:
                    json.dump({"logo_path": logo_path}, f, indent=2)
                os.replace(temp, LOGO_CONFIG_FILE)
                self.logo_source_path = logo_path
                self._load_company_logo()
                messagebox.showinfo("Configuration saved", "Plant paths and logo path saved. Restart the application to refresh the logo on all screens.", parent=win)
                win.destroy()
                self.refresh_project_list()
            except OSError as exc:
                messagebox.showerror("Save failed", f"Could not save configuration. Check Configure folder permissions.\n\n{exc}", parent=win)
        ttk.Button(win, text="Save Configuration", command=save_links).pack(anchor="e", padx=18, pady=14)

    @staticmethod
    def _browse_folder_into(variable):
        path = filedialog.askdirectory(title="Select plant data folder")
        if path:
            variable.set(path)

    @staticmethod
    def _browse_logo_into(variable):
        path = filedialog.askopenfilename(title="Select company logo", filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp"), ("All files", "*.*")])
        if path:
            variable.set(path)

    def _plant_root(self):
        return self.load_plant_links().get(self.plant_var.get().strip(), "").strip()

    def remove_admin_dialog(self, admin_listbox, parent):
        """Remove an administrator while permanently protecting the dd1093 account."""
        if not self.require_admin("remove administrators"):
            return
        selection = admin_listbox.curselection()
        if not selection:
            messagebox.showwarning("Select administrator", "Select an administrator from the list first.", parent=parent)
            return
        displayed = admin_listbox.get(selection[0])
        username = displayed.split("  (protected primary administrator)", 1)[0].strip()
        if self.username_key(username) == self.username_key(DEFAULT_ADMIN):
            messagebox.showerror("Protected administrator", "dd1093 is the protected primary administrator and cannot be removed.", parent=parent)
            return
        if not messagebox.askyesno("Remove administrator", f"Remove administrator access for '{username}'?\n\nThey will lose administrator access after their app refreshes or restarts.", parent=parent):
            return
        old_admins = list(self.admins)
        self.admins = [admin for admin in self.admins if self.username_key(admin) != self.username_key(username)]
        # Always keep the protected administrator, even if the configuration was edited manually.
        if self.username_key(DEFAULT_ADMIN) not in {self.username_key(a) for a in self.admins}:
            self.admins.append(DEFAULT_ADMIN)
        if self.save_admins():
            self.is_current_admin = self.username_key(self.current_user) in {self.username_key(a) for a in self.admins}
            admin_listbox.delete(0, "end")
            for admin in self.admins:
                label = f"{admin}  (protected primary administrator)" if self.username_key(admin) == self.username_key(DEFAULT_ADMIN) else admin
                admin_listbox.insert("end", label)
            messagebox.showinfo("Administrator removed", f"Administrator access removed for {username}.", parent=parent)
        else:
            self.admins = old_admins

    def add_admin_dialog(self):
        if not self.require_admin("add administrators"):
            return
        win = tk.Toplevel(self.root)
        win.title("Add Administrator")
        win.geometry("430x190")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Windows username (e.g. jsmith)").pack(anchor="w", padx=18, pady=(18, 5))
        var = tk.StringVar()
        entry = ttk.Entry(win, textvariable=var, width=40)
        entry.pack(fill="x", padx=18)
        entry.focus_set()
        def add():
            username = var.get().strip()
            if not username or any(ch in username for ch in "\\/:*?\"<>|"):
                messagebox.showwarning("Invalid username", "Enter a valid Windows username.", parent=win)
                return
            if self.username_key(username) in {self.username_key(x) for x in self.admins}:
                messagebox.showinfo("Already an administrator", f"{username} already has administrator access.", parent=win)
                return
            self.admins.append(username)
            if self.save_admins():
                messagebox.showinfo("Administrator added", f"{username} will have administrator access when the app is restarted.", parent=win)
                win.destroy()
        ttk.Button(win, text="Add Administrator", command=add).pack(anchor="e", padx=18, pady=18)

    def new_project_dialog(self):
        if not self.require_admin("create projects"):
            return
        win = tk.Toplevel(self.root)
        win.title("Admin — Create Project")
        win.geometry("600x430")
        win.transient(self.root)
        win.grab_set()
        ttk.Label(win, text="Create a project for engineers", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=18, pady=(16, 10))
        form = ttk.Frame(win, padding=(18, 0))
        form.pack(fill="both", expand=True)
        plant_var = tk.StringVar(value=self.plant_var.get() or PLANTS[0])
        product_var = tk.StringVar(value=PRODUCTS[0])
        vars_ = {field: tk.StringVar() for field in PROJECT_FIELDS}
        ttk.Label(form, text="Plant").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(form, textvariable=plant_var, values=PLANTS, state="readonly", width=36).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Label(form, text="Product").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(form, textvariable=product_var, values=PRODUCTS, state="readonly", width=36).grid(row=1, column=1, sticky="ew", pady=5)
        for row, field in enumerate(PROJECT_FIELDS, start=2):
            ttk.Label(form, text=field).grid(row=row, column=0, sticky="w", pady=5, padx=(0, 12))
            ttk.Entry(form, textvariable=vars_[field], width=38).grid(row=row, column=1, sticky="ew", pady=5)
        form.columnconfigure(1, weight=1)
        def create():
            if not vars_["Project Name"].get().strip() or not vars_["Antenna Model"].get().strip():
                messagebox.showwarning("Required fields", "Project Name and Antenna Model are required.", parent=win)
                return
            plant_root = self._plant_root_for(product_var.get(), plant_var.get())
            if not plant_root or not os.path.isdir(plant_root):
                messagebox.showerror("Plant folder unavailable", f"The configured folder for {plant_var.get()} is blank or unavailable. Ask an administrator to correct it.\n\n{plant_root or '(blank path)'}", parent=win)
                return
            eao = vars_["EAO No."].get().strip()
            key = safe_name(eao if eao else f'{vars_["Project Name"].get().strip()}_{vars_["Antenna Model"].get().strip()}')
            folder = os.path.join(plant_root, safe_name(product_var.get()), key)
            path = os.path.join(folder, "project.json")
            if os.path.exists(path):
                messagebox.showerror("Duplicate project", f"A project with this identifier already exists:\n{path}", parent=win)
                return
            data = self.empty_project()
            data["product"] = product_var.get()
            data["plant"] = plant_var.get()
            data["project"] = {field: vars_[field].get().strip() for field in PROJECT_FIELDS}
            data["created_by"] = self.current_user
            data["updated_by"] = self.current_user
            data["audit_log"] = [{"timestamp": datetime.now().isoformat(timespec="seconds"), "user": self.current_user, "action": "Created project"}]
            try:
                os.makedirs(os.path.join(folder, "images"), exist_ok=False)
                with open(path, "x", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except FileExistsError:
                messagebox.showerror("Duplicate project", "This project identifier already exists.", parent=win)
                return
            except OSError as exc:
                messagebox.showerror("Create failed", f"Could not create project in shared folder.\n\n{exc}", parent=win)
                return
            messagebox.showinfo("Project created", "Project created. Engineers can now select it from the saved-project list.", parent=win)
            win.destroy()
            self.product_var.set(product_var.get())
            self.plant_var.set(plant_var.get())
            self.refresh_project_list()
            self.refresh_recent_projects()
        ttk.Button(win, text="Create Project", command=create).pack(anchor="e", padx=18, pady=14)

    def empty_project(self):
        return {
            "plant": getattr(self, "plant_var", tk.StringVar(value=PLANTS[0])).get(),
            "product": "BSA",
            "project": {key: "" for key in PROJECT_FIELDS},
            "records": {"Build Report": [], "DFMEA": [], "PFMEA": []},
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "created_by": self.current_user,
            "updated_by": self.current_user,
            "audit_log": []
        }

    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=27, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 17, "bold"), foreground="#14385d")
        style.configure("Subheader.TLabel", font=("Segoe UI", 10), foreground="#58718a")
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 8))
        style.configure("Module.TButton", font=("Segoe UI", 11, "bold"), padding=(12, 10))

        # The launch page is shown first. The data-entry workspace is kept intact behind it.
        self.landing_frame = tk.Frame(self.root, bg="#eef4f8")
        self.landing_frame.pack(fill="both", expand=True)
        self._build_landing_page()

        self.main_frame = ttk.Frame(self.root)
        header = ttk.Frame(self.main_frame, padding=(14, 10))
        header.pack(fill="x")
        if self.company_logo is not None:
            try:
                self.header_logo = self._make_logo_thumbnail(180, 80)
                ttk.Label(header, image=self.header_logo).pack(side="left", padx=(0, 12))
            except tk.TclError:
                pass
        ttk.Label(header, text=APP_TITLE, style="Header.TLabel").pack(side="left")
        ttk.Label(header, text="  |  BSA  •  Helix  •  MWS", font=("Segoe UI", 10)).pack(side="left", padx=12)
        ttk.Label(header, text=f"Logged in: {self.current_user}", font=("Segoe UI", 9, "bold")).pack(side="right")

        project_box = ttk.LabelFrame(self.main_frame, text="Project Information", padding=10)
        project_box.pack(fill="x", padx=10, pady=(0, 8))
        for i, field in enumerate(PROJECT_FIELDS):
            ttk.Label(project_box, text=field).grid(row=0, column=i, sticky="w", padx=5, pady=(0, 4))
            var = tk.StringVar()
            self.project_vars[field] = var
            width = 24 if field in ("Project Name", "Team Members") else 18
            entry = ttk.Entry(project_box, textvariable=var, width=width)
            entry.grid(row=1, column=i, sticky="ew", padx=5)
            self.project_entries[field] = entry
            if not self.is_current_admin:
                entry.configure(state="readonly")
            project_box.columnconfigure(i, weight=1)

        controls = ttk.Frame(self.main_frame, padding=(10, 0, 10, 8))
        controls.pack(fill="x")
        ttk.Button(controls, text="⌂ Home / Dashboard", command=self.show_home).pack(side="left", padx=(0, 10))
        ttk.Label(controls, text="Product:").pack(side="left")
        ttk.Label(controls, text="Plant:").pack(side="left")
        self.plant_combo = ttk.Combobox(controls, textvariable=self.plant_var, values=PLANTS, state="readonly", width=8)
        self.plant_combo.pack(side="left", padx=(5, 12))
        self.plant_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_project_list())
        self.product_combo = ttk.Combobox(controls, textvariable=self.product_var, values=PRODUCTS,
                                          state="readonly", width=12)
        self.product_combo.pack(side="left", padx=(5, 15))
        self.product_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_project_list())
        ttk.Label(controls, text="Saved Projects:").pack(side="left")
        self.saved_project_var = tk.StringVar()
        self.saved_project_combo = ttk.Combobox(controls, textvariable=self.saved_project_var,
                                                 state="readonly", width=38)
        self.saved_project_combo.pack(side="left", padx=5)
        ttk.Button(controls, text="Select / Load", command=self.load_selected_project).pack(side="left", padx=4)
        self.new_project_button = ttk.Button(controls, text="New Project (Admin)", command=self.new_project_dialog, state=("normal" if self.is_current_admin else "disabled"))
        self.new_project_button.pack(side="left", padx=4)
        ttk.Button(controls, text="Save Project", command=self.save_project).pack(side="left", padx=4)
        ttk.Button(controls, text="Refresh List", command=self.refresh_project_list).pack(side="left", padx=4)

        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.module_widgets = {}
        for module in ("Build Report", "DFMEA", "PFMEA"):
            tab = ttk.Frame(self.notebook, padding=8)
            self.notebook.add(tab, text=module)
            self.module_widgets[module] = {}
            self._build_module(tab, module)
        self.notebook.bind("<<NotebookTabChanged>>", self._tab_changed)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.main_frame, textvariable=self.status_var, anchor="w", relief="sunken", padding=(8, 3)).pack(fill="x", side="bottom")

    def _build_landing_page(self):
        """Build two separate launch screens: plant selection, then product dashboard."""
        # Screen 1: plant selection only. Product/module choices are intentionally hidden here.
        self.plant_screen = tk.Frame(self.landing_frame, bg="#eef4f8")
        self.plant_screen.pack(fill="both", expand=True)
        self._build_brand_header(self.plant_screen, show_admin=True)

        plant_body = tk.Frame(self.plant_screen, bg="#eef4f8")
        plant_body.pack(fill="both", expand=True, padx=42, pady=32)
        tk.Label(plant_body, text="Welcome to Andrew Quality", bg="#eef4f8", fg="#15395d",
                 font=("Segoe UI", 24, "bold")).pack(anchor="w", pady=(8, 4))
        tk.Label(plant_body, text="NPI Quality Management System", bg="#eef4f8", fg="#526b80",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(plant_body, text="STEP 1  •  SELECT YOUR PLANT", bg="#eef4f8", fg="#15395d",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(30, 10))
        tk.Label(plant_body, text="Choose IN13 or CN10 to continue to the product dashboard.",
                 bg="#eef4f8", fg="#526b80", font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 14))

        plant_cards = tk.Frame(plant_body, bg="#eef4f8")
        plant_cards.pack(fill="x", pady=(0, 18))
        self.plant_buttons = {}
        for plant, color, description in (
            ("IN13", "#1e6fb5", "IN13 plant workspace"),
            ("CN10", "#13866d", "CN10 plant workspace"),
        ):
            card = tk.Frame(plant_cards, bg="white", highlightbackground=color, highlightthickness=2)
            card.pack(side="left", fill="both", expand=True, padx=(0 if plant == "IN13" else 14, 0), ipadx=12, ipady=12)
            tk.Label(card, text=plant, bg="white", fg=color, font=("Segoe UI", 25, "bold")).pack(pady=(18, 4))
            tk.Label(card, text=description, bg="white", fg="#5c7183", font=("Segoe UI", 10)).pack(pady=(0, 12))
            btn = tk.Button(card, text=f"Select {plant}", bg=color, fg="white", activebackground="#dce8f1",
                            activeforeground=color, relief="flat", font=("Segoe UI", 11, "bold"),
                            padx=24, pady=10, command=lambda pl=plant: self.select_landing_plant(pl))
            btn.pack(fill="x", padx=24, pady=(0, 18))
            self.plant_buttons[plant] = btn

        self.landing_plant_status = tk.StringVar(value="No plant selected")
        tk.Label(plant_body, textvariable=self.landing_plant_status, bg="#eef4f8", fg="#526b80",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 10))
        self.continue_button = tk.Button(plant_body, text="Continue to Product Dashboard  →", state="disabled",
                                         bg="#173e63", fg="white", activebackground="#2b587c",
                                         activeforeground="white", relief="flat", font=("Segoe UI", 11, "bold"),
                                         padx=18, pady=10, command=self.show_product_dashboard)
        self.continue_button.pack(anchor="e", pady=(8, 0))

        # Screen 2: product dashboard with recent projects and quick/admin actions.
        self.dashboard_frame = tk.Frame(self.landing_frame, bg="#eef4f8")
        self._build_product_dashboard()
        self.show_plant_screen()

    def _build_brand_header(self, parent, show_admin=False):
        top = tk.Frame(parent, bg="#173e63", height=100)
        top.pack(fill="x")
        top.pack_propagate(False)
        if self.company_logo is not None:
            try:
                logo = self._make_logo_thumbnail(160, 80)
                if parent is self.plant_screen:
                    self.landing_logo = logo
                else:
                    self.dashboard_logo = logo
                tk.Label(top, image=logo, bg="#173e63").pack(side="left", padx=(24, 14), pady=8)
            except tk.TclError:
                pass
        tk.Label(top, text="Andrew Quality", bg="#173e63", fg="white",
                 font=("Segoe UI", 21, "bold")).pack(side="left", pady=(13, 0))
        tk.Label(top, text="NPI Quality Management System", bg="#173e63", fg="#b9d2e6",
                 font=("Segoe UI", 10)).pack(side="left", padx=14, pady=(18, 0))
        user_box = tk.Frame(top, bg="#173e63")
        user_box.pack(side="right", padx=20, pady=15)
        tk.Label(user_box, text="SIGNED IN AS", bg="#173e63", fg="#b9d2e6",
                 font=("Segoe UI", 8, "bold")).pack(anchor="e")
        tk.Label(user_box, text=self.current_user, bg="#173e63", fg="white",
                 font=("Segoe UI", 10, "bold")).pack(anchor="e")
        if show_admin and self.is_current_admin:
            tk.Button(top, text="⚙ Admin Panel", bg="#dce8f1", fg="#173e63", relief="flat",
                      font=("Segoe UI", 9, "bold"), command=self.open_admin_panel).pack(side="right", padx=12, pady=28)

    def _build_product_dashboard(self):
        self._build_brand_header(self.dashboard_frame, show_admin=True)
        body = tk.Frame(self.dashboard_frame, bg="#eef4f8")
        body.pack(fill="both", expand=True, padx=24, pady=18)
        dashboard_title = tk.Frame(body, bg="#eef4f8")
        dashboard_title.pack(fill="x")
        tk.Label(dashboard_title, text="Product Dashboard", bg="#eef4f8", fg="#15395d",
                 font=("Segoe UI", 22, "bold")).pack(side="left", anchor="w")
        self.dashboard_plant_label = tk.StringVar(value="Selected plant: —")
        tk.Label(dashboard_title, textvariable=self.dashboard_plant_label, bg="#eef4f8", fg="#526b80",
                 font=("Segoe UI", 10, "bold")).pack(side="right", anchor="e")
        tk.Label(body, text="STEP 2  •  SELECT PRODUCT AND QUALITY MODULE", bg="#eef4f8", fg="#526b80",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(4, 12))

        cards = tk.Frame(body, bg="#eef4f8")
        cards.pack(fill="x")
        product_info = {
            "BSA": ("BSA", "BSA product workspace", "#1e6fb5"),
            "Helix": ("HELIX", "Helix product workspace", "#6554c0"),
            "MWS": ("MWS", "MWS product workspace", "#13866d"),
        }
        for product in PRODUCTS:
            title, desc, color = product_info[product]
            card = tk.Frame(cards, bg="white", highlightbackground="#d5e2eb", highlightthickness=1)
            card.pack(side="left", fill="both", expand=True, padx=(0 if product == "BSA" else 12, 0), ipadx=8, ipady=7)
            tk.Frame(card, bg=color, height=6).pack(fill="x")
            tk.Label(card, text=title, bg="white", fg=color, font=("Segoe UI", 20, "bold")).pack(pady=(12, 2))
            tk.Label(card, text=desc, bg="white", fg="#5c7183", font=("Segoe UI", 9)).pack(pady=(0, 10))
            for module, button_color in (("Build Report", "#2678c8"), ("DFMEA", "#8064d8"), ("PFMEA", "#169879")):
                tk.Button(card, text=module, bg=button_color, fg="white", activebackground="#dce8f1",
                          activeforeground=button_color, relief="flat", font=("Segoe UI", 9, "bold"),
                          command=lambda p=product, m=module: self.enter_workspace(p, m)).pack(fill="x", padx=12, pady=3)

        lower = tk.Frame(body, bg="#eef4f8")
        lower.pack(fill="both", expand=True, pady=(16, 0))
        recent_box = tk.Frame(lower, bg="white", highlightbackground="#d5e2eb", highlightthickness=1)
        recent_box.pack(side="left", fill="both", expand=True)
        tk.Label(recent_box, text="Recent Projects", bg="white", fg="#15395d",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(recent_box, text="Double-click a project to open it.", bg="white", fg="#6c8090",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=14, pady=(0, 8))
        columns = ("Plant", "Product", "Project Name", "EAO No.", "Antenna Model", "Status")
        self.recent_tree = ttk.Treeview(recent_box, columns=columns, show="headings", height=7)
        for col, width in zip(columns, (75, 80, 220, 120, 150, 110)):
            self.recent_tree.heading(col, text=col)
            self.recent_tree.column(col, width=width, anchor="w")
        self.recent_tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.recent_tree.bind("<Double-1>", self.open_recent_project)

        quick = tk.Frame(lower, bg="#173e63", width=230)
        quick.pack(side="right", fill="y", padx=(14, 0))
        quick.pack_propagate(False)
        tk.Label(quick, text="QUICK ACTIONS", bg="#173e63", fg="#b9d2e6",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=16, pady=(16, 10))
        tk.Button(quick, text="＋  Create / Open Project", bg="#ffffff", fg="#173e63", relief="flat",
                  font=("Segoe UI", 10, "bold"), command=self.open_project_dashboard).pack(fill="x", padx=14, pady=5)
        tk.Button(quick, text="↻  Refresh Projects", bg="#2b587c", fg="white", relief="flat",
                  font=("Segoe UI", 10), command=self.refresh_recent_projects).pack(fill="x", padx=14, pady=5)
        tk.Button(quick, text="←  Change Plant", bg="#dce8f1", fg="#173e63", relief="flat",
                  font=("Segoe UI", 10, "bold"), command=self.show_plant_screen).pack(fill="x", padx=14, pady=5)
        if self.is_current_admin:
            tk.Button(quick, text="⚙  Admin Panel", bg="#dce8f1", fg="#173e63", relief="flat",
                      font=("Segoe UI", 10, "bold"), command=self.open_admin_panel).pack(fill="x", padx=14, pady=5)
        else:
            tk.Label(quick, text="Engineer access: open existing projects. Project creation and administrator management are restricted.",
                     wraplength=195, justify="left", bg="#173e63", fg="#d3e1ec", font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(12, 0))
        self.refresh_recent_projects()

    def show_plant_screen(self):
        self.dashboard_frame.pack_forget()
        self.plant_screen.pack(fill="both", expand=True)
        self._update_landing_plant_state()

    def show_product_dashboard(self):
        if not self.plant_var.get().strip():
            messagebox.showwarning("Select a plant", "Please select IN13 or CN10 first.", parent=self.root)
            return
        self.plant_screen.pack_forget()
        self.dashboard_frame.pack(fill="both", expand=True)
        self.dashboard_plant_label.set(f"Selected plant: {self.plant_var.get()}")
        self.refresh_recent_projects()
        self.refresh_project_list()

    def select_landing_plant(self, plant):
        self.plant_var.set(plant)
        self.landing_plant_status.set(f"Selected plant: {plant}. Click Continue to open the product dashboard.")
        self.continue_button.configure(state="normal")
        self._update_landing_plant_state()

    def _update_landing_plant_state(self):
        selected = self.plant_var.get().strip()
        for plant, button in getattr(self, "plant_buttons", {}).items():
            if plant == selected:
                button.configure(text=f"✓  {plant} selected", relief="sunken")
            else:
                button.configure(text=f"Select {plant}", relief="flat")

    def enter_workspace(self, product, module):
        if not self.plant_var.get().strip():
            messagebox.showwarning("Select a plant", "Please select IN13 or CN10 before opening a product workspace.", parent=self.root)
            return
        self.product_var.set(product)
        self.refresh_project_list()
        self.landing_frame.pack_forget()
        self.main_frame.pack(fill="both", expand=True)
        self.notebook.select(("Build Report", "DFMEA", "PFMEA").index(module))
        self.active_module = module
        self.status_var.set(f"{product} workspace — {module}")

    def show_home(self):
        self.main_frame.pack_forget()
        self.landing_frame.pack(fill="both", expand=True)
        self.show_product_dashboard()

    def open_project_dashboard(self):
        self.enter_workspace(self.product_var.get() or PRODUCTS[0], "Build Report")

    def refresh_recent_projects(self):
        if not hasattr(self, "recent_tree"):
            return
        for item in self.recent_tree.get_children():
            self.recent_tree.delete(item)
        count = 0
        selected_plant = self.plant_var.get().strip()
        plants_to_show = [selected_plant] if selected_plant in PLANTS else []
        for plant in plants_to_show:
          for product in PRODUCTS:
            product_dir = os.path.join(self._plant_root_for(product, plant), safe_name(product))
            try:
                for folder in os.listdir(product_dir):
                    path = os.path.join(product_dir, folder, "project.json")
                    if not os.path.isfile(path):
                        continue
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        pr = data.get("project", {})
                        self.recent_tree.insert("", "end", values=(plant, product, pr.get("Project Name", folder),
                            pr.get("EAO No.", ""), pr.get("Antenna Model", ""), pr.get("Project Status", "")),
                            tags=(path,))
                        count += 1
                    except (OSError, json.JSONDecodeError):
                        continue
            except OSError:
                continue
        if count == 0:
            # Do not show mixed-plant records before a plant is selected.
            note = "Select IN13 or CN10 above" if not selected_plant else "No projects found / check plant data link"
            self.recent_tree.insert("", "end", values=(selected_plant or "—", "—", note, "", "", ""))

    def open_recent_project(self, _event=None):
        selection = self.recent_tree.selection()
        if not selection:
            return
        values = self.recent_tree.item(selection[0], "values")
        if len(values) < 6 or values[0] not in PLANTS or values[1] not in PRODUCTS:
            return
        plant, product, project_name = values[0], values[1], values[2]
        self.select_landing_plant(plant)
        self.enter_workspace(product, "Build Report")
        self.refresh_project_list()
        for label in self.saved_project_combo["values"]:
            if label.startswith(project_name + " |"):
                self.saved_project_var.set(label)
                self.load_selected_project()
                return

    def _build_module(self, tab, module):
        """Create a structured, easier-to-scan entry workspace for each quality module."""
        fields = BUILD_FIELDS if module == "Build Report" else FMEA_FIELDS
        self.module_widgets[module]["vars"] = {}
        self.module_widgets[module]["image_fields"] = set()
        # Keep the entry area scrollable and height-limited so the record table stays visible.
        form_shell = ttk.Frame(tab)
        form_shell.pack(fill="x", expand=False, pady=(0, 6))
        form_canvas = tk.Canvas(form_shell, height=300, highlightthickness=0, borderwidth=0)
        form_scroll = ttk.Scrollbar(form_shell, orient="vertical", command=form_canvas.yview)
        form_canvas.configure(yscrollcommand=form_scroll.set)
        form_scroll.pack(side="right", fill="y")
        form_canvas.pack(side="left", fill="x", expand=True)
        form = ttk.LabelFrame(form_canvas, text=f"  {module} — Advanced Entry / Edit  ", padding=10)
        form_window = form_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _e, c=form_canvas: c.configure(scrollregion=c.bbox("all")))
        form_canvas.bind("<Configure>", lambda e, c=form_canvas, w=form_window: c.itemconfigure(w, width=e.width))
        form_canvas.bind("<MouseWheel>", lambda e, c=form_canvas: c.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.module_widgets[module]["form"] = form
        self.module_widgets[module]["form_canvas"] = form_canvas
        self.module_widgets[module]["text_widgets"] = {}

        if module == "Build Report":
            groups = [
                ("Finding Details", ["Item No.", "Stage", "Category", "Severity", "Issue Description", "Issue Related Picture"]),
                ("Corrective Action", ["Action Taken / Proposed Solution", "Action Related Pictures", "Responsible Person", "Status", "Target Date", "Remark"]),
            ]
        else:
            groups = [
                ("1  |  Failure Analysis", ["Process Step", "Potential Failure Mode", "Potential Effect", "Potential Cause"]),
                ("2  |  Current Risk Controls", ["Prevention Control", "Severity No.", "Occurrence No.", "Detection Controls", "Detection No.", "RPN No."]),
                ("3  |  Recommended / Completed Actions", ["Recommended Actions", "Action Taken", "Action Owner", "Status",
                    "Revised Severity No.", "Revised Occurrence No.", "Revised Detection No.", "Revised RPN No.",
                    "Failure Mode Related Photos", "Action Related Photos"]),
                ("4  |  Build Report Linkage (Optional)", ["Source Build Report Item No.", "Source Build Issue Description",
                    "Source Build Issue Photos", "Source Build Action Taken", "Source Build Action Photos"]),
            ]

        image_fields = {
            "Issue Related Picture", "Action Related Pictures",
            "Failure Mode Related Photos", "Action Related Photos",
            "Source Build Issue Photos", "Source Build Action Photos"
        }
        long_fields = {
            "Issue Description", "Action Taken / Proposed Solution", "Remark",
            "Potential Failure Mode", "Potential Effect", "Potential Cause",
            "Prevention Control", "Detection Controls", "Recommended Actions",
            "Action Taken", "Source Build Issue Description", "Source Build Action Taken"
        }
        rating_fields = {"Severity No.", "Occurrence No.", "Detection No.",
            "Revised Severity No.", "Revised Occurrence No.", "Revised Detection No."}
        status_values = ("Open", "In Progress", "Completed", "Closed", "On Hold", "N/A")
        stage_values = ("Concept", "Design", "Prototype", "DRR", "PRR", "RTM", "Production", "Other")
        category_values = ("Design", "Process", "Material", "Tooling", "Assembly", "Inspection", "Other")
        severity_values = tuple(str(n) for n in range(1, 11))

        for group_title, group_fields in groups:
            section = ttk.LabelFrame(form, text=group_title, padding=(8, 6))
            section.pack(fill="x", expand=True, pady=(0, 7))
            for i, field in enumerate(group_fields):
                row, col = divmod(i, 2)
                col *= 2
                ttk.Label(section, text=field).grid(row=row * 2, column=col, columnspan=2,
                    sticky="w", padx=5, pady=(4, 1))
                var = tk.StringVar()
                self.module_widgets[module]["vars"][field] = var

                if field in image_fields:
                    ttk.Entry(section, textvariable=var, width=38).grid(
                        row=row * 2 + 1, column=col, sticky="ew", padx=(5, 1), pady=(0, 5))
                    button_box = ttk.Frame(section)
                    button_box.grid(row=row * 2 + 1, column=col + 1, sticky="ew", padx=(1, 5), pady=(0, 5))
                    ttk.Button(button_box, text="Browse…", width=9,
                        command=lambda m=module, f=field: self.browse_image(m, f)).pack(side="left", padx=(0, 3))
                    ttk.Button(button_box, text="Paste", width=7,
                        command=lambda m=module, f=field: self.paste_clipboard_image(m, f)).pack(side="left")
                    ttk.Button(button_box, text="View", width=6,
                        command=lambda m=module, f=field: self.view_images(m, f)).pack(side="left", padx=(3, 0))
                    self.module_widgets[module]["image_fields"].add(field)
                elif field in rating_fields:
                    ttk.Combobox(section, textvariable=var, values=severity_values,
                        state="readonly", width=34).grid(row=row * 2 + 1, column=col, columnspan=2,
                        sticky="ew", padx=5, pady=(0, 5))
                elif field == "Status":
                    ttk.Combobox(section, textvariable=var, values=status_values, width=34).grid(
                        row=row * 2 + 1, column=col, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
                elif field == "Stage":
                    ttk.Combobox(section, textvariable=var, values=stage_values, width=34).grid(
                        row=row * 2 + 1, column=col, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
                elif field == "Category":
                    ttk.Combobox(section, textvariable=var, values=category_values, width=34).grid(
                        row=row * 2 + 1, column=col, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
                elif field in long_fields:
                    text_box = tk.Text(section, height=3, width=38, wrap="word", font=("Segoe UI", 9),
                                       relief="solid", borderwidth=1, undo=True)
                    text_box.grid(row=row * 2 + 1, column=col, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
                    self.module_widgets[module]["text_widgets"][field] = text_box
                    text_box.bind("<FocusOut>", lambda _e, m=module, f=field: self._sync_text_to_var(m, f))
                else:
                    ent = ttk.Entry(section, textvariable=var, width=38)
                    ent.grid(row=row * 2 + 1, column=col, columnspan=2, sticky="ew", padx=5, pady=(0, 5))
                    if field in ("RPN No.", "Revised RPN No."):
                        ent.configure(state="readonly")
                section.columnconfigure(col, weight=1)
                section.columnconfigure(col + 1, weight=1)

        if module in ("DFMEA", "PFMEA"):
            self.module_widgets[module]["risk_var"] = tk.StringVar(value="Current RPN risk: —")
            for rating_field in ("Severity No.", "Occurrence No.", "Detection No.",
                                 "Revised Severity No.", "Revised Occurrence No.", "Revised Detection No."):
                self.module_widgets[module]["vars"][rating_field].trace_add(
                    "write", lambda *_args, m=module: self._update_live_rpn(m))
            self._update_live_rpn(module)

        actions = ttk.Frame(tab, padding=(0, 2))
        actions.pack(fill="x", pady=(0, 6))
        ttk.Button(actions, text="＋ Add Entry", style="Primary.TButton",
                   command=lambda m=module: self.add_record(m)).pack(side="left", padx=(0, 5))
        ttk.Button(actions, text="Update Selected", command=lambda m=module: self.update_record(m)).pack(side="left", padx=5)
        ttk.Button(actions, text="Clear Form", command=lambda m=module: self.clear_form(m)).pack(side="left", padx=5)
        if module in ("DFMEA", "PFMEA"):
            ttk.Button(actions, text="Import Build Finding", command=lambda m=module: self.link_build_report(m)).pack(side="left", padx=5)
        ttk.Button(actions, text="Delete Selected", command=lambda m=module: self.delete_record(m)).pack(side="left", padx=5)
        ttk.Button(actions, text="Export This Report to Excel", command=lambda m=module: self.export_report_to_excel(m)).pack(side="left", padx=5)
        ttk.Button(actions, text="Export All Reports", command=self.export_all_reports_to_excel).pack(side="left", padx=5)
        ttk.Label(actions, text="Select a row below to edit • RPN is calculated automatically",
                  foreground="#526b80").pack(side="right")
        if module in ("DFMEA", "PFMEA"):
            risk_label = ttk.Label(tab, textvariable=self.module_widgets[module]["risk_var"],
                                   font=("Segoe UI", 10, "bold"), foreground="#526b80")
            risk_label.pack(anchor="w", pady=(0, 5))
            self.module_widgets[module]["risk_label"] = risk_label
            self._update_live_rpn(module)

        table_frame = ttk.Frame(tab)
        table_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(table_frame, columns=fields, show="headings", selectmode="browse")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        for field in fields:
            tree.heading(field, text=field)
            width = 220 if field in long_fields or field in image_fields else 150
            tree.column(field, width=width, minwidth=100, anchor="w", stretch=False)
        tree.bind("<Double-1>", lambda e, m=module: self.populate_form_from_selection(m))
        self.module_widgets[module]["tree"] = tree

    def _sync_text_to_var(self, module, field):
        widget = self.module_widgets[module].get("text_widgets", {}).get(field)
        if widget is not None:
            self.module_widgets[module]["vars"][field].set(widget.get("1.0", "end-1c").strip())

    def _field_value(self, module, field):
        widget = self.module_widgets[module].get("text_widgets", {}).get(field)
        if widget is not None:
            value = widget.get("1.0", "end-1c").strip()
            self.module_widgets[module]["vars"][field].set(value)
            return value
        return self.module_widgets[module]["vars"][field].get().strip()

    def _set_field_value(self, module, field, value):
        var = self.module_widgets[module]["vars"].get(field)
        if var is None:
            return
        text_widget = self.module_widgets[module].get("text_widgets", {}).get(field)
        if text_widget is not None:
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", str(value or ""))
        var.set(str(value or ""))

    def _update_live_rpn(self, module):
        vars_ = self.module_widgets[module]["vars"]
        for output, inputs in (("RPN No.", ("Severity No.", "Occurrence No.", "Detection No.")),
                               ("Revised RPN No.", ("Revised Severity No.", "Revised Occurrence No.", "Revised Detection No."))):
            try:
                nums = [int(vars_[name].get().strip()) for name in inputs]
                result = str(nums[0] * nums[1] * nums[2]) if all(1 <= n <= 10 for n in nums) else ""
            except (ValueError, KeyError):
                result = ""
            if output in vars_ and vars_[output].get() != result:
                vars_[output].set(result)
        try:
            rpn = int(vars_.get("RPN No.").get())
            if rpn >= 200:
                message, color = f"Current RPN risk: HIGH ({rpn})", "#b42318"
            elif rpn >= 100:
                message, color = f"Current RPN risk: MEDIUM ({rpn})", "#9a6700"
            else:
                message, color = f"Current RPN risk: LOW ({rpn})", "#18794e"
        except (ValueError, AttributeError, TypeError):
            message, color = "Current RPN risk: Enter Severity, Occurrence and Detection", "#526b80"
        risk_var = self.module_widgets[module].get("risk_var")
        if risk_var is not None:
            risk_var.set(message)
            # Update the displayed label colour if the widget has already been created.
            risk_label = self.module_widgets[module].get("risk_label")
            if risk_label is not None:
                risk_label.configure(foreground=color)

    def _tab_changed(self, _event=None):
        idx = self.notebook.index(self.notebook.select())
        self.active_module = ("Build Report", "DFMEA", "PFMEA")[idx]

    def _plant_root_for(self, product, plant):
        # No common fallback: the selected plant's configured path is mandatory.
        return self.load_plant_links().get(plant, "").strip()

    def _active_product_dir(self):
        root = self._plant_root()
        return os.path.join(root, safe_name(self.product_var.get())) if root else ""

    def _project_key(self):
        eao = self.project_vars["EAO No."].get().strip()
        name = self.project_vars["Project Name"].get().strip()
        model = self.project_vars["Antenna Model"].get().strip()
        # EAO is preferred as unique ID; otherwise use project name + model.
        return safe_name(eao if eao else f"{name}_{model}")

    def _project_folder(self, key=None):
        key = key or self._project_key()
        return os.path.join(self._active_product_dir(), key)

    def refresh_project_list(self):
        if not self.plant_var.get().strip():
            self.saved_project_combo["values"] = []
            self.saved_project_var.set("")
            if hasattr(self, "status_var"):
                self.status_var.set("Select IN13 or CN10 to view plant projects")
            return
        root = self._plant_root()
        if not root or not os.path.isdir(root):
            self.saved_project_combo["values"] = []
            self.saved_project_var.set("")
            if hasattr(self, "status_var"):
                self.status_var.set(f"Plant folder unavailable for {self.plant_var.get()}; check Admin Configuration")
            return
        product_dir = self._active_product_dir()
        projects = []
        try:
            if not os.path.isdir(product_dir):
                self.saved_project_combo["values"] = []
                self.saved_project_var.set("")
                self.status_var.set(f"No projects folder yet for {self.product_var.get()}")
                return
            for folder in os.listdir(product_dir):
                path = os.path.join(product_dir, folder, "project.json")
                if os.path.isfile(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        p = data.get("project", {})
                        label = f'{p.get("Project Name", folder)} | EAO: {p.get("EAO No.", "-")} | {p.get("Antenna Model", "-")}'
                        projects.append(label)
                    except (OSError, json.JSONDecodeError):
                        projects.append(folder)
        except OSError as exc:
            self.status_var.set(f"Could not read plant project folder: {exc}")
            return
        projects.sort(key=str.casefold)
        self.saved_project_combo["values"] = projects
        if self.saved_project_var.get() not in projects:
            self.saved_project_var.set("")
        self.status_var.set(f"{len(projects)} saved project(s) for {self.product_var.get()}")

    def new_project(self):
        if not self.require_admin("start a new project"):
            return
        if self._has_unsaved_changes():
            if not messagebox.askyesno("Unsaved changes", "Start a new project and discard unsaved changes?"):
                return
        self.project_data = self.empty_project()
        self.current_path = None
        self._loaded_signature = None
        self.product_var.set(self.product_var.get() or PRODUCTS[0])
        for field, var in self.project_vars.items():
            var.set("")
        for module in ("Build Report", "DFMEA", "PFMEA"):
            self.module_rows[module] = []
            self.refresh_tree(module)
            self.clear_form(module, confirm=False)
        self.saved_project_var.set("")
        self.status_var.set("New project — enter project details and save.")

    def _has_unsaved_changes(self):
        # The app does not attempt automatic change tracking; this is a conservative prompt
        # when a project has loaded or rows exist.
        return bool(self.current_path or any(self.module_rows[m] for m in self.module_rows)
                    or any(v.get().strip() for v in self.project_vars.values()))

    @staticmethod
    def _file_signature(path):
        """Content hash used to detect another engineer saving after this project was loaded."""
        try:
            with open(path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return None

    @staticmethod
    def _split_image_paths(value):
        return [part.strip().strip('"') for part in str(value or "").split(";") if part.strip()]

    def save_project(self, quiet=False):
        if not self.current_path:
            messagebox.showerror("No project selected", "Create a project from the Admin Panel, then select/load it before adding records.")
            return False
        path = self.current_path
        folder = os.path.dirname(path)
        plant = self.project_data.get("plant", self.plant_var.get())
        root = self._plant_root_for(self.project_data.get("product", self.product_var.get()), plant)
        if not root or not os.path.isdir(root) or not os.path.isdir(folder):
            messagebox.showerror("Plant folder unavailable", f"The configured plant folder or project folder is unavailable. Saving is blocked to protect data.\n\n{root or '(blank path)'}")
            return False
        current_signature = self._file_signature(path)
        if current_signature is None:
            messagebox.showerror("Project unavailable", "The project file cannot be read. Saving is blocked to avoid creating an unintended replacement.")
            return False
        if self._loaded_signature and current_signature != self._loaded_signature:
            messagebox.showerror("Project changed by another user", "Another engineer may have saved this project since you loaded it. Your changes were not saved. Refresh and reload the project before editing again.")
            return False
        try:
            image_dir = os.path.join(folder, "images")
            os.makedirs(image_dir, exist_ok=True)
            project_fields_now = {field: var.get().strip() for field, var in self.project_vars.items()}
            data = {
                "plant": plant,
                "product": self.project_data.get("product", self.product_var.get()),
                "project": project_fields_now,
                "records": {module: [dict(record) for record in self.module_rows[module]] for module in self.module_rows},
                "created_at": self.project_data.get("created_at", datetime.now().isoformat(timespec="seconds")),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "created_by": self.project_data.get("created_by", self.current_user),
                "updated_by": self.current_user,
                "audit_log": list(self.project_data.get("audit_log", [])) + [{
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "user": self.current_user,
                    "action": "Saved project records"
                }]
            }
            # Copy each image separately, preserving multiple semicolon-separated attachments.
            for module, records in data["records"].items():
                for record in records:
                    image_fields = ("Issue Related Picture", "Action Related Pictures") if module == "Build Report" else ("Failure Mode Related Photos", "Action Related Photos", "Source Build Issue Photos", "Source Build Action Photos")
                    for field in image_fields:
                        raw_value = record.get(field, "")
                        if not raw_value:
                            continue
                        saved_paths = []
                        for raw in self._split_image_paths(raw_value):
                            candidate = raw if os.path.isabs(raw) else os.path.normpath(os.path.join(folder, raw))
                            if not os.path.isfile(candidate):
                                # Keep unresolved text rather than silently deleting a reference.
                                saved_paths.append(raw)
                                continue
                            try:
                                if os.path.commonpath([os.path.abspath(candidate), os.path.abspath(folder)]) == os.path.abspath(folder):
                                    saved_paths.append(os.path.relpath(candidate, folder))
                                    continue
                            except ValueError:
                                pass
                            ext = os.path.splitext(candidate)[1] or ".png"
                            stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                            image_name = f"{safe_name(module)}_{safe_name(field)}_{stamp}_{len(saved_paths)+1}{ext}"
                            dest = os.path.join(image_dir, image_name)
                            shutil.copy2(candidate, dest)
                            saved_paths.append(os.path.relpath(dest, folder))
                        record[field] = "; ".join(saved_paths)
            temp_path = path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_path, path)
            self.project_data = data
            self._loaded_signature = self._file_signature(path)
            # Resolve saved relative paths in memory for further edits.
            for module, records in self.module_rows.items():
                for record in records:
                    for field in (("Issue Related Picture", "Action Related Pictures") if module == "Build Report" else ("Failure Mode Related Photos", "Action Related Photos", "Source Build Issue Photos", "Source Build Action Photos")):
                        vals = self._split_image_paths(record.get(field, ""))
                        if vals:
                            record[field] = "; ".join(os.path.normpath(os.path.join(folder, v)) if not os.path.isabs(v) else v for v in vals)
            self.refresh_project_list()
            if not quiet:
                self.status_var.set(f"Saved records for {plant} / {data.get('product', self.product_var.get())}: {path}")
                messagebox.showinfo("Saved", "Project records saved successfully.")
            return True
        except (OSError, TypeError, ValueError) as exc:
            messagebox.showerror("Save failed", f"Could not save the project. Check shared-folder access and image paths.\n\n{exc}")
            return False

    def load_selected_project(self):
        label = self.saved_project_var.get()
        if not label:
            messagebox.showwarning("Select project", "Choose a project from Saved Projects first.")
            return
        if self._has_unsaved_changes() and not messagebox.askyesno(
                "Load project", "Loading another project will replace the current screen. Continue?"):
            return
        product_dir = self._active_product_dir()
        if not product_dir or not os.path.isdir(product_dir):
            messagebox.showerror("Plant folder unavailable", "The selected plant/product folder is unavailable. Check Admin Configuration.")
            return
        found = None
        for folder in os.listdir(product_dir):
            path = os.path.join(product_dir, folder, "project.json")
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                p = data.get("project", {})
                candidate = f'{p.get("Project Name", folder)} | EAO: {p.get("EAO No.", "-")} | {p.get("Antenna Model", "-")}'
                if candidate == label:
                    found = (path, data)
                    break
            except (OSError, json.JSONDecodeError):
                continue
        if not found:
            messagebox.showerror("Project not found", "The selected project file could not be found or read.")
            self.refresh_project_list()
            return
        path, data = found
        self.current_path = path
        self._loaded_signature = self._file_signature(path)
        self.project_data = data
        self.plant_var.set(data.get("plant", self.plant_var.get()))
        self.product_var.set(data.get("product", self.product_var.get()))
        for field, var in self.project_vars.items():
            var.set(data.get("project", {}).get(field, ""))
        records = data.get("records", {})
        for module in ("Build Report", "DFMEA", "PFMEA"):
            self.module_rows[module] = records.get(module, [])
            # Resolve relative image paths to absolute paths for display/opening.
            image_fields = ("Issue Related Picture", "Action Related Pictures") if module == "Build Report" else ("Failure Mode Related Photos", "Action Related Photos", "Source Build Issue Photos", "Source Build Action Photos")
            for rec in self.module_rows[module]:
                for field in image_fields:
                    vals = self._split_image_paths(rec.get(field, ""))
                    if vals:
                        rec[field] = "; ".join(os.path.normpath(os.path.join(os.path.dirname(path), val)) if not os.path.isabs(val) else val for val in vals)
            self.refresh_tree(module)
            self.clear_form(module, confirm=False)
        self.status_var.set(f"Loaded: {path}")

    def link_build_report(self, module):
        """Select a Build Report record and pull its issue/action details and picture references."""
        reports = self.module_rows.get("Build Report", [])
        if not reports:
            messagebox.showinfo(
                "No Build Reports",
                "There are no Build Report findings to import. You can still create DFMEA/PFMEA entries manually. "
                "Add a Build Report finding later if you want to link it."
            )
            return

        win = tk.Toplevel(self.root)
        win.title(f"Link Build Report to {module}")
        win.geometry("900x430")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(
            win,
            text="Select a Build Report finding to import into this FMEA entry",
            font=("Arial", 11, "bold")
        ).pack(anchor="w", padx=12, pady=(12, 6))

        columns = ("Item No.", "Stage", "Category", "Severity", "Issue Description",
                   "Action Taken / Proposed Solution", "Responsible Person", "Status")
        frame = ttk.Frame(win, padding=(12, 0, 12, 8))
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
        ys = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=160, minwidth=100, stretch=False)
        for i, record in enumerate(reports):
            tree.insert("", "end", iid=str(i), values=[record.get(c, "") for c in columns])

        def apply_link(_event=None):
            selection = tree.selection()
            if not selection:
                messagebox.showwarning("Select an issue", "Choose a Build Report row first.", parent=win)
                return
            record = reports[int(selection[0])]
            vars_ = self.module_widgets[module]["vars"]
            mapping = {
                "Source Build Report Item No.": record.get("Item No.", ""),
                "Source Build Issue Description": record.get("Issue Description", ""),
                "Source Build Issue Photos": record.get("Issue Related Picture", ""),
                "Source Build Action Taken": record.get("Action Taken / Proposed Solution", ""),
                "Source Build Action Photos": record.get("Action Related Pictures", ""),
            }
            for field, value in mapping.items():
                if field in vars_:
                    self._set_field_value(module, field, value)
            self.status_var.set(f"Linked Build Report item {record.get('Item No.', '')} to {module}.")
            win.destroy()

        buttons = ttk.Frame(win, padding=(12, 0, 12, 12))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Import Selected Finding", command=apply_link).pack(side="right", padx=(5, 0))
        ttk.Button(buttons, text="Cancel", command=win.destroy).pack(side="right")
        tree.bind("<Double-1>", apply_link)

    def _calculate_fmea(self, values):
        try:
            s = int(values.get("Severity No.", ""))
            o = int(values.get("Occurrence No.", ""))
            d = int(values.get("Detection No.", ""))
            if not all(1 <= x <= 10 for x in (s, o, d)):
                raise ValueError
            values["RPN No."] = str(s * o * d)
        except ValueError:
            raise ValueError("Severity, Occurrence, and Detection must be whole numbers from 1 to 10.")
        try:
            rs = int(values.get("Revised Severity No.", ""))
            ro = int(values.get("Revised Occurrence No.", ""))
            rd = int(values.get("Revised Detection No.", ""))
            if not all(1 <= x <= 10 for x in (rs, ro, rd)):
                raise ValueError
            values["Revised RPN No."] = str(rs * ro * rd)
        except ValueError:
            # Revised ratings can be left blank until actions are completed.
            if any(values.get(f, "").strip() for f in
                   ("Revised Severity No.", "Revised Occurrence No.", "Revised Detection No.")):
                raise ValueError("Revised ratings must all be whole numbers from 1 to 10, or all be blank.")
            values["Revised RPN No."] = ""

    def _form_values(self, module):
        values = {field: self._field_value(module, field) for field in self.module_widgets[module]["vars"]}
        if module in ("DFMEA", "PFMEA"):
            self._calculate_fmea(values)
        return values

    def add_record(self, module):
        try:
            values = self._form_values(module)
        except ValueError as exc:
            messagebox.showerror("Input validation", str(exc))
            return
        if not any(values.values()):
            messagebox.showwarning("Empty entry", "Enter at least one field before adding an entry.")
            return
        values["_Created By"] = self.current_user
        values["_Created At"] = datetime.now().isoformat(timespec="seconds")
        values["_Updated By"] = self.current_user
        values["_Updated At"] = values["_Created At"]
        self.module_rows[module].append(values)
        self.refresh_tree(module)
        self.clear_form(module, confirm=False)
        if self.current_path:
            if self.save_project(quiet=True):
                self.status_var.set(f"Added entry to {module} and saved the project.")
            else:
                self.module_rows[module].pop()
                self.refresh_tree(module)
                self.status_var.set("Entry was not saved; the new row has been removed from the screen.")
        else:
            self.status_var.set(f"Added entry to {module}; select/load a project before saving it.")

    def update_record(self, module):
        tree = self.module_widgets[module]["tree"]
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select entry", "Select a row to update.")
            return
        idx = tree.index(selected[0])
        try:
            values = self._form_values(module)
        except ValueError as exc:
            messagebox.showerror("Input validation", str(exc))
            return
        if not any(values.values()):
            messagebox.showwarning("Empty entry", "Enter at least one field before updating.")
            return
        old_values = self.module_rows[module][idx]
        values["_Created By"] = old_values.get("_Created By", self.current_user)
        values["_Created At"] = old_values.get("_Created At", datetime.now().isoformat(timespec="seconds"))
        values["_Updated By"] = self.current_user
        values["_Updated At"] = datetime.now().isoformat(timespec="seconds")
        self.module_rows[module][idx] = values
        self.refresh_tree(module)
        self.clear_form(module, confirm=False)
        if self.current_path:
            if self.save_project(quiet=True):
                self.status_var.set(f"Updated entry in {module} and saved the project.")
            else:
                self.module_rows[module][idx] = old_values
                self.refresh_tree(module)
                self.status_var.set("Update was not saved; the previous row has been restored on screen.")
        else:
            self.status_var.set(f"Updated entry in {module}; select/load a project before saving it.")

    def delete_record(self, module):
        tree = self.module_widgets[module]["tree"]
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("Select entry", "Select a row to delete.")
            return
        if not messagebox.askyesno("Delete entry", "Delete the selected entry?"):
            return
        idx = tree.index(selected[0])
        deleted = self.module_rows[module].pop(idx)
        self.refresh_tree(module)
        self.clear_form(module, confirm=False)
        if self.current_path:
            if self.save_project(quiet=True):
                self.status_var.set(f"Deleted entry from {module} and saved the project.")
            else:
                self.module_rows[module].insert(idx, deleted)
                self.refresh_tree(module)
                self.status_var.set("Delete was not saved; the entry has been restored on screen.")
        else:
            self.status_var.set(f"Deleted entry from {module}; no project is loaded to save it.")

    def populate_form_from_selection(self, module):
        tree = self.module_widgets[module]["tree"]
        selected = tree.selection()
        if not selected:
            return
        idx = tree.index(selected[0])
        values = self.module_rows[module][idx]
        for field in self.module_widgets[module]["vars"]:
            self._set_field_value(module, field, values.get(field, ""))
        self._update_live_rpn(module)
        self.status_var.set(f"Editing selected {module} entry. Press Update Selected to apply changes.")

    def clear_form(self, module, confirm=False):
        for field in self.module_widgets[module]["vars"]:
            self._set_field_value(module, field, "")
        self._update_live_rpn(module)

    def refresh_tree(self, module):
        tree = self.module_widgets[module]["tree"]
        tree.delete(*tree.get_children())
        fields = BUILD_FIELDS if module == "Build Report" else FMEA_FIELDS
        for record in self.module_rows[module]:
            rpn_text = str(record.get("RPN No.", "")).strip()
            try:
                rpn = int(rpn_text)
            except (TypeError, ValueError):
                rpn = None
            if rpn is None:
                tag = "risk_unknown"
            elif rpn >= 200:
                tag = "risk_high"
            elif rpn >= 100:
                tag = "risk_medium"
            else:
                tag = "risk_low"
            tree.insert("", "end", values=[record.get(field, "") for field in fields], tags=(tag,))
        tree.tag_configure("risk_high", background="#fde2e2")
        tree.tag_configure("risk_medium", background="#fff0cc")
        tree.tag_configure("risk_low", background="#e4f4e8")
        tree.tag_configure("risk_unknown", background="white")

    def browse_image(self, module, field):
        paths = filedialog.askopenfilenames(
            title="Select picture(s)" if field == "Action Related Pictures" else "Select picture",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"), ("All files", "*.*")]
        )
        if paths:
            self._append_image_paths(module, field, paths)

    def paste_clipboard_image(self, module, field):
        """Paste an image copied with Ctrl+C from Snipping Tool, Paint, etc. into the current project."""
        if not self.current_path:
            messagebox.showwarning(
                "Select a project first",
                "Load an existing project before pasting a picture so the image can be saved with that project."
            )
            return
        try:
            from PIL import ImageGrab
        except ImportError:
            messagebox.showerror(
                "Image paste needs Pillow",
                "To enable clipboard image paste, open Command Prompt and run:\n\npython -m pip install pillow"
            )
            return
        try:
            clipboard_data = ImageGrab.grabclipboard()
            if clipboard_data is None:
                messagebox.showinfo(
                    "No image in clipboard",
                    "Copy an image first (for example, use Snipping Tool and press Ctrl+C), then click Paste."
                )
                return
            # Windows clipboard may contain copied file paths instead of pixel data.
            if isinstance(clipboard_data, list):
                paths = [p for p in clipboard_data if isinstance(p, str) and os.path.isfile(p)]
                if not paths:
                    messagebox.showinfo("No image found", "The clipboard does not contain an image or image file.")
                    return
                selected = paths if field in ("Action Related Pictures", "Action Related Photos", "Source Build Issue Photos", "Source Build Action Photos") else paths[:1]
                self._append_image_paths(module, field, selected)
                return
            if not hasattr(clipboard_data, "save"):
                messagebox.showinfo("No image found", "Copy an image, then click Paste.")
                return
            image_dir = os.path.join(os.path.dirname(self.current_path), "images")
            os.makedirs(image_dir, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            image_path = os.path.join(image_dir, f"clipboard_{stamp}.png")
            clipboard_data.save(image_path, format="PNG")
            self._append_image_paths(module, field, [image_path])
            self.status_var.set("Pasted clipboard image into the selected picture field.")
        except Exception as exc:
            messagebox.showerror("Paste failed", f"Could not paste the clipboard image.\n\n{exc}")

    def view_images(self, module, field):
        """Show image thumbnails and allow an attachment to be removed from this field."""
        raw = self._field_value(module, field)
        paths = self._split_image_paths(raw)
        if not paths:
            messagebox.showinfo("No image selected", "Use Browse or Paste to attach an image first.")
            return
        resolved = []
        base = os.path.dirname(self.current_path or "")
        for path in paths:
            candidate = path if os.path.isabs(path) else os.path.normpath(os.path.join(base, path))
            if os.path.isfile(candidate):
                resolved.append((path, candidate))
        if not resolved:
            messagebox.showwarning("Image not found", "None of the attached image paths could be found. Save or reload the project, then try again.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Attachments — {field}")
        win.geometry("760x560")
        win.transient(self.root)
        outer = ttk.Frame(win, padding=12)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text=f"{field} ({len(resolved)} attachment(s))", style="Header.TLabel").pack(anchor="w", pady=(0, 8))
        canvas = tk.Canvas(outer, highlightthickness=0)
        scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        photo_refs = []
        def remove_attachment(original):
            current = self._split_image_paths(self._field_value(module, field))
            current = [item for item in current if item != original]
            self._set_field_value(module, field, "; ".join(current))
            win.destroy()
            self.view_images(module, field) if current else messagebox.showinfo("Attachment removed", "The image reference was removed from this field.")
        for original, candidate in resolved:
            card = ttk.LabelFrame(inner, text=os.path.basename(candidate), padding=8)
            card.pack(fill="x", expand=True, pady=5)
            try:
                from PIL import Image, ImageTk
                with Image.open(candidate) as source:
                    image = source.convert("RGB")
                    image.thumbnail((260, 150))
                    photo = ImageTk.PhotoImage(image)
                photo_refs.append(photo)
                ttk.Label(card, image=photo).pack(side="left", padx=(0, 12))
            except ImportError:
                ttk.Label(card, text="Install Pillow to preview thumbnails.\nYou can still open the image using Open.").pack(side="left", padx=(0, 12))
            except Exception:
                ttk.Label(card, text="Preview unavailable").pack(side="left", padx=(0, 12))
            controls = ttk.Frame(card)
            controls.pack(side="right", fill="y")
            ttk.Button(controls, text="Open", command=lambda path=candidate: os.startfile(path)).pack(fill="x", pady=3)
            ttk.Button(controls, text="Remove attachment", command=lambda orig=original: remove_attachment(orig)).pack(fill="x", pady=3)
        win._photo_refs = photo_refs

    def _append_image_paths(self, module, field, paths):
        var = self.module_widgets[module]["vars"][field]
        existing = var.get().strip()
        chosen = "; ".join(paths)
        var.set((existing + "; " + chosen) if existing else chosen)

    def _excel_project_metadata(self):
        return {
            "Plant": self.plant_var.get().strip(),
            "Product": self.product_var.get().strip(),
            "Project Name": self.project_vars.get("Project Name", tk.StringVar()).get().strip(),
            "EAO No.": self.project_vars.get("EAO No.", tk.StringVar()).get().strip(),
            "Antenna Model": self.project_vars.get("Antenna Model", tk.StringVar()).get().strip(),
            "Team Members": self.project_vars.get("Team Members", tk.StringVar()).get().strip(),
            "Project Status": self.project_vars.get("Project Status", tk.StringVar()).get().strip(),
        }

    def _write_excel_sheet(self, workbook, title, fields, records, metadata):
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        ws = workbook.create_sheet(title=title[:31])
        ws.append(["NPI Quality Management System"])
        ws["A1"].font = Font(bold=True, size=16, color="FFFFFF")
        ws["A1"].fill = PatternFill("solid", fgColor="173E63")
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(1, len(fields)))
        ws.append([f"{k}: {v}" for k, v in metadata.items()])
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=max(1, len(fields)))
        ws["A2"].font = Font(italic=True, color="526B80")
        ws.append(fields)
        for cell in ws[3]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="2678C8" if title == "Build Report" else ("8064D8" if title == "DFMEA" else "169879"))
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        for record in records:
            ws.append([record.get(field, "") for field in fields])
        thin_gray = Side(style="thin", color="D5E2EB")
        for row in ws.iter_rows(min_row=3, max_row=ws.max_row, min_col=1, max_col=len(fields)):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                cell.border = Border(bottom=thin_gray)
        for idx, field in enumerate(fields, start=1):
            values = [len(str(field))]
            values.extend(min(55, len(str(ws.cell(r, idx).value or ""))) for r in range(4, min(ws.max_row, 100) + 1))
            ws.column_dimensions[__import__("openpyxl").utils.get_column_letter(idx)].width = max(14, min(42, max(values, default=14) + 2))
        ws.freeze_panes = "A4"
        ws.auto_filter.ref = f"A3:{__import__('openpyxl').utils.get_column_letter(len(fields))}{max(3, ws.max_row)}"
        ws.sheet_view.showGridLines = False
        return ws

    def _export_excel(self, modules, suggested_name):
        if not self.current_path:
            messagebox.showwarning("No project loaded", "Select and load an existing project before exporting reports.")
            return
        try:
            from openpyxl import Workbook
        except ImportError:
            messagebox.showerror("Excel export unavailable", "Excel export requires openpyxl. Install it with: python -m pip install openpyxl")
            return
        path = filedialog.asksaveasfilename(
            title="Export NPI reports to Excel", defaultextension=".xlsx",
            initialfile=suggested_name,
            filetypes=[("Excel workbook", "*.xlsx")]
        )
        if not path:
            return
        try:
            wb = Workbook()
            default = wb.active
            wb.remove(default)
            metadata = self._excel_project_metadata()
            for module in modules:
                fields = BUILD_FIELDS if module == "Build Report" else FMEA_FIELDS
                records = self.module_rows.get(module, [])
                self._write_excel_sheet(wb, module, fields, records, metadata)
            wb.save(path)
            messagebox.showinfo("Export complete", f"Exported {', '.join(modules)} to:\n{path}")
            self.status_var.set(f"Exported {', '.join(modules)} to Excel: {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export the reports.\n\n{exc}")

    def export_report_to_excel(self, module):
        metadata = self._excel_project_metadata()
        project_name = safe_name(metadata.get("Project Name") or "NPI_Project")
        plant = safe_name(metadata.get("Plant") or "Plant")
        product = safe_name(metadata.get("Product") or "Product")
        self._export_excel([module], f"{plant}_{product}_{project_name}_{safe_name(module)}.xlsx")

    def export_all_reports_to_excel(self):
        metadata = self._excel_project_metadata()
        project_name = safe_name(metadata.get("Project Name") or "NPI_Project")
        plant = safe_name(metadata.get("Plant") or "Plant")
        product = safe_name(metadata.get("Product") or "Product")
        self._export_excel(["Build Report", "DFMEA", "PFMEA"], f"{plant}_{product}_{project_name}_All_Reports.xlsx")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    app = NPIQualityApp(root)
    app.run()

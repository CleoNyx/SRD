import json, os, requests
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_wtf import FlaskForm
from flask_wtf.csrf import CSRFProtect, CSRFError
from wtforms import StringField, PasswordField, SubmitField, SelectField, IntegerField
from wtforms.validators import DataRequired, Email, Length, NumberRange
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from backend.config import Settings
from backend.models import Base, User
from backend.grafana_api import ensure_prometheus_datasource, ensure_folder, upsert_dashboard, list_datasources, list_dashboards
from backend.prom_alerts import build_rules_yaml, write_rules_and_reload
from flask_cors import CORS  # Optional if serving frontend elsewhere
import requests

settings = Settings()
app = Flask(__name__)
# If your HTML is served from the same Flask app, you can remove CORS.
CORS(app)
app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.config["SECRET_KEY"] = settings.SECRET_KEY
# Keep CSRF enabled globally for security, but can disable via .env if needed
app.config["WTF_CSRF_ENABLED"] = True  # can toggle via .env below
# CSRFProtect(app)
csrf = CSRFProtect(app)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template("index.html") + f"<pre class='codeblock'>CSRF error: {e.description}</pre>", 400
# CSRFProtect(app)  # Enable CSRF protection globally

@app.errorhandler(500)
def internal_error(e):
    app.logger.exception("Unhandled 500", exc_info=e)
    # Render a simple page that extends index.html (1 block only)
    return render_template("error.html", error=e), 500

GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3001")
GRAFANA_TOKEN = os.environ.get("GRAFANA_TOKEN")  # REQUIRED

if not GRAFANA_TOKEN:
  # Fail fast so you know to set it
  raise RuntimeError("GRAFANA_TOKEN is not set. Export your service account token.")

engine = create_engine("sqlite:///srd_users.db", echo=False, future=True)
Base.metadata.create_all(engine)

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    with Session(engine) as s:
        return s.get(User, int(user_id))

class LoginForm(FlaskForm):
    # Disable CSRF for this form only (keeps CSRF enabled elsewhere)
    class Meta:
        csrf = False

    # allow private/internal domains (no deliverability check) for admins creating the first user
    # Relax the email validator so private domains are ok
    # email = StringField("Email", validators=[DataRequired()])  # <- simple check only
    email = StringField("Email", validators=[Email(check_deliverability=False), DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")

class UserForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(min=2, max=120)])
    # same relaxation here for admins creating users
    email = StringField("Email", validators=[Email(), DataRequired()])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    role = SelectField("Role", choices=[("user", "User"), ("admin", "Admin")])
    submit = SubmitField("Save")

class ThresholdForm(FlaskForm):
    cpu = IntegerField("CPU threshold (%)", validators=[DataRequired(), NumberRange(min=10, max=100)])
    memory = IntegerField("Memory threshold (%)", validators=[DataRequired(), NumberRange(min=10, max=100)])
    disk = IntegerField("Disk threshold (%)", validators=[DataRequired(), NumberRange(min=10, max=100)])
    submit = SubmitField("Update & Reload")

def require_admin():
    if not current_user.is_authenticated or current_user.role != "admin":
        abort(403)

def _grafana_headers():
    return {"Authorization": f"Bearer {settings.GRAFANA_TOKEN}", "Content-Type": "application/json"}

def gf(path, method="GET", body=None, params=None):
  url = f"{GRAFANA_URL}{path}"
  resp = requests.request(method, url, headers=g_headers(), json=body, params=params, timeout=30)
  # Raise for non-2xx to catch in try/except for clearer errors
  if not resp.ok:
    # Try to extract Grafana error message
    try:
      msg = resp.json()
    except Exception:
      msg = resp.text
    raise requests.HTTPError(f"{resp.status_code} {resp.reason}: {msg}")
  # Return JSON if possible, else raw text
  try:
    return resp.json()
  except ValueError:
    return {"text": resp.text}

def ensure_datasource(ds_payload):
  """
  Try to create the datasource. If it already exists, return its info.
  """
  try:
    created = gf("/api/datasources", method="POST", body=ds_payload)
    return {"created": True, "data": created}
  except requests.HTTPError as e:
    # Datasource may already exist; try to GET by name
    if "409" in str(e) or "already exists" in str(e).lower():
      # List and find by name
      all_ds = gf("/api/datasources")
      match = next((d for d in all_ds if d.get("name") == ds_payload.get("name")), None)
      if match:
        return {"created": False, "data": match}
    # Unexpected error
    raise

def ensure_folder(title):
  """
  Create folder (POST /api/folders). If exists, return existing by title.
  """
  try:
    created = gf("/api/folders", method="POST", body={"title": title})
    return {"created": True, "data": created}
  except requests.HTTPError as e:
    # If already exists, list and return the one with matching title
    if "409" in str(e) or "already exists" in str(e).lower():
      folders = gf("/api/folders")
      match = next((f for f in folders if f.get("title") == title), None)
      if match:
        return {"created": False, "data": match}
    raise

def upsert_dashboard(dashboard_payload, folder_uid):
  """
  Create/update dashboard in a folder (POST /api/dashboards/db with overwrite).
  dashboard_payload should at least contain: { uid, title, panels? }
  """
  # Grafana expects a "dashboard" object with schemaVersion, etc.
  base_dashboard = {
    "uid": dashboard_payload.get("uid", None),
    "title": dashboard_payload.get("title", "New Dashboard"),
    "timezone": "browser",
    "schemaVersion": 39,  # adjust to your Grafana version if needed
    "version": 1,
    "panels": dashboard_payload.get("panels", []),
  }

  body = {
    "dashboard": base_dashboard,
    "folderUid": folder_uid,
    "overwrite": True
  }
  return gf("/api/dashboards/db", method="POST", body=body)

# --- Routes ---

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("admin_home" if current_user.role=="admin" else "user_home"))
    return redirect(url_for("login"))

'''@app.route("/login", methods=["GET","POST"])               # removed to disable login for now
def login():
    # Create default admin only once (first ever run)
    with Session(engine) as s:
        if s.query(User).count() == 0:
            admin = User(email="admin@srd.local", name="Admin", role="admin")
            admin.set_password("ChangeMe123!")
            s.add(admin); s.commit()
            flash("Default admin created: admin@srd.local / ChangeMe123! (please change)", "warning")

    form = LoginForm()
    # <-- If POST and valid, try to log in
    if form.validate_on_submit():
        with Session(engine) as s:
            user = s.execute(select(User).where(User.email==form.email.data)).scalar_one_or_none()
            if user and user.is_active and user.check_password(form.password.data):
                login_user(user)
                return redirect(url_for("index"))
        flash("Invalid credentials", "danger")
        return render_template("login.html", form=form)
    
    # <-- If POST but not valid, surface the errors (CSRF, email, etc.)
    if request.method == "POST":
        app.logger.warning(f"Login form errors: {form.errors}")
        # Show the first error to the user
        human_error = "; ".join([f"{k}: {', '.join(v)}" for k,v in form.errors.items()]) or "Form validation failed."
        flash(human_error, "danger")

    return render_template("login.html", form=form) '''

# Login (CSRF exempt so it won’t block)
@csrf.exempt
@app.route("/login", methods=["GET","POST"])
def login():
    # Create default admin only once (first ever run)
    with Session(engine) as s:
        if s.query(User).count() == 0:
            admin = User(email="admin@srd.local", name="Admin", role="admin")
            admin.set_password("ChangeMe123!")
            s.add(admin); s.commit()
            flash("Default admin created: admin@srd.local / ChangeMe123! (please change)", "warning")

    form = LoginForm()

    if request.method == "POST":
        # No CSRF/email hurdles here; just authenticate
        email = (form.email.data or "").strip().lower()
        pwd   = form.password.data or ""
        with Session(engine) as s:
            user = s.execute(select(User).where(User.email == form.email.data)).scalar_one_or_none()
            if user and user.is_active and user.check_password(form.password.data):
                login_user(user)
                return redirect(url_for("index"))
        flash("Invalid credentials or inactive account.", "danger")
        # PRG: redirect so the form is a fresh GET (fields empty)
        return render_template("login.html", form=form)

    # GET: ensure the form has NO bound data
    form.process(formdata=None)
    return render_template("login.html", form=form)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# --- JSON status endpoint ---
@app.route("/api/status")
@login_required
def api_status():
    status = {"prometheus": False, "grafana": False}
    try:
        r = requests.get(settings.PROMETHEUS_URL, timeout=2)
        status["prometheus"] = (r.status_code == 200)
    except Exception:
        status["prometheus"] = False
    try:
        r = requests.get(f"{settings.GRAFANA_URL}/api/health", headers=_grafana_headers(), timeout=2)
        status["grafana"] = (r.status_code == 200)
    except Exception:
        status["grafana"] = False
    return jsonify(status)

# --- Admin area ---
@app.route("/admin")
@login_required
def admin_home():
    require_admin()
    return render_template("admin_home.html", prom_ok=True, graf_ok=True, settings=settings)


@app.route("/admin/users", methods=["GET","POST"])
@login_required
def manage_users():
    require_admin()
    form = UserForm()
    created = None
    if form.validate_on_submit():
        with Session(engine) as s:
            if s.execute(select(User).where(User.email==form.email.data)).first():
                flash("Email already exists", "danger")
            else:
                u = User(email=form.email.data, name=form.name.data, role=form.role.data)
                u.set_password(form.password.data)
                s.add(u); s.commit()
                created = u
                flash("User created", "success")
    with Session(engine) as s:
        users = s.query(User).all()
    return render_template("manage_users.html", users=users, form=form, created=created)

@app.route("/admin/users/<int:user_id>/toggle")
@login_required
def toggle_user(user_id):
    require_admin()
    with Session(engine) as s:
        u = s.get(User, user_id)
        if not u: abort(404)
        u.is_active = not u.is_active
        s.commit()
    return redirect(url_for("manage_users"))

@app.route("/admin/provision", methods=["POST"])
@login_required
def provision():
  """
  Expects JSON:
  {
    "datasource": { name, type, url, access?, isDefault? },
    "folder": { title },
    "dashboard": { uid, title, panels? }
  }
  """
  try:
    payload = request.get_json(force=True) or {}
    ds_payload = payload.get("datasource") or {
      "name": "Prometheus",
      "type": "prometheus",
      "url": "http://prometheus:9090",
      "access": "proxy",
      "isDefault": True,
    }
    folder_payload = payload.get("folder") or { "title": "SRD Monitoring" }
    dash_payload = payload.get("dashboard") or { "uid": "srd-api", "title": "SRD HTTP API Dashboard", "panels": [] }

    # 1) Ensure datasource
    ds_result = ensure_datasource(ds_payload)

    # 2) Ensure folder
    folder_result = ensure_folder(folder_payload["title"])
    folder_uid = folder_result["data"]["uid"]

    # 3) Upsert dashboard in that folder
    dash_result = upsert_dashboard(dash_payload, folder_uid)

    return jsonify({
      "ok": True,
      "grafana_url": GRAFANA_URL,
      "datasource": ds_result,
      "folder": folder_result,
      "dashboard": dash_result
    })

  except requests.HTTPError as http_err:
    return jsonify({"ok": False, "error": str(http_err)}), 502
  except Exception as e:
    return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/admin/provision-all", methods=["POST"])
@login_required
def provision_all():
    require_admin()

    # 1) Ensure Prometheus datasource
    prom_uid, _ = ensure_prometheus_datasource(settings.GRAFANA_URL, settings.GRAFANA_TOKEN, settings.PROMETHEUS_URL)

    # 2) Ensure folder
    folder_uid = ensure_folder(settings.GRAFANA_URL, settings.GRAFANA_TOKEN, settings.GRAFANA_FOLDER_TITLE)

    # 3) Load dashboard JSON and inject datasource UID
    path = os.path.join(os.path.dirname(__file__), "grafana", "dashboard_http_api.json")
    with open(path, "r", encoding="utf-8") as f:
        dash = json.load(f)
        
    def inject(obj):
        if isinstance(obj, dict):
            for k,v in list(obj.items()):
                obj[k] = inject(v)
            if obj.get("type")=="prometheus" and obj.get("uid")=="__PROM__":
                obj["uid"] = prom_uid
            return obj
        if isinstance(obj, list):
            return [inject(x) for x in obj]
        return obj
    
    dash = inject(dash)
    dash["title"] = settings.GRAFANA_DASHBOARD_TITLE

    # 4) Upsert via Grafana HTTP API
    res = upsert_dashboard(settings.GRAFANA_URL, settings.GRAFANA_TOKEN, folder_uid, dash, overwrite=True)

    # Grafana typically returns {"status":"success","uid":"...","url":"/d/uid/slug","version":...}
    dash_url_path = res.get("url") or ""
    full_url = f"{settings.GRAFANA_URL}{dash_url_path}" if dash_url_path else settings.GRAFANA_URL
    return jsonify({
        "ok": True,
        "message": "Dashboard provisioned successfully.",
        "grafana_dashboard_url": full_url,
        "grafana_folder": settings.GRAFANA_FOLDER_TITLE,
        "grafana_dashboard_title": settings.GRAFANA_DASHBOARD_TITLE,
        "raw": res
    })

@app.route("/api/alerts/update", methods=["POST"])
@login_required
def api_alerts_update():
    require_admin()
    data = request.get_json(force=True, silent=True) or {}
    try:
        cpu = int(data.get("cpu", 80))
        memory = int(data.get("memory", 80))
        disk = int(data.get("disk", 80))
        for v in (cpu, memory, disk):
            if v < 10 or v > 100:
                raise ValueError("threshold out of range")
    except Exception as e:
        return jsonify({"error": f"Invalid thresholds: {e}"}), 400
    yaml_text = build_rules_yaml({"cpu": cpu, "memory": memory, "disk": disk})
    write_rules_and_reload(settings.PROM_RULES_PATH, yaml_text, settings.PROM_RELOAD_URL, settings.ALERTMANAGER_RELOAD_URL)
    return jsonify({"status": "ok", "cpu": cpu, "memory": memory, "disk": disk})

@app.route("/admin/edit-dashboard", methods=["GET","POST"])
@login_required
def edit_dashboard():
    require_admin()
    path = os.path.join(os.path.dirname(__file__), "grafana", "dashboard_http_api.json")
    if request.method == "POST":
        new_text = request.form.get("json_text", "")
        try:
            json.loads(new_text)
        except Exception as e:
            flash(f"JSON error: {e}", "danger")
            return render_template("edit_dashboard.html", text=new_text)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
        flash("Saved. Click 'Provision' on Admin Home to apply.", "success")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return render_template("edit_dashboard.html", text=text)

@app.route("/admin/alerts", methods=["GET","POST"])
@login_required
def alert_settings():
    require_admin()
    form = ThresholdForm()
    if form.validate_on_submit():
        yaml_text = build_rules_yaml({"cpu": form.cpu.data, "memory": form.memory.data, "disk": form.disk.data})
        write_rules_and_reload(settings.PROM_RULES_PATH, yaml_text, settings.PROM_RELOAD_URL, settings.ALERTMANAGER_RELOAD_URL)
        flash("Rules updated and Prometheus reloaded.", "success")
        return redirect(url_for("admin_home"))
    form.cpu.data, form.memory.data, form.disk.data = 80,80,80
    return render_template("alert_settings.html", form=form)

@app.route("/admin/grafana-info")
@login_required
def grafana_info():
    require_admin()
    try:
        dss = list_datasources(settings.GRAFANA_URL, settings.GRAFANA_TOKEN)
        dashes = list_dashboards(settings.GRAFANA_URL, settings.GRAFANA_TOKEN)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"datasources": dss, "dashboards": dashes})

@app.route("/user")
@login_required
def user_home():
    if current_user.role not in ("user","admin"):
        abort(403)
    return render_template("user_home.html", grafana_url=settings.GRAFANA_URL,
                           folder_title=settings.GRAFANA_FOLDER_TITLE,
                           dashboard_title=settings.GRAFANA_DASHBOARD_TITLE)

@app.errorhandler(500)
def internal_error(e):
    # Shows a friendlier message, and you still get the full traceback in the terminal with FLASK_DEBUG=1
    return render_template("index.html") + "<pre class='codeblock'>Server error – check the terminal for the traceback.</pre>", 500

if __name__ == "__main__":
    app.run(host=settings.FLASK_HOST, port=settings.FLASK_PORT)

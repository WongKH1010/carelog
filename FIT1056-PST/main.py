import datetime as dt
from flask import Flask, abort, render_template, redirect, url_for, flash, request, session
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import login_user, LoginManager, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from forms import RegisterForm, LoginForm, FeedbackForm, PatientProfileForm, SearchPatientForm, EditProfileForm, \
    PasswordChangeForm, CreateAppointmentForm, CreatePatientLogForm, PatientNoteForm, StaffPatientProfileForm, \
    SearchAccountForm, RoleForm
from functools import wraps
from dotenv import load_dotenv
import os
import requests
from app.models import User, PatientProfile, PatientLog, Appointment, db, Role


load_dotenv(".env")
SHEETY_ENDPOINT = os.environ.get("SHEETY_ENDPOINT")

# App setup
app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap5(app)
app.config['PERMANENT_SESSION_LIFETIME'] = dt.timedelta(minutes=10)

# Databases
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db.init_app(app)

with app.app_context():
    db.create_all()

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.role_level != 4:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))



# HOME PAGES
@app.route("/test")
def test():
    return render_template("admin_base.html")

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if request.method == "POST":
        if form.validate_on_submit():
            # Checks if email already exists.
            account = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
            # If email exists
            if account:
                flash("That email is already registered. Try logging in instead.", "error")
                return redirect(url_for("register"))
            else:
                new_user = User(
                    username=form.name.data,
                    email=form.email.data,
                    gender=form.gender.data,
                    dob=form.dob.data,
                    contact=form.tel.data,
                    password=generate_password_hash(form.password.data, salt_length=8),
                    role_level=Role.PATIENT
                )
                db.session.add(new_user)
                db.session.commit()

                login_user(new_user)
                session.permanent = True
                flash("Successfully created account", "success")
                return redirect(url_for("home"))
    return render_template("account_register.html", form=form, type="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        account = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if account:
            if check_password_hash(account.password, form.password.data):
                login_user(account)
                session.permanent = True
                flash("Successfully logged in", "success")
                return redirect(url_for("home"))
            else:
                flash("Invalid credentials", "error")
                return redirect(url_for("login"))
        else:
            flash("That email has not been registered. Try signing up instead.", "danger")
            return redirect(url_for("login"))
    return render_template("account_login.html", form=form, type="login")

@login_required
@app.route("/logout", methods=["POST"])
def logout():
    flash("Successfully logged out of account", "success")
    logout_user()
    return redirect(url_for("home"))

@login_required
@app.route("/profile")
def profile():
    role = Role(current_user.role_level).name
    patient_profile = current_user.patient_profile
    log_list = []
    if patient_profile:
        for log in patient_profile.patient_logs:
            log_list.append({
                "date": log.date,
                "time": log.time,
                "created_by": current_user.username,
                "medical": log.medical,
                "emotional": log.emotional,
                "notes": log.note,
                "patient_note": log.patient_note,
                "add": f"<a href='{url_for("add_patient_notes", log_id=log.id)}' class='btn btn-primary btn-sm'>Add Notes</a>",
            })
    titles = [
        ("date", "Date"),
        ("time", "Time"),
        ("created_by", "Created By"),
        ("medical", "Medical Observations"),
        ("emotional", "Emotional State"),
        ("notes", "Notes"),
        ("patient_note", "Patient Notes"),
        ("add", "#"),
    ]
    return render_template("profile.html", role=role, patient_profile=patient_profile, log_list=log_list, titles=titles)

@app.route("/profile/log/<int:log_id>/add_note", methods=["GET", "POST"])
def add_patient_notes(log_id):
    log = db.session.get(PatientLog, log_id)
    form = PatientNoteForm(note=log.patient_note)
    if request.method == "POST" and form.validate_on_submit():
        log.patient_note = form.note.data
        db.session.commit()
        return redirect(url_for("profile"))
    return render_template("add_patient_note.html", form=form)


@app.route("/profile/edit", methods=["GET","POST"])
def edit_profile():
    form = EditProfileForm(
        name=current_user.username,
        gender=current_user.gender,
        dob=current_user.dob,
        tel=current_user.contact
    )
    if request.method == "POST" and form.validate_on_submit():
        current_user.name = form.name.data
        current_user.gender = form.gender.data
        current_user.dob = form.dob.data
        current_user.contact = form.tel.data
        db.session.commit()
    return render_template("edit_user_profile.html", form=form)

@app.route("/profile/edit/password", methods=["GET", "POST"])
def change_password():
    form = PasswordChangeForm()
    if request.method == "POST" and form.validate_on_submit():
        if check_password_hash(current_user.password, form.old_pass.data):
            current_user.password = generate_password_hash(form.password.data, salt_length=8)
            db.session.commit()
            flash("Successfully changed password", "success")
            return redirect(url_for("profile"))
        else:
            flash("Password Incorrect", "error")
            return redirect(url_for("change_password"))
    return render_template("change_password.html", form=form)

@app.route("/profile/create", methods=["GET", "POST"])
def create_patient_profile():
    form = PatientProfileForm()
    if request.method == "POST":
        if form.validate_on_submit():
            new_profile = PatientProfile(
                cultural = form.cultural.data,
                dietary = form.dietary.data,
                allergens = form.allergens.data,
                medical_history = form.medical_history.data,
                user_id = current_user.id,
                risk_level = "Low"
            )
            db.session.add(new_profile)
            db.session.commit()
            flash("Successfully created patient profile", "success")
        return redirect(url_for("profile"))
    return render_template("profile_edit.html", form=form)

@app.route("/profile/patient/edit", methods=["GET", "POST"])
def edit_patient_profile():
    cur_profile = current_user.patient_profile
    form = PatientProfileForm(
        cultural=cur_profile.cultural,
        dietary=cur_profile.dietary,
        allergens=cur_profile.allergens,
        medical_history=cur_profile.medical_history
    )
    if request.method == "POST":
        if form.validate_on_submit():
            cur_profile.cultural = form.cultural.data
            cur_profile.dietary = form.dietary.data
            cur_profile.allergens = form.allergens.data
            cur_profile.medical_history = form.medical_history.data
            flash("Successfully edited patient profile", "success")

            db.session.commit()
        return redirect(url_for("profile"))
    return render_template("profile_edit.html", form=form, editing=True)

@app.route("/appointment")
def appointment():
    appointments = sorted(
        current_user.appointments,
        key=lambda a: (a.date, a.time),
        reverse=True
    )
    return render_template("appointments.html", appointments=appointments)

@app.route("/appointment/create", methods=["GET","POST"])
def create_appointment():
    form = CreateAppointmentForm()
    if request.method == "POST" and form.validate_on_submit():
        new_appointment = Appointment(
                            date=form.date.data,
                            time=form.time.data,
                            reason=form.reason.data,
                            created_by=current_user.id,
                            status="Pending",
                            patient_id = current_user.id,
                        )
        db.session.add(new_appointment)
        db.session.commit()
        flash("Successfully booked an appointment", "success")
        return redirect(url_for("appointment"))
    return render_template("create_appointment.html", form=form)


@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    form = FeedbackForm()
    if request.method == "POST" and form.validate_on_submit():
        new_row = {
            "feedback": {
                "name": form.name.data,
                "email": form.email.data,
                "feedback_type": form.feedback_type.data,
                "rating": form.rating.data,
                "category": form.category.data,
                "message": form.message.data,
                "anonymous": form.anonymous.data,
            }
        }
        requests.post(SHEETY_ENDPOINT, json=new_row)
        flash("Successfully sent feedback", "success")
        return redirect(url_for("feedback"))
    return render_template("feedback.html", form=form)

@app.route("/staff/patients", methods=["POST","GET"])
def patient_page():
    form = SearchPatientForm()
    patients = db.select(User).where(User.role_level == 0)
    if request.method == "POST" and form.validate_on_submit():
        if form.search.data.strip() != "":
            patients = patients.where(User.username.ilike(f"%{form.search.data}%"))
        if form.gender.data:
            patients = patients.where(User.gender == form.gender.data)
        if form.min_age.data:
            patients = patients.where(User.dob <= dt.date.today() - dt.timedelta(form.min_age.data))
        if form.max_age.data:
            patients = patients.where(User.dob >= dt.date.today() - dt.timedelta(form.max_age.data))
        if form.risk_level.data:
            patients = patients.join(User.patient_profile).where(PatientProfile.risk_level == form.risk_level.data)
    patients = db.session.execute(patients).scalars().all()
    patient_list = []
    if patients:
        for patient in patients:
            if patient.patient_profile:
                risk = patient.patient_profile.risk_level
            else:
                risk = None
            profile_url = url_for("patient_details", patient_id=patient.id)
            patient_list.append(
                {
                    "name": patient.username,
                    "dob": patient.dob,
                    "gender": patient.gender,
                    "risk_level": risk,
                    "profile": f"<a href='{ profile_url }' class='btn btn-primary btn-sm'>Profile</a>"
                }
            )
    else:
        patient_list.append({}),
    titles = [
        ("name","Patient Name"),
        ("dob", "DOB"),
        ("gender", "Gender"),
        ("risk_level", "Risk Level"),
        ("profile", "#")
    ]


    return render_template("patient_list.html", form=form, patient_list=patient_list, titles=titles)

@app.route("/staff/patients/<int:patient_id>")
def patient_details(patient_id):
    result = db.session.execute(db.select(User).where(User.id == patient_id, User.role_level == 0)).scalar()
    if result.patient_profile:
        patient_log = result.patient_profile.patient_logs
        log_list = []
        if patient_log:
            for log in patient_log:
                log_list.append({
                    "date": log.date,
                    "time": log.time,
                    "created_by": current_user.username,
                    "medical": log.medical,
                    "emotional": log.emotional,
                    "notes": log.note,
                    "patient_note": log.patient_note,
                    "edit": f"<a href='{ url_for("edit_log", patient_id=patient_id, log_id=log.id) }' class='btn btn-primary btn-sm'>Edit</a>",
                })
        else:
            log_list = [{}]
    else:
        log_list = [{}]
    titles = [
        ("date", "Date"),
        ("time", "Time"),
        ("created_by", "Created By"),
        ("medical", "Medical Observations"),
        ("emotional", "Emotional State"),
        ("notes", "Notes"),
        ("patient_note", "Patient Notes"),
        ("edit", "#"),
    ]
    return render_template("patient_profiles.html", patient=result, log_list=log_list, titles=titles)

@app.route("/staff/patients/<int:patient_id>/log/<int:log_id>/edit", methods=["GET", "POST"])
def edit_log(patient_id, log_id):
    log = db.session.get(PatientLog, log_id)
    form = CreatePatientLogForm(
        medical= log.medical,
        emotional= log.emotional,
        note= log.note,
    )
    if request.method == "POST" and form.validate_on_submit():
        log.medical = form.medical.data
        log.emotional = form.emotional.data
        log.note = form.note.data
        db.session.commit()
        return redirect(url_for("patient_details", patient_id=patient_id))
    return render_template("create_patient_log.html", form=form, edit=True)

@app.route("/staff/patients/<int:patient_id>/create", methods=["GET","POST"])
def create_profile_staff(patient_id):
    form = PatientProfileForm()
    if request.method == "POST":
        if form.validate_on_submit():
            new_profile = PatientProfile(
                cultural=form.cultural.data,
                dietary=form.dietary.data,
                allergens=form.allergens.data,
                medical_history=form.medical_history.data,
                user_id=patient_id,
                risk_level="Low"
            )
            db.session.add(new_profile)
            db.session.commit()
        return redirect(url_for("patient_details", patient_id=patient_id))
    return render_template("profile_edit.html", form=form)

@app.route("/staff/patients/<int:patient_id>/edit", methods=["GET","POST"])
def edit_profile_staff(patient_id):
    cur_profile = db.session.get(User, patient_id).patient_profile
    form = StaffPatientProfileForm(
        cultural=cur_profile.cultural,
        dietary=cur_profile.dietary,
        allergens=cur_profile.allergens,
        medical_history=cur_profile.medical_history,
        risk=cur_profile.risk_level
    )
    if request.method == "POST":
        if form.validate_on_submit():
            cur_profile.cultural = form.cultural.data
            cur_profile.dietary = form.dietary.data
            cur_profile.allergens = form.allergens.data
            cur_profile.medical_history = form.medical_history.data
            cur_profile.risk_level = form.risk.data
            flash("Successfully edited patient profile", "success")

            db.session.commit()
        return redirect(url_for("patient_details", patient_id=patient_id))
    return render_template("profile_edit.html", form=form, editing=True)

@app.route("/staff/patients/<int:patient_id>/log/create", methods=["GET", "POST"])
def create_patient_log(patient_id):
    form = CreatePatientLogForm()
    if request.method == "POST" and form.validate_on_submit():
        new_log = PatientLog(
            date=dt.date.today(),
            time=dt.datetime.today().time(),
            medical=form.medical.data,
            emotional=form.emotional.data,
            note=form.note.data,
            created_by=current_user.username,
            profile_id=db.session.get(User, patient_id).patient_profile.id
        )
        db.session.add(new_log)
        db.session.commit()
        flash("Successfully added a patient log", "success")
        return redirect(url_for("patient_details", patient_id=patient_id))
    return render_template("create_patient_log.html", form=form, patient_id=patient_id)

@app.route("/staff/appointments")
def staff_appointment():
    user_appointments = db.session.execute(
        db.select(Appointment).where(Appointment.doctor_id == current_user.id)
    ).scalars().all()

    pending_appointments = db.session.execute(
        db.select(Appointment).where(
            Appointment.doctor_id.is_(None),
            Appointment.status == "Pending"
        )
    ).scalars().all()

    return render_template(
        "staff_appointments.html",
        user_appointments=user_appointments,
        pending_appointments=pending_appointments
    )


@app.route("/staff/appointments/<int:appointment_id>/accept", methods=["POST"])
def accept_appointment(appointment_id):
    appointment = db.session.get(Appointment, appointment_id)
    appointment.doctor_id = current_user.id
    appointment.status = "Scheduled"
    db.session.commit()
    return redirect(url_for("staff_appointment"))

@app.route("/staff/appointments/<int:appointment_id>/complete", methods=["POST"])
def complete_appointment(appointment_id):
    appointment = db.session.get(Appointment, appointment_id)
    appointment.status = "Completed"
    db.session.commit()
    return redirect(url_for("staff_appointment"))

@app.route("/staff/appointments/<int:appointment_id>/cancel", methods=["POST"])
def cancel_appointment(appointment_id):
    appointment = db.session.get(Appointment, appointment_id)
    appointment.status = "Cancelled"
    db.session.commit()
    if request.args.get("patient"):
        return redirect(url_for("appointment"))
    return redirect(url_for("staff_appointment"))

@app.route("/staff/patients/<int:patient_id>/appointment/create", methods=["GET", "POST"])
def staff_create_appointment(patient_id):
    form = CreateAppointmentForm()
    if request.method == "POST" and form.validate_on_submit():
        if current_user.role_level == 3:
            new_appointment = Appointment(
                date=form.date.data,
                time=form.time.data,
                reason=form.reason.data,
                created_by=current_user.id,
                status="Scheduled",
                patient_id=patient_id,
                doctor_id=current_user.id
            )
        else:
            new_appointment = Appointment(
                date=form.date.data,
                time=form.time.data,
                reason=form.reason.data,
                created_by=current_user.id,
                status="Pending",
                patient_id=patient_id,
            )
        db.session.add(new_appointment)
        db.session.commit()
        flash("Successfully booked an appointment", "success")
        return redirect(url_for("appointment"))
    return render_template("create_appointment.html", form=form)

@app.route("/staff/reports")
def reports():
    total_patients = db.session.query(User).where(User.role_level == 0).count()
    total_appointments = db.session.query(Appointment).where(Appointment.status != "Cancelled").count()
    total_logs = db.session.query(PatientLog).count()
    high_risk = db.session.query(User).join(User.patient_profile).where(User.role_level == 0).filter_by(risk_level="High").count()

    appointments_per_month_query = (
        db.session.query(
            func.strftime("%Y-%m", Appointment.date).label("month"),
            func.count(Appointment.id)
        )
        .group_by("month")
        .order_by("month")
        .all()
    )

    appointments_per_month = {
        dt.datetime.strptime(month, "%Y-%m").strftime("%b %Y"): count
        for month, count in appointments_per_month_query
    }

    risk_distribution = {
        "Low": db.session.query(User).join(User.patient_profile).where(User.role_level == 0).filter_by(risk_level="Low").count(),
        "Moderate": db.session.query(User).join(User.patient_profile).where(User.role_level == 0).filter_by(risk_level="Moderate").count(),
        "High": db.session.query(User).join(User.patient_profile).where(User.role_level == 0).filter_by(risk_level="High").count()
    }

    today = dt.date.today()
    seven_days_ago = today - dt.timedelta(days=6)

    logs_over_time_query = (
        db.session.query(
            func.strftime("%Y-%m-%d", PatientLog.date).label("day"),
            func.count(PatientLog.id)
        )
        .filter(PatientLog.date.between(seven_days_ago, today))
        .group_by("day")
        .order_by("day")
        .all()
    )

    logs_over_time = {
        dt.datetime.strptime(day, "%Y-%m-%d").strftime("%d %b"): count
        for day, count in logs_over_time_query
    }

    doctors = db.session.query(User).where(User.role_level == 3)
    doctor_activity = {
        doctor.username: db.session.query(PatientLog).where(PatientLog.created_by == doctor.id).count() for doctor in doctors
    }
    #
    # # 5️⃣ Attachments Uploaded Over Time (past 6 months)
    # attachments_per_month = {
    #     (datetime.now() - timedelta(days=i * 30)).strftime("%b %Y"): random.randint(10, 50)
    #     for i in reversed(range(6))
    # }
    #
    # return render_template("staff_reports.html",
    #                        appointments_per_month=appointments_per_month,
    #                        risk_distribution=risk_distribution,
    #                        logs_over_time=logs_over_time,
    #                        doctor_activity=doctor_activity,
    #                        attachments_per_month=attachments_per_month
    #                        )

    return render_template("staff_reports.html",
                           total_patients=total_patients,
                           total_appointments=total_appointments,
                           total_logs=total_logs,
                           high_risk=high_risk,
                           appointments_per_month=appointments_per_month,
                           risk_distribution=risk_distribution,
                           logs_over_time=logs_over_time,
                           doctor_activity=doctor_activity,
                           )

@app.route("/staff/risk-dashboard")
def risk_dashboard():
    # Get risk level counts
    risk_data = (
        db.session.query(PatientProfile.risk_level, func.count(PatientProfile.id))
        .group_by(PatientProfile.risk_level)
        .all()
    )

    risk_distribution = {level or "Unknown": count for level, count in risk_data}

    risk_patients = {
        "High": PatientProfile.query.filter_by(risk_level="High").all(),
        "Medium": PatientProfile.query.filter_by(risk_level="Moderate").all(),
        "Low": PatientProfile.query.filter_by(risk_level="Low").all(),
    }

    total_patients = sum(risk_distribution.values())
    high_risk = risk_distribution.get("High", 0)
    medium_risk = risk_distribution.get("Moderate", 0)
    low_risk = risk_distribution.get("Low", 0)

    print(risk_patients.items())

    return render_template(
        "risk_dashboard.html",
        risk_distribution=risk_distribution,
        total_patients=total_patients,
        high_risk=high_risk,
        medium_risk=medium_risk,
        low_risk=low_risk,
        risk_patients=risk_patients
    )

# @app.route("/staff/alert-and-notes")
# def alert_and_notes():
#     pass

# @app.route("/admin/manage-patients")
# def manage_patients():
#     pass

@app.route("/admin/manage-staff", methods=["GET", "POST"])
def manage_staff():
    form = SearchAccountForm()
    accounts = db.select(User)
    if request.method == "POST" and form.validate_on_submit():
        if form.search.data.strip() != "":
            accounts = accounts.where(User.username.ilike(f"%{form.search.data}%"))
        if form.gender.data:
            accounts = accounts.where(User.gender == form.gender.data)
        if form.role.data:
            accounts = accounts.where(User.role_level == form.role.data)
    elif request.method == "POST":
        form.search.data = request.form.get("search")
        form.gender.data = request.form.get("gender")
        form.role.data = request.form.get("role")
    accounts = db.session.execute(accounts).scalars()
    account_list = []
    if accounts:
        for account in accounts:
            role = account.role_level
            match role:
                case 0:
                    role = "Patient"
                case 1:
                    role = "Receptionist"
                case 2:
                    role = "Nurse"
                case 3:
                    role = "Doctor"
                case 4:
                    role = "Admin"
                case _:
                    role = "ERROR"
            role_change_url = url_for("change_role", user_id=account.id)
            if account.role_level < 4:
                btn = f"<a href='{role_change_url}' class='btn btn-primary btn-sm change'>Change Role</a>"
            else:
                btn = f"<a href='{role_change_url}' class='btn btn-danger btn-sm disabled-link'>Not Allowed</a>"
            account_list.append(
                {
                    "name": account.username,
                    "email": account.email,
                    "gender": account.gender,
                    "role": role,
                    "change": btn
                }
            )
    else:
        account_list.append({}),
    titles = [
        ("name", "Account Name"),
        ("email", "Email"),
        ("gender", "Gender"),
        ("role", "Role"),
        ("change", "#")
    ]

    return render_template("staff_list.html", form=form, account_list=account_list, titles=titles)

@app.route("/admin/manage-staff/<int:user_id>/change", methods=["GET", "POST"])
def change_role(user_id):
    user = db.session.get(User, user_id)
    form = RoleForm(role=user.role_level)
    if request.method == "POST" and form.validate_on_submit():
        user.role_level = form.role.data
        db.session.commit()
        return redirect(url_for("manage_staff"))
    return render_template("role_change.html", form=form)

@app.route("/staff")
def staff():
    return render_template("staff_dashboard.html")

@app.route("/admin")
def admin():
    return render_template("admin_dashboard.html")

if __name__ == "__main__":
    app.run(debug=True)
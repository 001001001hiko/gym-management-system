import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session
import psycopg2
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
load_dotenv()

app = Flask(__name__)
app.secret_key = "gym-management-secret-key-2026"


# =========================================================
# DATABASE SETTINGS
# =========================================================

DB_HOST = "localhost"
DB_NAME = "gym_management"
DB_USER = "postgres"
DB_PASSWORD = "8440"
DB_PORT = "5432"


def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT
    )


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("logged_in"):
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return wrapper


# =========================================================
# CREATE DEFAULT ADMIN
# =========================================================

def create_default_admin():

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            admin_id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    """)

    conn.commit()

    cur.execute("""
        SELECT admin_id
        FROM admin_users
        LIMIT 1;
    """)

    admin = cur.fetchone()

    if not admin:

        password_hash = generate_password_hash("12345")

        cur.execute("""
            INSERT INTO admin_users (
                username,
                password_hash
            )
            VALUES (%s, %s);
        """, (
            "admin",
            password_hash
        ))

        conn.commit()

    cur.close()
    conn.close()


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if session.get("logged_in"):
        return redirect(url_for("index"))

    if request.method == "POST":

        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()

        cur = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cur.execute("""
            SELECT *
            FROM admin_users
            WHERE username = %s;
        """, (username,))

        admin = cur.fetchone()

        cur.close()
        conn.close()

        if admin and check_password_hash(
            admin["password_hash"],
            password
        ):

            session["logged_in"] = True
            session["username"] = admin["username"]

            return redirect(url_for("index"))

        flash("Incorrect username or password.")

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# CHANGE PASSWORD
# =========================================================

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():

    if request.method == "POST":

        old_password = request.form["old_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if len(new_password) < 6:

            flash("New password must be at least 6 characters.")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:

            flash("New passwords do not match.")
            return redirect(url_for("change_password"))

        conn = get_db()

        cur = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cur.execute("""
            SELECT *
            FROM admin_users
            WHERE username = %s;
        """, (
            session["username"],
        ))

        admin = cur.fetchone()

        if not admin or not check_password_hash(
            admin["password_hash"],
            old_password
        ):

            cur.close()
            conn.close()

            flash("Current password is incorrect.")
            return redirect(url_for("change_password"))

        new_hash = generate_password_hash(new_password)

        cur.execute("""
            UPDATE admin_users
            SET password_hash = %s
            WHERE username = %s;
        """, (
            new_hash,
            session["username"]
        ))

        conn.commit()
        cur.close()
        conn.close()

        flash("Password changed successfully.")

        return redirect(url_for("index"))

    return render_template("change_password.html")


# =========================================================
# CHANGE USERNAME
# =========================================================

@app.route("/change-username", methods=["GET", "POST"])
@login_required
def change_username():

    if request.method == "POST":

        new_username = request.form["new_username"].strip()
        current_password = request.form["current_password"]

        if len(new_username) < 3:

            flash("Username must be at least 3 characters.")
            return redirect(url_for("change_username"))

        conn = get_db()

        cur = conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        )

        cur.execute("""
            SELECT *
            FROM admin_users
            WHERE username = %s;
        """, (
            session["username"],
        ))

        admin = cur.fetchone()

        if not admin or not check_password_hash(
            admin["password_hash"],
            current_password
        ):

            cur.close()
            conn.close()

            flash("Current password is incorrect.")
            return redirect(url_for("change_username"))

        try:

            cur.execute("""
                UPDATE admin_users
                SET username = %s
                WHERE username = %s;
            """, (
                new_username,
                session["username"]
            ))

            conn.commit()

            session["username"] = new_username

            flash("Username changed successfully.")

        except Exception:

            conn.rollback()

            flash("This username already exists.")

        cur.close()
        conn.close()

        return redirect(url_for("index"))

    return render_template("change_username.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/")
@login_required
def index():

    conn = get_db()

    cur = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )

    cur.execute("""
        SELECT
            trainer_id,
            first_name,
            last_name,
            phone
        FROM trainers
        ORDER BY first_name, last_name;
    """)

    trainers = cur.fetchall()


    cur.execute("""
        SELECT
            m.member_id,
            m.first_name,
            m.last_name,
            m.phone,
            m.trainer_id,

            COALESCE(
                t.first_name || ' ' || t.last_name,
                'General'
            ) AS trainer_name

        FROM members m

        LEFT JOIN trainers t
            ON m.trainer_id = t.trainer_id

        WHERE m.is_active = TRUE

        ORDER BY
            m.first_name,
            m.last_name;
    """)

    students = cur.fetchall()


    cur.execute("""
        SELECT
            member_id,
            first_name,
            last_name,
            phone

        FROM members

        WHERE trainer_id IS NULL
        AND is_active = TRUE

        ORDER BY
            first_name,
            last_name;
    """)

    general_students = cur.fetchall()


    cur.execute("""
        SELECT
            member_id,
            first_name,
            last_name,
            phone

        FROM members

        WHERE is_active = FALSE

        ORDER BY
            first_name,
            last_name;
    """)

    inactive_students = cur.fetchall()


    cur.execute("""
        SELECT
            month_id,
            month_name
        FROM months
        ORDER BY month_id;
    """)

    months = cur.fetchall()


    cur.execute("""
        SELECT
            m.member_id,
            m.first_name,
            m.last_name,

            COALESCE(
                t.first_name || ' ' || t.last_name,
                'General'
            ) AS trainer_name,

            fp.payment_date,
            fp.fee_amount,
            fp.expiry_date,

            CASE

                WHEN fp.payment_id IS NULL
                    THEN 'No Payment'

                WHEN fp.expiry_date < CURRENT_DATE
                    THEN 'Expired'

                ELSE 'Paid'

            END AS fee_status

        FROM members m

        LEFT JOIN trainers t
            ON m.trainer_id = t.trainer_id

        LEFT JOIN LATERAL (

            SELECT *
            FROM fee_payments f

            WHERE f.member_id = m.member_id

            ORDER BY
                f.expiry_date DESC,
                f.payment_id DESC

            LIMIT 1

        ) fp ON TRUE

        WHERE m.is_active = TRUE

        ORDER BY
            m.first_name,
            m.last_name;
    """)

    statuses = cur.fetchall()


    paid = [
        student for student in statuses
        if student["fee_status"] == "Paid"
    ]

    expired = [
        student for student in statuses
        if student["fee_status"] == "Expired"
    ]

    no_payment = [
        student for student in statuses
        if student["fee_status"] == "No Payment"
    ]


    search = request.args.get(
        "q",
        ""
    ).strip()

    search_results = []

    if search:

        cur.execute("""
            SELECT
                fp.payment_id,

                m.member_id,
                m.first_name,
                m.last_name,

                COALESCE(
                    t.first_name || ' ' || t.last_name,
                    'General'
                ) AS trainer_name,

                mo.month_name,
                mo.month_id,

                fp.payment_year,
                fp.payment_date,
                fp.fee_amount,
                fp.expiry_date

            FROM members m

            LEFT JOIN trainers t
                ON m.trainer_id = t.trainer_id

            LEFT JOIN fee_payments fp
                ON m.member_id = fp.member_id

            LEFT JOIN months mo
                ON fp.month_id = mo.month_id

            WHERE
                m.first_name ILIKE %s
                OR
                m.last_name ILIKE %s
                OR
                (
                    m.first_name || ' ' || m.last_name
                ) ILIKE %s

            ORDER BY
                fp.payment_year,
                fp.month_id;
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ))

        search_results = cur.fetchall()


    trainer_groups = {}

    for trainer in trainers:

        full_name = (
            f"{trainer['first_name']} "
            f"{trainer['last_name']}"
        )

        trainer_groups[full_name] = [
            student
            for student in students
            if student["trainer_id"]
            == trainer["trainer_id"]
        ]


    cur.close()
    conn.close()


    return render_template(
        "index.html",
        trainers=trainers,
        students=students,
        general_students=general_students,
        inactive_students=inactive_students,
        months=months,
        paid=paid,
        expired=expired,
        no_payment=no_payment,
        trainer_groups=trainer_groups,
        search=search,
        search_results=search_results
    )


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
@login_required
def reports():

    conn = get_db()

    cur = conn.cursor(
        cursor_factory=psycopg2.extras.RealDictCursor
    )


    cur.execute("""
        SELECT COUNT(*) AS total
        FROM members
        WHERE is_active = TRUE;
    """)

    total_students = cur.fetchone()["total"]


    cur.execute("""
        SELECT COUNT(*) AS total
        FROM trainers;
    """)

    total_trainers = cur.fetchone()["total"]


    cur.execute("""
        SELECT
            COUNT(*) FILTER (
                WHERE latest.payment_id IS NOT NULL
                AND latest.expiry_date >= CURRENT_DATE
            ) AS paid,

            COUNT(*) FILTER (
                WHERE latest.payment_id IS NOT NULL
                AND latest.expiry_date < CURRENT_DATE
            ) AS expired,

            COUNT(*) FILTER (
                WHERE latest.payment_id IS NULL
            ) AS no_payment

        FROM members m

        LEFT JOIN LATERAL (
            SELECT *
            FROM fee_payments f
            WHERE f.member_id = m.member_id
            ORDER BY
                f.expiry_date DESC,
                f.payment_id DESC
            LIMIT 1
        ) latest ON TRUE

        WHERE m.is_active = TRUE;
    """)

    status = cur.fetchone()


    cur.execute("""
        SELECT
            COALESCE(SUM(fee_amount), 0) AS total_income
        FROM fee_payments;
    """)

    total_income = cur.fetchone()["total_income"]


    cur.execute("""
        SELECT
            mo.month_id,
            mo.month_name,
            COALESCE(SUM(fp.fee_amount), 0) AS total_income,
            COUNT(fp.payment_id) AS payments_count

        FROM months mo

        LEFT JOIN fee_payments fp
            ON mo.month_id = fp.month_id

        GROUP BY
            mo.month_id,
            mo.month_name

        ORDER BY
            mo.month_id;
    """)

    monthly_report = cur.fetchall()


    cur.close()
    conn.close()


    return render_template(
        "reports.html",
        total_students=total_students,
        total_trainers=total_trainers,
        paid=status["paid"],
        expired=status["expired"],
        no_payment=status["no_payment"],
        total_income=total_income,
        monthly_report=monthly_report
    )


# =========================================================
# ADD STUDENT
# =========================================================

@app.route(
    "/add-student",
    methods=["POST"]
)
@login_required
def add_student():

    first_name = request.form["first_name"]
    last_name = request.form["last_name"]
    phone = request.form.get("phone")
    trainer_id = request.form.get("trainer_id")

    if trainer_id in ["", "general"]:
        trainer_id = None

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO members (
            first_name,
            last_name,
            phone,
            trainer_id
        )
        VALUES (
            %s,
            %s,
            %s,
            %s
        );
    """, (
        first_name,
        last_name,
        phone,
        trainer_id
    ))

    conn.commit()
    cur.close()
    conn.close()

    flash("Student added successfully.")

    return redirect(url_for("index"))


# =========================================================
# EDIT STUDENT
# =========================================================

@app.route(
    "/edit-student/<int:member_id>",
    methods=["POST"]
)
@login_required
def edit_student(member_id):

    first_name = request.form["first_name"]
    last_name = request.form["last_name"]
    phone = request.form.get("phone")
    trainer_id = request.form.get("trainer_id")

    if trainer_id in ["", "general"]:
        trainer_id = None

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE members
        SET
            first_name = %s,
            last_name = %s,
            phone = %s,
            trainer_id = %s
        WHERE member_id = %s;
    """, (
        first_name,
        last_name,
        phone,
        trainer_id,
        member_id
    ))

    conn.commit()
    cur.close()
    conn.close()

    flash("Student updated successfully.")

    return redirect(url_for("index"))


# =========================================================
# DEACTIVATE STUDENT
# =========================================================

@app.route(
    "/deactivate-student/<int:member_id>",
    methods=["POST"]
)
@login_required
def deactivate_student(member_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE members
        SET is_active = FALSE
        WHERE member_id = %s;
    """, (member_id,))

    conn.commit()
    cur.close()
    conn.close()

    flash("Student deactivated.")

    return redirect(url_for("index"))


# =========================================================
# ACTIVATE STUDENT
# =========================================================

@app.route(
    "/activate-student/<int:member_id>",
    methods=["POST"]
)
@login_required
def activate_student(member_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE members
        SET is_active = TRUE
        WHERE member_id = %s;
    """, (member_id,))

    conn.commit()
    cur.close()
    conn.close()

    flash("Student activated again.")

    return redirect(url_for("index"))


# =========================================================
# ADD TRAINER
# =========================================================

@app.route(
    "/add-trainer",
    methods=["POST"]
)
@login_required
def add_trainer():

    first_name = request.form["first_name"]
    last_name = request.form["last_name"]
    phone = request.form.get("phone")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO trainers (
            first_name,
            last_name,
            phone
        )
        VALUES (
            %s,
            %s,
            %s
        );
    """, (
        first_name,
        last_name,
        phone
    ))

    conn.commit()
    cur.close()
    conn.close()

    flash("Trainer added successfully.")

    return redirect(url_for("index"))


# =========================================================
# EDIT TRAINER
# =========================================================

@app.route(
    "/edit-trainer/<int:trainer_id>",
    methods=["POST"]
)
@login_required
def edit_trainer(trainer_id):

    first_name = request.form["first_name"]
    last_name = request.form["last_name"]
    phone = request.form.get("phone")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE trainers
        SET
            first_name = %s,
            last_name = %s,
            phone = %s
        WHERE trainer_id = %s;
    """, (
        first_name,
        last_name,
        phone,
        trainer_id
    ))

    conn.commit()
    cur.close()
    conn.close()

    flash("Trainer updated successfully.")

    return redirect(url_for("index"))


# =========================================================
# DELETE TRAINER
# =========================================================

@app.route(
    "/delete-trainer/<int:trainer_id>",
    methods=["POST"]
)
@login_required
def delete_trainer(trainer_id):

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE members
        SET trainer_id = NULL
        WHERE trainer_id = %s;
    """, (
        trainer_id,
    ))

    cur.execute("""
        DELETE FROM trainers
        WHERE trainer_id = %s;
    """, (
        trainer_id,
    ))

    conn.commit()
    cur.close()
    conn.close()

    flash(
        "Trainer deleted. Students moved to General."
    )

    return redirect(url_for("index"))


# =========================================================
# ADD FEE
# =========================================================

@app.route(
    "/add-fee",
    methods=["POST"]
)
@login_required
def add_fee():

    member_id = request.form["member_id"]
    month_id = request.form["month_id"]
    payment_year = request.form["payment_year"]
    payment_date = request.form["payment_date"]
    fee_amount = request.form["fee_amount"]
    expiry_date = request.form["expiry_date"]

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO fee_payments (
                member_id,
                month_id,
                payment_year,
                payment_date,
                fee_amount,
                expiry_date
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            );
        """, (
            member_id,
            month_id,
            payment_year,
            payment_date,
            fee_amount,
            expiry_date
        ))

        conn.commit()

        flash("Fee added successfully.")

    except Exception:

        conn.rollback()

        flash(
            "This month may already be registered for this student."
        )

    cur.close()
    conn.close()

    return redirect(url_for("index"))


# =========================================================
# EDIT FEE
# =========================================================

@app.route(
    "/edit-fee/<int:payment_id>",
    methods=["POST"]
)
@login_required
def edit_fee(payment_id):

    month_id = request.form["month_id"]
    payment_year = request.form["payment_year"]
    payment_date = request.form["payment_date"]
    fee_amount = request.form["fee_amount"]
    expiry_date = request.form["expiry_date"]

    search_name = request.form.get(
        "search_name",
        ""
    )

    conn = get_db()
    cur = conn.cursor()

    try:

        cur.execute("""
            UPDATE fee_payments
            SET
                month_id = %s,
                payment_year = %s,
                payment_date = %s,
                fee_amount = %s,
                expiry_date = %s
            WHERE payment_id = %s;
        """, (
            month_id,
            payment_year,
            payment_date,
            fee_amount,
            expiry_date,
            payment_id
        ))

        conn.commit()

        flash("Fee updated successfully.")

    except Exception:

        conn.rollback()

        flash(
            "Could not update fee. This month may already exist."
        )

    cur.close()
    conn.close()

    return redirect(
        url_for(
            "index",
            q=search_name
        )
    )


# =========================================================
# DELETE FEE
# =========================================================

@app.route(
    "/delete-fee/<int:payment_id>",
    methods=["POST"]
)
@login_required
def delete_fee(payment_id):

    search_name = request.form.get(
        "search_name",
        ""
    )

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM fee_payments
        WHERE payment_id = %s;
    """, (
        payment_id,
    ))

    conn.commit()
    cur.close()
    conn.close()

    flash("Fee deleted successfully.")

    return redirect(
        url_for(
            "index",
            q=search_name
        )
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    create_default_admin()

    app.run(debug=True)
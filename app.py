from flask import Flask, request, redirect, render_template, jsonify
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

app = Flask(__name__)

DATABASE = "medicines.db"
IST = ZoneInfo("Asia/Kolkata")


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    connection = sqlite3.connect(
        DATABASE,
        timeout=10,
        check_same_thread=False
    )
    connection.row_factory = sqlite3.Row
    return connection


# =========================================================
# DATABASE SETUP + MIGRATION
# =========================================================

def create_tables():
    connection = get_connection()

    try:
        # Medicines table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                dosage TEXT NOT NULL,
                time TEXT NOT NULL,
                duration_days INTEGER NOT NULL DEFAULT 1,
                start_date TEXT NOT NULL,
                last_notified TEXT DEFAULT ''
            )
        """)

        # History table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                medicine_name TEXT NOT NULL,
                dosage TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                taken_time TEXT NOT NULL,
                date TEXT NOT NULL
            )
        """)

        # -------------------------------------------------
        # DATABASE MIGRATION
        # This allows an older medicines.db to continue
        # working after adding duration_days/start_date.
        # -------------------------------------------------

        columns = connection.execute(
            "PRAGMA table_info(medicines)"
        ).fetchall()

        column_names = [column["name"] for column in columns]

        # Add duration_days if it doesn't exist
        if "duration_days" not in column_names:
            connection.execute("""
                ALTER TABLE medicines
                ADD COLUMN duration_days INTEGER NOT NULL DEFAULT 36500
            """)

        # Add start_date if it doesn't exist
        if "start_date" not in column_names:
            today = datetime.now(IST).strftime("%Y-%m-%d")

            connection.execute(
                """
                ALTER TABLE medicines
                ADD COLUMN start_date TEXT
                """
            )

            connection.execute(
                """
                UPDATE medicines
                SET start_date = ?
                WHERE start_date IS NULL OR start_date = ''
                """,
                (today,)
            )

        # Make sure old records have usable values
        connection.execute("""
            UPDATE medicines
            SET duration_days = 36500
            WHERE duration_days IS NULL OR duration_days <= 0
        """)

        connection.execute("""
            UPDATE medicines
            SET start_date = ?
            WHERE start_date IS NULL OR start_date = ''
        """, (
            datetime.now(IST).strftime("%Y-%m-%d"),
        ))

        connection.commit()

    except Exception as error:
        connection.rollback()
        print("DATABASE SETUP ERROR:", error)

    finally:
        connection.close()


create_tables()


# =========================================================
# MEDICINE FUNCTIONS
# =========================================================

def add_medicine(
    name,
    dosage,
    medicine_time,
    duration_days,
    start_date
):
    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO medicines
            (
                name,
                dosage,
                time,
                duration_days,
                start_date,
                last_notified
            )
            VALUES (?, ?, ?, ?, ?, '')
            """,
            (
                name,
                dosage,
                medicine_time,
                duration_days,
                start_date
            )
        )

        connection.commit()
        return True

    except Exception as error:
        connection.rollback()
        print("ADD MEDICINE ERROR:", error)
        return False

    finally:
        connection.close()


def get_medicines():
    connection = get_connection()

    try:
        medicines = connection.execute(
            """
            SELECT *
            FROM medicines
            ORDER BY time
            """
        ).fetchall()

        return medicines

    finally:
        connection.close()


def delete_medicine(medicine_id):
    connection = get_connection()

    try:
        connection.execute(
            """
            DELETE FROM medicines
            WHERE id = ?
            """,
            (medicine_id,)
        )

        connection.commit()
        return True

    except Exception as error:
        connection.rollback()
        print("DELETE MEDICINE ERROR:", error)
        return False

    finally:
        connection.close()


# =========================================================
# HISTORY FUNCTIONS
# =========================================================

def get_history():
    connection = get_connection()

    try:
        history = connection.execute(
            """
            SELECT *
            FROM history
            ORDER BY id DESC
            """
        ).fetchall()

        return history

    finally:
        connection.close()


def add_history(
    medicine_name,
    dosage,
    scheduled_time
):
    now = datetime.now(IST)

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO history
            (
                medicine_name,
                dosage,
                scheduled_time,
                taken_time,
                date
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                medicine_name,
                dosage,
                scheduled_time,
                now.strftime("%H:%M"),
                now.strftime("%Y-%m-%d")
            )
        )

        connection.commit()
        return True

    except Exception as error:
        connection.rollback()
        print("HISTORY SAVE ERROR:", error)
        return False

    finally:
        connection.close()


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    medicines = get_medicines()
    history = get_history()

    return render_template(
        "index.html",
        medicines=medicines,
        history=history
    )


# =========================================================
# ADD MEDICINE
# =========================================================

@app.route("/add", methods=["POST"])
def add():

    try:
        name = request.form.get("name", "").strip()
        dosage = request.form.get("dosage", "").strip()
        medicine_time = request.form.get("time", "").strip()

        duration_text = request.form.get(
            "duration_days",
            "1"
        ).strip()

        if not name or not dosage or not medicine_time:
            return redirect("/")

        duration_days = int(duration_text)

        if duration_days < 1:
            duration_days = 1

        # Maximum is intentionally generous.
        # User can enter years if required.
        if duration_days > 36500:
            duration_days = 36500

        start_date = datetime.now(IST).strftime(
            "%Y-%m-%d"
        )

        success = add_medicine(
            name,
            dosage,
            medicine_time,
            duration_days,
            start_date
        )

        if not success:
            return "Unable to add medicine", 500

        return redirect("/")

    except ValueError:
        return "Invalid number of reminder days", 400

    except Exception as error:
        print("ADD ROUTE ERROR:", error)
        return "Unable to add medicine", 500


# =========================================================
# DELETE MEDICINE
# =========================================================

@app.route("/delete/<int:medicine_id>")
def delete(medicine_id):

    delete_medicine(medicine_id)

    return redirect("/")


# =========================================================
# TEST REMINDER
# =========================================================

@app.route("/api/test")
def test_reminder():

    now = datetime.now(IST)

    return jsonify({
        "active": True,
        "id": -1,
        "medicine": "Test Medicine",
        "dosage": "1 tablet",
        "time": now.strftime("%H:%M")
    })


# =========================================================
# MARK MEDICINE AS TAKEN
# =========================================================

@app.route(
    "/api/take/<int:medicine_id>",
    methods=["POST"]
)
def take_medicine(medicine_id):

    # -----------------------------------------------------
    # TEST REMINDER
    # -----------------------------------------------------

    if medicine_id == -1:

        return jsonify({
            "success": True,
            "message": "Test reminder marked as taken"
        })


    # -----------------------------------------------------
    # FIND MEDICINE
    # -----------------------------------------------------

    connection = get_connection()

    try:
        medicine = connection.execute(
            """
            SELECT *
            FROM medicines
            WHERE id = ?
            """,
            (medicine_id,)
        ).fetchone()

    finally:
        connection.close()


    if medicine is None:

        return jsonify({
            "success": False,
            "message": "Medicine not found"
        }), 404


    # -----------------------------------------------------
    # SAVE TO HISTORY
    # -----------------------------------------------------

    saved = add_history(
        medicine["name"],
        medicine["dosage"],
        medicine["time"]
    )


    if not saved:

        return jsonify({
            "success": False,
            "message": "Could not save medicine history"
        }), 500


    return jsonify({
        "success": True,
        "message": "Medicine marked as taken"
    })


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )

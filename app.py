
from flask import Flask, request, redirect, render_template, jsonify
import sqlite3
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# ============================================================
# APPLICATION
# ============================================================

app = Flask(__name__)

DATABASE = "medicines.db"

IST = ZoneInfo("Asia/Kolkata")


# ============================================================
# REMINDER MEMORY
# ============================================================

latest_reminder = {
    "active": False,
    "id": 0,
    "medicine": "",
    "dosage": "",
    "time": ""
}


# ============================================================
# DATABASE
# ============================================================

def get_connection():

    connection = sqlite3.connect(
        DATABASE,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


def create_tables():

    connection = get_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS medicines (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            dosage TEXT NOT NULL,

            time TEXT NOT NULL,

            last_notified TEXT DEFAULT ''

        )
    """)


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


    connection.commit()

    connection.close()


create_tables()


# ============================================================
# MEDICINE FUNCTIONS
# ============================================================

def add_medicine(name, dosage, medicine_time):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO medicines
        (name, dosage, time)
        VALUES (?, ?, ?)
        """,
        (
            name,
            dosage,
            medicine_time
        )
    )

    connection.commit()

    connection.close()


def get_medicines():

    connection = get_connection()

    medicines = connection.execute(
        """
        SELECT *
        FROM medicines
        ORDER BY time
        """
    ).fetchall()

    connection.close()

    return medicines


def delete_medicine(medicine_id):

    connection = get_connection()

    connection.execute(
        """
        DELETE FROM medicines
        WHERE id = ?
        """,
        (medicine_id,)
    )

    connection.commit()

    connection.close()


def update_last_notified(
    medicine_id,
    date
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE medicines
        SET last_notified = ?
        WHERE id = ?
        """,
        (
            date,
            medicine_id
        )
    )

    connection.commit()

    connection.close()


# ============================================================
# HISTORY
# ============================================================

def get_history():

    connection = get_connection()

    history = connection.execute(
        """
        SELECT *
        FROM history
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return history


def add_history(
    medicine_name,
    dosage,
    scheduled_time
):

    now = datetime.now(IST)

    connection = get_connection()

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

    connection.close()


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():

    medicines = get_medicines()

    history = get_history()

    return render_template(
        "index.html",

        medicines=medicines,

        history=history,

        reminder=latest_reminder
    )


# ============================================================
# ADD MEDICINE
# ============================================================

@app.route(
    "/add",
    methods=["POST"]
)
def add():

    name = request.form["name"]

    dosage = request.form["dosage"]

    medicine_time = request.form["time"]


    add_medicine(
        name,
        dosage,
        medicine_time
    )


    return redirect("/")


# ============================================================
# DELETE MEDICINE
# ============================================================

@app.route(
    "/delete/<int:medicine_id>"
)
def delete(medicine_id):

    delete_medicine(
        medicine_id
    )

    return redirect("/")


# ============================================================
# REMINDER API
# ============================================================

@app.route("/api/reminder")
def reminder_api():

    return jsonify(
        latest_reminder
    )


# ============================================================
# TEST REMINDER
# ============================================================

@app.route("/api/test")
def test_reminder():

    latest_reminder["active"] = True

    latest_reminder["id"] = -1

    latest_reminder["medicine"] = "Test Medicine"

    latest_reminder["dosage"] = "1 tablet"

    latest_reminder["time"] = datetime.now(
        IST
    ).strftime("%H:%M")


    return jsonify(
        latest_reminder
    )


# ============================================================
# MARK MEDICINE AS TAKEN
# ============================================================

@app.route(
    "/api/take/<int:medicine_id>",
    methods=["POST"]
)
def take_medicine(medicine_id):

    global latest_reminder


    if medicine_id == -1:

        latest_reminder = {
            "active": False,
            "id": 0,
            "medicine": "",
            "dosage": "",
            "time": ""
        }

        return jsonify(
            {
                "success": True
            }
        )


    connection = get_connection()


    medicine = connection.execute(
        """
        SELECT *
        FROM medicines
        WHERE id = ?
        """,
        (medicine_id,)
    ).fetchone()


    connection.close()


    if medicine is None:

        return jsonify(
            {
                "success": False,
                "message": "Medicine not found"
            }
        )


    add_history(
        medicine["name"],
        medicine["dosage"],
        medicine["time"]
    )


    latest_reminder = {
        "active": False,
        "id": 0,
        "medicine": "",
        "dosage": "",
        "time": ""
    }


    return jsonify(
        {
            "success": True
        }
    )


# ============================================================
# REMINDER SCHEDULER
# ============================================================

def check_reminders():

    print("Medicine reminder scheduler started.")

    print("Using Indian Standard Time (IST).")


    while True:

        try:

            now = datetime.now(IST)

            current_time = now.strftime(
                "%H:%M"
            )

            today = now.strftime(
                "%Y-%m-%d"
            )


            medicines = get_medicines()


            for medicine in medicines:


                if (

                    medicine["time"]
                    == current_time

                    and

                    medicine["last_notified"]
                    != today

                ):


                    latest_reminder["active"] = True

                    latest_reminder["id"] = medicine["id"]

                    latest_reminder["medicine"] = medicine["name"]

                    latest_reminder["dosage"] = medicine["dosage"]

                    latest_reminder["time"] = current_time


                    print(
                        "🔔 Reminder:",
                        medicine["name"]
                    )


                    update_last_notified(
                        medicine["id"],
                        today
                    )


        except Exception as error:

            print(
                "Scheduler error:",
                error
            )


        time.sleep(20)


# ============================================================
# START SCHEDULER
# ============================================================

scheduler_thread = threading.Thread(

    target=check_reminders,

    daemon=True

)

scheduler_thread.start()


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False
    )

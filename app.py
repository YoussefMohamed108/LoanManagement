import sqlite3
import json
from datetime import date, datetime
from decimal import Decimal

from flask import Flask, request, jsonify, send_from_directory


# APP CONFIG


app = Flask(__name__, static_folder=".")

DB_NAME = "bank.db"


# SQLITE SCHEMA


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Borrower (
    Borrower_ID INTEGER PRIMARY KEY,
    Full_Name TEXT NOT NULL,
    Email_Address TEXT,
    Phone_Number TEXT,
    Home_Address TEXT,
    Date_of_Birth TEXT,
    Income_Level REAL,
    Credit_Score INTEGER
);

CREATE TABLE IF NOT EXISTS Staff (
    Staff_ID INTEGER PRIMARY KEY,
    Staff_Name TEXT NOT NULL,
    Role TEXT,
    Department TEXT
);

CREATE TABLE IF NOT EXISTS Loan (
    Loan_ID INTEGER PRIMARY KEY,
    Borrower_ID INTEGER,
    Staff_ID INTEGER,
    Loan_Type TEXT,
    Principal_Amount REAL NOT NULL,
    Interest_Rate REAL,
    Term_Months INTEGER,
    Start_Date TEXT,
    End_Date TEXT,
    Loan_Status TEXT,

    FOREIGN KEY (Borrower_ID)
        REFERENCES Borrower(Borrower_ID),

    FOREIGN KEY (Staff_ID)
        REFERENCES Staff(Staff_ID)
);

CREATE TABLE IF NOT EXISTS Payment (
    Payment_ID INTEGER PRIMARY KEY,
    Loan_ID INTEGER,
    Amount_Paid REAL NOT NULL,
    Payment_Date TEXT,
    Payment_Method TEXT,
    Late_Fee_Applied REAL DEFAULT 0,

    FOREIGN KEY (Loan_ID)
        REFERENCES Loan(Loan_ID)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Collateral (
    Collateral_ID INTEGER PRIMARY KEY,
    Loan_ID INTEGER,
    Asset_Type TEXT,
    Market_Value REAL,
    Asset_Description TEXT,

    FOREIGN KEY (Loan_ID)
        REFERENCES Loan(Loan_ID)
        ON DELETE CASCADE
);
"""


# DATABASE HELPERS

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def apply_schema():
    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.executescript(SCHEMA_SQL)

        conn.commit()

        cur.close()
        conn.close()

        print(" Database schema ready.")

    except Exception as e:
        print(f" Schema Error: {e}")

def rows_to_json(rows):
    return [dict(row) for row in rows]

def serial(obj):
    if isinstance(obj, Decimal):
        return float(obj)

    if isinstance(obj, (date, datetime)):
        return obj.isoformat()

    raise TypeError(f"Not serializable: {type(obj)}")


# EMI CALCULATOR


def calc_emi(principal, annual_rate, term):

    principal = float(principal)
    annual_rate = float(annual_rate)
    term = int(term)

    if annual_rate == 0:
        return round(principal / term, 2)

    r = (annual_rate / 100) / 12

    emi = (
        principal * r * (1 + r) ** term
    ) / (
        ((1 + r) ** term) - 1
    )

    return round(emi, 2)


# FRONTEND


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


# EMI API


@app.route("/api/emi")
def api_emi():

    principal = request.args.get("principal", 0)
    rate = request.args.get("rate", 0)
    term = request.args.get("term", 1)

    return jsonify({
        "emi": calc_emi(principal, rate, term)
    })

# DASHBOARD STATS


@app.route("/api/stats")
def api_stats():

    try:

        conn = get_conn()
        cur = conn.cursor()

        stats = {}

        cur.execute("SELECT COUNT(*) FROM Borrower")
        stats["borrowers"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM Staff")
        stats["staff"] = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM Loan")
        stats["loans"] = cur.fetchone()[0]

        cur.execute("""
            SELECT COALESCE(SUM(Principal_Amount), 0)
            FROM Loan
            WHERE Loan_Status='Active'
        """)

        stats["active_portfolio"] = cur.fetchone()[0]

        cur.execute("""
            SELECT COALESCE(SUM(Amount_Paid), 0)
            FROM Payment
        """)

        stats["total_collected"] = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM Loan
            WHERE Loan_Status='Defaulted'
        """)

        stats["defaults"] = cur.fetchone()[0]

        cur.execute("""
            SELECT Loan_Status, COUNT(*)
            FROM Loan
            GROUP BY Loan_Status
        """)

        stats["loan_status_breakdown"] = {
            row[0]: row[1]
            for row in cur.fetchall()
        }

        cur.execute("""
            SELECT Loan_Type,
                   COALESCE(SUM(Principal_Amount), 0)
            FROM Loan
            GROUP BY Loan_Type
        """)

        stats["loans_by_type"] = [
            {
                "type": row[0],
                "total": row[1]
            }
            for row in cur.fetchall()
        ]

        conn.close()

        return jsonify(stats)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# BORROWERS


@app.route("/api/borrowers", methods=["GET"])
def list_borrowers():

    try:

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM Borrower
            ORDER BY Borrower_ID
        """)

        data = rows_to_json(cur.fetchall())

        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/borrowers", methods=["POST"])
def add_borrower():

    try:

        d = request.json

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO Borrower VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            d["Borrower_ID"],
            d["Full_Name"],
            d.get("Email_Address"),
            d.get("Phone_Number"),
            d.get("Home_Address"),
            d.get("Date_of_Birth"),
            d.get("Income_Level"),
            d.get("Credit_Score")
        ))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/borrowers/<int:bid>", methods=["DELETE"])
def delete_borrower(bid):

    try:

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM Borrower
            WHERE Borrower_ID=?
        """, (bid,))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# STAFF

@app.route("/api/staff", methods=["GET"])
def list_staff():

    try:

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT *
            FROM Staff
            ORDER BY Staff_ID
        """)

        data = rows_to_json(cur.fetchall())

        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/staff", methods=["POST"])
def add_staff():

    try:

        d = request.json

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO Staff VALUES (
                ?, ?, ?, ?
            )
        """, (
            d["Staff_ID"],
            d["Staff_Name"],
            d.get("Role"),
            d.get("Department")
        ))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# LOANS


@app.route("/api/loans", methods=["GET"])
def list_loans():

    try:

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                l.*,
                b.Full_Name AS Borrower_Name,
                s.Staff_Name

            FROM Loan l

            LEFT JOIN Borrower b
                ON l.Borrower_ID = b.Borrower_ID

            LEFT JOIN Staff s
                ON l.Staff_ID = s.Staff_ID

            ORDER BY l.Loan_ID
        """)

        data = rows_to_json(cur.fetchall())

        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/loans", methods=["POST"])
def add_loan():

    try:

        d = request.json

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO Loan VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, (
            d["Loan_ID"],
            d["Borrower_ID"],
            d["Staff_ID"],
            d["Loan_Type"],
            d["Principal_Amount"],
            d["Interest_Rate"],
            d["Term_Months"],
            d.get("Start_Date"),
            d.get("End_Date"),
            d.get("Loan_Status", "Active")
        ))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# PAYMENTS


@app.route("/api/payments", methods=["GET"])
def list_payments():

    try:

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                p.*,
                l.Loan_Type,
                b.Full_Name AS Borrower_Name

            FROM Payment p

            JOIN Loan l
                ON p.Loan_ID = l.Loan_ID

            JOIN Borrower b
                ON l.Borrower_ID = b.Borrower_ID

            ORDER BY p.Payment_Date DESC
        """)

        data = rows_to_json(cur.fetchall())

        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/payments", methods=["POST"])
def add_payment():

    try:

        d = request.json

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO Payment VALUES (
                ?, ?, ?, ?, ?, ?
            )
        """, (
            d["Payment_ID"],
            d["Loan_ID"],
            d["Amount_Paid"],
            d["Payment_Date"],
            d["Payment_Method"],
            d.get("Late_Fee_Applied", 0)
        ))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# COLLATERAL


@app.route("/api/collateral", methods=["GET"])
def list_collateral():

    try:

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                c.*,
                l.Loan_Type,
                b.Full_Name AS Borrower_Name

            FROM Collateral c

            JOIN Loan l
                ON c.Loan_ID = l.Loan_ID

            JOIN Borrower b
                ON l.Borrower_ID = b.Borrower_ID

            ORDER BY c.Collateral_ID
        """)

        data = rows_to_json(cur.fetchall())

        conn.close()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/collateral", methods=["POST"])
def add_collateral():

    try:

        d = request.json

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO Collateral VALUES (
                ?, ?, ?, ?, ?
            )
        """, (
            d["Collateral_ID"],
            d["Loan_ID"],
            d["Asset_Type"],
            d["Market_Value"],
            d.get("Asset_Description")
        ))

        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ENTRY POINT


if __name__ == "__main__":

    print("=" * 60)
    print("🏦 BANK LOAN MANAGEMENT SYSTEM")
    print("=" * 60)

    apply_schema()

    print(" Server running at:")
    print("http://localhost:5000")

    print("=" * 60)

    app.run(debug=True, port=5000)
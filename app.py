# SECTION 1 -SQL SCHEMA

SCHEMA_SQL = """
CREATE DATABASE IF NOT EXISTS Bank;
USE Bank;

CREATE TABLE IF NOT EXISTS Borrower (
    Borrower_ID   INT PRIMARY KEY,
    Full_Name     VARCHAR(100) NOT NULL,
    Email_Address VARCHAR(100),
    Phone_Number  VARCHAR(20),
    Home_Address  TEXT,
    Date_of_Birth DATE,
    Income_Level  DECIMAL(15,2),
    Credit_Score  INT
);

CREATE TABLE IF NOT EXISTS Staff (
    Staff_ID   INT PRIMARY KEY,
    Staff_Name VARCHAR(100) NOT NULL,
    Role       VARCHAR(50),
    Department VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS Loan (
    Loan_ID          INT PRIMARY KEY,
    Borrower_ID      INT,
    Staff_ID         INT,
    Loan_Type        VARCHAR(50),
    Principal_Amount DECIMAL(15,2) NOT NULL,
    Interest_Rate    DECIMAL(5,2),
    Term_Months      INT,
    Start_Date       DATE,
    End_Date         DATE,
    Loan_Status      VARCHAR(20),
    FOREIGN KEY (Borrower_ID) REFERENCES Borrower(Borrower_ID),
    FOREIGN KEY (Staff_ID)    REFERENCES Staff(Staff_ID)
);

CREATE TABLE IF NOT EXISTS Payment (
    Payment_ID      INT PRIMARY KEY,
    Loan_ID         INT,
    Amount_Paid     DECIMAL(15,2) NOT NULL,
    Payment_Date    DATE,
    Payment_Method  VARCHAR(50),
    Late_Fee_Applied DECIMAL(10,2) DEFAULT 0.00,
    FOREIGN KEY (Loan_ID) REFERENCES Loan(Loan_ID) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS Collateral (
    Collateral_ID   INT PRIMARY KEY,
    Loan_ID         INT,
    Asset_Type      VARCHAR(50),
    Market_Value    DECIMAL(15,2),
    Asset_Description TEXT,
    FOREIGN KEY (Loan_ID) REFERENCES Loan(Loan_ID) ON DELETE CASCADE
);
"""


# SECTION 2 -IMPORTS & CONFIG

import os, json, math
from datetime import date, datetime
from decimal import Decimal
from flask import Flask, request, jsonify, send_from_directory
import mysql.connector
from mysql.connector import Error

# CONFIG edit these to match your MySQL setup
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "7724",
    "database": "bank",
    "port":     3306,
}

app = Flask(__name__, static_folder=".")


# SECTION 3 -DATABASE HELPERS

def get_conn():
    """Open a fresh connection to MySQL (bank database)."""
    return mysql.connector.connect(**DB_CONFIG)

def apply_schema():
    """
    Run SCHEMA_SQL on first startup to create the database/tables
    if they don't already exist.
    """
    try:
        cfg = {k: v for k, v in DB_CONFIG.items() if k != "database"}
        conn = mysql.connector.connect(**cfg)
        cur  = conn.cursor()
        for stmt in SCHEMA_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        conn.commit()
        cur.close(); conn.close()
        print("Schema applied (or already up to date).")
    except Error as e:
        print(f"Schema error: {e}")

def serial(obj):
    """JSON serialiser for Decimal / date / datetime."""
    if isinstance(obj, Decimal):   return float(obj)
    if isinstance(obj, (date, datetime)): return obj.isoformat()
    raise TypeError(f"Not serialisable: {type(obj)}")

def rows_to_json(cursor):
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]

def calc_emi(principal: float, annual_rate: float, term: int) -> float:
    if annual_rate == 0:
        return round(principal / term, 2) if term else 0
    r   = (annual_rate / 100) / 12
    emi = principal * r * (1 + r)**term / ((1 + r)**term - 1)
    return round(emi, 2)


# SECTION 4 -FLASK ROUTES


# Serve frontend
@app.route("/")
def index():
    return send_from_directory(".", "index.html")

# EMI calculator
@app.route("/api/emi")
def api_emi():
    p = float(request.args.get("principal", 0))
    r = float(request.args.get("rate",      0))
    n = int(request.args.get("term",        1))
    return jsonify({"emi": calc_emi(p, r, n)})

# Dashboard stats
@app.route("/api/stats")
def api_stats():
    try:
        conn = get_conn(); cur = conn.cursor()
        stats = {}
        cur.execute("SELECT COUNT(*) FROM Borrower"); stats["borrowers"] = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM Staff");    stats["staff"]     = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM Loan");     stats["loans"]     = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM(Principal_Amount),0) FROM Loan WHERE Loan_Status='Active'")
        stats["active_portfolio"] = float(cur.fetchone()[0])
        cur.execute("SELECT COALESCE(SUM(Amount_Paid),0) FROM Payment")
        stats["total_collected"] = float(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM Loan WHERE Loan_Status='Defaulted'")
        stats["defaults"] = cur.fetchone()[0]
        cur.execute("""SELECT Loan_Status, COUNT(*) as cnt FROM Loan GROUP BY Loan_Status""")
        stats["loan_status_breakdown"] = {r[0]: r[1] for r in cur.fetchall()}
        cur.execute("""SELECT Loan_Type, COALESCE(SUM(Principal_Amount),0) as total
                       FROM Loan GROUP BY Loan_Type ORDER BY total DESC""")
        stats["loans_by_type"] = [{"type": r[0], "total": float(r[1])} for r in cur.fetchall()]
        cur.close(); conn.close()
        return jsonify(stats)
    except Error as e:
        return jsonify({"error": str(e)}), 500


# BORROWER CRUD

@app.route("/api/borrowers", methods=["GET"])
def list_borrowers():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM Borrower ORDER BY Borrower_ID")
        data = rows_to_json(cur); cur.close(); conn.close()
        return json.dumps(data, default=serial), 200, {"Content-Type": "application/json"}
    except Error as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/borrowers", methods=["POST"])
def add_borrower():
    d = request.json
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute(
            "INSERT INTO Borrower VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (d["Borrower_ID"], d["Full_Name"], d.get("Email_Address"),
             d.get("Phone_Number"), d.get("Home_Address"), d.get("Date_of_Birth"),
             d.get("Income_Level"), d.get("Credit_Score"))
        )
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/borrowers/<int:bid>", methods=["PUT"])
def update_borrower(bid):
    d = request.json
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""UPDATE Borrower SET Full_Name=%s, Email_Address=%s, Phone_Number=%s,
                       Home_Address=%s, Date_of_Birth=%s, Income_Level=%s, Credit_Score=%s
                       WHERE Borrower_ID=%s""",
                    (d["Full_Name"], d.get("Email_Address"), d.get("Phone_Number"),
                     d.get("Home_Address"), d.get("Date_of_Birth"),
                     d.get("Income_Level"), d.get("Credit_Score"), bid))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/borrowers/<int:bid>", methods=["DELETE"])
def delete_borrower(bid):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM Borrower WHERE Borrower_ID=%s", (bid,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400


# STAFF CRUD
@app.route("/api/staff", methods=["GET"])
def list_staff():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM Staff ORDER BY Staff_ID")
        data = rows_to_json(cur); cur.close(); conn.close()
        return json.dumps(data, default=serial), 200, {"Content-Type": "application/json"}
    except Error as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/staff", methods=["POST"])
def add_staff():
    d = request.json
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO Staff VALUES (%s,%s,%s,%s)",
                    (d["Staff_ID"], d["Staff_Name"], d.get("Role"), d.get("Department")))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/staff/<int:sid>", methods=["PUT"])
def update_staff(sid):
    d = request.json
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE Staff SET Staff_Name=%s, Role=%s, Department=%s WHERE Staff_ID=%s",
                    (d["Staff_Name"], d.get("Role"), d.get("Department"), sid))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/staff/<int:sid>", methods=["DELETE"])
def delete_staff(sid):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM Staff WHERE Staff_ID=%s", (sid,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400


# LOAN CRUD

@app.route("/api/loans", methods=["GET"])
def list_loans():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT l.*, b.Full_Name AS Borrower_Name, s.Staff_Name
            FROM Loan l
            LEFT JOIN Borrower b ON l.Borrower_ID = b.Borrower_ID
            LEFT JOIN Staff    s ON l.Staff_ID    = s.Staff_ID
            ORDER BY l.Loan_ID
        """)
        data = rows_to_json(cur); cur.close(); conn.close()
        return json.dumps(data, default=serial), 200, {"Content-Type": "application/json"}
    except Error as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/loans", methods=["POST"])
def add_loan():
    d = request.json
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""INSERT INTO Loan VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (d["Loan_ID"], d["Borrower_ID"], d["Staff_ID"], d["Loan_Type"],
                     d["Principal_Amount"], d["Interest_Rate"], d["Term_Months"],
                     d.get("Start_Date"), d.get("End_Date"), d.get("Loan_Status","Active")))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/loans/<int:lid>", methods=["PUT"])
def update_loan(lid):
    d = request.json
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""UPDATE Loan SET Loan_Status=%s, Interest_Rate=%s, Term_Months=%s,
                       End_Date=%s WHERE Loan_ID=%s""",
                    (d["Loan_Status"], d["Interest_Rate"], d["Term_Months"],
                     d.get("End_Date"), lid))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/loans/<int:lid>", methods=["DELETE"])
def delete_loan(lid):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM Loan WHERE Loan_ID=%s", (lid,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

# PAYMENT CRUD
@app.route("/api/payments", methods=["GET"])
def list_payments():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT p.*, l.Loan_Type, b.Full_Name AS Borrower_Name
            FROM Payment p
            JOIN Loan     l ON p.Loan_ID    = l.Loan_ID
            JOIN Borrower b ON l.Borrower_ID = b.Borrower_ID
            ORDER BY p.Payment_Date DESC
        """)
        data = rows_to_json(cur); cur.close(); conn.close()
        return json.dumps(data, default=serial), 200, {"Content-Type": "application/json"}
    except Error as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/payments", methods=["POST"])
def add_payment():
    d = request.json
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO Payment VALUES (%s,%s,%s,%s,%s,%s)",
                    (d["Payment_ID"], d["Loan_ID"], d["Amount_Paid"],
                     d["Payment_Date"], d["Payment_Method"], d.get("Late_Fee_Applied", 0)))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/payments/<int:pid>", methods=["DELETE"])
def delete_payment(pid):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM Payment WHERE Payment_ID=%s", (pid,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

# COLLATERAL CRUD
@app.route("/api/collateral", methods=["GET"])
def list_collateral():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""
            SELECT c.*, l.Loan_Type, b.Full_Name AS Borrower_Name
            FROM Collateral c
            JOIN Loan     l ON c.Loan_ID    = l.Loan_ID
            JOIN Borrower b ON l.Borrower_ID = b.Borrower_ID
            ORDER BY c.Collateral_ID
        """)
        data = rows_to_json(cur); cur.close(); conn.close()
        return json.dumps(data, default=serial), 200, {"Content-Type": "application/json"}
    except Error as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/collateral", methods=["POST"])
def add_collateral():
    d = request.json
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO Collateral VALUES (%s,%s,%s,%s,%s)",
                    (d["Collateral_ID"], d["Loan_ID"], d["Asset_Type"],
                     d["Market_Value"], d.get("Asset_Description")))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/collateral/<int:cid>", methods=["DELETE"])
def delete_collateral(cid):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM Collateral WHERE Collateral_ID=%s", (cid,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({"ok": True})
    except Error as e:
        return jsonify({"error": str(e)}), 400


# SECTION 5 -ENTRY POINT

if __name__ == "__main__":
    print("═" * 60)
    print("  BANK LOAN MANAGEMENT SYSTEM")
    print("═" * 60)
    apply_schema()
    print("  Server starting at http://localhost:5000")
    print("   Open index.html via this URL (not as a file)")
    print("═" * 60)
    app.run(debug=True, port=5000)
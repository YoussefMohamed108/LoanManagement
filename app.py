import os
from flask import Flask, request, jsonify, render_template
from supabase import create_client
from dotenv import load_dotenv

# =========================
# INIT
# =========================

load_dotenv()
app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Missing SUPABASE_URL or SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def sb(table):
    return supabase.table(table)


# =========================
# SAFE HELPERS
# =========================

def safe_select(table):
    try:
        return sb(table).select("*").execute().data or []
    except Exception as e:
        print(f"[ERROR SELECT] {table}: {e}")
        return []


def safe_insert(table, payload):
    try:
        return sb(table).insert(payload).execute().data
    except Exception as e:
        print(f"[ERROR INSERT] {table}: {e}")
        return {"error": str(e)}


# =========================
# FRONTEND
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# STATS
# =========================

@app.route("/api/stats")
def stats():
    borrowers = safe_select("borrower")
    loans = safe_select("loan")
    payments = safe_select("payment")

    active_portfolio = sum(
        float(l.get("principal_amount") or 0)
        for l in loans
        if l.get("loan_status") == "Active"
    )

    total_collected = sum(
        float(p.get("amount_paid") or 0)
        for p in payments
    )

    return jsonify({
        "borrowers": len(borrowers),
        "loans": len(loans),
        "active_portfolio": active_portfolio,
        "total_collected": total_collected
    })


# =========================
# BORROWERS
# =========================

@app.route("/api/borrowers", methods=["GET"])
def get_borrowers():
    return jsonify(safe_select("borrower"))


@app.route("/api/borrowers", methods=["POST"])
def add_borrower():
    data = request.json

    payload = {
        "full_name": data.get("full_name"),
        "email_address": data.get("email_address"),
        "phone_number": data.get("phone_number"),
        "home_address": data.get("home_address"),
        "date_of_birth": data.get("date_of_birth"),
        "income_level": data.get("income_level"),
        "credit_score": data.get("credit_score"),
    }

    return jsonify(safe_insert("borrower", payload))


@app.route("/api/borrowers/<int:bid>", methods=["DELETE"])
def delete_borrower(bid):
    try:
        return jsonify(
            sb("borrower").delete().eq("borrower_id", bid).execute().data
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# STAFF
# =========================

@app.route("/api/staff", methods=["GET"])
def get_staff():
    return jsonify(safe_select("staff"))


@app.route("/api/staff", methods=["POST"])
def add_staff():
    data = request.json

    payload = {
        "staff_name": data.get("staff_name"),
        "role": data.get("role"),
        "department": data.get("department"),
    }

    return jsonify(safe_insert("staff", payload))


# =========================
# LOANS
# =========================

@app.route("/api/loans", methods=["GET"])
def get_loans():
    return jsonify(safe_select("loan"))


@app.route("/api/loans", methods=["POST"])
def add_loan():
    data = request.json

    payload = {
        "borrower_id": data.get("borrower_id"),
        "staff_id": data.get("staff_id"),
        "loan_type": data.get("loan_type"),
        "principal_amount": data.get("principal_amount"),
        "interest_rate": data.get("interest_rate"),
        "term_months": data.get("term_months"),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "loan_status": data.get("loan_status", "Active"),
    }

    return jsonify(safe_insert("loan", payload))


# =========================
# PAYMENTS
# =========================

@app.route("/api/payments", methods=["GET"])
def get_payments():
    return jsonify(safe_select("payment"))


@app.route("/api/payments", methods=["POST"])
def add_payment():
    data = request.json

    payload = {
        "loan_id": data.get("loan_id"),
        "amount_paid": data.get("amount_paid"),
        "payment_date": data.get("payment_date"),
        "payment_method": data.get("payment_method"),
        "late_fee_applied": data.get("late_fee_applied", 0),
    }

    return jsonify(safe_insert("payment", payload))


# =========================
# COLLATERAL
# =========================

@app.route("/api/collateral", methods=["GET"])
def get_collateral():
    return jsonify(safe_select("collateral"))


@app.route("/api/collateral", methods=["POST"])
def add_collateral():
    data = request.json

    payload = {
        "loan_id": data.get("loan_id"),
        "asset_type": data.get("asset_type"),
        "market_value": data.get("market_value"),
        "asset_description": data.get("asset_description"),
    }

    return jsonify(safe_insert("collateral", payload))


# =========================
# RUN
# =========================

if __name__ == "__main__":
    app.run(debug=True, port=5000)
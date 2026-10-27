import csv
import io
import os
import secrets
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from flask import Flask, flash, make_response, redirect, render_template, request, url_for

from database import get_db, init_db, close_db
from ledgerly_logic import format_money, invoice_total, parse_date, parse_decimal

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.teardown_appcontext(close_db)

CURRENCY = os.getenv("CURRENCY", "PKR")


def money(value):
    return format_money(value, CURRENCY)


app.jinja_env.filters["money"] = money

def get_invoice_or_404(invoice_id, include_items=True):
    db = get_db()
    invoice = db.execute(
        """SELECT invoices.*, clients.name AS client_name, clients.email AS client_email,
                  clients.company AS client_company, clients.address AS client_address
           FROM invoices JOIN clients ON clients.id = invoices.client_id WHERE invoices.id = ?""",
        (invoice_id,),
    ).fetchone()
    if invoice is None:
        from flask import abort
        abort(404)
    data = dict(invoice)
    if include_items:
        data["items"] = [dict(row) for row in db.execute(
            "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id", (invoice_id,)
        ).fetchall()]
    return data


@app.before_request
def ensure_database():
    init_db()


@app.context_processor
def inject_globals():
    return {"app_name": "Ledgerly", "current_year": date.today().year, "currency": CURRENCY}


@app.get("/")
def dashboard():
    db = get_db()
    today = date.today().isoformat()
    totals = db.execute(
        """SELECT
            COALESCE(SUM(CASE WHEN status = 'paid' THEN total ELSE 0 END), 0) AS paid_total,
            COALESCE(SUM(CASE WHEN status != 'paid' THEN total ELSE 0 END), 0) AS open_total,
            COALESCE(SUM(CASE WHEN status != 'paid' AND due_date < ? THEN 1 ELSE 0 END), 0) AS overdue_count,
            COUNT(*) AS invoice_count
        FROM invoices""", (today,)
    ).fetchone()
    recent = db.execute(
        """SELECT invoices.*, clients.name AS client_name
           FROM invoices JOIN clients ON clients.id = invoices.client_id
           ORDER BY invoices.created_at DESC, invoices.id DESC LIMIT 6"""
    ).fetchall()
    client_count = db.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
    return render_template("dashboard.html", totals=totals, recent=recent, client_count=client_count, today=today)


@app.get("/clients")
def clients():
    db = get_db()
    rows = db.execute(
        """SELECT clients.*, COUNT(invoices.id) AS invoice_count,
                  COALESCE(SUM(CASE WHEN invoices.status = 'paid' THEN invoices.total ELSE 0 END), 0) AS paid_total
           FROM clients LEFT JOIN invoices ON invoices.client_id = clients.id
           GROUP BY clients.id ORDER BY clients.name COLLATE NOCASE"""
    ).fetchall()
    return render_template("clients.html", clients=rows)


@app.route("/clients/new", methods=["GET", "POST"])
def new_client():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        company = request.form.get("company", "").strip()
        address = request.form.get("address", "").strip()
        if not name:
            flash("Client name is required.", "error")
            return render_template("client_form.html", form=request.form), 400
        if len(name) > 120 or len(email) > 180 or len(company) > 180 or len(address) > 1000:
            flash("One or more fields are too long.", "error")
            return render_template("client_form.html", form=request.form), 400
        try:
            db = get_db()
            db.execute(
                "INSERT INTO clients (name, email, company, address, created_at) VALUES (?, ?, ?, ?, ?)",
                (name, email, company, address, datetime.now().isoformat(timespec="seconds")),
            )
            db.commit()
            flash("Client saved.", "success")
            return redirect(url_for("clients"))
        except Exception:
            get_db().rollback()
            app.logger.exception("Unable to save client")
            flash("Could not save this client. Please try again.", "error")
            return render_template("client_form.html", form=request.form), 500
    return render_template("client_form.html", form={})


@app.get("/invoices")
def invoices():
    status = request.args.get("status", "all")
    if status not in {"all", "draft", "sent", "paid"}:
        status = "all"
    db = get_db()
    if status == "all":
        rows = db.execute(
            """SELECT invoices.*, clients.name AS client_name FROM invoices
               JOIN clients ON clients.id = invoices.client_id
               ORDER BY invoices.created_at DESC, invoices.id DESC"""
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT invoices.*, clients.name AS client_name FROM invoices
               JOIN clients ON clients.id = invoices.client_id WHERE invoices.status = ?
               ORDER BY invoices.created_at DESC, invoices.id DESC""", (status,)
        ).fetchall()
    return render_template("invoices.html", invoices=rows, selected_status=status, today=date.today().isoformat())


@app.route("/invoices/new", methods=["GET", "POST"])
def new_invoice():
    db = get_db()
    client_rows = db.execute("SELECT * FROM clients ORDER BY name COLLATE NOCASE").fetchall()
    if request.method == "GET":
        if not client_rows:
            flash("Add a client before creating your first invoice.", "info")
            return redirect(url_for("new_client"))
        return render_template("invoice_form.html", clients=client_rows, today=date.today().isoformat(), form={})

    try:
        client_id = int(request.form.get("client_id", ""))
        if not db.execute("SELECT id FROM clients WHERE id = ?", (client_id,)).fetchone():
            raise ValueError("Choose a valid client.")
        issue_date = parse_date(request.form.get("issue_date"), "Issue date")
        due_date = parse_date(request.form.get("due_date"), "Due date")
        if due_date < issue_date:
            raise ValueError("Due date cannot be earlier than the issue date.")
        tax_rate = parse_decimal(request.form.get("tax_rate", "0"), "Tax rate", Decimal("0"), Decimal("100"))
        discount = parse_decimal(request.form.get("discount", "0"), "Discount")
        descriptions = request.form.getlist("item_description[]")
        quantities = request.form.getlist("item_quantity[]")
        prices = request.form.getlist("item_price[]")
        if not descriptions or len(descriptions) != len(quantities) or len(descriptions) != len(prices):
            raise ValueError("Add at least one complete line item.")
        if len(descriptions) > 40:
            raise ValueError("An invoice can contain up to 40 line items.")
        items = []
        subtotal = Decimal("0.00")
        for description, quantity_raw, price_raw in zip(descriptions, quantities, prices):
            description = description.strip()
            if not description or len(description) > 240:
                raise ValueError("Every line item needs a description of 1–240 characters.")
            quantity = parse_decimal(quantity_raw, "Quantity", Decimal("0.01"), Decimal("1000000"))
            unit_price = parse_decimal(price_raw, "Unit price", Decimal("0"), Decimal("999999999"))
            line_total = (quantity * unit_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            subtotal += line_total
            items.append((description, quantity, unit_price, line_total))
        if discount > subtotal + (subtotal * tax_rate / Decimal("100")):
            raise ValueError("Discount cannot exceed the invoice amount before discount.")
        tax_amount, total = invoice_total(subtotal, tax_rate, discount)
        notes = request.form.get("notes", "").strip()
        if len(notes) > 3000:
            raise ValueError("Notes must be 3,000 characters or fewer.")
        created_at = datetime.now().isoformat(timespec="seconds")
        cur = db.execute(
            """INSERT INTO invoices (client_id, invoice_number, issue_date, due_date, status,
               subtotal, tax_rate, tax_amount, discount, total, notes, created_at)
               VALUES (?, 'PENDING', ?, ?, 'draft', ?, ?, ?, ?, ?, ?, ?)""",
            (client_id, issue_date, due_date, str(subtotal), str(tax_rate), str(tax_amount), str(discount), str(total), notes, created_at),
        )
        invoice_id = cur.lastrowid
        invoice_number = f"LDG-{datetime.now().year}-{invoice_id:04d}"
        db.execute("UPDATE invoices SET invoice_number = ? WHERE id = ?", (invoice_number, invoice_id))
        db.executemany(
            "INSERT INTO invoice_items (invoice_id, description, quantity, unit_price, line_total) VALUES (?, ?, ?, ?, ?)",
            [(invoice_id, desc, str(qty), str(price), str(line_total)) for desc, qty, price, line_total in items],
        )
        db.commit()
        flash("Invoice created successfully.", "success")
        return redirect(url_for("invoice_detail", invoice_id=invoice_id))
    except (ValueError, TypeError) as exc:
        db.rollback()
        flash(str(exc), "error")
    except Exception:
        db.rollback()
        app.logger.exception("Unable to create invoice")
        flash("Could not create the invoice. Check your fields and try again.", "error")
    return render_template("invoice_form.html", clients=client_rows, today=date.today().isoformat(), form=request.form), 400


@app.get("/invoices/<int:invoice_id>")
def invoice_detail(invoice_id):
    invoice = get_invoice_or_404(invoice_id)
    return render_template("invoice_detail.html", invoice=invoice, today=date.today().isoformat())


@app.post("/invoices/<int:invoice_id>/status")
def update_invoice_status(invoice_id):
    db = get_db()
    if not db.execute("SELECT id FROM invoices WHERE id = ?", (invoice_id,)).fetchone():
        from flask import abort
        abort(404)
    status = request.form.get("status", "")
    if status not in {"draft", "sent", "paid"}:
        flash("Choose a valid invoice status.", "error")
    else:
        db.execute("UPDATE invoices SET status = ? WHERE id = ?", (status, invoice_id))
        db.commit()
        flash("Invoice status updated.", "success")
    return redirect(url_for("invoice_detail", invoice_id=invoice_id))


@app.post("/invoices/<int:invoice_id>/delete")
def delete_invoice(invoice_id):
    db = get_db()
    row = db.execute("SELECT id FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if row is None:
        from flask import abort
        abort(404)
    db.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    db.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
    db.commit()
    flash("Invoice deleted.", "success")
    return redirect(url_for("invoices"))


@app.get("/export/invoices.csv")
def export_csv():
    db = get_db()
    rows = db.execute(
        """SELECT invoices.invoice_number, clients.name, clients.company, invoices.issue_date,
                  invoices.due_date, invoices.status, invoices.subtotal, invoices.tax_rate,
                  invoices.tax_amount, invoices.discount, invoices.total, invoices.created_at
           FROM invoices JOIN clients ON clients.id = invoices.client_id
           ORDER BY invoices.created_at DESC"""
    ).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Invoice number", "Client", "Company", "Issue date", "Due date", "Status", "Subtotal", "Tax rate (%)", "Tax amount", "Discount", "Total", "Created at"])
    writer.writerows([tuple(row) for row in rows])
    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = "attachment; filename=ledgerly-invoices.csv"
    return response


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="That page or record could not be found."), 404


@app.errorhandler(413)
def too_large(_error):
    return render_template("error.html", code=413, message="The submitted request is too large."), 413


if __name__ == "__main__":
    init_db()
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")

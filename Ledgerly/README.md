# Ledgerly — Freelance Invoice & Payment Tracker

Ledgerly is a local-first invoicing workspace for freelancers and small independent teams. It keeps client records, invoice items, tax/discount calculations, payment statuses, and exportable invoice records in one small Flask application.

## Features

- Client directory with saved contact details.
- Itemized invoice builder with quantity, unit price, tax, discount, issue date, due date, and notes.
- Server-side validation and total calculations.
- Invoice status tracking: Draft, Sent, and Paid.
- Dashboard for collected revenue, unpaid totals, invoice count, clients, and overdue invoices.
- Print-ready invoice pages. Use **Print / Save PDF** in a browser to save an invoice as a PDF.
- CSV export of invoice records.
- Local SQLite database; no account, cloud service, or API key required.
- Responsive paper-style interface.

## Requirements

- Python 3.10 or later.
- Windows + VS Code is fine. The app can also run on macOS/Linux.

## Run on Windows

1. Extract `Ledgerly.zip` and open the `Ledgerly` folder in VS Code.
2. Open **Terminal → New Terminal**.
3. Create a virtual environment:

   ```powershell
   py -m venv .venv
   ```

4. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   If PowerShell blocks activation, run this once for the current terminal only, then activate again:

   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```

5. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

6. Optional configuration: copy `.env.example` to `.env`. Generate a secret with:

   ```powershell
   py -c "import secrets; print(secrets.token_hex(32))"
   ```

   Replace the placeholder value for `SECRET_KEY` in `.env`. Keep `.env` private. You can change `CURRENCY=PKR` to another currency code if needed.

7. Start the app:

   ```powershell
   python app.py
   ```

8. Open `http://127.0.0.1:5000` in your browser.

The SQLite file (`ledgerly.sqlite3`) is created automatically in the project folder on first use.

## Run the tests

```powershell
python -m unittest discover -s tests -v
```

## Important notes

- Ledgerly is designed as a local portfolio project, not a production multi-user accounting service.
- It does not send invoices or collect payments. It records the invoice status you choose.
- Browser print is used for PDF saving, so the browser controls the final PDF appearance.
- Store backups of `ledgerly.sqlite3` if the records matter to you.
- The app does not execute uploaded files or user-provided code. It only stores and presents invoice text and amounts.

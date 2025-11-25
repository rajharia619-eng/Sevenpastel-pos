SEVENPASTEL - Minimal POS (Yacht events)

What's included:
- Flask app (app.py)
- SQLite DB (pos.db created on first run)
- Simple HTML pages to create event, sell tickets, view tickets by QR token, and redeem amounts.

How to run (locally or in Google Colab):
1. unzip pos_sevenpastel.zip
2. create a virtualenv (recommended) and install requirements:
   pip install -r requirements.txt
3. Run Flask:
   export FLASK_APP=app.py
   flask run --host=0.0.0.0 --port=5000
   (Or: python app.py)
4. Open http://127.0.0.1:5000 in your browser.
5. To expose publicly in Colab, you can use ngrok (not included here).

Notes for beginners:
- QR token is a short UUID stored in the database. For scanning at the gate you can use the token text (copy-paste) or later add a QR image generator.
- Redeem endpoint decrements redeemable_balance and logs a transaction. Database transactions are simple with SQLite here.
- This starter avoids payment/third-party integrations to keep things simple.

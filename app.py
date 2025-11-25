from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
import uuid, os

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev_secret_change_this")

# Render-compatible SQLite storage
db_folder = "/var/data"
os.makedirs(db_folder, exist_ok=True)

db_path = os.path.join(db_folder, "pos.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Create DB on startup
with app.app_context():
    db.create_all()


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    date = db.Column(db.String(50), nullable=False)
    capacity = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    buyer_name = db.Column(db.String(200))
    tier = db.Column(db.String(200))
    price = db.Column(db.Integer, default=0)
    redeemable_balance = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='issued')
    qr_token = db.Column(db.String(100), unique=True, index=True, nullable=False)
    issued_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50))
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id'))
    event_id = db.Column(db.Integer)
    amount = db.Column(db.Integer)
    redeem_before = db.Column(db.Integer)
    redeem_after = db.Column(db.Integer)
    processed_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

class Audit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100))
    ticket_id = db.Column(db.Integer)
    message = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())

@app.route('/')
def index():
    events = Event.query.order_by(Event.date).all()
    return render_template('index.html', events=events)

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        title = request.form['title']
        date = request.form['date']
        capacity = int(request.form.get('capacity','0') or 0)
        event = Event(title=title, date=date, capacity=capacity)
        db.session.add(event)
        db.session.commit()
        flash('Event created', 'success')
        return redirect(url_for('index'))
    return render_template('create_event.html')

@app.route('/event/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    tickets = Ticket.query.filter_by(event_id=event.id).all()
    total_sales = sum(t.price for t in tickets)
    total_redeemed = sum((tx.amount) for tx in Transaction.query.filter_by(event_id=event.id, type='redeem').all())
    return render_template('event_detail.html', event=event, tickets=tickets, total_sales=total_sales, total_redeemed=total_redeemed)

@app.route('/sell_ticket/<int:event_id>', methods=['GET', 'POST'])
def sell_ticket(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        buyer = request.form.get('buyer_name') or 'Guest'
        tier = request.form.get('tier') or 'Full Cover'
        price = int(request.form.get('price') or 0)
        redeemable = int(request.form.get('redeemable') or price)
        token = str(uuid.uuid4()).replace('-', '')[:12]
        ticket = Ticket(event_id=event.id, buyer_name=buyer, tier=tier, price=price, redeemable_balance=redeemable, qr_token=token)
        db.session.add(ticket)
        db.session.commit()
        tx = Transaction(type='sale', ticket_id=ticket.id, event_id=event.id, amount=price, redeem_before=None, redeem_after=redeemable)
        db.session.add(tx)
        db.session.commit()
        Audit_entry = Audit(action='sale', ticket_id=ticket.id, message=f"Sold ticket {ticket.id} for ₹{price}")
        db.session.add(Audit_entry)
        db.session.commit()
        flash(f'Ticket sold. QR token: {token}', 'success')
        return redirect(url_for('event_detail', event_id=event.id))
    return render_template('sell_ticket.html', event=event)

@app.route('/ticket/qr/<token>')
def ticket_by_qr(token):
    ticket = Ticket.query.filter_by(qr_token=token).first()
    if not ticket:
        flash('Ticket not found', 'danger')
        return redirect(url_for('index'))
    return render_template('ticket_view.html', ticket=ticket)

@app.route('/redeem/<int:ticket_id>', methods=['POST'])
def redeem(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    amount = int(request.form.get('amount') or 0)
    if amount <= 0:
        flash('Enter a valid amount', 'danger')
        return redirect(url_for('ticket_by_qr', token=ticket.qr_token))
    if ticket.redeemable_balance <= 0:
        flash('No balance left', 'danger')
        return redirect(url_for('ticket_by_qr', token=ticket.qr_token))
    if amount > ticket.redeemable_balance:
        flash('Amount exceeds balance', 'danger')
        return redirect(url_for('ticket_by_qr', token=ticket.qr_token))
    before = ticket.redeemable_balance
    ticket.redeemable_balance -= amount
    db.session.commit()
    tx = Transaction(type='redeem', ticket_id=ticket.id, event_id=ticket.event_id, amount=amount, redeem_before=before, redeem_after=ticket.redeemable_balance)
    db.session.add(tx)
    db.session.commit()
    audit = Audit(action='redeem', ticket_id=ticket.id, message=f"Redeemed ₹{amount}. New balance ₹{ticket.redeemable_balance}")
    db.session.add(audit)
    db.session.commit()
    flash(f'Redeemed ₹{amount}. New balance ₹{ticket.redeemable_balance}', 'success')
    return redirect(url_for('ticket_by_qr', token=ticket.qr_token))

@app.template_filter('rupee')
def format_rupee(value):
    try:
        return f"₹{int(value):,}"
    except:
        return value

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT',5000)))

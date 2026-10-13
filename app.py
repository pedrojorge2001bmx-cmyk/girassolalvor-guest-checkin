import os, sqlite3, secrets, csv, io, hmac
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, Response
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()
app=Flask(__name__)
app.config.update(SECRET_KEY=os.getenv('SECRET_KEY',secrets.token_hex(32)), WTF_CSRF_TIME_LIMIT=None, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','1')=='1', MAX_CONTENT_LENGTH=30000)
CSRFProtect(app)
DB=os.getenv('DATABASE_PATH','checkin.db')
def db():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c
def init():
 with db() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS bookings(id INTEGER PRIMARY KEY, reference TEXT NOT NULL, token TEXT UNIQUE NOT NULL, arrival TEXT NOT NULL, departure TEXT NOT NULL, expected_guests INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS guests(id INTEGER PRIMARY KEY, booking_id INTEGER NOT NULL REFERENCES bookings(id) ON DELETE CASCADE, full_name TEXT NOT NULL, nationality TEXT NOT NULL, birth_date TEXT NOT NULL, document_type TEXT NOT NULL, document_number TEXT NOT NULL, issuing_country TEXT NOT NULL, residence_country TEXT NOT NULL, created_at TEXT NOT NULL);
  CREATE INDEX IF NOT EXISTS idx_guests_booking ON guests(booking_id);''')
init()
def admin_required(fn):
 @wraps(fn)
 def wrapper(*a,**kw):
  if not session.get('admin'): return redirect(url_for('login'))
  return fn(*a,**kw)
 return wrapper
def now(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def clean(value, maxlen=150): return (value or '').strip()[:maxlen]
@app.after_request
def headers(resp):
 resp.headers['Cache-Control']='no-store';resp.headers['X-Content-Type-Options']='nosniff';resp.headers['X-Frame-Options']='DENY';resp.headers['Referrer-Policy']='no-referrer';resp.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
 return resp
@app.get('/')
def home(): return redirect(url_for('login'))
@app.route('/setup',methods=['GET','POST'])
def setup():
 with db() as c: existing=c.execute('SELECT COUNT(*) FROM admins').fetchone()[0]
 if existing: abort(404)
 if request.method=='POST':
  user=clean(request.form.get('username'),80); pwd=request.form.get('password','')
  if len(user)<3 or len(pwd)<14: flash('Use um utilizador com 3+ caracteres e palavra-passe com 14+ caracteres.');return redirect(url_for('setup'))
  with db() as c: c.execute('INSERT INTO admins(username,password_hash) VALUES (?,?)',(user,generate_password_hash(pwd)))
  return redirect(url_for('login'))
 return render_template('setup.html')
@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  with db() as c: row=c.execute('SELECT * FROM admins WHERE username=?',(clean(request.form.get('username'),80),)).fetchone()
  if row and check_password_hash(row['password_hash'],request.form.get('password','')):
   session.clear();session['admin']=row['id'];return redirect(url_for('dashboard'))
  flash('Credenciais inválidas.')
 return render_template('login.html')
@app.post('/logout')
def logout(): session.clear();return redirect(url_for('login'))
@app.get('/admin')
@admin_required
def dashboard():
 with db() as c: bookings=c.execute('SELECT b.*, (SELECT COUNT(*) FROM guests g WHERE g.booking_id=b.id) AS submitted FROM bookings b ORDER BY arrival DESC').fetchall()
 return render_template('dashboard.html',bookings=bookings)
@app.post('/admin/bookings')
@admin_required
def create_booking():
 reference=clean(request.form.get('reference'),80);arrival=clean(request.form.get('arrival'),10);departure=clean(request.form.get('departure'),10)
 try:
  n=int(request.form.get('expected_guests',1)); assert 1<=n<=15
  assert datetime.fromisoformat(arrival)<datetime.fromisoformat(departure)
  assert reference
 except (ValueError,AssertionError): flash('Verifique a referência, as datas e o número de hóspedes.');return redirect(url_for('dashboard'))
 token=secrets.token_urlsafe(32)
 with db() as c: c.execute('INSERT INTO bookings(reference,token,arrival,departure,expected_guests,created_at) VALUES(?,?,?,?,?,?)',(reference,token,arrival,departure,n,now()))
 flash('Reserva criada. Copie o link privado da reserva.');return redirect(url_for('dashboard'))
@app.get('/admin/bookings/<int:booking_id>')
@admin_required
def booking_detail(booking_id):
 with db() as c:
  booking=c.execute('SELECT * FROM bookings WHERE id=?',(booking_id,)).fetchone()
  guests=c.execute('SELECT * FROM guests WHERE booking_id=? ORDER BY id',(booking_id,)).fetchall()
 if not booking: abort(404)
 return render_template('detail.html',booking=booking,guests=guests)
@app.post('/admin/bookings/<int:booking_id>/delete')
@admin_required
def delete_booking(booking_id):
 with db() as c: c.execute('DELETE FROM bookings WHERE id=?',(booking_id,))
 flash('Reserva e dados associados eliminados.');return redirect(url_for('dashboard'))
@app.get('/admin/export.csv')
@admin_required
def export_csv():
 with db() as c: rows=c.execute('SELECT b.reference,b.arrival,b.departure,g.full_name,g.nationality,g.birth_date,g.document_type,g.document_number,g.issuing_country,g.residence_country FROM guests g JOIN bookings b ON b.id=g.booking_id ORDER BY b.arrival,g.id').fetchall()
 output=io.StringIO(); writer=csv.writer(output);writer.writerow(['Reserva','Entrada','Saída','Nome completo','Nacionalidade','Data de nascimento','Tipo documento','Número documento','País emissor','País residência'])
 for row in rows: writer.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@')) else v for v in row])
 return Response('\ufeff'+output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=checkins-alvor.csv'})
@app.route('/checkin/<token>',methods=['GET','POST'])
def guest_checkin(token):
 with db() as c: booking=c.execute('SELECT * FROM bookings WHERE token=?',(token,)).fetchone()
 if not booking: abort(404)
 if booking['status']=='submitted': return render_template('thanks.html')
 if request.method=='POST':
  n=booking['expected_guests']; entries=[]
  for i in range(n):
   vals=[clean(request.form.get(f'{k}_{i}')) for k in ['full_name','nationality','birth_date','document_type','document_number','issuing_country','residence_country']]
   if any(not v for v in vals): flash('Preencha todos os campos de todos os hóspedes.');return redirect(url_for('guest_checkin',token=token))
   try: datetime.fromisoformat(vals[2])
   except ValueError: flash('Data de nascimento inválida.');return redirect(url_for('guest_checkin',token=token))
   entries.append(vals)
  if request.form.get('privacy_ack')!='yes': flash('Confirme que leu a informação de privacidade.');return redirect(url_for('guest_checkin',token=token))
  with db() as c:
   if c.execute('SELECT status FROM bookings WHERE id=?',(booking['id'],)).fetchone()['status']=='submitted':return render_template('thanks.html')
   for vals in entries: c.execute('INSERT INTO guests(booking_id,full_name,nationality,birth_date,document_type,document_number,issuing_country,residence_country,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(booking['id'],*vals,now()))
   c.execute("UPDATE bookings SET status='submitted' WHERE id=?",(booking['id'],))
  return render_template('thanks.html')
 return render_template('guest.html',booking=booking)
@app.get('/privacy')
def privacy():return render_template('privacy.html')
if __name__=='__main__':app.run(debug=False)

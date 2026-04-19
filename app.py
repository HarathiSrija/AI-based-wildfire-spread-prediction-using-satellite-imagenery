from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import mysql
from werkzeug.security import generate_password_hash, check_password_hash
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.layers import Dense as KerasDense
import numpy as np
import os

from db_config import get_db_connection

# ---------------- Flask Setup ----------------
app = Flask(__name__)
app.secret_key = 'your_secret_key'

UPLOAD_FOLDER = 'static/uploads/'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- Login Setup ----------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ---------------- User class ----------------
class User(UserMixin):
    def __init__(self, id_, username, role):
        self.id = str(id_)
        self.username = username
        self.role = role


# ---------------- Load User ----------------
@login_manager.user_loader
def load_user(user_id):

    # Handle direct admin session
    if str(user_id) == "0":
        return User(
            id_=0,
            username="admin",
            role="admin"
        )

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM login WHERE id=%s",
        (user_id,)
    )

    user = cursor.fetchone()

    cursor.close()
    db.close()

    if user:
        return User(
            user['id'],
            user['username'],
            user['role']
        )

    return None


# ---------------- TensorFlow Fix ----------------
class DenseNoQuant(KerasDense):
    def __init__(self, *args, **kwargs):
        kwargs.pop("quantization_config", None)
        super().__init__(*args, **kwargs)


# ---------------- Load Model ----------------
model = load_model(
    'wildfire_model.h5',
    custom_objects={"Dense": DenseNoQuant}
)


def predict_fire(img_path):

    img = image.load_img(
        img_path,
        target_size=(128, 128)
    )

    img_array = image.img_to_array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    prediction = model.predict(img_array)[0][0]

    confidence = prediction * 100

    if prediction > 0.5:
        return f"🔥 Fire Risk ({confidence:.2f}% confidence)"
    else:
        return f"✅ No Fire Risk ({100 - confidence:.2f}% confidence)"


# ---------------- Routes ----------------

@app.route('/')
def default():
    return redirect(url_for('home'))


@app.route('/home')
def home():
    return render_template("home.html")


@app.route('/forgot_email')
def forgot_email():
    return render_template("forgot_email.html")



@app.route('/forgot_otp')
def forgot_otp():
    return render_template("forgot_password.html")

from sendAlerts import *
@app.route('/otpsend', methods=['GET', 'POST'])
def otpsend():
      if request.method == 'POST':

        email = request.form['email'].strip()

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM login WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user:
            import random
            num = random.randint(10000, 1000000)
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)
            cursor.execute(
            "update login set otp=%s WHERE email=%s",
            (num,email)
            )
            db.commit()
            cursor.close()
            db.close()
            body = f"Your OTP for password reset is: {num}"
            send_email(email,body)
            flash("OTP sent to your email (simulated)")
            return redirect(url_for('forgot_otp'))
        else:
            flash("Email not found")
            return redirect(url_for('forgot_email'))

# ---------------- Prediction ----------------
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index_page():

    if request.method == 'POST':

        if 'file' not in request.files:
            flash("No file uploaded")
            return redirect(request.url)

        file = request.files['file']

        if file.filename == '':
            flash("No file selected")
            return redirect(request.url)

        filepath = os.path.join(
            UPLOAD_FOLDER,
            file.filename
        )

        file.save(filepath)

        result = predict_fire(filepath)

        return render_template(
            'result.html',
            result=result,
            img_path=filepath
        )

    return render_template('index.html')


# ---------------- Register ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username").strip()
        password = request.form.get("password").strip()
        email = request.form.get("email").strip()
        contact = request.form.get("contact").strip()
        address = request.form.get("address").strip()
        role = request.form.get("role").strip()

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM login WHERE username=%s",
            (username,)
        )

        user = cursor.fetchone()

        if user:
            flash("Username already exists!")
            cursor.close()
            db.close()
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO login
            (username, password_hash, email, contact, address, role)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                username,
                hashed_password,
                email,
                contact,
                address,
                role
            )
        )

        db.commit()

        cursor.close()
        db.close()

        flash("Registration successful!")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- Login ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username'].strip()
        password = request.form['password'].strip()

        # ---------------- DIRECT ADMIN LOGIN ----------------
        if username == "admin" and password == "admin":

            admin_user = User(
                id_=0,
                username="admin",
                role="admin"
            )

            login_user(admin_user)

            print("Admin login successful")

            return redirect(url_for('admin'))

        # ---------------- NORMAL USER LOGIN ----------------

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute(
            "SELECT * FROM login WHERE username=%s",
            (username,)
        )

        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and check_password_hash(
                user['password_hash'],
                password):

            login_user(
                User(
                    user['id'],
                    user['username'],
                    user['role']
                )
            )

            return redirect(url_for('index_page'))

        else:

            flash("Invalid username or password")

    return render_template('login.html')


# ---------------- Admin Dashboard ----------------
@app.route('/admin')
@login_required
def admin():

    if current_user.role != "admin":

        flash("Access denied: Admins only")
        return redirect(url_for("home"))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            id,
            username,
            email,
            contact,
            address,
            role
        FROM login
        """
    )

    users = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template(
        "admin.html",
        users=users
    )
    
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():

    if request.method == 'POST':

        otp = request.form['otp']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        # Check passwords match
        if new_password != confirm_password:
            flash("Passwords do not match")
            return redirect(url_for('forgot_password'))

        hashed_password = generate_password_hash(new_password)

        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="root",
            database="wildfire",
            port=3306
        )

        cursor = conn.cursor()

        # Correct table and column names
        cursor.execute(
            "UPDATE login SET password_hash=%s WHERE otp=%s",
            (hashed_password, otp)
        )

        conn.commit()

        flash("Password reset successful")

        return redirect(url_for('login'))

    return render_template('forgot_email.html')
# ---------------- Logout ----------------
@app.route('/logout')
@login_required
def logout():

    logout_user()

    flash('You have logged out.')

    return redirect(url_for('login'))


# ---------------- Run ----------------
if __name__ == '__main__':
    app.run(debug=True)

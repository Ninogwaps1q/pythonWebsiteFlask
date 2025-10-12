import os
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import google.generativeai as genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("Messing api key in .env file")

    
    genai.configure(api_key="AIzaSyBDlPAFKwK7D3x7g99r0emxNjbqm1m1INY")
    
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///melynalTrading.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.secret_key = os.getenv("FLASK_SECRET_KEY")

UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    firstname = db.Column(db.String(150), nullable=False)
    lastname = db.Column(db.String(150), nullable=False)
    contact = db.Column(db.String(150), nullable=False)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    profile_pic = db.Column(db.String(300), nullable=True)
    
    orders = db.relationship('Order', back_populates='user', cascade="all, delete-orphan")

class Product(db.Model):
    __tablename__ = 'products'
    product_id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(200), default='default.jpg')
    
    orders = db.relationship('Order', back_populates='product', cascade="all, delete-orphan")
    
class Order(db.Model):
    __tablename__ = 'orders'
    order_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.product_id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', back_populates='orders')
    product = db.relationship('Product', back_populates='orders')
    
def init_db():
    with app.app_context():
        db.create_all()
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            hashed_password = generate_password_hash('admin')
            admin = User(
                firstname = 'Manilyn',
                lastname = 'Cavalida',
                contact = '09123456789',
                username = 'admin',
                email = 'admin@melynal.com',
                password = hashed_password,
                role = 'admin',
                profile_pic = 'default_profile.jpg'
            )
            db.session.add(admin)
            db.session.commit()
            print("Default admin created.")
        else:
            print("Admin already exists.")
            
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    g.user = None
    g.admin = False
    if user_id:
        user = User.query.get(user_id)
        if user:
            g.user = user
            g.is_admin = (user.role == 'admin')
            
from functools import wraps

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapped

def admin_required(f):
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        user = User.query.get(session.get('user_id'))
        if user and user.role == 'admin':
            return f(*args, **kwargs)
        flash("Admin access required.", "danger")
        return redirect(url_for('index'))
    return wrapped

@app.route('/')
def index():
    search_query = request.args.get('search', '')
    if search_query:
        like = f"%{search_query}%"
        products = Product.query.filter(
            (Product.product_name.ilike(like)) | (Product.description.ilike(like))
        ).order_by(Product.product_name).all()
    else:
        products = Product.query.order_by(Product.product_name).all()
    return render_template('index.html', products=products, search_query=search_query)

@app.route('/chatbot', methods=['POST'])
def chatbot():
    data = request.json
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "Please type a message about Melyñal Trading."})
    
    system_prompt = (
        "You are Melyñal Chat, the official virtual assistant for Melyñal Trading — "
        "a cosmetics and beauty products company. Only answer questions related to "
        "Melyñal Trading's products, delivery, pricing, policies, or customer support. "
        "If the user asks about unrelated topics, politely respond that you can only "
        "answer questions about Melyñal Trading."
        "price range 50 to 1999"
        "facebook contact manilyn cavalida adlawan"
    )
    
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(f"{system_prompt}\nUser: {user_message}\nMelyñal Chat:")
        reply = response.text.strip()
    except Exception as e:
        reply = f"⚠️ Sorry, an error occurred contacting the AI: {str(e)}"
        
    return jsonify({"reply": reply})

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get(product_id)
    if product is None:
        flash('Product not found.', 'danger')
        return redirect(url_for('index'))
    return render_template('product_detail.html', product=product)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        error = None
        
        user = User.query.filter_by(username=username).first()
        if user is None:
            error = "Incorrect username."
        elif not check_password_hash(user.password, password):
            error = "Incorrect password."
            
        if error is None:
            session.clear()
            session['user_id'] = user.id
            flash("Logged in successfully.", "success")
            return redirect(url_for('index'))
        
        flash(error, "danger")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form.get('firstname', '').strip()
        lastname = request.form.get('lastname', '').strip()
        contact = request.form.get('contact', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        error = None
        
        if not username or not firstname or not lastname or not contact:
            error = 'All personal fields are required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
            
        if error is None:
            try:
                hashed_password = generate_password_hash(password)
                user = User(
                    firstname = firstname,
                    lastname = lastname,
                    contact = contact,
                    username = username,
                    email = email,
                    password = hashed_password,
                    role = 'costumer'
                )
                db.session.add(user)
                db.session.commit()
                flash("Registration successful. Please log in.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                error = f"User or email already registered: {str(e)}"
            
        flash(error, "danger")
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/cart')
@login_required
def cart():
    cart_items = session.get('cart', {})
    product_ids = list(cart_items.keys())
    products = {}
    total_cart_price = 0.0

    if product_ids:
        int_ids = [int(pid) for pid in product_ids]
        db_products = Product.query.filter(Product.product_id.in_(int_ids)).all()
        for product in db_products:
            quantity = int(cart_items.get(str(product.product_id), 0))
            if quantity > 0:
                subtotal = product.price * quantity
                products[product.product_id] = {
                    'product_id': product.product_id,
                    'name': product.product_name,
                    'price': product.price,
                    'quantity': quantity,
                    'subtotal': subtotal,
                    'image': product.image
                }
                total_cart_price += subtotal

    return render_template('cart.html', cart_products=products, total_cart_price=total_cart_price)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        error = None

        if not name or not email or not subject or not message:
            error = "All fields are required."
        elif '@' not in email:
            error = "Please enter a valid email address."

        if error is None:
            flash("Your message has been sent! We'll get back to you soon.", "success")
            return redirect(url_for('contact'))
        else:
            flash(error, "danger")

    return render_template('contact.html')


@app.route('/about')
def about_page():
    return render_template('about.html')

@app.route("/buy_now/<int:product_id>", methods=["POST"])
@login_required
def buy_now(product_id):
    product = Product.query.get(product_id)
    if not product:
        flash("Product not found.", "danger")
        return redirect(url_for("index"))
    if product.stock <= 0:
        flash("Sorry, this product is out of stock.", "danger")
        return redirect(url_for("index"))

    user_id = session["user_id"]
    quantity = 1
    total_price = product.price * quantity
    order_date = datetime.now()

    try:
        order = Order(
            user_id=user_id,
            product_id=product.product_id,
            quantity=quantity,
            total_price=total_price,
            order_date=order_date
        )
        product.stock = product.stock - quantity
        db.session.add(order)
        db.session.commit()
        flash(f"You successfully bought {product.product_name} for ₱{product.price:.2f}.", "success")
        return redirect(url_for("order_history"))
    except Exception as e:
        db.session.rollback()
        flash(f"Error processing purchase: {e}", "danger")
        return redirect(url_for("index"))


@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get(product_id)
    if product is None:
        flash('Product not found.', 'danger')
        return redirect(url_for('index'))

    quantity_str = request.form.get('quantity', '1')
    try:
        quantity = int(quantity_str)
        if quantity < 1:
            quantity = 1
    except ValueError:
        quantity = 1

    if product.stock < quantity:
        flash(f'Only {product.stock} items in stock.', 'danger')
        return redirect(url_for('product_detail', product_id=product_id))

    cart = session.get('cart', {})
    pid_str = str(product_id)
    current_quantity = cart.get(pid_str, 0)

    if current_quantity + quantity > product.stock:
        flash(f'Adding {quantity} items exceeds stock. Total in cart would be {current_quantity + quantity}, but only {product.stock} available.', 'danger')
    else:
        cart[pid_str] = current_quantity + quantity
        session['cart'] = cart
        flash('Product added to cart!', 'success')

    return redirect(request.referrer or url_for('product_detail', product_id=product_id))

@app.route('/update_cart/<int:product_id>', methods=['POST'])
@login_required
def update_cart(product_id):
    new_quantity = request.form.get('quantity', 0, type=int)
    product = Product.query.get(product_id)
    product_id_str = str(product_id)
    cart = session.get('cart', {})

    if product_id_str in cart:
        if new_quantity <= 0:
            cart.pop(product_id_str, None)
            flash('Product removed from cart.', 'info')
        else:
            if product and new_quantity <= product.stock:
                cart[product_id_str] = new_quantity
                flash('Cart updated.', 'success')
            else:
                flash(f'Cannot update. Only {product.stock if product else 0} items in stock.', 'danger')
        session['cart'] = cart

    return redirect(url_for('cart'))

@app.route('/place_order', methods=['POST'])
@login_required
def place_order():
    cart_items = session.get('cart', {})
    if not cart_items:
        flash('Your cart is empty. Cannot place an order.', 'warning')
        return redirect(url_for('cart'))

    user_id = session['user_id']
    total_order_price = 0

    try:
        for pid_str, quantity in cart_items.items():
            product = Product.query.get(int(pid_str))
            if not product or quantity <= 0:
                continue
            if product.stock < quantity:
                flash(f'Not enough stock for {product.product_name}.', 'danger')
                return redirect(url_for('cart'))

            subtotal = product.price * quantity
            total_order_price += subtotal

            order = Order(
                user_id=user_id,
                product_id=product.product_id,
                quantity=quantity,
                total_price=subtotal,
                order_date=datetime.utcnow()
            )
            product.stock -= quantity
            db.session.add(order)

        db.session.commit()
        session['cart'] = {}
        flash(f'Order placed successfully! Total: ₱{total_order_price:.2f}', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        db.session.rollback()
        flash(f'Error placing order: {str(e)}', 'danger')
        return redirect(url_for('cart'))
    

@app.route('/checkout')
@login_required
def checkout():
    cart_items = session.get('cart', {})
    if not cart_items:
        flash('Your cart is empty!', 'warning')
        return redirect(url_for('index'))
    return redirect(url_for('cart'))


@app.route('/order_history')
@login_required
def order_history():
    orders = Order.query.join(Product, Order.product_id == Product.product_id)\
                        .filter(Order.user_id == session['user_id'])\
                        .order_by(Order.order_date.desc())\
                        .add_columns(Order.order_id, Order.quantity, Order.total_price, Order.order_date, Product.product_name, Product.image)\
                        .all()
    return render_template('order_history.html', orders=orders)


@app.route('/profile')
@login_required
def profile():
    user = User.query.get(session['user_id'])
    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for('index'))
    return render_template('profile.html', user=user)

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = User.query.get(session['user_id'])
    if user is None:
        flash("User not found.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        firstname = request.form.get('firstname', '').strip()
        lastname = request.form.get('lastname', '').strip()
        contact = request.form.get('contact', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        image_file = request.files.get('profile_image')
        error = None
        current_image = user.profile_pic or 'default_profile.jpg'

        if not firstname or not lastname or not contact or not email:
            error = "All fields (except password) are required."

        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image_file.save(save_path)
              
                if current_image and current_image != 'default_profile.jpg':
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], current_image))
                    except OSError:
                        pass
                current_image = filename
            else:
                error = 'Invalid image file type. Allowed: png, jpg, jpeg, gif.'

        if error is None:
            try:
                user.firstname = firstname
                user.lastname = lastname
                user.contact = contact
                user.email = email
                user.profile_pic = current_image
                if password:
                    user.password = generate_password_hash(password)
                db.session.commit()
                flash("Profile updated successfully.", "success")
                return redirect(url_for('profile'))
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating profile: {e}", "danger")
        else:
            flash(error, 'danger')

    return render_template('edit_profile.html', user=user)



@app.route('/admin')
@admin_required
def admin_dashboard():
    products = Product.query.order_by(Product.product_name).all()
    return render_template('admin/dashboard.html', products = products)

@app.route('/admin/add_product', methods=('GET', 'POST'))
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form.get('product_name', '').strip()
        price = request.form.get('price', '').strip()
        stock = request.form.get('stock', '').strip()
        description = request.form.get('description', '').strip()
        image_file = request.files.get('image')
        error = None

        if not name or not price or not stock:
            error = 'Name, price, and stock are required.'

        filename = 'default.jpg'
        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                filename = secure_filename(image_file.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            else:
                error = 'Invalid image file type. Allowed: png, jpg, jpeg, gif.'

        if error is None:
            try:
                product = Product(
                    product_name=name,
                    price=float(price),
                    stock=int(stock),
                    description=description,
                    image=filename
                )
                db.session.add(product)
                db.session.commit()
                flash(f'Product "{name}" added successfully.', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                db.session.rollback()
                error = f'Database error: {e}'

        flash(error, 'danger')

    return render_template('admin/add_product.html')

@app.route('/admin/edit_product/<int:product_id>', methods=('GET', 'POST'))
@admin_required
def edit_product(product_id):
    product = Product.query.get(product_id)
    if product is None:
        flash('Product not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        name = request.form.get('product_name', '').strip()
        price = request.form.get('price', '').strip()
        stock = request.form.get('stock', '').strip()
        description = request.form.get('description', '').strip()
        image_file = request.files.get('image')
        error = None
        current_image = product.image

        if not name or not price or not stock:
            error = 'Name, price, and stock are required.'

        if image_file and image_file.filename:
            if allowed_file(image_file.filename):
                if current_image and current_image != 'default.jpg':
                    try:
                        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], current_image))
                    except OSError:
                        pass
                filename = secure_filename(image_file.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_image = filename
            else:
                error = 'Invalid image file type. Allowed: png, jpg, jpeg, gif.'

        if error is None:
            try:
                product.product_name = name
                product.price = float(price)
                product.stock = int(stock)
                product.description = description
                product.image = current_image
                db.session.commit()
                flash(f'Product "{name}" updated successfully.', 'success')
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                db.session.rollback()
                error = f'Database error: {e}'

        flash(error, 'danger')

    return render_template('admin/edit_product.html', product=product)


@app.route('/admin/delete_product/<int:product_id>', methods=('POST',))
@admin_required
def delete_product(product_id):
    product = Product.query.get(product_id)
    if product is None:
        flash('Product not found.', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        image_filename = product.image
        db.session.delete(product)
        db.session.commit()
        if image_filename and image_filename != 'default.jpg':
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
            except OSError:
                pass
        flash(f'Product "{product.product_name}" and associated data deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting product: {e}. Check if there are related orders.', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/orders')
@admin_required
def view_all_orders():
    orders = Order.query.order_by(Order.order_date.desc()).all()

    return render_template('admin/all_orders.html', orders=orders)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
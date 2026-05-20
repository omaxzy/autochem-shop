from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import os
import uuid
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

import json

@app.template_filter('fromjson')
def fromjson_filter(value):
    try:
        return json.loads(value)
    except:
        return []

db = SQLAlchemy(app)

# ========== МОДЕЛИ ==========

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_manager = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    brand = db.Column(db.String(100), nullable=False)
    volume = db.Column(db.String(50), nullable=False)
    image = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    customer_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    address = db.Column(db.Text, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    items = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Новый')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='orders')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/icons', exist_ok=True)

# ========== ДЕКОРАТОРЫ ==========

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            flash('Доступ запрещён', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def manager_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or (not user.is_admin and not user.is_manager):
            flash('Доступ запрещён', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def optimize_image(image_path, max_size=(800, 800)):
    try:
        with Image.open(image_path) as img:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.save(image_path, quality=85, optimize=True)
    except Exception as e:
        print(f"Error optimizing image: {e}")

# ========== АВТОРИЗАЦИЯ ==========

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует', 'error')
            return redirect(url_for('register'))
        
        if len(password) < 4:
            flash('Пароль должен быть не менее 4 символов', 'error')
            return redirect(url_for('register'))
        
        hashed = generate_password_hash(password)
        user = User(username=username, password_hash=hashed)
        db.session.add(user)
        db.session.commit()
        
        session['user_id'] = user.id
        session['username'] = user.username
        flash('Регистрация успешна!', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Вход выполнен!', 'success')
            return redirect(url_for('index'))
        
        flash('Неверный логин или пароль', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))

@app.route('/account')
@login_required
def account():
    user = User.query.get(session['user_id'])
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return render_template('account.html', user=user, orders=orders)

# ========== ГЛАВНАЯ (ЛЕНДИНГ) ==========

@app.route('/')
def index():
    return render_template('index.html')

# ========== КАТАЛОГ ==========

@app.route('/catalog')
def catalog():
    products = Product.query.order_by(Product.created_at.desc()).all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('catalog.html', products=products, categories=[cat[0] for cat in categories])

@app.route('/category/<category>')
def filter_by_category(category):
    products = Product.query.filter_by(category=category).order_by(Product.created_at.desc()).all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('catalog.html', products=products, categories=[cat[0] for cat in categories], current_category=category)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    if query:
        products = Product.query.filter(
            (Product.name.contains(query)) | 
            (Product.description.contains(query)) |
            (Product.brand.contains(query))
        ).all()
    else:
        products = Product.query.all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('catalog.html', products=products, categories=[cat[0] for cat in categories], search_query=query)

# ========== СТРАНИЦА ТОВАРА ==========

@app.route('/product/<int:id>')
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template('product.html', product=product)

# ========== КОРЗИНА ==========

@app.route('/cart')
def cart_page():
    return render_template('cart_page.html')

# ========== ЗАКАЗЫ ==========

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        items = request.form.get('items', '').strip()
        total_str = request.form.get('total', '0').strip()
        
        if not items or items == '[]':
            items = request.form.get('cart_items', '[]')
        
        if not name or not phone or not address:
            flash('Заполните все поля: имя, телефон и адрес', 'error')
            return redirect(url_for('checkout'))
        
        if not items or items == '[]':
            flash('Корзина пуста!', 'error')
            return redirect(url_for('catalog'))
        
        try:
            total = float(total_str)
        except ValueError:
            total = 0
        
        order = Order(
            user_id=session['user_id'],
            customer_name=name,
            phone=phone,
            address=address,
            total_price=total,
            items=items
        )
        db.session.add(order)
        db.session.commit()
        
        flash('Заказ успешно оформлен!', 'success')
        return redirect(url_for('thankyou'))
    
    return render_template('checkout.html')

@app.route('/thankyou')
def thankyou():
    return render_template('thankyou.html')

# ========== ПАНЕЛЬ МЕНЕДЖЕРА ==========

@app.route('/manager')
@manager_or_admin_required
def manager_panel():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('manager.html', orders=orders)

@app.route('/manager/order/<int:id>/status', methods=['POST'])
@manager_or_admin_required
def manager_update_status(id):
    order = Order.query.get_or_404(id)
    order.status = request.form['status']
    db.session.commit()
    flash('Статус обновлён!', 'success')
    return redirect(url_for('manager_panel'))

# ========== АДМИН-ПАНЕЛЬ ==========

@app.route('/admin')
@admin_required
def admin_panel():
    products = Product.query.order_by(Product.created_at.desc()).all()
    orders = Order.query.order_by(Order.created_at.desc()).all()
    users = User.query.all()
    return render_template('admin.html', products=products, orders=orders, users=users)

@app.route('/admin/add', methods=['GET', 'POST'])
@admin_required
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        brand = request.form['brand']
        volume = request.form['volume']
        
        if 'image' not in request.files:
            flash('Нет изображения', 'error')
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            flash('Файл не выбран', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4()}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            optimize_image(filepath)
            
            product = Product(
                name=name, description=description, price=price,
                category=category, brand=brand, volume=volume, image=filename
            )
            db.session.add(product)
            db.session.commit()
            flash('Товар добавлен!', 'success')
            return redirect(url_for('admin_panel'))
    
    return render_template('add_product.html')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.category = request.form['category']
        product.brand = request.form['brand']
        product.volume = request.form['volume']
        
        if 'image' in request.files and request.files['image'].filename != '':
            file = request.files['image']
            if file and allowed_file(file.filename):
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
                if os.path.exists(old_path):
                    os.remove(old_path)
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                optimize_image(filepath)
                product.image = filename
        
        product.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Товар обновлён!', 'success')
        return redirect(url_for('admin_panel'))
    
    return render_template('edit_product.html', product=product)

@app.route('/admin/delete/<int:id>')
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
    if os.path.exists(image_path):
        os.remove(image_path)
    db.session.delete(product)
    db.session.commit()
    flash('Товар удалён!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/user/<int:id>/role', methods=['POST'])
@admin_required
def update_user_role(id):
    user = User.query.get_or_404(id)
    role = request.form['role']
    if role == 'admin':
        user.is_admin = True
        user.is_manager = True
    elif role == 'manager':
        user.is_admin = False
        user.is_manager = True
    else:
        user.is_admin = False
        user.is_manager = False
    db.session.commit()
    flash('Роль обновлена!', 'success')
    return redirect(url_for('admin_panel'))

# ========== API ДЛЯ КОРЗИНЫ ==========

@app.route('/api/product/<int:id>')
def get_product(id):
    product = Product.query.get_or_404(id)
    return {
        'id': product.id,
        'name': product.name,
        'price': product.price,
        'image': product.image
    }

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ========== СОЗДАНИЕ АДМИНА ==========
def create_admin():
    # Проверяем и добавляем колонку is_manager, если её нет
    try:
        User.query.filter_by(username='admin').first()
    except:
        db.session.execute(db.text('ALTER TABLE user ADD COLUMN is_manager BOOLEAN DEFAULT 0'))
        db.session.commit()
    
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            is_admin=True,
            is_manager=True
        )
        db.session.add(admin)
        db.session.commit()
        print('Admin created: admin / admin123')
@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/delivery')
def delivery():
    return render_template('delivery.html')

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
    app.run(debug=True, host='0.0.0.0', port=5000)
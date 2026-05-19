from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from PIL import Image
import os
import uuid
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-this'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'connect_args': {'check_same_thread': False}}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)

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

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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

@app.route('/')
def index():
    products = Product.query.order_by(Product.created_at.desc()).all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('index.html', products=products, categories=[cat[0] for cat in categories])

@app.route('/category/<category>')
def filter_by_category(category):
    products = Product.query.filter_by(category=category).order_by(Product.created_at.desc()).all()
    categories = db.session.query(Product.category).distinct().all()
    return render_template('index.html', products=products, categories=[cat[0] for cat in categories], current_category=category)

@app.route('/admin')
def admin_panel():
    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('admin.html', products=products)

@app.route('/admin/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        brand = request.form['brand']
        volume = request.form['volume']
        
        if 'image' not in request.files:
            flash('No image file', 'error')
            return redirect(request.url)
        
        file = request.files['image']
        if file.filename == '':
            flash('No selected file', 'error')
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
            flash('Product added!', 'success')
            return redirect(url_for('admin_panel'))
    
    return render_template('add_product.html')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
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
                old_image_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                optimize_image(filepath)
                product.image = filename
        
        product.updated_at = datetime.utcnow()
        db.session.commit()
        flash('Product updated!', 'success')
        return redirect(url_for('admin_panel'))
    
    return render_template('edit_product.html', product=product)

@app.route('/admin/delete/<int:id>')
def delete_product(id):
    product = Product.query.get_or_404(id)
    image_path = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
    if os.path.exists(image_path):
        os.remove(image_path)
    db.session.delete(product)
    db.session.commit()
    flash('Product deleted!', 'success')
    return redirect(url_for('admin_panel'))

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
    return render_template('index.html', products=products, categories=[cat[0] for cat in categories], search_query=query)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
@app.route('/cart')
def cart():
    return render_template('cart.html')

@app.route('/api/product/<int:id>')
def get_product(id):
    product = Product.query.get_or_404(id)
    return {
        'id': product.id,
        'name': product.name,
        'price': product.price,
        'image': product.image
    }

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)

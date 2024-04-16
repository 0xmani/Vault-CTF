from flask import Flask, redirect, render_template_string, render_template, request, url_for, session
from datetime import datetime
from flask.helpers import flash
import db, os
import mysql.connector
from werkzeug.utils import secure_filename


app = Flask(__name__)

msg = 'Invalid Username or Password.'
app.config['SECRET_KEY'] = "supersecretpassword"

UPLOAD_FOLDER = 'uploads/productimg/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():

    message = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        conn = db.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query)
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Logged as '+username+'!')
            return redirect(url_for('index'))
        else:
            flash("Invalid Username or Password!")
            return render_template('login.html')
    else:
        return render_template('login.html')


@app.route('/admin')
def admin_panel():
    if 'role' in session and session['role'] == 'admin':
        # Fetch admin-related data, like all orders
        return render_template('admin_panel.html')
    else:
        return "Access denied", 403

@app.route('/orders')
def orders():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if session['role'] == 'admin':
        cursor.execute("SELECT * FROM orders")
    else:
        cursor.execute("SELECT * FROM orders WHERE user_id = %s", (session['user_id'],))

    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('orders.html', orders=orders)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/addproducts', methods=['GET', 'POST'])
def add_product():
    if 'username' not in session or session['role'] != 'admin':
        return "Access denied", 403

    if request.method == 'POST':
        # Extract product data from the form
        name = request.form['product_name']
        price = request.form['product_price']
        description = request.form['product_description']
        stock = request.form['product_stock']
        price = request.form['product_price']

        file = request.files['image_url']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)  # This is the string path
            file.save(os.path.join(app.static_folder, file_path))
            
        # Insert product data into the database
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO products (name, description, price, stock, image_url) VALUES (%s, %s, %s, %s, %s)',
                           (name, description, price, stock, file_path))
        conn.commit()
        cursor.close()
        conn.close()

        flash("Product added Successfully!")
        return render_template('addproducts.html')

    return render_template('addproducts.html')

@app.route('/products')
def show_products():
    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('products.html', products=products)

@app.route('/addtocart/<int:product_id>')
def add_to_cart(product_id):
    if 'cart' not in session:
        session['cart'] = []

    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products WHERE product_id = %s', (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    # Add product details to the cart
    session['cart'].append({
        'id': product['product_id'],
        'name': product['name'],
        'price': product['price'],
        'image_url': product['image_url']
    })
    session.modified = True
    flash('Product added to the cart sucessfully!')
    return redirect(url_for('show_products'))

@app.route('/cart')
def cart():
    if 'cart' not in session:
        return render_template('cart.html', cart_items=[])


    cart_product_ids = [item['product_id'] for item in session['cart']]
    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    #query = 'SELECT * FROM products WHERE product_id IN ({})'.format(', '.join(['%s'] * len(cart_product_ids)))
    #cursor.execute(query, tuple(cart_product_ids))
    cursor.execute("SELECT * FROM products WHERE product_id IN (%s)", (cart_product_ids,))
    cart_items = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('cart.html', cart_items=cart_items)

@app.route('/buynow/<int:product_id>')
def buy_now(product_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, product_id, quantity) VALUES (%s, %s, 1)',
                   (user_id, product_id))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Order Placed Successfully!')
    return render_template('products.html')



#logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))




if __name__ == '__main__':
    app.run(debug=True)
    
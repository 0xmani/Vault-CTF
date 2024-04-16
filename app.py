from flask import Flask, request, render_template, redirect, url_for, session, flash, render_template_string, send_from_directory
import mysql.connector
from werkzeug.utils import secure_filename
import os, db, requests
import xml.etree.ElementTree as ET
from lxml import etree


app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = "supersecretpassword"
UPLOAD_FOLDER = 'static/uploads/productimg/'
USER_UPLOAD_FOLDER = 'static/uploads/userimg/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

'''
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
'''

def allowed_file(filename):
    return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = db.get_db_connection()
        cursor = conn.cursor(dictionary=True)
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        cursor.execute(query)
        #cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            session['user_id'] = user['user_id']
            flash('Logged in successfully!')
            return redirect(url_for('index'))
        else:
            flash("Invalid Username or Password!")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/products')
def show_products():
    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/addproducts', methods=['GET', 'POST'])
def add_product():
    if 'username' not in session or session['role'] != 'admin':
        return "Access denied", 403

    if request.method == 'POST':
        name = request.form['product_name']
        description = request.form['product_description']
        price = request.form['product_price']
        stock = request.form['product_stock']
        file = request.files['image_url']
        
        #if file and allowed_file(file.filename):
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(os.path.join(app.static_folder, file_path))

            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT INTO products (name, description, price, stock, image_url) VALUES (%s, %s, %s, %s, %s)',
                           (name, description, price, stock, file_path))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Product added successfully!")
        else:
            flash("File type not allowed!")
    
    return render_template('addproducts.html')

@app.route('/addtocart/<int:product_id>')
def add_to_cart(product_id):
    if 'username' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('login'))
    
    if 'cart' not in session:
        session['cart'] = []

    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products WHERE product_id = %s', (product_id,))
    product = cursor.fetchone()
    cursor.close()
    conn.close()

    session['cart'].append({
        'product_id': product['product_id'],
        'name': product['name'],
        'price': product['price'],
        'image_url': product['image_url']
    })
    session.modified = True
    flash('Product added to cart successfully!')
    return redirect(url_for('show_products'))

@app.route('/cart')
def cart():
    if 'cart' not in session:
        return render_template('cart.html', cart_items=[])
    
    
    cart_items = []
    for item in session['cart']:
        product_id = item.get('product_id')
        if product_id:
            # Fetch product details from the database
            conn = db.get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM products WHERE product_id = %s', (product_id,))
            product = cursor.fetchone()
            cursor.close()
            conn.close()
            if product:
                cart_items.append(product)

    return render_template('cart.html', cart_items=cart_items)


@app.route('/buynow/<int:product_id>')
def buy_now(product_id):
    if 'username' not in session:
        flash("Please log in to continue.")
        return redirect(url_for('login'))

    price = request.args.get('price', type=float)
    if price is None:
        flash("Invalid price.")
        return redirect(url_for('show_products'))

    user_id = session['user_id']
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, product_id, quantity, price) VALUES (%s, %s, 1, %s)', 
               (user_id, product_id, price))
    conn.commit()
    cursor.close()
    conn.close()
    flash('Order placed successfully!')

    return redirect(url_for('my_orders'))

    #return redirect(url_for('my_orders', order_id=order_id))

@app.route('/admin/orders')
def admin_orders():
    if 'username' not in session or session['role'] != 'admin':
        return "Access Denied", 403

    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT o.order_id, o.user_id, p.name, o.price, p.image_url, o.order_status
        FROM orders o
        INNER JOIN products p ON o.product_id = p.product_id""")
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin_orders.html', orders=orders)

@app.route('/order-status/<int:order_id>/<new_status>')
def update_order_status(order_id, new_status):
    if 'username' not in session or session['role'] != 'admin':
        return "Access Denied", 403

    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET order_status = %s WHERE order_id = %s", (new_status, order_id))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Order status updated successfully!')
    return redirect(url_for('admin_orders'))

@app.route('/my-orders')
def my_orders():
    if 'username' not in session:
        flash("Please log in to view your orders.")
        return redirect(url_for('login'))

    user_id = session['user_id']

    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT o.order_id, p.name, o.price, p.image_url, o.order_status
        FROM orders o
        INNER JOIN products p ON o.product_id = p.product_id
        WHERE o.user_id = %s
    """, (user_id,))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('orders.html', orders=orders)


@app.route('/editprofile', methods=['GET', 'POST'])
def editprofile():
    if 'username' not in session:
        flash("Please log in to access your profile.")
        return redirect(url_for('login'))

    username = session['username']
    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        address = request.form['address']
        mobile_number = request.form['mobile_number']
        profile_url = request.form['profile_url']
        file = request.files.get('profile_pic')

        file_path = None
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = 'uploads/userimg/' + filename
            save_path = os.path.join(app.static_folder, file_path.replace('/', os.sep))
            file.save(save_path)

        
        '''profile_pic_path = None
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            profile_pic_path = os.path.join(USER_UPLOAD_FOLDER, filename)
            file.save(os.path.join(app.static_folder, profile_pic_path))'''

        if file_path:
            cursor.execute("""
                UPDATE users 
                SET first_name = %s, last_name = %s, address = %s, mobile_number = %s, profile_pic = %s, profile_url = %s 
                WHERE username = %s
            """, (first_name, last_name, address, mobile_number, file_path, profile_url, username))
        else:
            cursor.execute("""
                UPDATE users 
                SET first_name = %s, last_name = %s, address = %s, mobile_number = %s, profile_url = %s
                WHERE username = %s
            """, (first_name, last_name, address, mobile_number, profile_url, username))
        conn.commit()

        flash("Profile updated successfully.")

    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('edit-profile.html', user=user)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        flash("Please log in to access your profile.")
        return redirect(url_for('login'))

    username = session['username']
    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template('profile.html', user=user)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    #results = fetch_results(query)
    query = f"You Searched for: {query}"
    return render_template('base.html', query=query)
    #return f'Search results for: {query}'

@app.route('/about-us')
def aboutus():
    return render_template('aboutus.html')

@app.route('/contact-us')
def contactus():
    return render_template('contactus.html')


@app.route('/users')
def users():
    conn = db.get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('users.html', users=users)


@app.route('/fetchimage', methods=['GET', 'POST'])
def fetchimage():
    if request.method == 'POST':
        image_url = request.form.get('image_url')

        try:
            response = requests.get(image_url, timeout=5)
            
            if response.status_code == 200:
                # Here you might save the image data to a file or database
                return "Image imported successfully."
            else:
                return "Failed to import image."
        except requests.exceptions.RequestException:
            return "Error fetching the image."

    return render_template('fetchimage.html')

@app.route('/upload_reviews', methods=['GET', 'POST'])
def upload_reviews():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.xml'):
            try:
                parser = etree.XMLParser(resolve_entities=True)
                tree = etree.parse(file, parser)
                
                reviews = []
                for review in tree.xpath('//review'):
                    reviewer = review.findtext('reviewer')
                    product = review.findtext('product')
                    rating = review.findtext('rating')
                    text = review.findtext('text')
                    reviews.append({'reviewer': reviewer, 'product': product, 'rating': rating, 'text': text})

                flash("Reviews uploaded successfully")
                return render_template('reviews.html', reviews=reviews)
            except Exception as e:
                flash(f"Error processing XML file: {str(e)}")
        else:
            flash("Invalid file format")

    # Render the form for the first GET request or if the upload fails
    return render_template('reviews.html', reviews=[])
    


@app.route('/downloadxml', methods=['GET'])
def downloadxml():
    directory = "static/uploads/samplexml/"
    filename = "sample_xml_file.xml"
    return send_from_directory(directory, filename, as_attachment=True)

@app.errorhandler(404)
def page_not_found(error):
    path = request.path
    out = render_template_string(path)
    return render_template('404.html', path=out), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0')

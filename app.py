from flask import Flask, render_template, redirect, url_for, flash, request
from extensions import db, login_manager, bcrypt
from datetime import datetime
import os
import json
from functools import wraps
from datetime import datetime, timedelta


from flask_login import login_user, logout_user, login_required, current_user

# --- Configuration Constants ---
# Use a secure random key in a real deployment
SECRET_KEY = os.environ.get('SECRET_KEY', 'a_secret_key_for_dev') 
DATABASE_URI = 'sqlite:///milky_shaky.db' # SQLite DB file
MAX_DRINKS = 10  # configurable limit

def create_app():
    app = Flask(__name__)
    
    # Configure App
    app.config['SECRET_KEY'] = SECRET_KEY
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions with the app
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    login_manager.login_view = 'login' # Set the view function for login

    # Provide a lightweight "moment" for templates (supports format('YYYY') etc.)
    class _SimpleMoment:
        def __init__(self, dt):
            self.dt = dt
        def format(self, fmt: str):
            # support common tokens used in your template
            mapping = {'YYYY': '%Y', 'MM': '%m', 'DD': '%d', 'HH': '%H', 'mm': '%M', 'ss': '%S'}
            for k, v in mapping.items():
                fmt = fmt.replace(k, v)
            return self.dt.strftime(fmt)

    @app.context_processor
    def inject_moment():
        return {'moment': lambda: _SimpleMoment(datetime.utcnow())}

    # This function is crucial for Flask-Login to load a user from the session
    @login_manager.user_loader
    def load_user(user_id):
        # We need to import the User model here to avoid circular dependency
        from models import User
        # use Session.get to avoid SQLAlchemy Query.get legacy warning
        return db.session.get(User, int(user_id))
    
# Decorator to restrict access to Manager only
    def manager_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check 1: Is the user authenticated?
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login'))
                
            # Check 2: Does the user have the 'manager' role?
            # Assumes User model has a property/method 'is_manager' or 'role' attribute.
            if not getattr(current_user, 'is_manager', False):
                flash('Access denied. Manager role required.', 'error')
                return redirect(url_for('index')) # Redirect non-managers home
                
            return f(*args, **kwargs)
        return decorated_function

    # Import forms here to avoid circular import at module import time
    from forms import RegistrationForm, LoginForm
    # --- Basic Routes (Placeholder) ---
    @app.route('/')
    def index():
        return render_template('base.html', title='Welcome')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = LoginForm()
        if form.validate_on_submit():
            from models import User, AuditLog
            # Allow login by email
            user = User.query.filter_by(email=form.email.data).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember.data)
                flash('Logged in successfully.', 'success')

                # Audit log: successful login
                try:
                    audit = AuditLog(action='Login Success', actor=user.username or user.email,
                                     details=json.dumps({'user_id': user.id, 'ip': request.remote_addr}))
                    db.session.add(audit)
                    db.session.commit()
                except Exception:
                    db.session.rollback()

                next_page = request.args.get('next') or url_for('index')
                return redirect(next_page)

            # Audit log: failed login attempt
            try:
                audit = AuditLog(action='Login Failed', actor=form.email.data,
                                 details=json.dumps({'reason': 'invalid credentials', 'ip': request.remote_addr}))
                db.session.add(audit)
                db.session.commit()
            except Exception:
                db.session.rollback()

            flash('Invalid email or password.', 'error')
        return render_template('login.html', title='Login', form=form)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        form = RegistrationForm()
        if form.validate_on_submit():
            from models import User, AuditLog
            # check for duplicates
            if User.query.filter((User.username==form.username.data) | (User.email==form.email.data)).first():
                flash('Username or email already in use.', 'error')
                return render_template('register.html', title='Register', form=form)

            user = User(username=form.username.data, email=form.email.data, role='client')
            user.set_password(form.password.data)

            try:
                db.session.add(user)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                import traceback
                traceback.print_exc()           # check console for the error
                flash('Error creating account — see server log.', 'error')
                return render_template('register.html', title='Register', form=form)

            # immediate verification
            saved = User.query.filter_by(email=form.email.data).first()
            if not saved:
                flash('Failed to save user; please try again.', 'error')
                return render_template('register.html', title='Register', form=form)

            # Audit log: user created
            try:
                audit = AuditLog(action='User Registered', actor=saved.username or saved.email,
                                 details=json.dumps({'user_id': saved.id, 'email': saved.email, 'ip': request.remote_addr}))
                db.session.add(audit)
                db.session.commit()
            except Exception:
                db.session.rollback()

            flash('Account created. Please log in.', 'success')
            return redirect(url_for('login'))

        # show validation errors in console for POST
        if request.method == 'POST' and form.errors:
            import pprint
            print('Registration validation errors:', pprint.pformat(form.errors))

        return render_template('register.html', title='Register', form=form)

    @app.route('/logout')
    @login_required
    def logout():
        from models import AuditLog
        # Audit log: explicit logout
        try:
            audit = AuditLog(action='Logout', actor=getattr(current_user, 'username', str(current_user.get_id())),
                             details=json.dumps({'user_id': int(current_user.get_id()), 'ip': request.remote_addr}))
            db.session.add(audit)
            db.session.commit()
        except Exception:
            db.session.rollback()

        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('index'))

    @app.route('/order', methods=['GET', 'POST'])
    @login_required
    def order():
        from forms import OrderForm
        from models import Order, AuditLog, User, Product, Config
        import json

        form = OrderForm()

        lookup_data = {}
        
        products = db.session.query(Product).all()

        for p in products:
            p_type_lower = getattr(p, 'type', '').lower()
            key_prefix = p_type_lower + '_prices'
        
        # Ensure key_prefix exists in lookup_data
            if key_prefix not in lookup_data:
                lookup_data[key_prefix] = {}
            
        # Standardize the name (lowercase, replace space with underscore) for lookup keys
            lookup_key = p.name.lower().replace(' ', '_')
        
        # Use the 'value' field for price
            lookup_data[key_prefix][lookup_key] = p.value

        configs = db.session.query(Config).all()
        for c in configs:
            if c.name.upper() == 'VAT':
                try: lookup_data['VAT_RATE'] = float(c.value)
                except (ValueError, TypeError): lookup_data['VAT_RATE'] = 0.15 # Fallback
            elif c.name.upper() == 'MAXIMUM DRINKS':
                try: lookup_data['MAX_DRINKS'] = int(c.value)
                except (ValueError, TypeError): lookup_data['MAX_DRINKS'] = 10 # Fallback
        
        # Debug: log incoming POST/form data
        if request.method == 'POST':
            print("=== /order POST received ===")
            print("request.form keys:", list(request.form.keys()))
            print("request.form:", dict(request.form))
            try:
                print("raw body:", request.get_data(as_text=True)[:2000])
            except Exception:
                pass
            print("Client IP:", request.remote_addr)

        if form.validate_on_submit():
            try:
                # number validation
                n = int(form.number_of_milkshakes.data)
                if n < 1 or n > MAX_DRINKS:
                    flash(f'Number of drinks must be between 1 and {MAX_DRINKS}.', 'error')
                    return render_template('order.html', form=form)

                # parse pickup time (accepts datetime-local format)
                try:
                    pickup_iso = form.pickup_time.data
                    pickup_dt = datetime.fromisoformat(pickup_iso)
                except Exception:
                    flash('Invalid pickup time format.', 'error')
                    return render_template('order.html', form=form)

                # enforce 15 minute lead time (UTC)
                now = datetime.utcnow()
                if pickup_dt < now + timedelta(minutes=15):
                    flash('Pickup time must be at least 15 minutes from now.', 'error')
                    return render_template('order.html', form=form)

                # parse items JSON (from hidden field)
                try:
                    items = json.loads(form.order_data.data or "[]")
                except Exception:
                    flash('Invalid order data.', 'error')
                    return render_template('order.html', form=form)

                if len(items) != n:
                    flash('The number of milkshake entries does not match the number specified.', 'error')
                    return render_template('order.html', form=form)

                # Compute totals server-side. Prefer model helper if present.
                user = db.session.get(User, int(current_user.get_id()))
                if hasattr(Order, 'compute_totals_for_items'):
                    valid, errors, subtotal, vat, discount, total, items_with_prices = Order.compute_totals_for_items(items, user=user)
                    if not valid:
                        flash('Order data invalid: ' + '; '.join(errors), 'error')
                        return render_template('order.html', form=form)
                else:
                    # fallback: trust item.price values and compute simple totals
                    subtotal = 0.0
                    items_with_prices = []
                    for it in items:
                        price = float(it.get('price', 0) or 0)
                        subtotal += price
                        items_with_prices.append({**it, 'price': round(price, 2)})
                    discount = 0.0
                    # simple frequent-customer example
                    try:
                        if user and hasattr(user, 'completed_orders_count') and user.completed_orders_count() >= 3:
                            discount = 0.05 * subtotal
                    except Exception:
                        discount = 0.0
                    vat = round((subtotal - discount) * 0.15, 2)
                    total = round(subtotal - discount + vat, 2)
                    subtotal = round(subtotal, 2)

                # create and persist order (ensure user_id is int)
                order = Order(user_id=int(current_user.get_id()), pickup_time=pickup_dt, location=form.location.data)
                if hasattr(order, 'set_items'):
                    order.set_items(items_with_prices)
                else:
                    order.items = json.dumps(items_with_prices)
                # set totals if columns exist
                try: order.subtotal = subtotal
                except Exception: pass
                try: order.vat = vat
                except Exception: pass
                try: order.discount = discount
                except Exception: pass
                try: order.total = total
                except Exception: pass
                order.status = 'Pending Payment'

                db.session.add(order)
                db.session.commit()
                print(f"Saved order id={order.id} user_id={order.user_id} total={getattr(order,'total',None)}")

                # audit log entry
                try:
                    audit = AuditLog(action='Order Created', actor=getattr(current_user, 'username', str(current_user.get_id())),
                                     details=json.dumps({'order_id': order.id, 'total': getattr(order,'total',None)}))
                    db.session.add(audit)
                    db.session.commit()
                except Exception:
                    db.session.rollback()

                flash('Order created. Status: Pending Payment', 'success')
                return redirect(url_for('orders'))

            except Exception as e:
                db.session.rollback()
                import traceback
                traceback.print_exc()
                flash('Unexpected error while creating order; see server logs.', 'error')
                return render_template('order.html', form=form)

        # show validation errors on POST
        if request.method == 'POST' and form.errors:
            print("Form validation failed. errors:", form.errors)
            flash('Form validation failed: ' + str(form.errors), 'error')

        return render_template('order.html', form=form, lookup_data=lookup_data)

    # --- My Orders & Order Detail ---
    @app.route('/orders')
    @login_required
    def orders():
        from models import Order
        # show all orders for current user, newest first
        user_id = int(current_user.get_id())
        orders = db.session.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).all()
        return render_template('orders.html', orders=orders)

    @app.route('/orders/<int:order_id>')
    @login_required
    def order_detail(order_id):
        from models import Order
        order = db.session.get(Order, order_id)
        if not order or str(order.user_id) != str(current_user.get_id()):
            flash('Order not found or access denied.', 'error')
            return redirect(url_for('orders'))
        items = order.get_items()
        return render_template('order_detail.html', order=order, items=items)

    @app.route('/orders/<int:order_id>/receipt')
    @login_required
    def order_receipt(order_id):
        from models import Order
        order = db.session.get(Order, order_id)
        if not order or str(order.user_id) != str(current_user.get_id()):
            flash('Order not found or access denied.', 'error')
            return redirect(url_for('orders'))
        # Simple HTML receipt — you can expand to generate PDF or trigger email sending after payment
        return render_template('receipt.html', order=order)

    @app.route('/orders/<int:order_id>/pay', methods=['GET'])
    @login_required
    def order_pay(order_id):
        from models import Order
        from forms import PaymentForm
        order = db.session.get(Order, order_id)
        if not order or int(order.user_id) != int(current_user.get_id()):
            flash('Order not found or access denied.', 'error')
            return redirect(url_for('orders'))
        if getattr(order, 'status', '').lower() != 'pending payment':
            flash('Order is not pending payment.', 'info')
            return redirect(url_for('order_detail', order_id=order_id))
        form = PaymentForm()
        return render_template('payment.html', order=order, form=form)

    @app.route('/orders/<int:order_id>/pay/submit', methods=['POST'])
    @login_required
    def order_pay_submit(order_id):
        from models import Order, Payment
        from forms import PaymentForm
        import secrets

        form = PaymentForm()
        # validate CSRF and form submission
        if not form.validate_on_submit():
            flash('Payment form validation failed.', 'error')
            return redirect(url_for('order_pay', order_id=order_id))

        order = db.session.get(Order, order_id)
        if not order or int(order.user_id) != int(current_user.get_id()):
            flash('Order not found or access denied.', 'error')
            return redirect(url_for('orders'))
        if getattr(order, 'status', '').lower() != 'pending payment':
            flash('Order is not pending payment.', 'info')
            return redirect(url_for('order_detail', order_id=order_id))

        # create a Payment record in DB with a provider_ref token that simulates a gateway session
        provider_ref = secrets.token_urlsafe(24)
        payment = Payment(order_id=order.id, amount=getattr(order, 'total', 0.0),
                          provider='simulated_gateway', provider_ref=provider_ref, status='Pending')
        db.session.add(payment)
        db.session.commit()
        return render_template('payment_simulator.html', payment=payment, order=order)

    # Webhook / callback endpoint (simulated). This would be called by the payment provider.
    @app.route('/payments/webhook', methods=['POST'])
    def payments_webhook():
        from models import Payment, Order, AuditLog
        import json
        # Expect JSON payload: { provider_ref: "...", status: "Success" | "Failed", provider_ref_info: "..." }
        payload = request.get_json(silent=True) or {}
        pr = payload.get('provider_ref')
        new_status = payload.get('status')
        if not pr or not new_status:
            return ('missing provider_ref or status', 400)
        payment = db.session.query(Payment).filter_by(provider_ref=pr).first()
        if not payment:
            return ('payment not found', 404)
        # Accept only certain statuses
        if new_status not in ('Success', 'Failed'):
            return ('invalid status', 400)
        try:
            payment.status = new_status
            db.session.add(payment)
            # update order status on success
            order = db.session.get(Order, payment.order_id)
            if new_status == 'Success' and order:
                order.status = 'Confirmed'
                db.session.add(order)
                # create audit log
                audit = AuditLog(action='Payment Received', actor='system', details=json.dumps({'order_id': order.id, 'payment_id': payment.id, 'amount': payment.amount}))
                db.session.add(audit)
                # simulate sending receipt email (replace with real mailer later)
                user_email = getattr(order.user, 'email', None) if hasattr(order, 'user') else None
                print(f"[SIMULATED EMAIL] To: {user_email} - Subject: Payment receipt for Order {order.id} - Amount: R{payment.amount}")
            db.session.commit()
            return ('ok', 200)
        except Exception as e:
            db.session.rollback()
            print('Webhook processing error:', e)
            return ('error', 500)
        
    # ADDED: Manager Dashboard/Lookup List
    @app.route('/admin')
    @login_required
    @manager_required
    def admin_dashboard():
        from models import Product, Config
        # Fetch all lookup data
        products = db.session.query(Product).order_by(Product.type, Product.name).all()
        configs = db.session.query(Config).all()
        
        # Merge for unified display
        lookup_items = products + configs
        
        return render_template('admin_dashboard.html', items=lookup_items)
    
# ADDED: Create/Edit Lookup Item (Product or Config)
    @app.route('/admin/lookup/edit', methods=['GET', 'POST'])
    @app.route('/admin/lookup/edit/<int:item_id>', methods=['GET', 'POST'])
    @login_required
    @manager_required
    def admin_lookup_edit(item_id=None):
        from models import Product, Config
        from forms import LookupForm
        
        item = None
        form = LookupForm()
        
        if item_id:
            # Determine if it's a Product or a Config based on its structure/ID. 
            # For simplicity, we assume Product has item_id > 100, Config <= 100, 
            # or just try Product first.
            item = db.session.get(Product, item_id)
            if not item:
                item = db.session.get(Config, item_id) # Example: If item_id mapping is complex
                
            if not item:
                flash('Item not found.', 'error')
                return redirect(url_for('admin_dashboard'))

        if form.validate_on_submit():
            try:
                if form.type.data == 'Config':
                    # Handle Config model update/creation
                    # Use unique name to fetch Config item
                    config_item = db.session.query(Config).filter_by(name=form.name.data).first() 
                    if not config_item:
                        config_item = Config()
                    config_item.name = form.name.data
                    config_item.type = form.type.data
                    config_item.value = form.value.data
                    db.session.add(config_item)
                    
                else:
                    # Handle Product model update/creation (Flavour/Topping/Consistency)
                    if not item or not hasattr(item, 'type') or item.type == 'Config':
                        # Create new Product item or overwrite existing non-Config item
                        item = Product()
                    item.name = form.name.data
                    item.type = form.type.data
                    item.value = float(form.value.data) # Value is the price
                    item.price = float(form.value.data) 
                    item.description = form.description.data
                    db.session.add(item)

                db.session.commit()
                flash(f'Item "{item.name}" saved successfully.', 'success')
                return redirect(url_for('admin_dashboard'))

            except Exception as e:
                db.session.rollback()
                flash(f'Error saving item: {e}', 'error')
                return render_template('admin_lookup_edit.html', form=form, item=item)

        elif item:
            # Populate form for editing existing item
            form.name.data = item.name
            form.type.data = item.type
            form.value.data = getattr(item, 'value', '')
            form.description.data = getattr(item, 'description', '')

        return render_template('admin_lookup_edit.html', form=form, item=item)
    
    # Management Reports Dashboard
    @app.route('/admin/reports')
    @login_required
    @manager_required
    def admin_reports():
        from models import Order, AuditLog
        from datetime import date, timedelta
        
        # --- Filtering Logic (Simplified for initial implementation) ---
        from extensions import db
        from sqlalchemy import func

        # Determine date range from query parameters
        today = date.today()
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        
        # Default to the last 7 days if no dates are provided
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1) # Include the end day
            except ValueError:
                start_date = today - timedelta(days=7)
                end_date = today + timedelta(days=1)
        else:
            start_date = today - timedelta(days=7)
            end_date = today + timedelta(days=1)
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = (end_date - timedelta(days=1)).strftime('%Y-%m-%d')

        # --- Data Fetching ---
        
        # 1. Fetch Orders within the date range
        orders = db.session.query(Order).filter(
            Order.created_at >= start_date,
            Order.created_at < end_date
        ).order_by(Order.created_at.desc()).all()
        
        # 2. Fetch Audit Logs within the date range
        audit_logs = db.session.query(AuditLog).filter(
            AuditLog.created_at >= start_date,
            AuditLog.created_at < end_date
        ).order_by(AuditLog.created_at.desc()).all()

        # 2. Trends Aggregation (Orders grouped by time periods)
        
        # a. Weekly Orders (Group by day of the week)
        # SQLite's strftime('%w', ...) returns 0=Sun, 1=Mon, ..., 6=Sat.
        weekly_orders_q = db.session.query(
            func.count(Order.id),
            func.strftime('%w', Order.created_at)
        ).filter(
            Order.created_at >= start_date,
            Order.created_at < end_date
        ).group_by(
            func.strftime('%w', Order.created_at)
        ).all()
        
        # b. Monthly Orders (Group by month number 01-12)
        monthly_orders_q = db.session.query(
            func.count(Order.id),
            func.strftime('%m', Order.created_at)
        ).filter(
            Order.created_at >= start_date,
            Order.created_at < end_date
        ).group_by(
            func.strftime('%m', Order.created_at)
        ).all()
        
        # c. Yearly Growth (Group by year YYYY)
        yearly_growth_q = db.session.query(
            func.count(Order.id),
            func.strftime('%Y', Order.created_at)
        ).group_by(
            func.strftime('%Y', Order.created_at)
        ).order_by(
            func.strftime('%Y', Order.created_at)
        ).all()

        # --- FIX: Convert Query Results to Lists ---
        # Explicitly convert the list of SQLAlchemy Row/Result objects into lists of lists/tuples
        weekly_trends = [list(r) for r in weekly_orders_q]
        monthly_trends = [list(r) for r in monthly_orders_q]
        yearly_trends = [list(r) for r in yearly_growth_q]
        # -------------------------------------------
        
        # Simplify order items for the table display (get the first item only)
        for order in orders:
            items = order.get_items()
            if items:
                order.first_item_flavour = items[0].get('flavour', 'N/A').title()
                order.first_item_topping = items[0].get('topping', 'N/A').title()
                order.first_item_thick = items[0].get('thick', 'N/A').title()
            else:
                order.first_item_flavour = 'Empty'
                order.first_item_topping = 'Empty'
                order.first_item_thick = 'Empty'
                
        context = {
            'orders': orders,
            'audit_logs': audit_logs,
            'trends_data': {
                'weekly': weekly_trends, # <-- Use converted list
                'monthly': monthly_trends, # <-- Use converted list
                'yearly': yearly_trends, # <-- Use converted list
            },
            'start_date_str': start_date_str,
            'end_date_str': end_date_str,
            'total_orders': len(orders),
            'date_filter_applied': start_date_str != (today - timedelta(days=7)).strftime('%Y-%m-%d')
        }
        
        return render_template('admin_reports.html', **context)

    # --- Database Initialization ---
    with app.app_context():
        # Import models so SQLAlchemy knows about them
        from models import User, Product, Order, AuditLog 
        
        # Create database tables if they don't exist
        db.create_all()
        print("Database tables created or already exist.")

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', debug=True)
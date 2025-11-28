from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from extensions import db, bcrypt
import json



VAT_RATE = 0.15  # 15%

# Simple User model
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    role = Column(String(20), default='client', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def set_password(self, password: str):
        # bcrypt.generate_password_hash returns bytes; store decoded string
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

    def completed_orders_count(self):
        # consider all non-pending payment orders as past purchases
        return sum(1 for o in getattr(self, 'orders', []) if o.status != 'Pending Payment')
    @property
    def is_manager(self):
        return self.role == 'manager'

class Config(db.Model):
    __tablename__ = 'config'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    type = Column(String(50), nullable=False) # e.g., 'Config'
    value = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Config {self.name}: {self.value}>'

# Minimal Product, Order, AuditLog placeholders
class Product(db.Model):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    type = Column(String(50), nullable=False)
    price = Column(Float, nullable=False)
    value = Column(Float, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.type}: {self.name} R{self.value}>'

class Order(db.Model):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    pickup_time = Column(DateTime, nullable=True)
    location = Column(String(255), nullable=True)
    items = Column(Text, nullable=False, default='[]')  # JSON string of items
    total = Column(Float, default=0.0)
    subtotal = Column(Float, default=0.0)
    vat = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    status = Column(String(50), default='Pending Payment')
    user = relationship('User', backref='orders')

    def set_items(self, items_list):
        self.items = json.dumps(items_list)

    def get_items(self):
        try:
            return json.loads(self.items or "[]")
        except Exception:
            return []
        
    @staticmethod
    def _get_lookup_cache():
        """Fetches and caches prices/configs from the database."""
        # This is a rudimentary cache; a real app might use Flask-Caching.
        cache = {
            'prices': {}, # Key: "type_name", Value: price
            'vat_rate': 0.15
        }
        
        # Avoid circular import issues by importing models locally
        from models import Product, Config
        
        # 1. Load Product Prices
        products = db.session.query(Product).all()
        for p in products:
            # Create a unique key like "flavour_vanilla"
            key = f"{p.type.lower()}_{p.name.lower().replace(' ', '_')}"
            # Use the new 'value' field for price
            cache['prices'][key] = getattr(p, 'value', 0.0)
            
        # 2. Load Config Settings
        configs = db.session.query(Config).all()
        for c in configs:
            if c.name.upper() == 'VAT':
                try:
                    cache['vat_rate'] = float(c.value)
                except (ValueError, TypeError):
                    pass # Default to 0.15 if parsing fails
        
        return cache

    @staticmethod
    def compute_totals_for_items(items, user=None):
        """
        Validate items and compute subtotal, vat, discount, total using DB lookups.
        """
        # Load the dynamic prices and configs
        lookup_cache = Order._get_lookup_cache()
        
        errors = []
        subtotal = 0.0
        items_out = []
        
        # --- 1. Validate items and compute price ---
        for idx, it in enumerate(items, start=1):
            flavour = it.get('flavour') or ''
            thick = it.get('thick') or ''
            topping = it.get('topping') or ''
            
            # Construct lookup keys based on submitted item names
            fkey = f"flavour_{flavour}"
            ckey = f"consistency_{thick}"
            tkey = f"topping_{topping}"
            
            # --- Perform Price Lookup from Cache ---
            fprice = lookup_cache['prices'].get(fkey, 0.0)
            cprice = lookup_cache['prices'].get(ckey, 0.0)
            tprice = lookup_cache['prices'].get(tkey, 0.0)

            # Validation checks
            if not flavour or fprice == 0.0:
                errors.append(f'Item {idx}: invalid flavour: {flavour}')
            if not thick or cprice == 0.0:
                errors.append(f'Item {idx}: invalid consistency: {thick}')
            if topping is None or tprice == 0.0: # Check for None or missing topping, assumes 'none' is a valid topping with price 0
                 # Only error if topping is completely missing and it's not the 'none' entry
                 if topping is None or (topping.lower() != 'none' and tprice == 0.0):
                     errors.append(f'Item {idx}: invalid topping: {topping}')

            price = float(fprice) + float(cprice) + float(tprice)
            subtotal += price
            items_out.append({**it, 'price': price})
            
        # --- 2. Calculate Discount, VAT, Total ---
        
        # frequent customer discount policy:
        discount = 0.0
        if user is not None:
            try:
                completed = user.completed_orders_count()
                # example policy: 5% discount if user has 3+ completed orders
                if completed >= 3:
                    discount = 0.05 * subtotal
            except Exception:
                discount = 0.0
        
        vat_rate = lookup_cache['vat_rate']
        vat = (subtotal - discount) * vat_rate
        total = subtotal - discount + vat
        valid = len(errors) == 0
        
        return valid, errors, round(subtotal,2), round(vat,2), round(discount,2), round(total,2), items_out

    def __repr__(self):
        return f'<Order {self.id} user={self.user_id} total={self.total} status={self.status}>'

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = Column(Integer, primary_key=True)
    action = Column(String(255))
    actor = Column(String(120))
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Payment(db.Model):
    __tablename__ = 'payments'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    amount = Column(Float, nullable=False)
    provider = Column(String(80), nullable=False, default='simulated_gateway')
    provider_ref = Column(String(128), nullable=True, unique=True)
    status = Column(String(30), nullable=False, default='Pending')  # Pending, Success, Failed
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Payment {self.id} order={self.order_id} amount={self.amount} status={self.status}>'
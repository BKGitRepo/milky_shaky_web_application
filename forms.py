from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo
from wtforms import IntegerField, HiddenField
from wtforms.validators import NumberRange, Optional
from wtforms import IntegerField, HiddenField, SelectField
from wtforms.validators import NumberRange, Optional, InputRequired

class RegistrationForm(FlaskForm):
    username = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    submit = SubmitField('Get Started')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Log In')

class OrderForm(FlaskForm):
    number_of_milkshakes = IntegerField('Number of Milkshakes', validators=[DataRequired(), NumberRange(min=1, max=20)])
    pickup_time = StringField('Pickup time', validators=[DataRequired()])  # expects HTML datetime-local value
    location = StringField('Pickup location', validators=[DataRequired(), Length(max=255)])
    order_data = HiddenField('Order data (JSON)', validators=[DataRequired()])  # JSON payload of items
    submit = SubmitField('Continue')

class PaymentForm(FlaskForm):
    submit = SubmitField('Pay Now (Simulated)')

# ADDED: Form for managing lookup items (Products and Configs)
class LookupForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=120)])
    type = SelectField('Type', choices=[
        ('Flavour', 'Flavour'), 
        ('Topping', 'Topping'), 
        ('Consistency', 'Consistency'), 
        ('Config', 'Configuration')
    ], validators=[InputRequired()])
    value = StringField('Value', validators=[DataRequired(), Length(max=255)]) # Used for price or config value (e.g., 15% or 10)
    description = StringField('Description (optional)', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Save')
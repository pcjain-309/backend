from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy.orm import relationship
from io import StringIO, BytesIO
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    JWTManager, jwt_required, create_access_token,
    get_jwt_identity
)
from flask import send_from_directory
from werkzeug.utils import secure_filename
import os
from io import TextIOWrapper
import csv
from datetime import datetime
from collections import defaultdict


app = Flask(__name__)
CORS(app)



UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Be2d542b6b43G4f3D*4AEF*cAAF1AdEf@monorail.proxy.rlwy.net:29117/railway'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_here'  
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Setup the Flask-JWT-Extended extension
app.config['JWT_SECRET_KEY'] = 'secret'  
jwt = JWTManager(app)

db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(1000), nullable=False)
    user_type = db.Column(db.String(10))  # 'investor' or 'founder'
    name = db.Column(db.String(80))
    company_name = db.Column(db.String(100))
    business_description = db.Column(db.String(500))
    revenue = db.Column(db.String(50))
    startup_interests = db.relationship('InvestorInterest', foreign_keys='InvestorInterest.investor_id', back_populates='investor')

class InvestorInterest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    startup_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    investor = db.relationship('User', back_populates='startup_interests', foreign_keys=[investor_id])
    startup = db.relationship('User', back_populates='startup_interests', foreign_keys=[startup_id])

class SalesData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    order_date = db.Column(db.Date)
    sales = db.Column(db.Float)

with app.app_context():
    db.create_all()






@app.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()

    print(data, "Hello")

    if 'email' not in data or 'password' not in data:
        return jsonify({'error': 'Invalid registration data'}), 400

    email = data['email']
    password = generate_password_hash(data['password'], method='pbkdf2:sha1')

    # Check if the user already exists
    existing_user = User.query.filter_by(email=email).first()

    user_type = data.get('userType')
    new_user = User(
        email=email,
        password=password,
        user_type=user_type,
    )

    if user_type == 'investor':
        new_user.name = data.get('name')
    elif user_type == 'founder':
        new_user.company_name = data.get('companyName')
        new_user.business_description = data.get('description')
        new_user.revenue = data.get('revenue')

    print("Helllo")
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'Registration successful.'})


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    print(email, password)
    print(user.email, user.password)
    print(check_password_hash(user.password, password))
    print(user is None or not check_password_hash(user.password, password))
    print(user is None)
    print(not check_password_hash(user.password, password) )
    if user is None or not check_password_hash(user.password, password):
        return jsonify({'error': 'Invalid email or password.'})

    print("Hello")
    access_token = create_access_token(identity=user.id)
    print(access_token)
    return jsonify(access_token=access_token)

@app.route('/protected', methods=['GET'])
@jwt_required
def protected():
    current_user = get_jwt_identity()
    return jsonify(logged_in_as=current_user), 200


# Add a new endpoint to get the user type
@app.route('/user-info', methods=['GET'])
@jwt_required()
def get_user_info():
    user_id = get_jwt_identity()
    print("Hello", user_id)
    user = User.query.filter_by(id=user_id).first()

    if user:
        return jsonify({'userType': user.user_type, 
                        'userId': user.id})
    else:
        return jsonify({'error': 'User not found'})

@app.route('/isRegistered/<email>', methods=['GET'])
def is_registered(email):

    user = User.query.filter_by(email=email).first()

    is_registered = (user is not None)

    return jsonify({'isRegistered': is_registered})


# Endpoint to get interested investors for a startup
@app.route('/interested-investors/<startup_id>', methods=['GET'])
@jwt_required()
def get_interested_investors(startup_id):
    startup = User.query.filter_by(id=startup_id, user_type='founder').first()

    if not startup:
        return jsonify({'error': 'Startup not found'}), 404

    interested_investors = User.query.filter(User.user_type == 'investor')\
                                     .join(InvestorInterest, User.id == InvestorInterest.investor_id)\
                                     .filter(InvestorInterest.startup_id == startup_id).all()

    interested_investors_data = [{'id': investor.id, 'name': investor.name} for investor in interested_investors]


    return jsonify({'interestedInvestors': interested_investors_data}), 200



# Endpoint to get all startups
@app.route('/allStartups', methods=['GET'])
@jwt_required()
def get_all_startups():
    print("Inside get all startups")
    startups = User.query.filter_by(user_type='founder').all()
    print(startups)
    startups_data = [
        {
            'id': startup.id,
            'name': startup.company_name,
            'revenue': startup.revenue,
            'businessDescription': startup.business_description,
        }
        for startup in startups
    ]
    print(startups_data)
    return jsonify({'startups': startups_data}), 200

#  Endpoint to show interest in a startup
@app.route('/showInterest/<startup_id>', methods=['POST'])
@jwt_required()
def show_interest(startup_id):
    investor_id = get_jwt_identity()
    print(investor_id)
    existing_interest = InvestorInterest.query.filter_by(investor_id=investor_id, startup_id=startup_id).first()

    if existing_interest:
        return jsonify({'error': 'Investor already interested in this startup'}), 400

    new_interest = InvestorInterest(investor_id=investor_id, startup_id=startup_id)
    db.session.add(new_interest)
    db.session.commit()

    return jsonify({'message': 'Interest shown successfully'}), 200

# Endpoint to remove interest in a startup
@app.route('/removeInterest/<startup_id>', methods=['DELETE'])
@jwt_required()
def remove_interest(startup_id):
    investor_id = get_jwt_identity()

    interest_to_remove = InvestorInterest.query.filter_by(investor_id=investor_id, startup_id=startup_id).first()

    if not interest_to_remove:
        return jsonify({'error': 'Investor not interested in this startup'}), 400

    db.session.delete(interest_to_remove)
    db.session.commit()

    return jsonify({'message': 'Interest removed successfully'}), 200


@app.route('/check-interest/<startup_id>', methods=['GET'])
@jwt_required()
def check_interest(startup_id):
    investor_id = get_jwt_identity()

    # Check if the investor is interested in the specified startup
    is_interested = InvestorInterest.query.filter_by(investor_id=investor_id, startup_id=startup_id).first() is not None

    return jsonify({'isInterested': is_interested}), 200

@app.route('/upload-sales/<user_id>', methods=['POST'])
@jwt_required()
def upload_sales_data(user_id):
    try:
        print("Inside upload_sales")
        user_id = get_jwt_identity()
        print(user_id, "Hello")
        file = request.files['sales_data']

        if file.filename.endswith('.csv'):
            # Read CSV file
            print("Ins")
            csv_reader = csv.reader(TextIOWrapper(file.stream, 'utf-8'))
            header = next(csv_reader)  # Skip the header

            # Assuming your CSV has 'Order Date' and 'Sales' columns
            order_date_index = header.index('Order Date')
            sales_index = header.index('Sales')
            print("Order Date", order_date_index, sales_index)
            for row in csv_reader:
                print(row)
                order_date_str = row[order_date_index].strip()
                sales_str = row[sales_index].strip()
                print("Sale Date", sales_str, order_date_str)
                order_date = datetime.strptime(order_date_str, '%m/%d/%Y').date()

                sales = float(sales_str.replace(',', ''))

                print(order_date, sales)
                # Store data in the database
                sales_data = SalesData(user_id=user_id, order_date=order_date, sales=sales) 
                print(sales_data)
                db.session.add(sales_data)

            db.session.commit()

            return jsonify({'message': 'Sales data uploaded successfully'}), 200
        else:
            return jsonify({'error': 'Invalid file format. Please upload a CSV file.'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate-sales-chart', methods=['POST'])
@jwt_required()
def generate_sales_chart():
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        # Retrieve sales data based on the selected date range
        start_date = datetime.strptime(data['startDate'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['endDate'], '%Y-%m-%d').date()

        print(start_date, end_date)

        sales_data = SalesData.query.filter_by(user_id=user_id) \
                                   .filter(SalesData.order_date.between(start_date, end_date)) \
                                   .all()

        print(sales_data)
        # Calculate daily total sales
        daily_totals = defaultdict(float)
        for sale in sales_data:
            daily_totals[sale.order_date] += sale.sales

        # Extract dates and total sales from the calculated daily totals
        dates = list(daily_totals.keys())
        total_sales = list(daily_totals.values())

        # Convert dates to ordinal representation
        date_ordinals = [date.toordinal() for date in dates]

        # Generate sales chart using matplotlib in non-interactive mode
        plt.switch_backend('agg')  # Use non-interactive backend
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(date_ordinals, total_sales, marker='o', linestyle='-', color='blue')
        ax.set_title('Daily Total Sales Chart')
        ax.set_xlabel('Date')
        ax.set_ylabel('Total Sales')
        ax.set_xticks(date_ordinals)  # Set tick locations to be the original dates
        ax.set_xticklabels(dates)  # Set tick labels to be the original dates
        ax.tick_params(axis='x', rotation=45)
        fig.tight_layout()

        # Save the chart image as BytesIO
        chart_image = BytesIO()
        fig.savefig(chart_image, format='png')
        plt.close(fig)  # Close the figure

        # Send the chart image to the frontend
        chart_image.seek(0)
        return send_file(chart_image, mimetype='image/png')

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)

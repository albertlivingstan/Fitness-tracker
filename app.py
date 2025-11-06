from flask import *
from pymongo import MongoClient
import random
import string
import plotly.graph_objs as go
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from bson import ObjectId
from pymongo import MongoClient
from twilio.rest import Client
from flask import Flask, request, redirect, url_for

import datetime
import re
from flask_mail import *

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

with open('config.json') as f:
    params = json.load(f)['param']

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017") 
db = client['health_tracker']
users_collection = db['users']
activity_collection = db['activity']
exercise_collection = db['exercise']
nutrition_collection = db['nutrition']
goals_collection = db['goals']
progress_collection = db['progress']
social_collection = db['social']
playlist_collection = db['playlist']
recommendations_collection = db['recommendations']
goals_history_collection = db['goals_history']

# Twilio configuration
TWILIO_ACCOUNT_SID = 'AC7fc641ee1014b3b1a2b09044390cd1f7'
TWILIO_AUTH_TOKEN = '3f552ba876a7a0be8af905f06007e39b'

TWILIO_PHONE_NUMBER = '+15078733406'



# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Utility functions
def send_otp(phone, otp):
    try:
        # Clean and format phone number
        phone = phone.strip().replace(" ", "").replace("-", "")
        
        # Validate and format for Indian numbers
        if not phone.startswith('+'):
            if phone.startswith('0'):
                phone = '+91' + phone[1:]
            elif len(phone) == 10 and phone.isdigit():
                phone = '+91' + phone
            else:
                raise ValueError("Invalid phone number format. Must be 10 digits for India.")
        
        # Verify E.164 format
        if not re.match(r'^\+[1-9]\d{7,14}$', phone):
            raise ValueError("Phone number must be in valid E.164 format.")
        
        # Send SMS via Twilio
        message = twilio_client.messages.create(
            body=f'Your Health Tracker OTP is: {otp}. This OTP is valid for 10 minutes.',
            from_=TWILIO_PHONE_NUMBER,
            to=phone
        )
        
        print(f"✅ OTP sent successfully to {phone}. Message SID: {message.sid}")
        flash('OTP sent successfully via SMS.', 'success')
        return True
        
    except Exception as e:
        print(f"❌ Twilio error: {str(e)}")
        flash(f'Failed to send OTP via SMS: {str(e)}', 'error')
        return False

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_email(receiver_email, otp):
    try:
        # Try to login and send email
        server=smtplib.SMTP('smtp.gmail.com',587)
        #adding TLS security 
        server.starttls()
        #get your app password of gmail ----as directed in the video
        sender_email = params['gmail-user']
        password= params['gmail-password']
        server.login(sender_email,password)

        #send
        server.sendmail(sender_email, receiver_email, otp)
        server.quit()

        flash('OTP sent successfully via email.', 'success')
    except Exception as e:
        flash(f'Failed to send OTP via email: {str(e)}', 'error')
def send_exercise_call(phone, reminder_message="Hey there! It’s time to rise and move toward your goals. Remember, every small step you take today brings you closer to the stronger, healthier version of yourself. Don’t wait for motivation — create it with action. You’ve got the power, the discipline, and the drive to make today count. Now, take a deep breath, smile, and let’s get moving — your best self is waiting!"):


    try:
        # Phone format normalization
        phone = phone.strip().replace(" ", "").replace("-", "")
        if not phone.startswith('+'):
            if phone.startswith('0'):
                phone = '+91' + phone[1:]
            elif len(phone) == 10 and phone.isdigit():
                phone = '+91' + phone
            else:
                raise ValueError("Invalid phone number format. Must be 10 digits for India.")
        
        # 1. Send SMS notification before the call
        notification_message = "You will receive a call shortly for your exercise reminder."
        try:
            twilio_client.messages.create(
                body=notification_message,
                from_=TWILIO_PHONE_NUMBER,
                to=phone
            )
            print(f"✅ Notification SMS sent to {phone}")
        except Exception as sms_error:
            print(f"❌ Failed to send SMS notification: {sms_error}")

        # 2. Send the voice call as reminder
        from twilio.twiml.voice_response import VoiceResponse
        response = VoiceResponse()
        response.say(reminder_message, voice="alice", language="en-IN")  # Indian accent

        call = twilio_client.calls.create(
            twiml=str(response),
            to=phone,
            from_=TWILIO_PHONE_NUMBER
        )
        print(f"✅ Reminder call sent successfully to {phone}. Call SID: {call.sid}")
        flash('Reminder call sent successfully.', 'success')
        return True
    except Exception as e:
        print(f"❌ Twilio call error: {str(e)}")
        flash(f'Failed to place call: {str(e)}', 'error')
        return False


def calculate_calories(user_data):
    # Harris-Benedict equation to calculate BMR
    if user_data['gender'] == 'male':
        bmr = 88.362 + (13.397 * user_data['weight']) + (4.799 * user_data['height']) - (5.677 * user_data['age'])
    elif user_data['gender'] == 'female':
        bmr = 447.593 + (9.247 * user_data['weight']) + (3.098 * user_data['height']) - (4.330 * user_data['age'])
    else:
        # Handle other gender options if needed
        bmr = 0

    # Adjust BMR based on activity level to estimate TDEE
    activity_level_multiplier = {
        'sedentary': 1.2,
        'lightly_active': 1.375,
        'moderately_active': 1.55,
        'very_active': 1.725,
        'extra_active': 1.9
    }

    if user_data['activity_level'] in activity_level_multiplier:
        tdee = bmr * activity_level_multiplier[user_data['activity_level']]
    else:
        # Default to sedentary if activity level is not provided
        tdee = bmr * activity_level_multiplier['sedentary']

    return tdee

def generate_recommendations(user_data):
    today = datetime.date.today()
    year, month, date = map(int, user_data['dob'].split('-'))
    age = today.year - year
    recommendations = []

    # Age-based recommendations
    if age < 30:
        recommendations.append("Consider incorporating more high-intensity workouts for better metabolism.")
    elif age >= 30 and user_data['age'] < 50:
        recommendations.append("Focus on maintaining a balanced exercise routine including cardio and strength training.")
    else:
        recommendations.append("Include more flexibility and mobility exercises to maintain joint health.")

    # Weight-related recommendations
    if user_data['weight'] > user_data['ideal_weight']:
        recommendations.append("Try to focus on a calorie deficit diet to reach your ideal weight.")
    elif user_data['weight'] < user_data['ideal_weight']:
        recommendations.append("Ensure you are consuming enough calories to maintain your ideal weight.")
    else:
        recommendations.append("Maintain your current weight by balancing your calorie intake with your energy expenditure.")

    # Activity level recommendations
    if user_data['activity_level'] == 'sedentary':
        recommendations.append("Consider increasing your daily activity level by taking short walks or incorporating light exercises.")
    elif user_data['activity_level'] == 'moderately_active':
        recommendations.append("Continue your current activity level but ensure to maintain a balanced diet to support your lifestyle.")
    elif user_data['activity_level'] == 'very_active':
        recommendations.append("Ensure you are consuming enough calories to fuel your high activity level and consider adding more protein to your diet.")

    # Dietary preferences recommendations
    if 'vegetarian' in user_data['dietary_preferences']:
        recommendations.append("Ensure you are getting enough protein from plant-based sources such as beans, lentils, and tofu.")
    if 'vegan' in user_data['dietary_preferences']:
        recommendations.append("Consider supplementing with vitamin B12 and omega-3 fatty acids as they may be lacking in a vegan diet.")

    # Health condition recommendations (hypothetical examples)
    if 'diabetes' in user_data['health_conditions']:
        recommendations.append("Monitor your carbohydrate intake and aim for balanced meals to manage blood sugar levels.")
    if 'high_blood_pressure' in user_data['health_conditions']:
        recommendations.append("Limit your sodium intake and focus on consuming whole foods rich in potassium and magnesium.")

    return recommendations


# Routes
# Route to render home page
@app.route('/')
def home():
    return render_template('home.html')


@app.route('/reminder_call', methods=['POST'])
def reminder_call():
    if 'user' in session:
        user_data = users_collection.find_one({'_id': ObjectId(session['user'])})
        phone = user_data.get('phone')
        if phone:
            send_exercise_call(phone)
            return redirect('/dashboard')
        flash('Phone number not found.', 'error')
    else:
        flash('Please login first.', 'error')
    return redirect('/login')

# Route to handle forgot password request
@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user_data = users_collection.find_one({'email': email})
        if user_data:
            otp = generate_otp()
            users_collection.update_one({'_id': user_data['_id']}, {'$set': {'otp': otp}})
            # Send OTP via Twilio
            #if send_otp(user_data['phone'], otp):
                #flash('OTP sent successfully via email.', 'success')
                #return redirect(url_for('verify_otp', email=email))
            # Send OTP via email
            send_email(email, otp)
            return render_template('set_password.html')
        else:
            return "Email not found. Please enter a valid email address.", 404
    else:
        return render_template('forgot.html')

@app.route('/dashboard')
def dashboard():
    if 'user' in session:
        user_id = ObjectId(session['user'])  # Convert string to ObjectId
        user_data = users_collection.find_one({'_id': user_id})
        
        # Fetch progress data
        progress_data = {
            'activity': list(activity_collection.find({'user_id': user_data['_id']})),
            'exercise': list(exercise_collection.find({'user_id': user_data['_id']})),
            'nutrition': list(nutrition_collection.find({'user_id': user_data['_id']})),
            'goals': list(goals_collection.find({'user_id': user_data['_id']}))
        }

        return render_template('dashboard.html', user=user_data, progress=progress_data)
    else:
        return redirect('/login')
    
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        dob = request.form['dob']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        activity_level = request.form['activity_level']
        dietary_preferences = request.form.getlist('dietary_preferences')
        health_conditions = request.form.getlist('health_conditions')
        weight = float(request.form['weight'])
        height = float(request.form['height'])
        ideal_weight = float(request.form['ideal_weight'])

        if password != confirm_password:
            return render_template('signup.html', message='Passwords do not match')

        otp = generate_otp()

        user_data = {
            'name': name,
            'phone': phone,
            'dob': dob,
            'email': email,
            'password': password,
            'otp': otp,
            'activity_level': activity_level,
            'dietary_preferences': dietary_preferences,
            'health_conditions': health_conditions,
            'weight': weight,
            'height': height,
            'ideal_weight': ideal_weight
        }
        users_collection.insert_one(user_data)

        send_otp(phone, otp)
    
        send_email(email, otp)

        flash('Please verify your phone number using the OTP sent to your phone.', 'success')
        return redirect('/verify')

    return render_template('signup.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        otp_entered = request.form['otp']
        user_data = users_collection.find_one({'otp': otp_entered})
        if user_data:
            session['user'] = str(user_data['_id'])  # Convert ObjectId to string
            users_collection.update_one({'_id': user_data['_id']}, {'$unset': {'otp': ''}})
            flash('Verification successful. Welcome!', 'success')
            return redirect('/dashboard')
        else:
            flash('Invalid OTP. Please try again.', 'error')
            return render_template('verify.html')

    return render_template('verify.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' not in session:
        if request.method == 'POST':
            email = request.form['email']
            password = request.form['password']
            user_data = users_collection.find_one({'email': email, 'password': password})
            if user_data:
                session['user'] = str(user_data['_id'])  # Convert ObjectId to string
                flash('Login successful. Welcome back!', 'success')
                return redirect('/dashboard')  # Redirect to dashboard.html upon successful login
            else:
                flash('Invalid email or password. Please try again.', 'error')
                return render_template('login.html')

        return render_template('login.html')
    else:
        return redirect('/dashboard')

@app.route('/developers')
def developers():
    return render_template('developers.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out successfully.', 'success')
    return redirect('/')

@app.route('/activity', methods=['GET', 'POST'])
def activity():
    if 'user' in session:
        if request.method == 'POST':
            activity_data = request.form.to_dict()
            activity_data['user_id'] = ObjectId(session['user'])  # Convert string to ObjectId
            activity_collection.insert_one(activity_data)
            flash('Activity logged successfully.', 'success')
            return redirect('/dashboard')
        else:
            return render_template('activity.html')
    else:
        return redirect('/login')

@app.route('/exercise', methods=['GET', 'POST'])
def exercise():
    if 'user' in session:
        if request.method == 'POST':
            exercise_data = request.form.to_dict()
            exercise_data['user_id'] = ObjectId(session['user'])  # Convert string to ObjectId
            exercise_collection.insert_one(exercise_data)
            flash('Exercise logged successfully.', 'success')
            return redirect('/dashboard')
        else:
            return render_template('exercise.html')
    else:
        return redirect('/login')

@app.route('/nutrition', methods=['GET', 'POST'])
def nutrition():
    if 'user' in session:
        if request.method == 'POST':
            nutrition_data = request.form.to_dict()
            nutrition_data['user_id'] = ObjectId(session['user'])  # Convert string to ObjectId
            nutrition_collection.insert_one(nutrition_data)
            flash('Nutrition logged successfully.', 'success')
            return redirect('/dashboard')
        else:
            return render_template('nutrition.html')
    else:
        return redirect('/login')
@app.route('/visualize_progress')
def visualize_progress():
    if 'user' in session:
        user_id = ObjectId(session['user'])
        # Fetch progress data from the database
        progress_entries = list(progress_collection.find({'user_id': user_id}))
        # Pass the progress entries (or build stats/chart data) to the template
        return render_template('visualize_progress.html', progress=progress_entries)
    else:
        return redirect('/login')




@app.route('/goals', methods=['GET', 'POST'])
def goals():
    if 'user' in session:
        user_id = ObjectId(session['user'])

        if request.method == 'POST':
            goals_data = request.form.to_dict()
            goals_data['user_id'] = user_id
            goals_collection.insert_one(goals_data)

            goals_history = list(goals_history_collection.find({'user_id': user_id}))
            flash('Goals updated successfully.', 'success')
            return redirect('/dashboard')
        else:
            goal = goals_collection.find_one({'user_id': user_id})
            goals_history = list(goals_history_collection.find({'user_id': user_id}))
            return render_template('goals.html', goal=goal, goals_history=goals_history)
    else:
        return redirect('/login')

@app.route('/progress')
def progress():
    if 'user' in session:
        user_data = users_collection.find_one({'_id': ObjectId(session['user'])})
        
        # Fetch all activity data and extract relevant attributes
        activity_entries = list(activity_collection.find({'user_id': user_data['_id']}))
        exercise_entries = list(exercise_collection.find({'user_id': user_data['_id']}))
        nutrition_entries = list(nutrition_collection.find({'user_id': user_data['_id']}))
        goals_entries = list(goals_collection.find({'user_id': user_data['_id']}))
        
        # Prepare labels (e.g., dates or indices)
        labels = [e.get('date', f"Day {i+1}") for i, e in enumerate(activity_entries)]
        
        # Prepare data arrays, use defaults if data is missing
        activity_data = [int(e.get('steps', 0)) for e in activity_entries]
        exercise_data = [int(e.get('duration', 0)) for e in exercise_entries]
        # Nutrition data must be a list of [protein, carbs, fats]
        if nutrition_entries:
            nutrition_data = [
                int(nutrition_entries[-1].get('protein', 0)),
                int(nutrition_entries[-1].get('carbs', 0)),
                int(nutrition_entries[-1].get('fat', 0))
            ]
        else:
            nutrition_data = [0, 0, 0]
        # Goal data for radar chart: fill with sample or real numbers
        if goals_entries:
            goal_data = [
                int(goals_entries[-1].get('steps', 0)),
                int(goals_entries[-1].get('workout', 0)),
                int(goals_entries[-1].get('calories', 0)),
                int(goals_entries[-1].get('sleep', 0)),
                int(goals_entries[-1].get('hydration', 0)),
            ]
        else:
            goal_data = [0, 0, 0, 0, 0]

        # Build the correctly structured dict
        progress_chart_data = {
            "activity_data": activity_data,
            "exercise_data": exercise_data,
            "nutrition_data": nutrition_data,
            "goal_data": goal_data,
            "labels": labels
        }

        return render_template('progress.html', progress=progress_chart_data)
    else:
        return redirect('/login')


# Home - show feed
@app.route('/social', methods=['GET', 'POST'])
def social():
    if 'user' in session:
        user_id = ObjectId(session['user'])
        user_data = db['users'].find_one({'_id': user_id})
        username = user_data.get('name', 'User')
        profile_pic = user_data.get('profile_pic') if 'profile_pic' in user_data else None

        # POST: Create post
        if request.method == 'POST':
            content = request.form.get('post_content', '').strip()
            photo_url = None
            photo_file = request.files.get('photo')
            if photo_file and photo_file.filename:
                # Save photo (simplified, update storage path as needed)
                filename = f"static/uploads/{photo_file.filename.split('/')[-1]}"
                photo_file.save(filename)
                photo_url = "/" + filename
            if content:
                post = {
                    'user_id': str(user_id),
                    'username': username,
                    'profile_pic': profile_pic,
                    'content': content,
                    'photo': photo_url,
                    'likes': 0,
                    'comments': [],
                    'liked_by': [],
                    'timestamp': datetime.datetime.utcnow()
                }
                social_collection.insert_one(post)
                flash('Post shared successfully!', 'success')
                return redirect('/social')
            else:
                flash('Post content cannot be empty.', 'error')

        # GET: render feed
        posts = list(social_collection.find().sort('timestamp', -1))
        for post in posts:
            time_diff = datetime.datetime.utcnow() - post['timestamp']
            if time_diff.days == 0:
                post['time_ago'] = f"{int(time_diff.seconds/3600)}h ago" if time_diff.seconds >= 3600 else f"{int(time_diff.seconds/60)}m ago"
            else:
                post['time_ago'] = f"{time_diff.days}d ago"
            post['profile_pic'] = post.get('profile_pic', None)
            post['user_id'] = str(post['user_id'])  # string for Jinja comparison
            post['_id'] = str(post['_id'])
            post['likes'] = post.get('likes', 0)
            post['liked_by_current_user'] = ('user' in session and session['user'] in post.get('liked_by', []))
            post['comments'] = post.get('comments', [])

        return render_template('social.html', posts=posts, user=user_data, session=session)
    else:
        return redirect('/login')



# Like post (AJAX)
@app.route('/like_post/<post_id>', methods=['POST'])
def like_post(post_id):
    if 'user' in session:
        user_id = session['user']
        post = social_collection.find_one({'_id': ObjectId(post_id)})
        if post and user_id not in post.get('liked_by', []):
            social_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes': 1}, '$push': {'liked_by': user_id}})
            return jsonify(success=True)
    return jsonify(success=False)

# Add comment (AJAX)
@app.route('/comment_post/<post_id>', methods=['POST'])
def comment_post(post_id):
    user = request.form.get('user', 'User')
    text = request.form.get('text', '')
    if user and text:
        social_collection.update_one({'_id': ObjectId(post_id)}, {'$push': {'comments': {'user': user, 'text': text}}})
        return jsonify(success=True)
    return jsonify(success=False)

# Delete post (AJAX)
@app.route('/delete_post/<post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user' in session:
        post = social_collection.find_one({'_id': ObjectId(post_id)})
        if post and str(post['user_id']) == session['user']:
            social_collection.delete_one({'_id': ObjectId(post_id)})
            return jsonify(success=True)
    return jsonify(success=False)




@app.route('/recommendations')
def recommendations():
    if 'user' in session:
        user_data = users_collection.find_one({'_id': ObjectId(session['user'])})
        recommendations_data = generate_recommendations(user_data)

        # Example tips, you could fetch these from your nutrition or exercise collections
        tips_list = [
            "Drink a glass of water every 2 hours.",
            "Aim for 8,000 steps today.",
            "Add an extra veggie to your lunch.",
            "Try a 5-min breathing exercise."
        ]
        # Optionally fetch recent stats from MongoDB to personalize cards
        latest_exercise = exercise_collection.find_one(
            {'user_id': user_data['_id']}, sort=[('date', -1)]) or {}
        latest_nutrition = nutrition_collection.find_one(
            {'user_id': user_data['_id']}, sort=[('date', -1)]) or {}

        return render_template(
            'recommendations.html',
            recommendations=recommendations_data,
            tips=tips_list,
            exercise=latest_exercise,
            nutrition=latest_nutrition,
            user=user_data
        )
    else:
        return redirect('/login')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' in session:
        if request.method == 'POST':
            user_id = ObjectId(session['user'])  # Convert string to ObjectId
            update_data = {
                'name': request.form['name'],
                'phone': request.form['phone'],
                'dob': request.form['dob'],
                'email': request.form['email'],
                'activity_level': request.form['activity_level'],
                'dietary_preferences': request.form.getlist('dietary_preferences'),
                'health_conditions': request.form.getlist('health_conditions'),
                'weight': float(request.form['weight']),
                'height': float(request.form['height']),
                'ideal_weight': float(request.form['ideal_weight'])
            }
            users_collection.update_one({'_id': user_id}, {'$set': update_data})
            flash('Profile updated successfully.', 'success')
            return redirect('/dashboard')
        else:
            user_data = users_collection.find_one({'_id': ObjectId(session['user'])})  # Convert string to ObjectId
            return render_template('profile.html', user=user_data)
    else:
        return redirect('/login')

# Forgot.html
@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    if request.method == 'POST':
        otp_entered = request.form['otp']
        # Retrieve user data from the database based on the entered OTP
        user_data = users_collection.find_one({'otp': otp_entered})
        if user_data:
            # OTP verification successful
            session['user'] = str(user_data['_id'])  # Store user ID in session
            # Clear the OTP from the database or mark it as verified
            users_collection.update_one({'_id': user_data['_id']}, {'$unset': {'otp': ''}})
            return jsonify({'success': True}), 200
        else:
            # Invalid OTP
            return jsonify({'success': False}), 400
    else:
        # Invalid request method
        return jsonify({'success': False, 'message': 'Invalid request method'}), 405


@app.route('/indashboard')
def indashboard():
    if 'user' in session:
        user_id = ObjectId(session['user'])
        user_data = users_collection.find_one({'_id': user_id})

        # Fetch activity data
        activities = list(activity_collection.find({'user_id': user_id}))
        exercises = list(exercise_collection.find({'user_id': user_id}))
        nutrition = list(nutrition_collection.find({'user_id': user_id}))
        goals = list(goals_collection.find({'user_id': user_id}))

        # Prepare data for charts
        dates = [a.get('date', '') for a in activities]
        steps = [int(a.get('steps', 0)) for a in activities]
        calories_burned = [int(a.get('calories_burned', 0)) for a in activities]
        calories_intake = [int(n.get('calories', 0)) for n in nutrition]

        # Summary stats
        total_steps = sum(steps)
        total_burned = sum(calories_burned)
        total_intake = sum(calories_intake)
        total_goals = len(goals)

        return render_template(
            'indashboard.html',
            user=user_data,
            dates=dates,
            steps=steps,
            calories_burned=calories_burned,
            calories_intake=calories_intake,
            total_steps=total_steps,
            total_burned=total_burned,
            total_intake=total_intake,
            total_goals=total_goals
        )
    else:
        return redirect('/login')


@app.route('/reset_password', methods=['POST'])
def reset_password():
    if 'user_id' in session:
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if new_password == confirm_password:
            # Update password in the database
            user_id = ObjectId(session['user_id'])
            users_collection.update_one({'_id': user_id}, {'$set': {'password': new_password}})
            flash('Password reset successfully.', 'success')
            return redirect('/login')
        else:
            flash('Passwords do not match. Please try again.', 'error')
    else:
        flash('Session expired. Please try again.', 'error')
    return redirect('/forgot')

if __name__ == '__main__':
    app.run(debug=True)

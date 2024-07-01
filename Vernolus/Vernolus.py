from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, jsonify
import os
from werkzeug.utils import secure_filename
import uuid
from PIL import Image

app = Flask(__name__)

profile_picture_folder = os.path.join(os.path.dirname(__file__), 'static/profile_pictures')
if not os.path.exists(profile_picture_folder):
    os.makedirs(profile_picture_folder)

UPLOAD_FOLDER = 'static/uploads'
PROFILE_PICTURE_FOLDER = 'static/profile_pictures'
ALLOWED_EXTENSIONS = {'mp4', 'mkv', 'jpg', 'jpeg', 'png', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_PICTURE_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static/profile_pictures')
app.secret_key = 'your_secret_key'

captions = {}

users = {
    'johndoe': {
        'username': 'johndoe',
        'bio': 'This is the current bio.',
        'profile_picture': 'static/profile_pictures/current_profile_picture.png'
    }
}

def is_same_image(img1_path, img2_path):
    try:
        img1 = Image.open(img1_path)
        img2 = Image.open(img2_path)
        return list(img1.getdata()) == list(img2.getdata())
    except FileNotFoundError:
        return False
    
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_users():
    users = {}
    if os.path.exists('userbase.txt'):
        with open('userbase.txt', 'r') as file:
            for line in file:
                parts = line.strip().split(',')
                if len(parts) < 2:
                    print(f"Skipping line due to incorrect format: '{line.strip()}'")
                    continue
                username = parts[0].strip()
                password = parts[1].strip()
                profile_picture = parts[2].strip() if len(parts) > 2 else ''
                bio = parts[3].strip() if len(parts) > 3 else ''
                users[username] = {'password': password, 'profile_picture': profile_picture, 'bio': bio}
    return users

def save_user(username, password, profile_picture='', bio=''):
    with open('userbase.txt', 'a') as file:
        file.write(f'{username},{password},{profile_picture},{bio}\n')

@app.route('/')
def home():
    if 'username' in session:
        media_files = []
        current_user = session['username']
        try:
            with open('db.txt', 'r', encoding='UTF-8') as f:
                for line in f:
                    line = line.strip()
                    if line and line.count(':') >= 5:
                        parts = line.split(':')
                        uid, filepath, caption, username, likes, likes_list = parts[:6]
                        filename = os.path.basename(filepath)
                        liked = current_user in likes_list.split(',')
                        media_files.append({
                            'uuid': uid,
                            'filename': filename,
                            'caption': caption,
                            'username': username,
                            'likes': likes,
                            'liked': liked,
                            'play_url': url_for('play_media', uuid_str=uid),
                            'download_url': url_for('download_media', uuid_str=uid)
                        })
        except FileNotFoundError:
            return "Database file 'db.txt' not found."
        return render_template('home.html', media_files=media_files, username=session['username'])
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        password = request.form['password']
        if username in users and users[username]['password'] == password:
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        users = load_users()
        username = request.form['username']
        password = request.form['password']
        if username in users:
            flash('Username already exists', 'error')
        else:
            save_user(username, password)
            flash('Registration successful, please login', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        caption = request.form['caption']
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(path)
            uuid_str = str(uuid.uuid4())
            username = session['username']
            with open('db.txt', 'a', encoding='UTF-8') as f:
                f.write(f'{uuid_str}:{path.replace("\\", "/")}:{caption}:{username}:0:\n')
            captions[filename] = caption
            return redirect(url_for('upload_success'))
    return render_template('post.html')

@app.route('/success')
def upload_success():
    return render_template('success.html')

@app.route('/play/<uuid_str>')
def play_media(uuid_str, username):
    users = load_users()
    user = users.get(username)
    try:
        with open('db.txt', 'r', encoding='UTF-8') as f:
            for line in f:
                uid, filepath = line.strip().split(':')
                if uid == uuid_str:
                    filename = os.path.basename(filepath)
                    return render_template('play.html', filename=filename, filepath=filepath)
    except FileNotFoundError:
        return 'File not found.'

@app.route('/download/<uuid_str>')
def download_media(uuid_str, username):
    users = load_users()
    user = users.get(username)
    try:
        with open('db.txt', 'r', encoding='UTF-8') as f:
            path = app.config['UPLOAD_FOLDER']
            for line in f:
                uid, filepath = line.strip().split(':')
                if uid == uuid_str:
                    filename = os.path.basename(filepath)
                    return send_from_directory(
                        path,
                        filename,
                        as_attachment=True,
                        mimetype='audio'
                    )
    except FileNotFoundError:
        return 'File not found.'

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' in session:
        username = session['username']
        users = load_users()
        user = users.get(username)

        if request.method == 'POST':
            bio = request.form['bio']
            if 'profile_picture' in request.files:
                profile_picture = request.files['profile_picture']
                if profile_picture and allowed_file(profile_picture.filename):
                    profile_picture_filename = secure_filename(profile_picture.filename)
                    profile_picture_path = os.path.join(app.config['PROFILE_PICTURE_FOLDER'], profile_picture_filename)
                    profile_picture.save(profile_picture_path)
                    user['profile_picture'] = profile_picture_filename

            user['bio'] = bio
            users[username] = user
            with open('userbase.txt', 'w') as file:
                for uname, udata in users.items():
                    file.write(f"{uname},{udata['password']},{udata.get('profile_picture', '')},{udata.get('bio', '')}\n")
            flash('Profile updated successfully', 'success')
            return redirect(url_for('profile', username=username))

        return render_template('edit_profile.html', user=user)

    return redirect(url_for('login'))

@app.route('/profile/<username>')
def profile(username):
    users = load_users()
    user = users.get(username)

    if not user:
        return "User not found", 404

    user['media'] = []

    if not user.get('profile_picture'):
        user['profile_picture'] = 'default_profile_picture.png'

    try:
        with open('db.txt', 'r', encoding='UTF-8') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 3 and parts[3] == username:
                    uid, filepath, caption = parts[:3]
                    filename = os.path.basename(filepath)
                    user['media'].append({'filename': filename, 'caption': caption})
    except FileNotFoundError:
        pass

    if 'username' in session:
        current_username = session['username']
        if current_username == username:
            return render_template('profile.html', user=user, is_current_user=True)
    return render_template('profile.html', user=user)

@app.route('/like/<uuid_str>', methods=['POST'])
def like_post(uuid_str):
    updated_lines = []
    likes_count = 0
    username = session['username']
    already_liked = False

    try:
        with open('db.txt', 'r', encoding='UTF-8') as f:
            lines = f.readlines()
        
        for line in lines:
            parts = line.strip().split(':')
            if len(parts) >= 6 and parts[0] == uuid_str:
                likes_list = parts[5].split(',') if parts[5] else []
                if username in likes_list:
                    already_liked = True
                    likes_count = parts[4]
                else:
                    likes_list.append(username)
                    parts[4] = str(int(parts[4]) + 1)
                    parts[5] = ','.join(likes_list)
                    likes_count = parts[4]
            updated_lines.append(':'.join(parts) + '\n')

        if already_liked:
            return {'error': 'You have already liked this post'}, 400
        
        with open('db.txt', 'w', encoding='UTF-8') as f:
            f.writelines(updated_lines)
        
        return {'likes': likes_count}, 200

    except FileNotFoundError:
        return {'error': 'File not found'}, 404

if __name__ == '__main__':
    app.run(debug=True)

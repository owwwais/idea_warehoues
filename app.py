from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, send_from_directory, abort, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import os
from firebase_config import auth
import pyrebase
import requests
import json
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, FileField
from wtforms.validators import DataRequired, Length
from werkzeug.utils import secure_filename
import google.generativeai as genai
import random
import string
import shutil
from PIL import Image, ImageDraw

# Create the Flask application
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ideas.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['AVATAR_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static/avatars')
app.config['GEMINI_API_KEY'] = 'AIzaSyDN9gBMT823PMvxDIxjvdHG8ouGAjZTH3w'

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Create upload folders if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AVATAR_FOLDER'], exist_ok=True)
os.makedirs('static/icons', exist_ok=True)

# Models
class Warehouse(db.Model):
    __tablename__ = 'warehouses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users = db.relationship('User', backref='warehouse', lazy=True)
    ideas = db.relationship('Idea', backref='warehouse', lazy=True)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    firebase_uid = db.Column(db.String(128), unique=True, nullable=False)
    avatar = db.Column(db.String(255))
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'))
    ideas = db.relationship('Idea', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    
    def __repr__(self):
        return f'<User {self.email}>'
        
    def get_avatar_url(self):
        if self.avatar:
            return url_for('static', filename=f'avatars/{self.avatar}')
        return url_for('static', filename='avatars/default.png')

class Idea(db.Model):
    __tablename__ = 'ideas'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    stage = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouses.id'), nullable=False)
    comments = db.relationship('Comment', backref='idea', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('Attachment', backref='idea', lazy=True, cascade='all, delete-orphan')
    tags = db.relationship('Tag', secondary='idea_tags', backref=db.backref('ideas', lazy=True))

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey('ideas.id'), nullable=False)

class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

idea_tags = db.Table('idea_tags',
    db.Column('idea_id', db.Integer, db.ForeignKey('ideas.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True)
)

class Attachment(db.Model):
    __tablename__ = 'attachments'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    idea_id = db.Column(db.Integer, db.ForeignKey('ideas.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('welcome.html')
    
    if not current_user.warehouse_id:
        return redirect(url_for('select_warehouse'))
        
    ideas = Idea.query.filter_by(warehouse_id=current_user.warehouse_id).order_by(Idea.created_at.desc()).all()
    return render_template('index.html', ideas=ideas)

@app.route('/select-warehouse', methods=['GET', 'POST'])
@login_required
def select_warehouse():
    if current_user.warehouse_id:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create':
            name = request.form.get('name')
            description = request.form.get('description')
            
            if name:
                # إنشاء كود فريد للمستودع
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                
                warehouse = Warehouse(
                    name=name,
                    description=description,
                    code=code
                )
                db.session.add(warehouse)
                db.session.commit()
                
                current_user.warehouse_id = warehouse.id
                db.session.commit()
                
                flash('تم إنشاء المستودع بنجاح! كود المستودع: {}'.format(code), 'success')
                return redirect(url_for('select_warehouse', code=code))
                
        elif action == 'join':
            code = request.form.get('code')
            warehouse = Warehouse.query.filter_by(code=code).first()
            
            if warehouse:
                current_user.warehouse_id = warehouse.id
                db.session.commit()
                flash('تم الانضمام إلى المستودع بنجاح!', 'success')
                return redirect(url_for('index'))
            else:
                flash('كود المستودع غير صحيح', 'danger')
    
    return render_template('select_warehouse.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        confirm_password = request.form.get('confirm_password')
        
        if not all([email, password, name, confirm_password]):
            flash('جميع الحقول مطلوبة', 'danger')
            return redirect(url_for('register'))
            
        if password != confirm_password:
            flash('كلمات المرور غير متطابقة', 'danger')
            return redirect(url_for('register'))
        
        try:
            # Create user in Firebase
            firebase_user = auth.create_user_with_email_and_password(email, password)
            
            # Create user in local database
            db_user = User(
                email=email,
                name=name,
                firebase_uid=firebase_user['localId']
            )
            db.session.add(db_user)
            db.session.commit()
            
            # Log in the user
            login_user(db_user)
            
            flash('تم إنشاء حسابك بنجاح!', 'success')
            return redirect(url_for('select_warehouse'))
            
        except Exception as e:
            flash('حدث خطأ أثناء التسجيل. الرجاء المحاولة مرة أخرى.', 'danger')
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            # Authenticate with Firebase
            firebase_user = auth.sign_in_with_email_and_password(email, password)
            
            # Get or create user in local database
            user = User.query.filter_by(email=email).first()
            
            if not user:
                # Create user in local database if they exist in Firebase but not in local DB
                user = User(
                    email=email,
                    name=email.split('@')[0],  # Temporary name from email
                    firebase_uid=firebase_user['localId']
                )
                db.session.add(user)
                db.session.commit()
            
            login_user(user)
            session['firebase_token'] = firebase_user['idToken']
            flash('تم تسجيل الدخول بنجاح!', 'success')
            return redirect(url_for('select_warehouse'))
            
        except Exception as e:
            flash('البريد الإلكتروني أو كلمة المرور غير صحيحة', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('تم تسجيل الخروج بنجاح!', 'success')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'avatar' in request.files:
            file = request.files['avatar']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['AVATAR_FOLDER'], filename)
                file.save(file_path)
                current_user.avatar = filename
                db.session.commit()
                flash('Avatar updated successfully!', 'success')
        
        name = request.form.get('name')
        if name and name != current_user.name:
            current_user.name = name
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            
    return render_template('profile.html')

@app.route('/create_idea', methods=['GET', 'POST'])
@login_required
def create_idea():
    if not current_user.warehouse_id:
        flash('يجب عليك الانضمام إلى مستودع أولاً', 'warning')
        return redirect(url_for('select_warehouse'))
        
    form = IdeaForm()
    if form.validate_on_submit():
        idea = Idea(
            title=form.title.data,
            content=form.content.data,
            category=form.category.data,
            stage=form.stage.data,
            author_id=current_user.id,
            warehouse_id=current_user.warehouse_id
        )
        
        # Handle tags
        if form.tags.data:
            tag_names = [tag.strip() for tag in form.tags.data.split(',')]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                idea.tags.append(tag)
        
        # Handle file uploads
        if 'attachments' in request.files:
            files = request.files.getlist('attachments')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    
                    attachment = Attachment(
                        filename=filename,
                        original_filename=file.filename,
                        idea=idea
                    )
                    db.session.add(attachment)
        
        db.session.add(idea)
        db.session.commit()
        
        flash('تم إنشاء الفكرة بنجاح!', 'success')
        return redirect(url_for('view_idea', idea_id=idea.id))
        
    return render_template('create_idea.html', form=form)

@app.route('/idea/<int:idea_id>')
@login_required
def view_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    
    # التحقق من أن المستخدم ينتمي إلى نفس المستودع
    if idea.warehouse_id != current_user.warehouse_id:
        flash('لا يمكنك الوصول إلى هذه الفكرة', 'danger')
        return redirect(url_for('index'))
        
    return render_template('view_idea.html', idea=idea)

@app.route('/attachment/<int:attachment_id>')
@login_required
def download_attachment(attachment_id):
    attachment = Attachment.query.get_or_404(attachment_id)
    
    # Check if the user has access to this attachment
    idea = Idea.query.get(attachment.idea_id)
    if not idea:
        abort(404)
    
    # Construct the file path
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], attachment.filename)
    
    if not os.path.exists(file_path):
        abort(404)
    
    # Send the file with its original filename
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        attachment.filename,
        as_attachment=True,
        download_name=attachment.original_filename
    )

@app.route('/idea/<int:idea_id>/attach', methods=['POST'])
@login_required
def attach_file(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected', 'error')
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        attachment = Attachment(
            filename=filename,
            original_filename=file.filename,
            idea_id=idea_id
        )
        db.session.add(attachment)
        db.session.commit()
        
        flash('File uploaded successfully', 'success')
    
    return redirect(url_for('view_idea', idea_id=idea_id))

@app.route('/idea/<int:idea_id>/comment', methods=['POST'])
@login_required
def add_comment(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    content = request.form.get('content')
    
    if content:
        comment = Comment(
            content=content,
            author_id=current_user.id,
            idea_id=idea_id
        )
        db.session.add(comment)
        db.session.commit()
        flash('تم إضافة تعليقك بنجاح!', 'success')
    else:
        flash('لا يمكن إضافة تعليق فارغ', 'error')
    
    return redirect(url_for('view_idea', idea_id=idea_id))

@app.route('/idea/<int:idea_id>/delete', methods=['POST'])
@login_required
def delete_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    if idea.author_id != current_user.id:
        flash('لا يمكنك حذف هذه الفكرة', 'danger')
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    db.session.delete(idea)
    db.session.commit()
    flash('تم حذف الفكرة بنجاح', 'success')
    return redirect(url_for('index'))

@app.route('/idea/<int:idea_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    if idea.author_id != current_user.id:
        flash('لا يمكنك تعديل هذه الفكرة', 'danger')
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    if request.method == 'POST':
        idea.title = request.form.get('title')
        idea.content = request.form.get('content')
        idea.category = request.form.get('category')
        idea.stage = request.form.get('stage')
        
        # Handle tags
        tags_string = request.form.get('tags')
        if tags_string:
            # Clear existing tags
            idea.tags = []
            # Add new tags
            tag_names = [tag.strip() for tag in tags_string.split(',')]
            for tag_name in tag_names:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                idea.tags.append(tag)
        
        db.session.commit()
        flash('تم تحديث الفكرة بنجاح', 'success')
        return redirect(url_for('view_idea', idea_id=idea_id))
    
    return render_template('edit_idea.html', idea=idea)

@app.route('/idea/<int:idea_id>/ai-assist', methods=['POST'])
@login_required
def ai_assist_idea(idea_id):
    idea = Idea.query.get_or_404(idea_id)
    suggestions = get_ai_suggestions(idea.content)
    return jsonify({'suggestions': suggestions})

def get_ai_suggestions(content):
    genai.configure(api_key=app.config['GEMINI_API_KEY'])
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""
    أنا أعمل على فكرة وأحتاج إلى اقتراحات لتحسينها. محتوى الفكرة هو:
    
    {content}
    
    الرجاء تقديم:
    1. اقتراحات لتحسين الفكرة
    2. نقاط القوة والضعف المحتملة
    3. خطوات عملية للتنفيذ
    4. موارد مقترحة قد تكون مفيدة
    
    قدم الإجابة باللغة العربية وبشكل مختصر ومفيد.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return "عذراً، حدث خطأ أثناء توليد الاقتراحات. الرجاء المحاولة مرة أخرى."

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class IdeaForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired(), Length(min=3, max=100)])
    content = TextAreaField('Description', validators=[DataRequired(), Length(min=10)])
    category = SelectField('Category', choices=[
        ('technology', 'Technology'),
        ('business', 'Business'),
        ('education', 'Education'),
        ('health', 'Health'),
        ('environment', 'Environment'),
        ('social', 'Social'),
        ('other', 'Other')
    ])
    stage = SelectField('Stage', choices=[
        ('concept', 'Concept'),
        ('prototype', 'Prototype'),
        ('development', 'Development'),
        ('testing', 'Testing'),
        ('launch', 'Launch')
    ])
    tags = StringField('Tags')
    attachments = FileField('Attachments')

def init_db():
    # Drop all tables
    db.drop_all()
    
    # Create all tables
    db.create_all()
    
    # Create default categories
    categories = ['Technology', 'Business', 'Education', 'Health', 'Environment', 'Social', 'Other']
    for category_name in categories:
        category = Category(name=category_name)
        db.session.add(category)
    
    db.session.commit()

def create_default_icons():
    icons_path = os.path.join(app.static_folder, 'icons')
    os.makedirs(icons_path, exist_ok=True)
    
    sizes = [192, 512]
    for size in sizes:
        icon_path = os.path.join(icons_path, f'icon-{size}x{size}.png')
        if not os.path.exists(icon_path):
            # Create a simple icon
            img = Image.new('RGB', (size, size), color='#2563eb')
            draw = ImageDraw.Draw(img)
            draw.text((size/4, size/4), 'الأفكار', fill='white', size=size//4)
            img.save(icon_path)

@app.route('/static/js/sw.js')
def serve_sw():
    response = make_response(
        send_from_directory('static/js', 'sw.js')
    )
    # Add CORS headers
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

if __name__ == '__main__':
    with app.app_context():
        # Initialize the database before running the app
        init_db()
        create_default_icons()
    app.run(debug=True, port=5001)

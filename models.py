from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    native_language = db.Column(db.String(50), default='English')
    target_language = db.Column(db.String(50), default='Spanish')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    vocabularies = db.relationship('Vocabulary', backref='user', lazy=True)
    practice_sessions = db.relationship('PracticeSession', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Vocabulary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    word = db.Column(db.String(100), nullable=False)
    translation = db.Column(db.String(100), nullable=False)
    language = db.Column(db.String(50), nullable=False)
    context = db.Column(db.Text)
    proficiency = db.Column(db.Integer, default=0)  # 0-5 scale
    last_reviewed = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    review_count = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<Vocabulary {self.word}>'


class PracticeSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_date = db.Column(db.DateTime, default=datetime.utcnow)
    words_practiced = db.Column(db.Integer, default=0)
    correct_pronunciations = db.Column(db.Integer, default=0)
    session_duration = db.Column(db.Integer, default=0)  # in seconds


class DailySuggestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    word = db.Column(db.String(100), nullable=False)
    translation = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    practiced = db.Column(db.Boolean, default=False)
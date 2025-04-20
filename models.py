from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import relationship

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = sa.Column(sa.Integer, primary_key=True)
    email = sa.Column(sa.String(120), unique=True, nullable=False)
    username = sa.Column(sa.String(80), unique=True, nullable=False)
    password_hash = sa.Column(sa.String(128))
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    conversations = relationship('Conversation', backref='user', lazy=True)
    
    # Google OAuth fields
    google_id = sa.Column(sa.String(100), unique=True, nullable=True)
    is_guest = sa.Column(sa.Boolean, default=False)  # For guest users

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Conversation(db.Model):
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=True)  # Changed to nullable=True to allow guest conversations
    title = sa.Column(sa.String(200))
    starred = sa.Column(sa.Boolean, default=False)
    model_name = sa.Column(sa.String(50), default='gemini')  # New field for AI model selection
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    messages = relationship('Message', backref='conversation', lazy=True)

    def __repr__(self):
        return f'<Conversation {self.id}>'

class Message(db.Model):
    id = sa.Column(sa.Integer, primary_key=True)
    conversation_id = sa.Column(sa.Integer, sa.ForeignKey('conversation.id'), nullable=False)
    content = sa.Column(sa.Text, nullable=False)
    role = sa.Column(sa.String(20), nullable=False)  # 'user' o 'assistant'
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Message {self.id}>'

class GeneratedVideo(db.Model):
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=True) # Permitir videos de invitados
    prompt = sa.Column(sa.Text, nullable=False)
    video_url = sa.Column(sa.String(500), nullable=False) # URL donde se almacena el video
    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)
    user = relationship('User') # Relación opcional para acceder al usuario

    def __repr__(self):
        return f'<GeneratedVideo {self.id} by User {self.user_id}>'

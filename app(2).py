# ============================================
# BANTU HALII - AFRICAN CHAT APPLICATION
# Branch of Bantu Africa Ecosystem
# ALL-IN-ONE app.py - Production Ready
# ============================================

# ============================================
# 1. IMPORTS AND DEPENDENCIES
# ============================================
import os
import sys
import uuid
import json
import base64
import hashlib
import secrets
import string
import re
import time
import threading
from io import BytesIO
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_from_directory,
    make_response, abort, g
)
from flask_socketio import (
    SocketIO, emit, join_room, leave_room,
    close_room, rooms, disconnect
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import (
    text, func, and_, or_, not_, desc, asc,
    case, extract, distinct
)
from sqlalchemy.orm import aliased
from sqlalchemy.exc import IntegrityError, OperationalError
from dotenv import load_dotenv
from PIL import Image
import pytz
from datetime import timezone as tz

# Load environment variables
load_dotenv()

# ============================================
# 2. CONSTANTS AND ENUMS
# ============================================

class MessageType(Enum):
    """Message type enumeration"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    LOCATION = "location"
    CONTACT = "contact"
    STICKER = "sticker"
    MIXED = "mixed"
    SYSTEM = "system"

class RoomType(Enum):
    """Room type enumeration"""
    DIRECT = "direct"
    GROUP = "group"
    BROADCAST = "broadcast"
    COMMUNITY = "community"

class UserStatus(Enum):
    """User status enumeration"""
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    BUSY = "busy"
    TYPING = "typing"
    RECORDING = "recording"

class MediaCategory(Enum):
    """Media category for Cloudinary organization"""
    PROFILE_PIC = "profile_pictures"
    MESSAGE_IMAGE = "message_images"
    MESSAGE_VIDEO = "message_videos"
    MESSAGE_AUDIO = "message_audio"
    MESSAGE_DOCUMENT = "message_documents"
    GROUP_PIC = "group_pictures"
    STICKER = "stickers"
    TEMP = "temporary"

# Allowed file extensions
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'svg', 'heic', 'heif'}
ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm', 'mkv', '3gp', 'm4v'}
ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg', 'aac', 'm4a', 'wma', 'flac', 'opus', 'amr'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx', 'csv', 'rtf'}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS | ALLOWED_AUDIO_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS

# Maximum file sizes (in bytes)
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
MAX_AUDIO_SIZE = 20 * 1024 * 1024  # 20MB
MAX_DOCUMENT_SIZE = 50 * 1024 * 1024  # 50MB
MAX_PROFILE_PIC_SIZE = 5 * 1024 * 1024  # 5MB

# Message limits
MAX_MESSAGE_LENGTH = 5000
MAX_GROUP_NAME_LENGTH = 100
MAX_USERNAME_LENGTH = 50
MAX_STATUS_LENGTH = 200
MAX_BIO_LENGTH = 500

# Pagination
MESSAGES_PER_PAGE = 50
USERS_PER_PAGE = 30
ROOMS_PER_PAGE = 20

# Security
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_TIME = 15 * 60  # 15 minutes in seconds
SESSION_TIMEOUT = 24 * 60 * 60  # 24 hours in seconds
PASSWORD_MIN_LENGTH = 8
PASSWORD_COMPLEXITY = True

# ============================================
# 3. APP CONFIGURATION
# ============================================
app = Flask(__name__)

# Security configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=SESSION_TIMEOUT)

# Database configuration
database_url = os.getenv('DATABASE_URL', 'sqlite:///bantu_halii.db')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 20,
    'pool_timeout': 30,
}

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB total
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_IMAGE_SIZE'] = MAX_IMAGE_SIZE
app.config['MAX_VIDEO_SIZE'] = MAX_VIDEO_SIZE
app.config['MAX_AUDIO_SIZE'] = MAX_AUDIO_SIZE
app.config['MAX_DOCUMENT_SIZE'] = MAX_DOCUMENT_SIZE

# Create upload directories
upload_dirs = [
    'static/uploads/images',
    'static/uploads/videos',
    'static/uploads/audio',
    'static/uploads/documents',
    'static/uploads/temp',
    'static/uploads/thumbnails',
]
for dir_path in upload_dirs:
    os.makedirs(dir_path, exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=50 * 1024 * 1024,  # 50MB for media
    async_mode='threading',
    logger=True,
    engineio_logger=True,
    always_connect=True,
    manage_session=False
)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME', ''),
    api_key=os.getenv('CLOUDINARY_API_KEY', ''),
    api_secret=os.getenv('CLOUDINARY_API_SECRET', ''),
    secure=True
)

# ============================================
# 4. DATABASE MODELS
# ============================================

class User(db.Model):
    """Bantu Halii User Model - Complete"""
    __tablename__ = 'users'

    # Primary fields
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Authentication fields
    phone_number = db.Column(db.String(20), unique=True, nullable=True, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    username = db.Column(db.String(MAX_USERNAME_LENGTH), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    
    # Profile fields
    profile_pic = db.Column(db.String(500), default='')
    profile_pic_public_id = db.Column(db.String(200), default='')
    status = db.Column(db.String(MAX_STATUS_LENGTH), default='Hey there! I am using Bantu Halii 🌍')
    bio = db.Column(db.String(MAX_BIO_LENGTH), default='')
    
    # Online status
    is_online = db.Column(db.Boolean, default=False, index=True)
    last_seen = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_typing = db.Column(db.DateTime(timezone=True))
    user_status = db.Column(db.String(20), default=UserStatus.OFFLINE.value)
    
    # Security fields
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime(timezone=True))
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(100))
    
    # Settings
    notifications_enabled = db.Column(db.Boolean, default=True)
    read_receipts_enabled = db.Column(db.Boolean, default=True)
    last_seen_visible = db.Column(db.Boolean, default=True)
    dark_mode = db.Column(db.Boolean, default=False)
    language = db.Column(db.String(10), default='en')
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    sent_messages = db.relationship(
        'Message', 
        foreign_keys='Message.sender_id',
        backref='sender', 
        lazy='dynamic',
        primaryjoin='User.id == Message.sender_id'
    )
    received_messages = db.relationship(
        'Message', 
        foreign_keys='Message.receiver_id',
        backref='receiver', 
        lazy='dynamic',
        primaryjoin='User.id == Message.receiver_id'
    )
    owned_rooms = db.relationship('Room', backref='creator', lazy='dynamic', foreign_keys='Room.created_by')
    room_memberships = db.relationship('RoomMember', backref='member', lazy='dynamic', foreign_keys='RoomMember.user_id')
    contacts = db.relationship('Contact', foreign_keys='Contact.user_id', backref='user', lazy='dynamic')
    contact_of = db.relationship('Contact', foreign_keys='Contact.contact_id', backref='contact_user', lazy='dynamic')
    blocked_users = db.relationship('BlockedUser', foreign_keys='BlockedUser.user_id', backref='blocker', lazy='dynamic')
    blocked_by = db.relationship('BlockedUser', foreign_keys='BlockedUser.blocked_user_id', backref='blocked', lazy='dynamic')
    devices = db.relationship('UserDevice', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    message_reactions = db.relationship('MessageReaction', backref='user', lazy='dynamic')

    def set_password(self, password: str) -> None:
        """Set password with strong hashing"""
        if len(password) < PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters")
        
        if PASSWORD_COMPLEXITY:
            if not re.search(r'[A-Z]', password):
                raise ValueError("Password must contain at least one uppercase letter")
            if not re.search(r'[a-z]', password):
                raise ValueError("Password must contain at least one lowercase letter")
            if not re.search(r'\d', password):
                raise ValueError("Password must contain at least one number")
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                raise ValueError("Password must contain at least one special character")
        
        self.password_hash = generate_password_hash(password, method='scrypt')

    def check_password(self, password: str) -> bool:
        """Check password against hash"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def is_account_locked(self) -> bool:
        """Check if account is locked due to login attempts"""
        if self.locked_until and self.locked_until > datetime.now(timezone.utc):
            return True
        return False

    def increment_login_attempts(self) -> None:
        """Increment login attempts and lock if necessary"""
        self.login_attempts += 1
        if self.login_attempts >= MAX_LOGIN_ATTEMPTS:
            self.locked_until = datetime.now(timezone.utc) + timedelta(seconds=LOGIN_LOCKOUT_TIME)

    def reset_login_attempts(self) -> None:
        """Reset login attempts"""
        self.login_attempts = 0
        self.locked_until = None

    def to_dict(self, include_private: bool = False) -> Dict[str, Any]:
        """Convert user to dictionary"""
        data = {
            'id': self.id,
            'uuid': self.user_uuid,
            'username': self.username,
            'phone_number': self.phone_number if include_private else None,
            'email': self.email if include_private else None,
            'profile_pic': self.profile_pic or self.get_default_avatar(),
            'status': self.status,
            'bio': self.bio,
            'is_online': self.is_online,
            'user_status': self.user_status,
            'last_seen': self.last_seen.isoformat() if self.last_seen and self.last_seen_visible else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        return data

    def get_default_avatar(self) -> str:
        """Generate default avatar based on username"""
        initial = self.username[0].upper() if self.username else 'U'
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
                  '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']
        color_index = sum(ord(c) for c in self.username) % len(colors)
        color = colors[color_index]
        return f"https://ui-avatars.com/api/?name={initial}&background={color.replace('#', '')}&color=fff&size=200"

    def get_unread_count(self) -> int:
        """Get total unread messages count"""
        return Message.query.filter(
            Message.receiver_id == self.id,
            Message.is_read == False,
            Message.is_deleted == False
        ).count()

    def get_online_status_display(self) -> str:
        """Get display text for online status"""
        if self.is_online:
            return "Online"
        if self.last_seen:
            delta = datetime.now(timezone.utc) - self.last_seen
            if delta < timedelta(minutes=1):
                return "Last seen just now"
            elif delta < timedelta(hours=1):
                minutes = int(delta.total_seconds() / 60)
                return f"Last seen {minutes} minute{'s' if minutes > 1 else ''} ago"
            elif delta < timedelta(days=1):
                hours = int(delta.total_seconds() / 3600)
                return f"Last seen {hours} hour{'s' if hours > 1 else ''} ago"
            elif delta < timedelta(days=7):
                days = delta.days
                return f"Last seen {days} day{'s' if days > 1 else ''} ago"
            else:
                return f"Last seen on {self.last_seen.strftime('%d/%m/%Y')}"
        return "Offline"

    def __repr__(self) -> str:
        return f'<User {self.username}>'


class UserDevice(db.Model):
    """User device tracking for multi-device support"""
    __tablename__ = 'user_devices'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    device_id = db.Column(db.String(100), unique=True, nullable=False)
    device_name = db.Column(db.String(200))
    device_type = db.Column(db.String(50))  # mobile, desktop, tablet
    platform = db.Column(db.String(50))  # android, ios, web
    push_token = db.Column(db.String(500))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, default=True)
    last_active = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Room(db.Model):
    """Chat Room / Group Model"""
    __tablename__ = 'rooms'

    id = db.Column(db.Integer, primary_key=True)
    room_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(MAX_GROUP_NAME_LENGTH), nullable=False)
    description = db.Column(db.Text)
    room_pic = db.Column(db.String(500))
    room_pic_public_id = db.Column(db.String(200))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_type = db.Column(db.String(20), default=RoomType.GROUP.value)  # direct, group, broadcast, community
    is_encrypted = db.Column(db.Boolean, default=False)
    max_members = db.Column(db.Integer, default=256)
    invite_link = db.Column(db.String(100), unique=True)
    is_public = db.Column(db.Boolean, default=False)
    
    # Settings
    only_admins_can_send = db.Column(db.Boolean, default=False)
    disappearing_messages = db.Column(db.Integer, default=0)  # 0 = off, seconds otherwise
    media_shared_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_message_at = db.Column(db.DateTime(timezone=True))
    
    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime(timezone=True))

    # Relationships
    messages = db.relationship('Message', backref='room', lazy='dynamic', foreign_keys='Message.room_id')
    members = db.relationship('RoomMember', backref='room_detail', lazy='dynamic', foreign_keys='RoomMember.room_id')
    admins = db.relationship('RoomAdmin', backref='room', lazy='dynamic')
    pinned_messages = db.relationship('PinnedMessage', backref='room', lazy='dynamic')

    def to_dict(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Convert room to dictionary"""
        last_message = Message.query.filter_by(
            room_id=self.id, 
            is_deleted=False
        ).order_by(Message.created_at.desc()).first()
        
        member_count = RoomMember.query.filter_by(room_id=self.id).count()
        
        data = {
            'id': self.id,
            'uuid': self.room_uuid,
            'name': self.name,
            'description': self.description,
            'room_pic': self.room_pic or self.get_default_room_pic(),
            'room_type': self.room_type,
            'is_group': self.room_type != RoomType.DIRECT.value,
            'member_count': member_count,
            'created_by': self.created_by,
            'invite_link': self.invite_link,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_message_at': self.last_message_at.isoformat() if self.last_message_at else None,
            'last_message': last_message.to_dict() if last_message else None,
        }
        
        if user_id:
            # Check if user is admin
            is_admin = RoomAdmin.query.filter_by(room_id=self.id, user_id=user_id).first()
            data['is_admin'] = bool(is_admin)
            
            # Get unread count for user
            unread = UnreadMessage.query.filter_by(
                room_id=self.id, 
                user_id=user_id
            ).first()
            data['unread_count'] = unread.count if unread else 0
        
        return data

    def get_default_room_pic(self) -> str:
        """Generate default room picture"""
        initial = self.name[0].upper() if self.name else 'G'
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7']
        color_index = sum(ord(c) for c in self.name) % len(colors)
        color = colors[color_index]
        return f"https://ui-avatars.com/api/?name={initial}&background={color.replace('#', '')}&color=fff&size=200&bold=true"

    def generate_invite_link(self) -> str:
        """Generate unique invite link"""
        alphabet = string.ascii_letters + string.digits
        self.invite_link = ''.join(secrets.choice(alphabet) for _ in range(10))
        return self.invite_link

    def __repr__(self) -> str:
        return f'<Room {self.name}>'


class RoomMember(db.Model):
    """Room Membership Model"""
    __tablename__ = 'room_members'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), default='member')  # member, admin, owner
    joined_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    left_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, default=True)
    
    # Mute settings
    is_muted = db.Column(db.Boolean, default=False)
    muted_until = db.Column(db.DateTime(timezone=True))
    
    # Custom room settings
    custom_name = db.Column(db.String(100))
    is_pinned = db.Column(db.Boolean, default=False)
    notifications_enabled = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint('room_id', 'user_id', name='unique_room_member'),
    )


class RoomAdmin(db.Model):
    """Room Admin Model"""
    __tablename__ = 'room_admins'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    promoted_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    promoted_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    can_manage_members = db.Column(db.Boolean, default=True)
    can_manage_settings = db.Column(db.Boolean, default=True)
    can_delete_messages = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint('room_id', 'user_id', name='unique_room_admin'),
    )


class Contact(db.Model):
    """User Contacts Model"""
    __tablename__ = 'contacts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    contact_name = db.Column(db.String(100))  # Custom name for contact
    added_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_favorite = db.Column(db.Boolean, default=False)
    is_blocked = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'contact_id', name='unique_contact'),
    )


class BlockedUser(db.Model):
    """Blocked Users Model"""
    __tablename__ = 'blocked_users'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    blocked_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    blocked_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reason = db.Column(db.String(200))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'blocked_user_id', name='unique_block'),
    )


class Message(db.Model):
    """Messages Model - Complete"""
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    message_uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    
    # Sender and receiver
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=True, index=True)
    
    # Message content
    content = db.Column(db.Text)
    message_type = db.Column(db.String(20), default=MessageType.TEXT.value)
    
    # Media fields
    media_url = db.Column(db.String(1000))
    media_public_id = db.Column(db.String(500))
    media_type = db.Column(db.String(20))  # image, video, audio, document
    media_size = db.Column(db.BigInteger)
    media_duration = db.Column(db.Float)  # Duration in seconds for audio/video
    media_width = db.Column(db.Integer)
    media_height = db.Column(db.Integer)
    thumbnail_url = db.Column(db.String(1000))
    thumbnail_public_id = db.Column(db.String(500))
    
    # Message status
    is_read = db.Column(db.Boolean, default=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True))
    is_delivered = db.Column(db.Boolean, default=False)
    delivered_at = db.Column(db.DateTime(timezone=True))
    
    # Reply and forward
    reply_to_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)
    forward_from_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Special features
    is_edited = db.Column(db.Boolean, default=False)
    edited_at = db.Column(db.DateTime(timezone=True))
    is_pinned = db.Column(db.Boolean, default=False)
    is_starred = db.Column(db.Boolean, default=False)
    
    # Disappearing messages
    disappear_at = db.Column(db.DateTime(timezone=True))
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime(timezone=True))
    deleted_by = db.Column(db.Integer)

    # Relationships
    reply_to = db.relationship('Message', remote_side=[id], backref='replies')
    reactions = db.relationship('MessageReaction', backref='message', lazy='dynamic')
    reads = db.relationship('MessageRead', backref='message', lazy='dynamic')

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        sender = db.session.get(User, self.sender_id) if self.sender_id else None
        receiver = db.session.get(User, self.receiver_id) if self.receiver_id else None
        
        return {
            'id': self.id,
            'uuid': self.message_uuid,
            'sender_id': self.sender_id,
            'sender_username': sender.username if sender else 'Unknown',
            'sender_pic': sender.profile_pic if sender else '',
            'receiver_id': self.receiver_id,
            'receiver_username': receiver.username if receiver else None,
            'room_id': self.room_id,
            'content': self.content,
            'message_type': self.message_type,
            'media_url': self.media_url,
            'media_type': self.media_type,
            'media_size': self.media_size,
            'media_duration': self.media_duration,
            'media_width': self.media_width,
            'media_height': self.media_height,
            'thumbnail_url': self.thumbnail_url,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'is_delivered': self.is_delivered,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'reply_to_id': self.reply_to_id,
            'is_edited': self.is_edited,
            'edited_at': self.edited_at.isoformat() if self.edited_at else None,
            'is_pinned': self.is_pinned,
            'is_starred': self.is_starred,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reactions': [r.to_dict() for r in self.reactions.all()],
        }

    def mark_as_read(self) -> None:
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.now(timezone.utc)

    def soft_delete(self, user_id: int) -> None:
        """Soft delete message"""
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = user_id

    def __repr__(self) -> str:
        return f'<Message {self.id} from {self.sender_id}>'


class MessageRead(db.Model):
    """Track who read which message"""
    __tablename__ = 'message_reads'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    read_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', name='unique_message_read'),
    )


class MessageReaction(db.Model):
    """Message Reactions Model"""
    __tablename__ = 'message_reactions'

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    emoji = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('message_id', 'user_id', 'emoji', name='unique_reaction'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'message_id': self.message_id,
            'user_id': self.user_id,
            'emoji': self.emoji,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class PinnedMessage(db.Model):
    """Pinned Messages in Rooms"""
    __tablename__ = 'pinned_messages'

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False, index=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    pinned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pinned_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    message = db.relationship('Message', backref='pinned_in')


class UnreadMessage(db.Model):
    """Track unread message counts per room per user"""
    __tablename__ = 'unread_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False, index=True)
    count = db.Column(db.Integer, default=0)
    last_message_id = db.Column(db.Integer)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'room_id', name='unique_unread'),
    )


class Notification(db.Model):
    """User Notifications Model"""
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    notification_type = db.Column(db.String(50))  # message, group_invite, mention, system
    title = db.Column(db.String(200))
    body = db.Column(db.Text)
    data = db.Column(db.Text)  # JSON data
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'type': self.notification_type,
            'title': self.title,
            'body': self.body,
            'data': json.loads(self.data) if self.data else {},
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class MediaCache(db.Model):
    """Cache for frequently accessed media URLs"""
    __tablename__ = 'media_cache'

    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(1000), unique=True, nullable=False)
    transformed_url = db.Column(db.String(1000))
    transformation = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True))
    access_count = db.Column(db.Integer, default=0)


# ============================================
# 5. HELPER FUNCTIONS
# ============================================

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_extension(filename: str) -> str:
    """Get file extension"""
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def get_file_category(filename: str) -> str:
    """Determine file category based on extension"""
    ext = get_file_extension(filename)
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return 'image'
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        return 'video'
    elif ext in ALLOWED_AUDIO_EXTENSIONS:
        return 'audio'
    elif ext in ALLOWED_DOCUMENT_EXTENSIONS:
        return 'document'
    else:
        return 'other'

def validate_phone_number(phone: str) -> bool:
    """Validate African phone numbers"""
    # Common African phone number patterns
    patterns = [
        r'^\+?(?:254|255|256|257|250|249|252|251|253|260|261|262|263|264|265|266|267|268|269|27|20|212|213|216|218|221|222|223|224|225|226|227|228|229|230|231|232|233|234|235|236|237|238|239|240|241|242|243|244|245|246|247|248|291|258)\d{7,12}$',
        r'^0\d{9}$',  # Local format
    ]
    return any(re.match(pattern, phone) for pattern in patterns)

def generate_unique_filename(original_filename: str) -> str:
    """Generate unique filename"""
    ext = get_file_extension(original_filename)
    unique_name = f"{uuid.uuid4().hex}_{int(time.time())}"
    return f"{unique_name}.{ext}" if ext else unique_name

def compress_image(file_data: BytesIO, max_size: Tuple[int, int] = (1920, 1080), quality: int = 85) -> BytesIO:
    """Compress and resize image"""
    try:
        image = Image.open(file_data)
        
        # Convert RGBA to RGB if necessary
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        # Resize if too large
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save compressed image
        output = BytesIO()
        image.save(output, format='JPEG', quality=quality, optimize=True)
        output.seek(0)
        
        return output
    except Exception as e:
        print(f"Image compression error: {e}")
        file_data.seek(0)
        return file_data

def get_media_type_string(extension: str) -> str:
    """Convert file extension to media type string"""
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return 'image'
    elif extension in ALLOWED_VIDEO_EXTENSIONS:
        return 'video'
    elif extension in ALLOWED_AUDIO_EXTENSIONS:
        return 'audio'
    elif extension in ALLOWED_DOCUMENT_EXTENSIONS:
        return 'document'
    return 'other'

def format_file_size(size_bytes: int) -> str:
    """Format file size to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

# ============================================
# 6. CLOUDINARY FUNCTIONS
# ============================================

def upload_to_cloudinary(
    file_data,
    folder: str = 'bantu_halii',
    public_id: Optional[str] = None,
    resource_type: str = 'auto',
    transformation: Optional[Dict] = None,
    eager: Optional[List] = None
) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
    """
    Upload file to Cloudinary
    Returns: (url, public_id, upload_info)
    """
    try:
        upload_options = {
            'folder': folder,
            'resource_type': resource_type,
            'quality': 'auto',
            'fetch_format': 'auto',
            'use_filename': True,
            'unique_filename': True,
            'overwrite': False,
            'invalidate': True,
        }
        
        if public_id:
            upload_options['public_id'] = public_id
        
        if transformation:
            upload_options['transformation'] = transformation
        
        if eager:
            upload_options['eager'] = eager
        
        # Upload
        result = cloudinary.uploader.upload(file_data, **upload_options)
        
        return result.get('secure_url'), result.get('public_id'), result
        
    except Exception as e:
        print(f"Cloudinary upload error: {str(e)}")
        return None, None, None

def upload_image_to_cloudinary(
    file_data,
    folder: str = 'bantu_halii/images',
    optimize: bool = True
) -> Tuple[Optional[str], Optional[str]]:
    """Upload image with optimization"""
    try:
        # Compress image before upload
        compressed = compress_image(file_data)
        
        # Upload with transformations
        transformations = [
            {'quality': 'auto:best'},
            {'fetch_format': 'auto'},
            {'width': 1920, 'crop': 'limit'},
        ]
        
        url, public_id, _ = upload_to_cloudinary(
            compressed,
            folder=folder,
            resource_type='image',
            eager=transformations
        )
        
        return url, public_id
        
    except Exception as e:
        print(f"Image upload error: {str(e)}")
        return None, None

def upload_video_to_cloudinary(
    file_data,
    folder: str = 'bantu_halii/videos'
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Upload video with thumbnail generation"""
    try:
        url, public_id, info = upload_to_cloudinary(
            file_data,
            folder=folder,
            resource_type='video',
            eager=[
                {'streaming_profile': 'full_hd', 'format': 'm3u8'},
                {'format': 'mp4', 'quality': 'auto'},
            ]
        )
        
        # Generate thumbnail
        thumbnail_url = None
        if public_id:
            thumbnail_url, _ = cloudinary_url(
                public_id,
                resource_type='video',
                format='jpg',
                transformation=[
                    {'start_offset': '2', 'crop': 'fill', 'width': 640, 'height': 360}
                ]
            )
        
        return url, public_id, thumbnail_url
        
    except Exception as e:
        print(f"Video upload error: {str(e)}")
        return None, None, None

def upload_audio_to_cloudinary(
    file_data,
    folder: str = 'bantu_halii/audio'
) -> Tuple[Optional[str], Optional[str]]:
    """Upload audio file"""
    try:
        url, public_id, _ = upload_to_cloudinary(
            file_data,
            folder=folder,
            resource_type='video',  # Cloudinary uses video for audio
            transformation={'quality': 'auto'}
        )
        
        return url, public_id
        
    except Exception as e:
        print(f"Audio upload error: {str(e)}")
        return None, None

def upload_document_to_cloudinary(
    file_data,
    filename: str,
    folder: str = 'bantu_halii/documents'
) -> Tuple[Optional[str], Optional[str]]:
    """Upload document"""
    try:
        url, public_id, _ = upload_to_cloudinary(
            file_data,
            folder=folder,
            resource_type='raw',
            public_id=filename.rsplit('.', 1)[0] if '.' in filename else filename
        )
        
        return url, public_id
        
    except Exception as e:
        print(f"Document upload error: {str(e)}")
        return None, None

def delete_cloudinary_asset(public_id: str, resource_type: str = 'image') -> bool:
    """Delete asset from Cloudinary"""
    try:
        if public_id:
            cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return True
        return False
    except Exception as e:
        print(f"Cloudinary delete error: {str(e)}")
        return False

def get_optimized_url(public_id: str, width: int = 800, height: int = 600, crop: str = 'fill') -> str:
    """Get optimized URL for an image"""
    try:
        url, _ = cloudinary_url(
            public_id,
            width=width,
            height=height,
            crop=crop,
            quality='auto',
            fetch_format='auto'
        )
        return url
    except Exception:
        return ''

# ============================================
# 7. DECORATORS AND MIDDLEWARE
# ============================================

def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'Authentication required', 'code': 'AUTH_REQUIRED'}), 401
            flash('Please log in to access Bantu Halii', 'info')
            session['next_url'] = request.url
            return redirect(url_for('login'))
        
        # Check if user still exists
        user = db.session.get(User, session['user_id'])
        if not user or user.is_deleted:
            session.clear()
            return redirect(url_for('login'))
        
        # Store user in g for request context
        g.current_user = user
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        # This is a placeholder for future admin functionality
        return f(*args, **kwargs)
    return decorated_function

def validate_json(f):
    """Decorator to validate JSON requests"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        return f(*args, **kwargs)
    return decorated_function

# Error handlers for file uploads
@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(error):
    """Handle file too large error"""
    if request.is_json:
        return jsonify({
            'error': 'File too large',
            'max_size': app.config['MAX_CONTENT_LENGTH'],
            'max_size_display': format_file_size(app.config['MAX_CONTENT_LENGTH'])
        }), 413
    flash('The uploaded file is too large', 'error')
    return redirect(request.url)

# ============================================
# 8. CONTEXT PROCESSORS
# ============================================

@app.context_processor
def inject_global_variables():
    """Inject global variables into all templates"""
    context = {
        'app_name': 'Bantu Halii',
        'app_tagline': 'Connecting Africa',
        'app_version': '1.0.0',
        'current_year': datetime.now().year,
        'bantu_africa_url': 'https://bantuafrica.com',
    }
    
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        if user:
            context['current_user'] = user
            context['unread_count'] = user.get_unread_count()
    
    return context

# ============================================
# 9. AUTHENTICATION ROUTES
# ============================================

@app.route('/')
def index():
    """Bantu Halii Landing Page"""
    if 'user_id' in session:
        return redirect(url_for('chat'))
    return render_template('index.html', active_form='login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User Login"""
    if 'user_id' in session:
        return redirect(url_for('chat'))
    
    if request.method == 'POST':
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            login_id = data.get('login_id', '').strip()
            password = data.get('password', '')
            remember_me = data.get('remember_me', False)
        else:
            login_id = request.form.get('login_id', '').strip()
            password = request.form.get('password', '')
            remember_me = request.form.get('remember_me') == 'on'
        
        # Validation
        if not login_id or not password:
            error_msg = 'Please provide both login ID and password'
            if request.is_json:
                return jsonify({'error': error_msg}), 400
            flash(error_msg, 'error')
            return render_template('index.html', active_form='login')
        
        # Find user
        user = User.query.filter(
            or_(
                User.username == login_id,
                User.phone_number == login_id,
                User.email == login_id
            ),
            User.is_deleted == False
        ).first()
        
        if not user:
            error_msg = 'No account found with those credentials'
            if request.is_json:
                return jsonify({'error': error_msg}), 401
            flash(error_msg, 'error')
            return render_template('index.html', active_form='login')
        
        # Check if account is locked
        if user.is_account_locked():
            time_left = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
            error_msg = f'Account is locked. Please try again in {time_left} minutes'
            if request.is_json:
                return jsonify({'error': error_msg}), 423
            flash(error_msg, 'error')
            return render_template('index.html', active_form='login')
        
        # Verify password
        if user.check_password(password):
            # Successful login
            user.reset_login_attempts()
            user.is_online = True
            user.last_seen = datetime.now(timezone.utc)
            user.user_status = UserStatus.ONLINE.value
            
            # Session management
            session.permanent = remember_me
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_uuid'] = user.user_uuid
            session['login_time'] = datetime.now(timezone.utc).isoformat()
            
            db.session.commit()
            
            # Redirect to next URL if set
            next_url = session.pop('next_url', None)
            redirect_url = next_url if next_url else url_for('chat')
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': f'Welcome back, {user.username}!',
                    'user': user.to_dict(include_private=True),
                    'redirect': redirect_url
                }), 200
            
            flash(f'Welcome back to Bantu Halii, {user.username}! 👋', 'success')
            return redirect(redirect_url)
        else:
            # Failed login
            user.increment_login_attempts()
            db.session.commit()
            
            attempts_left = MAX_LOGIN_ATTEMPTS - user.login_attempts
            error_msg = f'Invalid password. {attempts_left} attempts remaining'
            
            if request.is_json:
                return jsonify({
                    'error': error_msg,
                    'attempts_left': attempts_left
                }), 401
            
            flash(error_msg, 'error')
            return render_template('index.html', active_form='login')
    
    return render_template('index.html', active_form='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User Registration"""
    if 'user_id' in session:
        return redirect(url_for('chat'))
    
    if request.method == 'POST':
        # Handle both JSON and form data
        if request.is_json:
            data = request.get_json()
            username = data.get('username', '').strip()
            phone_number = data.get('phone_number', '').strip()
            email = data.get('email', '').strip().lower()
            password = data.get('password', '')
            confirm_password = data.get('confirm_password', '')
        else:
            username = request.form.get('username', '').strip()
            phone_number = request.form.get('phone_number', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        errors = []
        
        if not username:
            errors.append('Username is required')
        elif len(username) < 3:
            errors.append('Username must be at least 3 characters')
        elif len(username) > MAX_USERNAME_LENGTH:
            errors.append(f'Username must be less than {MAX_USERNAME_LENGTH} characters')
        elif not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers, and underscores')
        elif User.query.filter_by(username=username).first():
            errors.append('Username already taken')
        
        if not phone_number and not email:
            errors.append('Please provide either a phone number or email')
        
        if phone_number:
            if not validate_phone_number(phone_number):
                errors.append('Invalid phone number format')
            elif User.query.filter_by(phone_number=phone_number).first():
                errors.append('Phone number already registered')
        
        if email:
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                errors.append('Invalid email format')
            elif User.query.filter_by(email=email).first():
                errors.append('Email already registered')
        
        if not password:
            errors.append('Password is required')
        elif len(password) < PASSWORD_MIN_LENGTH:
            errors.append(f'Password must be at least {PASSWORD_MIN_LENGTH} characters')
        elif PASSWORD_COMPLEXITY:
            if not re.search(r'[A-Z]', password):
                errors.append('Password must contain at least one uppercase letter')
            if not re.search(r'[a-z]', password):
                errors.append('Password must contain at least one lowercase letter')
            if not re.search(r'\d', password):
                errors.append('Password must contain at least one number')
            if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
                errors.append('Password must contain at least one special character')
        
        if password != confirm_password:
            errors.append('Passwords do not match')
        
        # Return errors if any
        if errors:
            if request.is_json:
                return jsonify({'errors': errors}), 400
            for error in errors:
                flash(error, 'error')
            return render_template('index.html', active_form='register')
        
        # Create user
        try:
            user = User(
                username=username,
                phone_number=phone_number if phone_number else None,
                email=email if email else None,
                profile_pic=f"https://ui-avatars.com/api/?name={username[0].upper()}&background=4ECDC4&color=fff&size=200&bold=true"
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            # Auto login after registration
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_uuid'] = user.user_uuid
            session['login_time'] = datetime.now(timezone.utc).isoformat()
            
            user.is_online = True
            user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': f'Welcome to Bantu Halii, {username}! 🎉',
                    'user': user.to_dict(include_private=True),
                    'redirect': url_for('chat')
                }), 201
            
            flash(f'Welcome to Bantu Halii, {username}! Your account has been created successfully. 🌍', 'success')
            return redirect(url_for('chat'))
            
        except Exception as e:
            db.session.rollback()
            error_msg = f'Registration failed: {str(e)}'
            if request.is_json:
                return jsonify({'error': error_msg}), 500
            flash(error_msg, 'error')
            return render_template('index.html', active_form='register')
    
    return render_template('index.html', active_form='register')

@app.route('/logout')
@login_required
def logout():
    """User Logout"""
    user = db.session.get(User, session['user_id'])
    if user:
        user.is_online = False
        user.user_status = UserStatus.OFFLINE.value
        user.last_seen = datetime.now(timezone.utc)
        db.session.commit()
    
    # Emit offline status
    socketio.emit('user_offline', {
        'user_id': user.id if user else None,
        'username': user.username if user else 'Unknown'
    }, broadcast=True)
    
    session.clear()
    flash('You have been logged out of Bantu Halii. See you soon! 👋', 'info')
    return redirect(url_for('index'))

# ============================================
# 10. CHAT ROUTES
# ============================================

@app.route('/chat')
@login_required
def chat():
    """Main Chat Interface"""
    user = db.session.get(User, session['user_id'])
    
    # Get user's rooms with last message
    memberships = RoomMember.query.filter_by(
        user_id=user.id, 
        is_active=True
    ).order_by(RoomMember.is_pinned.desc()).all()
    
    rooms_data = []
    for membership in memberships:
        room = db.session.get(Room, membership.room_id)
        if room and not room.is_deleted:
            room_data = room.to_dict(user_id=user.id)
            
            # Get unread count
            unread = UnreadMessage.query.filter_by(
                user_id=user.id, 
                room_id=room.id
            ).first()
            room_data['unread_count'] = unread.count if unread else 0
            
            rooms_data.append(room_data)
    
    # Sort rooms: pinned first, then by last message time
    rooms_data.sort(key=lambda x: (
        not memberships[[r['id'] for r in rooms_data].index(x['id'])].is_pinned if x['id'] in [r['id'] for r in rooms_data] else False,
        x.get('last_message_at', ''),
    ), reverse=True)
    
    # Get contacts
    contacts = Contact.query.filter_by(
        user_id=user.id,
        is_blocked=False
    ).order_by(Contact.is_favorite.desc()).all()
    
    contact_users = []
    for contact in contacts:
        contact_user = db.session.get(User, contact.contact_id)
        if contact_user and not contact_user.is_deleted:
            contact_user_dict = contact_user.to_dict()
            contact_user_dict['contact_name'] = contact.contact_name
            contact_user_dict['is_favorite'] = contact.is_favorite
            contact_users.append(contact_user_dict)
    
    # Get all users for search (with pagination)
    page = request.args.get('page', 1, type=int)
    all_users = User.query.filter(
        User.id != user.id,
        User.is_deleted == False
    ).order_by(User.username).paginate(
        page=page, 
        per_page=USERS_PER_PAGE, 
        error_out=False
    )
    
    return render_template(
        'chat.html',
        user=user,
        rooms=rooms_data,
        contacts=contact_users,
        all_users=all_users
    )

@app.route('/chat/<int:room_id>')
@login_required
def chat_room(room_id):
    """Specific Chat Room"""
    user = db.session.get(User, session['user_id'])
    room = db.session.get(Room, room_id)
    
    if not room or room.is_deleted:
        flash('This conversation does not exist', 'error')
        return redirect(url_for('chat'))
    
    # Check if user is a member
    membership = RoomMember.query.filter_by(
        room_id=room_id, 
        user_id=user.id, 
        is_active=True
    ).first()
    
    if not membership and room.room_type != RoomType.BROADCAST.value:
        flash('You are not a member of this conversation', 'error')
        return redirect(url_for('chat'))
    
    # Get messages with pagination
    page = request.args.get('page', 1, type=int)
    messages = Message.query.filter_by(
        room_id=room_id,
        is_deleted=False
    ).order_by(Message.created_at.desc()).paginate(
        page=page,
        per_page=MESSAGES_PER_PAGE,
        error_out=False
    )
    
    # Mark messages as read
    unread_messages = Message.query.filter_by(
        room_id=room_id,
        receiver_id=user.id,
        is_read=False,
        is_deleted=False
    ).all()
    
    for msg in unread_messages:
        msg.mark_as_read()
    
    # Reset unread count
    unread = UnreadMessage.query.filter_by(
        user_id=user.id,
        room_id=room_id
    ).first()
    if unread:
        unread.count = 0
    
    db.session.commit()
    
    # Get room members
    members = RoomMember.query.filter_by(
        room_id=room_id,
        is_active=True
    ).all()
    
    member_users = []
    for member in members:
        member_user = db.session.get(User, member.user_id)
        if member_user and not member_user.is_deleted:
            member_users.append({
                **member_user.to_dict(),
                'role': member.role,
                'joined_at': member.joined_at.isoformat() if member.joined_at else None
            })
    
    return render_template(
        'chat.html',
        user=user,
        room=room.to_dict(user_id=user.id),
        messages=messages,
        members=member_users,
        active_room_id=room_id
    )

# ============================================
# 11. ROOM MANAGEMENT ROUTES (CONTINUED)
# ============================================

@app.route('/create_room', methods=['POST'])
@login_required
def create_room():
    """Create a new chat room or group"""
    user = db.session.get(User, session['user_id'])
    
    if request.is_json:
        data = request.get_json()
        room_name = data.get('room_name', '').strip()
        room_type = data.get('room_type', RoomType.GROUP.value)
        description = data.get('description', '').strip()
        members = data.get('members', [])
        is_public = data.get('is_public', False)
        is_encrypted = data.get('is_encrypted', False)
    else:
        room_name = request.form.get('room_name', '').strip()
        room_type = request.form.get('room_type', RoomType.GROUP.value)
        description = request.form.get('description', '').strip()
        members = request.form.getlist('members[]')
        is_public = request.form.get('is_public') == 'true'
        is_encrypted = request.form.get('is_encrypted') == 'true'
    
    # Validation
    if not room_name:
        error_msg = 'Room name is required'
        if request.is_json:
            return jsonify({'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('chat'))
    
    if len(room_name) > MAX_GROUP_NAME_LENGTH:
        error_msg = f'Room name must be less than {MAX_GROUP_NAME_LENGTH} characters'
        if request.is_json:
            return jsonify({'error': error_msg}), 400
        flash(error_msg, 'error')
        return redirect(url_for('chat'))
    
    # Validate room type
    if room_type not in [rt.value for rt in RoomType]:
        room_type = RoomType.GROUP.value
    
    try:
        # Create room
        room = Room(
            name=room_name,
            description=description if description else None,
            created_by=user.id,
            room_type=room_type,
            is_public=is_public,
            is_encrypted=is_encrypted,
            max_members=256 if room_type == RoomType.GROUP.value else 2
        )
        
        # Generate invite link for groups
        if room_type == RoomType.GROUP.value:
            room.generate_invite_link()
        
        db.session.add(room)
        db.session.flush()  # Get room ID
        
        # Add creator as owner
        creator_membership = RoomMember(
            room_id=room.id,
            user_id=user.id,
            role='owner'
        )
        db.session.add(creator_membership)
        
        # Add creator as admin
        creator_admin = RoomAdmin(
            room_id=room.id,
            user_id=user.id,
            promoted_by=user.id
        )
        db.session.add(creator_admin)
        
        # Add other members
        added_members = [user.id]  # Track added members to avoid duplicates
        
        for member_id in members:
            try:
                member_id = int(member_id)
                if member_id != user.id and member_id not in added_members:
                    # Check if user exists
                    member_user = db.session.get(User, member_id)
                    if member_user and not member_user.is_deleted:
                        # Check if not blocked
                        is_blocked = BlockedUser.query.filter_by(
                            user_id=user.id, 
                            blocked_user_id=member_id
                        ).first()
                        
                        if not is_blocked:
                            membership = RoomMember(
                                room_id=room.id,
                                user_id=member_id,
                                role='member'
                            )
                            db.session.add(membership)
                            added_members.append(member_id)
                            
                            # Create notification for added member
                            notification = Notification(
                                user_id=member_id,
                                notification_type='group_invite',
                                title=f'Added to {room_name}',
                                body=f'{user.username} added you to {room_name}',
                                data=json.dumps({'room_id': room.id, 'room_uuid': room.room_uuid})
                            )
                            db.session.add(notification)
            except (ValueError, TypeError):
                continue
        
        # Handle room picture upload
        if 'room_pic' in request.files:
            file = request.files['room_pic']
            if file and file.filename and allowed_file(file.filename):
                file_data = BytesIO(file.read())
                file_data.filename = file.filename
                
                url, public_id = upload_image_to_cloudinary(
                    file_data,
                    folder=f'rooms/{room.room_uuid}/profile'
                )
                
                if url:
                    room.room_pic = url
                    room.room_pic_public_id = public_id
        
        db.session.commit()
        
        # Emit socket event for new room
        room_data = room.to_dict(user_id=user.id)
        room_data['member_count'] = len(added_members)
        
        for member_id in added_members:
            socketio.emit('new_room', room_data, room=f'user_{member_id}')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': f'Room "{room_name}" created successfully!',
                'room': room_data
            }), 201
        
        flash(f'Room "{room_name}" created successfully! 🎉', 'success')
        return redirect(url_for('chat_room', room_id=room.id))
        
    except Exception as e:
        db.session.rollback()
        error_msg = f'Failed to create room: {str(e)}'
        if request.is_json:
            return jsonify({'error': error_msg}), 500
        flash(error_msg, 'error')
        return redirect(url_for('chat'))

@app.route('/room/<int:room_id>/join', methods=['POST'])
@login_required
def join_room(room_id):
    """Join a room via invite link"""
    user = db.session.get(User, session['user_id'])
    room = db.session.get(Room, room_id)
    
    if not room or room.is_deleted:
        if request.is_json:
            return jsonify({'error': 'Room not found'}), 404
        flash('Room not found', 'error')
        return redirect(url_for('chat'))
    
    # Check if already a member
    existing = RoomMember.query.filter_by(
        room_id=room_id, 
        user_id=user.id
    ).first()
    
    if existing:
        if existing.is_active:
            if request.is_json:
                return jsonify({'message': 'Already a member', 'room_id': room_id})
            flash('You are already a member of this room', 'info')
            return redirect(url_for('chat_room', room_id=room_id))
        else:
            # Rejoin
            existing.is_active = True
            existing.joined_at = datetime.now(timezone.utc)
            db.session.commit()
            
            if request.is_json:
                return jsonify({'success': True, 'message': 'Rejoined room successfully'})
            flash('You have rejoined the room', 'success')
            return redirect(url_for('chat_room', room_id=room_id))
    
    # Check room capacity
    member_count = RoomMember.query.filter_by(room_id=room_id, is_active=True).count()
    if member_count >= room.max_members:
        if request.is_json:
            return jsonify({'error': 'Room is full'}), 403
        flash('This room has reached its maximum capacity', 'error')
        return redirect(url_for('chat'))
    
    # Check if room is public or has invite
    invite_code = request.form.get('invite_code', '') if not request.is_json else request.get_json().get('invite_code', '')
    
    if not room.is_public and invite_code != room.invite_link:
        if request.is_json:
            return jsonify({'error': 'Invalid invite code'}), 403
        flash('Invalid invite code', 'error')
        return redirect(url_for('chat'))
    
    try:
        # Add member
        membership = RoomMember(
            room_id=room_id,
            user_id=user.id,
            role='member'
        )
        db.session.add(membership)
        
        # Notify room creator
        notification = Notification(
            user_id=room.created_by,
            notification_type='member_joined',
            title=f'New member in {room.name}',
            body=f'{user.username} joined {room.name}',
            data=json.dumps({'room_id': room_id, 'user_id': user.id})
        )
        db.session.add(notification)
        
        db.session.commit()
        
        # Emit socket event
        socketio.emit('user_joined_room', {
            'room_id': room_id,
            'user': user.to_dict(),
            'member_count': member_count + 1
        }, room=f'room_{room_id}')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': f'Joined {room.name} successfully!',
                'room': room.to_dict(user_id=user.id)
            })
        
        flash(f'Welcome to {room.name}! 🎉', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to join room: {str(e)}', 'error')
        return redirect(url_for('chat'))

@app.route('/room/<int:room_id>/leave', methods=['POST'])
@login_required
def leave_room(room_id):
    """Leave a room"""
    user = db.session.get(User, session['user_id'])
    
    membership = RoomMember.query.filter_by(
        room_id=room_id, 
        user_id=user.id, 
        is_active=True
    ).first()
    
    if not membership:
        if request.is_json:
            return jsonify({'error': 'Not a member of this room'}), 400
        flash('You are not a member of this room', 'error')
        return redirect(url_for('chat'))
    
    try:
        membership.is_active = False
        membership.left_at = datetime.now(timezone.utc)
        
        # If owner leaves, assign new owner or delete room
        room = db.session.get(Room, room_id)
        if membership.role == 'owner' and room.room_type == RoomType.GROUP.value:
            # Find another admin to promote
            next_admin = RoomAdmin.query.filter(
                RoomAdmin.room_id == room_id,
                RoomAdmin.user_id != user.id
            ).first()
            
            if next_admin:
                # Promote to owner
                next_membership = RoomMember.query.filter_by(
                    room_id=room_id, 
                    user_id=next_admin.user_id
                ).first()
                if next_membership:
                    next_membership.role = 'owner'
            else:
                # Find any active member to promote
                next_member = RoomMember.query.filter(
                    RoomMember.room_id == room_id,
                    RoomMember.user_id != user.id,
                    RoomMember.is_active == True
                ).first()
                
                if next_member:
                    next_member.role = 'owner'
                    # Also make admin
                    new_admin = RoomAdmin(
                        room_id=room_id,
                        user_id=next_member.user_id,
                        promoted_by=user.id
                    )
                    db.session.add(new_admin)
                else:
                    # No members left, delete room
                    room.is_deleted = True
                    room.deleted_at = datetime.now(timezone.utc)
        
        # If direct chat, just deactivate
        if room.room_type == RoomType.DIRECT.value:
            # Check if other user is still active
            other_member = RoomMember.query.filter(
                RoomMember.room_id == room_id,
                RoomMember.user_id != user.id,
                RoomMember.is_active == True
            ).first()
            
            if not other_member:
                room.is_deleted = True
                room.deleted_at = datetime.now(timezone.utc)
        
        db.session.commit()
        
        # Emit socket event
        socketio.emit('user_left_room', {
            'room_id': room_id,
            'user_id': user.id,
            'username': user.username
        }, room=f'room_{room_id}')
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Left room successfully'})
        
        flash('You have left the room', 'info')
        return redirect(url_for('chat'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to leave room: {str(e)}', 'error')
        return redirect(url_for('chat'))

@app.route('/room/<int:room_id>/members')
@login_required
def get_room_members(room_id):
    """Get room members"""
    user = db.session.get(User, session['user_id'])
    
    # Check membership
    membership = RoomMember.query.filter_by(
        room_id=room_id, 
        user_id=user.id, 
        is_active=True
    ).first()
    
    if not membership:
        return jsonify({'error': 'Not a member of this room'}), 403
    
    members = RoomMember.query.filter_by(
        room_id=room_id, 
        is_active=True
    ).all()
    
    members_data = []
    for member in members:
        member_user = db.session.get(User, member.user_id)
        if member_user and not member_user.is_deleted:
            member_data = member_user.to_dict()
            member_data['role'] = member.role
            member_data['joined_at'] = member.joined_at.isoformat() if member.joined_at else None
            member_data['is_muted'] = member.is_muted
            member_data['is_admin'] = RoomAdmin.query.filter_by(
                room_id=room_id, 
                user_id=member.user_id
            ).first() is not None
            members_data.append(member_data)
    
    return jsonify(members_data)

@app.route('/room/<int:room_id>/add_members', methods=['POST'])
@login_required
def add_room_members(room_id):
    """Add members to room"""
    user = db.session.get(User, session['user_id'])
    
    # Check if user is admin
    is_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user.id).first()
    if not is_admin or not is_admin.can_manage_members:
        if request.is_json:
            return jsonify({'error': 'Only admins can add members'}), 403
        flash('You do not have permission to add members', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    if request.is_json:
        data = request.get_json()
        new_members = data.get('members', [])
    else:
        new_members = request.form.getlist('members[]')
    
    if not new_members:
        if request.is_json:
            return jsonify({'error': 'No members specified'}), 400
        flash('Please select members to add', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    room = db.session.get(Room, room_id)
    current_count = RoomMember.query.filter_by(room_id=room_id, is_active=True).count()
    
    added_count = 0
    errors = []
    
    for member_id in new_members:
        try:
            member_id = int(member_id)
            
            # Check if already a member
            existing = RoomMember.query.filter_by(
                room_id=room_id, 
                user_id=member_id
            ).first()
            
            if existing and existing.is_active:
                errors.append(f'User {member_id} is already a member')
                continue
            
            # Check room capacity
            if current_count + added_count >= room.max_members:
                errors.append('Room is at maximum capacity')
                break
            
            # Check if user is blocked
            is_blocked = BlockedUser.query.filter_by(
                user_id=user.id, 
                blocked_user_id=member_id
            ).first()
            
            if is_blocked:
                errors.append(f'You have blocked user {member_id}')
                continue
            
            # Add or reactivate member
            if existing:
                existing.is_active = True
                existing.joined_at = datetime.now(timezone.utc)
                existing.role = 'member'
            else:
                membership = RoomMember(
                    room_id=room_id,
                    user_id=member_id,
                    role='member'
                )
                db.session.add(membership)
            
            added_count += 1
            
            # Notify new member
            notification = Notification(
                user_id=member_id,
                notification_type='added_to_group',
                title=f'Added to {room.name}',
                body=f'{user.username} added you to {room.name}',
                data=json.dumps({'room_id': room_id, 'added_by': user.id})
            )
            db.session.add(notification)
            
        except (ValueError, TypeError):
            errors.append(f'Invalid member ID: {member_id}')
    
    try:
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'added_count': added_count,
                'errors': errors if errors else None
            })
        
        if added_count > 0:
            flash(f'Added {added_count} member(s) to the room', 'success')
        if errors:
            for error in errors:
                flash(error, 'warning')
        
        return redirect(url_for('chat_room', room_id=room_id))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to add members: {str(e)}', 'error')
        return redirect(url_for('chat_room', room_id=room_id))

@app.route('/room/<int:room_id>/remove_member/<int:member_id>', methods=['POST'])
@login_required
def remove_room_member(room_id, member_id):
    """Remove a member from room"""
    user = db.session.get(User, session['user_id'])
    
    # Check if user is admin
    is_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user.id).first()
    if not is_admin or not is_admin.can_manage_members:
        if request.is_json:
            return jsonify({'error': 'Only admins can remove members'}), 403
        flash('You do not have permission to remove members', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    # Cannot remove yourself
    if member_id == user.id:
        if request.is_json:
            return jsonify({'error': 'Cannot remove yourself. Use leave instead.'}), 400
        flash('Cannot remove yourself. Use leave instead.', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    # Cannot remove the owner
    member_membership = RoomMember.query.filter_by(
        room_id=room_id, 
        user_id=member_id, 
        is_active=True
    ).first()
    
    if not member_membership:
        if request.is_json:
            return jsonify({'error': 'User is not a member of this room'}), 404
        flash('User is not a member of this room', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    if member_membership.role == 'owner':
        if request.is_json:
            return jsonify({'error': 'Cannot remove the room owner'}), 403
        flash('Cannot remove the room owner', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    try:
        member_membership.is_active = False
        member_membership.left_at = datetime.now(timezone.utc)
        
        # Remove admin status if applicable
        admin_status = RoomAdmin.query.filter_by(
            room_id=room_id, 
            user_id=member_id
        ).first()
        if admin_status:
            db.session.delete(admin_status)
        
        # Notify removed member
        room = db.session.get(Room, room_id)
        notification = Notification(
            user_id=member_id,
            notification_type='removed_from_group',
            title=f'Removed from {room.name}',
            body=f'You were removed from {room.name} by {user.username}',
            data=json.dumps({'room_id': room_id, 'removed_by': user.id})
        )
        db.session.add(notification)
        
        db.session.commit()
        
        # Emit socket event
        socketio.emit('member_removed', {
            'room_id': room_id,
            'user_id': member_id,
            'removed_by': user.id
        }, room=f'room_{room_id}')
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Member removed successfully'})
        
        flash('Member removed successfully', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to remove member: {str(e)}', 'error')
        return redirect(url_for('chat_room', room_id=room_id))

@app.route('/room/<int:room_id>/settings', methods=['GET', 'POST'])
@login_required
def room_settings(room_id):
    """Get or update room settings"""
    user = db.session.get(User, session['user_id'])
    
    # Check if user is admin
    is_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user.id).first()
    if not is_admin:
        if request.is_json:
            return jsonify({'error': 'Only admins can modify room settings'}), 403
        flash('You do not have permission to modify room settings', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    
    if request.method == 'GET':
        return jsonify(room.to_dict(user_id=user.id))
    
    # POST - Update settings
    try:
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
        
        # Update fields
        if 'name' in data:
            new_name = data['name'].strip()
            if new_name and len(new_name) <= MAX_GROUP_NAME_LENGTH:
                room.name = new_name
        
        if 'description' in data:
            room.description = data['description'].strip()
        
        if 'is_public' in data:
            room.is_public = data['is_public'] in [True, 'true', '1']
        
        if 'only_admins_can_send' in data:
            room.only_admins_can_send = data['only_admins_can_send'] in [True, 'true', '1']
        
        if 'disappearing_messages' in data:
            try:
                seconds = int(data['disappearing_messages'])
                if seconds >= 0:
                    room.disappearing_messages = seconds
            except (ValueError, TypeError):
                pass
        
        if 'max_members' in data:
            try:
                max_m = int(data['max_members'])
                if 2 <= max_m <= 1000:
                    room.max_members = max_m
            except (ValueError, TypeError):
                pass
        
        # Handle room picture
        if 'room_pic' in request.files:
            file = request.files['room_pic']
            if file and file.filename and allowed_file(file.filename):
                # Delete old picture
                if room.room_pic_public_id:
                    delete_cloudinary_asset(room.room_pic_public_id)
                
                file_data = BytesIO(file.read())
                file_data.filename = file.filename
                
                url, public_id = upload_image_to_cloudinary(
                    file_data,
                    folder=f'rooms/{room.room_uuid}/profile'
                )
                
                if url:
                    room.room_pic = url
                    room.room_pic_public_id = public_id
        
        room.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Emit update to room members
        socketio.emit('room_updated', room.to_dict(), room=f'room_{room_id}')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Room settings updated',
                'room': room.to_dict()
            })
        
        flash('Room settings updated successfully', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to update settings: {str(e)}', 'error')
        return redirect(url_for('chat_room', room_id=room_id))

# ============================================
# 12. MESSAGE ROUTES
# ============================================

@app.route('/room/<int:room_id>/messages')
@login_required
def get_room_messages(room_id):
    """Get messages for a room with pagination"""
    user = db.session.get(User, session['user_id'])
    
    # Check membership
    membership = RoomMember.query.filter_by(
        room_id=room_id, 
        user_id=user.id, 
        is_active=True
    ).first()
    
    if not membership:
        return jsonify({'error': 'Not a member of this room'}), 403
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', MESSAGES_PER_PAGE, type=int)
    before_id = request.args.get('before_id', type=int)
    after_id = request.args.get('after_id', type=int)
    
    # Build query
    query = Message.query.filter_by(
        room_id=room_id,
        is_deleted=False
    )
    
    # Filter by message ID for pagination
    if before_id:
        query = query.filter(Message.id < before_id)
    elif after_id:
        query = query.filter(Message.id > after_id)
    
    # Order by creation time
    query = query.order_by(Message.created_at.desc())
    
    # Paginate
    messages = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Convert to dict
    messages_data = [msg.to_dict() for msg in messages.items]
    
    # Mark messages as read
    unread_ids = [msg.id for msg in messages.items if not msg.is_read and msg.sender_id != user.id]
    if unread_ids:
        Message.query.filter(Message.id.in_(unread_ids)).update(
            {'is_read': True, 'read_at': datetime.now(timezone.utc)},
            synchronize_session=False
        )
        
        # Reset unread count
        unread = UnreadMessage.query.filter_by(user_id=user.id, room_id=room_id).first()
        if unread:
            unread.count = 0
        
        db.session.commit()
    
    return jsonify({
        'messages': messages_data,
        'has_next': messages.has_next,
        'has_prev': messages.has_prev,
        'page': messages.page,
        'pages': messages.pages,
        'total': messages.total
    })

@app.route('/message/<int:message_id>')
@login_required
def get_message(message_id):
    """Get a single message"""
    message = Message.query.get_or_404(message_id)
    
    # Check if user has access
    user = db.session.get(User, session['user_id'])
    
    if message.room_id:
        membership = RoomMember.query.filter_by(
            room_id=message.room_id, 
            user_id=user.id, 
            is_active=True
        ).first()
        if not membership:
            return jsonify({'error': 'Access denied'}), 403
    else:
        if message.sender_id != user.id and message.receiver_id != user.id:
            return jsonify({'error': 'Access denied'}), 403
    
    return jsonify(message.to_dict())

@app.route('/message/<int:message_id>/edit', methods=['POST'])
@login_required
def edit_message(message_id):
    """Edit a message"""
    user = db.session.get(User, session['user_id'])
    message = Message.query.get_or_404(message_id)
    
    # Only sender can edit
    if message.sender_id != user.id:
        if request.is_json:
            return jsonify({'error': 'You can only edit your own messages'}), 403
        flash('You can only edit your own messages', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    # Can only edit text messages
    if message.message_type not in ['text', 'mixed']:
        if request.is_json:
            return jsonify({'error': 'Only text messages can be edited'}), 400
        flash('Only text messages can be edited', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    # Check time limit (1 hour)
    time_diff = datetime.now(timezone.utc) - message.created_at
    if time_diff.total_seconds() > 3600:
        if request.is_json:
            return jsonify({'error': 'Messages can only be edited within 1 hour of sending'}), 400
        flash('Messages can only be edited within 1 hour of sending', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    if request.is_json:
        data = request.get_json()
        new_content = data.get('content', '').strip()
    else:
        new_content = request.form.get('content', '').strip()
    
    if not new_content:
        if request.is_json:
            return jsonify({'error': 'Message content cannot be empty'}), 400
        flash('Message content cannot be empty', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    try:
        message.content = new_content
        message.is_edited = True
        message.edited_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Notify room members about edit
        if message.room_id:
            socketio.emit('message_edited', {
                'message_id': message.id,
                'content': new_content,
                'edited_at': message.edited_at.isoformat(),
                'room_id': message.room_id
            }, room=f'room_{message.room_id}')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Message edited successfully',
                'data': message.to_dict()
            })
        
        flash('Message edited successfully', 'success')
        return redirect(request.referrer or url_for('chat'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to edit message: {str(e)}', 'error')
        return redirect(request.referrer or url_for('chat'))

@app.route('/message/<int:message_id>/delete', methods=['POST'])
@login_required
def delete_message(message_id):
    """Delete a message"""
    user = db.session.get(User, session['user_id'])
    message = Message.query.get_or_404(message_id)
    
    # Check permissions
    can_delete = False
    
    if message.sender_id == user.id:
        can_delete = True
    elif message.room_id:
        # Check if user is room admin with delete permissions
        admin = RoomAdmin.query.filter_by(
            room_id=message.room_id, 
            user_id=user.id
        ).first()
        if admin and admin.can_delete_messages:
            can_delete = True
    
    if not can_delete:
        if request.is_json:
            return jsonify({'error': 'You do not have permission to delete this message'}), 403
        flash('You do not have permission to delete this message', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    try:
        # Soft delete
        message.soft_delete(user.id)
        
        # Delete media from Cloudinary if exists
        if message.media_public_id:
            resource_type = 'image'
            if message.media_type == 'video':
                resource_type = 'video'
            elif message.media_type in ['audio', 'document']:
                resource_type = 'raw'
            
            delete_cloudinary_asset(message.media_public_id, resource_type)
        
        db.session.commit()
        
        # Notify room members
        if message.room_id:
            socketio.emit('message_deleted', {
                'message_id': message.id,
                'room_id': message.room_id,
                'deleted_by': user.id
            }, room=f'room_{message.room_id}')
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Message deleted successfully'})
        
        flash('Message deleted successfully', 'info')
        return redirect(request.referrer or url_for('chat'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to delete message: {str(e)}', 'error')
        return redirect(request.referrer or url_for('chat'))

@app.route('/message/<int:message_id>/react', methods=['POST'])
@login_required
def react_to_message(message_id):
    """Add or remove reaction to message"""
    user = db.session.get(User, session['user_id'])
    message = Message.query.get_or_404(message_id)
    
    if request.is_json:
        data = request.get_json()
        emoji = data.get('emoji', '')
    else:
        emoji = request.form.get('emoji', '')
    
    if not emoji:
        return jsonify({'error': 'Emoji is required'}), 400
    
    try:
        # Check if reaction already exists
        existing = MessageReaction.query.filter_by(
            message_id=message_id,
            user_id=user.id,
            emoji=emoji
        ).first()
        
        if existing:
            # Remove reaction
            db.session.delete(existing)
            db.session.commit()
            
            action = 'removed'
        else:
            # Add reaction
            reaction = MessageReaction(
                message_id=message_id,
                user_id=user.id,
                emoji=emoji
            )
            db.session.add(reaction)
            db.session.commit()
            
            action = 'added'
        
        # Get updated reactions
        reactions = MessageReaction.query.filter_by(message_id=message_id).all()
        reactions_data = [r.to_dict() for r in reactions]
        
        # Notify via socket
        if message.room_id:
            socketio.emit('message_reaction', {
                'message_id': message_id,
                'room_id': message.room_id,
                'user_id': user.id,
                'username': user.username,
                'emoji': emoji,
                'action': action,
                'reactions': reactions_data
            }, room=f'room_{message.room_id}')
        
        return jsonify({
            'success': True,
            'action': action,
            'reactions': reactions_data
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/message/<int:message_id>/pin', methods=['POST'])
@login_required
def pin_message(message_id):
    """Pin a message in a room"""
    user = db.session.get(User, session['user_id'])
    message = Message.query.get_or_404(message_id)
    
    if not message.room_id:
        return jsonify({'error': 'Can only pin messages in rooms'}), 400
    
    # Check if user is admin
    is_admin = RoomAdmin.query.filter_by(
        room_id=message.room_id, 
        user_id=user.id
    ).first()
    
    if not is_admin:
        return jsonify({'error': 'Only admins can pin messages'}), 403
    
    try:
        # Check if already pinned
        existing = PinnedMessage.query.filter_by(
            room_id=message.room_id,
            message_id=message_id
        ).first()
        
        if existing:
            # Unpin
            db.session.delete(existing)
            db.session.commit()
            action = 'unpinned'
        else:
            # Pin
            pinned = PinnedMessage(
                room_id=message.room_id,
                message_id=message_id,
                pinned_by=user.id
            )
            db.session.add(pinned)
            message.is_pinned = True
            db.session.commit()
            action = 'pinned'
        
        # Notify room
        socketio.emit('message_pinned', {
            'message_id': message_id,
            'room_id': message.room_id,
            'action': action,
            'pinned_by': user.username
        }, room=f'room_{message.room_id}')
        
        return jsonify({
            'success': True,
            'action': action,
            'message': message.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/room/<int:room_id>/pinned_messages')
@login_required
def get_pinned_messages(room_id):
    """Get pinned messages for a room"""
    user = db.session.get(User, session['user_id'])
    
    # Check membership
    membership = RoomMember.query.filter_by(
        room_id=room_id, 
        user_id=user.id, 
        is_active=True
    ).first()
    
    if not membership:
        return jsonify({'error': 'Not a member of this room'}), 403
    
    pinned = PinnedMessage.query.filter_by(room_id=room_id).all()
    messages = []
    
    for pin in pinned:
        message = db.session.get(Message, pin.message_id)
        if message and not message.is_deleted:
            msg_data = message.to_dict()
            msg_data['pinned_by'] = pin.pinned_by
            msg_data['pinned_at'] = pin.pinned_at.isoformat() if pin.pinned_at else None
            messages.append(msg_data)
    
    return jsonify(messages)

# ============================================
# 13. CONTACT MANAGEMENT ROUTES
# ============================================

@app.route('/contacts')
@login_required
def get_contacts():
    """Get user contacts"""
    user = db.session.get(User, session['user_id'])
    
    contacts = Contact.query.filter_by(
        user_id=user.id,
        is_blocked=False
    ).order_by(Contact.is_favorite.desc()).all()
    
    contacts_data = []
    for contact in contacts:
        contact_user = db.session.get(User, contact.contact_id)
        if contact_user and not contact_user.is_deleted:
            data = contact_user.to_dict()
            data['contact_name'] = contact.contact_name or contact_user.username
            data['is_favorite'] = contact.is_favorite
            data['added_at'] = contact.added_at.isoformat() if contact.added_at else None
            contacts_data.append(data)
    
    return jsonify(contacts_data)

@app.route('/add_contact/<int:contact_id>', methods=['POST'])
@login_required
def add_contact(contact_id):
    """Add a user to contacts"""
    user = db.session.get(User, session['user_id'])
    
    if contact_id == user.id:
        if request.is_json:
            return jsonify({'error': 'Cannot add yourself as contact'}), 400
        flash('Cannot add yourself as contact', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    # Check if user exists
    contact_user = db.session.get(User, contact_id)
    if not contact_user or contact_user.is_deleted:
        if request.is_json:
            return jsonify({'error': 'User not found'}), 404
        flash('User not found', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    # Check if already a contact
    existing = Contact.query.filter_by(
        user_id=user.id,
        contact_id=contact_id
    ).first()
    
    if existing:
        if request.is_json:
            return jsonify({'message': 'Already in contacts', 'contact': existing})
        flash('User is already in your contacts', 'info')
        return redirect(request.referrer or url_for('chat'))
    
    try:
        contact_name = None
        if request.is_json:
            contact_name = request.get_json().get('contact_name')
        else:
            contact_name = request.form.get('contact_name')
        
        contact = Contact(
            user_id=user.id,
            contact_id=contact_id,
            contact_name=contact_name
        )
        db.session.add(contact)
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Contact added successfully',
                'contact': contact_user.to_dict()
            }), 201
        
        flash(f'{contact_user.username} added to contacts!', 'success')
        return redirect(request.referrer or url_for('chat'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to add contact: {str(e)}', 'error')
        return redirect(request.referrer or url_for('chat'))

@app.route('/remove_contact/<int:contact_id>', methods=['POST'])
@login_required
def remove_contact(contact_id):
    """Remove a contact"""
    user = db.session.get(User, session['user_id'])
    
    contact = Contact.query.filter_by(
        user_id=user.id,
        contact_id=contact_id
    ).first()
    
    if not contact:
        if request.is_json:
            return jsonify({'error': 'Contact not found'}), 404
        flash('Contact not found', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    try:
        db.session.delete(contact)
        db.session.commit()
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Contact removed successfully'})
        
        flash('Contact removed successfully', 'info')
        return redirect(request.referrer or url_for('chat'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to remove contact: {str(e)}', 'error')
        return redirect(request.referrer or url_for('chat'))

@app.route('/block_user/<int:user_id>', methods=['POST'])
@login_required
def block_user(user_id):
    """Block a user"""
    user = db.session.get(User, session['user_id'])
    
    if user_id == user.id:
        if request.is_json:
            return jsonify({'error': 'Cannot block yourself'}), 400
        flash('Cannot block yourself', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    # Check if already blocked
    existing = BlockedUser.query.filter_by(
        user_id=user.id,
        blocked_user_id=user_id
    ).first()
    
    if existing:
        if request.is_json:
            return jsonify({'message': 'User is already blocked'})
        flash('User is already blocked', 'info')
        return redirect(request.referrer or url_for('chat'))
    
    try:
        reason = None
        if request.is_json:
            reason = request.get_json().get('reason')
        else:
            reason = request.form.get('reason')
        
        block = BlockedUser(
            user_id=user.id,
            blocked_user_id=user_id,
            reason=reason
        )
        db.session.add(block)
        
        # Remove from contacts if exists
        contact = Contact.query.filter_by(
            user_id=user.id,
            contact_id=user_id
        ).first()
        if contact:
            db.session.delete(contact)
        
        db.session.commit()
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'User blocked successfully'})
        
        flash('User blocked successfully', 'info')
        return redirect(request.referrer or url_for('chat'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to block user: {str(e)}', 'error')
        return redirect(request.referrer or url_for('chat'))

@app.route('/unblock_user/<int:user_id>', methods=['POST'])
@login_required
def unblock_user(user_id):
    """Unblock a user"""
    user = db.session.get(User, session['user_id'])
    
    block = BlockedUser.query.filter_by(
        user_id=user.id,
        blocked_user_id=user_id
    ).first()
    
    if not block:
        if request.is_json:
            return jsonify({'error': 'User is not blocked'}), 404
        flash('User is not blocked', 'error')
        return redirect(request.referrer or url_for('chat'))
    
    try:
        db.session.delete(block)
        db.session.commit()
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'User unblocked successfully'})
        
        flash('User unblocked successfully', 'success')
        return redirect(request.referrer or url_for('chat'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to unblock user: {str(e)}', 'error')
        return redirect(request.referrer or url_for('chat'))

# ============================================
# 14. SEARCH ROUTES
# ============================================

@app.route('/search')
@login_required
def search():
    """Search users, rooms, and messages"""
    user = db.session.get(User, session['user_id'])
    query = request.args.get('q', '').strip()
    search_type = request.args.get('type', 'all')  # all, users, rooms, messages
    
    if not query:
        return jsonify({'users': [], 'rooms': [], 'messages': []})
    
    results = {
        'users': [],
        'rooms': [],
        'messages': []
    }
    
    # Search users
    if search_type in ['all', 'users']:
        users = User.query.filter(
            User.id != user.id,
            User.is_deleted == False,
            or_(
                User.username.ilike(f'%{query}%'),
                User.phone_number.ilike(f'%{query}%'),
                User.email.ilike(f'%{query}%'),
                User.status.ilike(f'%{query}%')
            )
        ).limit(20).all()
        
        results['users'] = [u.to_dict() for u in users]
    
    # Search rooms
    if search_type in ['all', 'rooms']:
        # Get user's rooms
        member_room_ids = [
            m.room_id for m in RoomMember.query.filter_by(
                user_id=user.id, 
                is_active=True
            ).all()
        ]
        
        rooms = Room.query.filter(
            Room.id.in_(member_room_ids),
            Room.is_deleted == False,
            or_(
                Room.name.ilike(f'%{query}%'),
                Room.description.ilike(f'%{query}%')
            )
        ).limit(10).all()
        
        results['rooms'] = [r.to_dict(user_id=user.id) for r in rooms]
    
    # Search messages
    if search_type in ['all', 'messages']:
        messages = Message.query.filter(
            Message.content.ilike(f'%{query}%'),
            Message.is_deleted == False,
            or_(
                Message.sender_id == user.id,
                Message.receiver_id == user.id,
                Message.room_id.in_(
                    db.session.query(RoomMember.room_id).filter_by(
                        user_id=user.id, 
                        is_active=True
                    )
                )
            )
        ).order_by(Message.created_at.desc()).limit(20).all()
        
        results['messages'] = [m.to_dict() for m in messages]
    
    return jsonify(results)

@app.route('/search_users')
@login_required
def search_users():
    """Quick user search for adding contacts/members"""
    user = db.session.get(User, session['user_id'])
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify([])
    
    # Exclude current user and blocked users
    blocked_ids = [
        b.blocked_user_id for b in BlockedUser.query.filter_by(user_id=user.id).all()
    ] + [b.user_id for b in BlockedUser.query.filter_by(blocked_user_id=user.id).all()]
    
    users = User.query.filter(
        User.id != user.id,
        User.id.notin_(blocked_ids),
        User.is_deleted == False,
        or_(
            User.username.ilike(f'%{query}%'),
            User.phone_number.ilike(f'%{query}%'),
            User.email.ilike(f'%{query}%')
        )
    ).limit(20).all()
    
    return jsonify([u.to_dict() for u in users])

# ============================================
# 15. FILE UPLOAD ROUTES
# ============================================

@app.route('/upload/media', methods=['POST'])
@login_required
def upload_media():
    """Upload media file for messaging"""
    user = db.session.get(User, session['user_id'])
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if not file or not file.filename:
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed'}), 400
    
    # Check file size
    ext = get_file_extension(file.filename)
    category = get_file_category(file.filename)
    
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset position
    
    size_limits = {
        'image': MAX_IMAGE_SIZE,
        'video': MAX_VIDEO_SIZE,
        'audio': MAX_AUDIO_SIZE,
        'document': MAX_DOCUMENT_SIZE
    }
    
    if file_size > size_limits.get(category, MAX_IMAGE_SIZE):
        return jsonify({
            'error': f'File too large. Maximum size is {format_file_size(size_limits.get(category, MAX_IMAGE_SIZE))}'
        }), 413
    
    try:
        file_data = BytesIO(file.read())
        file_data.filename = secure_filename(file.filename)
        
        url = None
        public_id = None
        thumbnail_url = None
        
        if category == 'image':
            url, public_id = upload_image_to_cloudinary(
                file_data,
                folder=f'messages/{user.user_uuid}/images'
            )
        elif category == 'video':
            url, public_id, thumbnail_url = upload_video_to_cloudinary(
                file_data,
                folder=f'messages/{user.user_uuid}/videos'
            )
        elif category == 'audio':
            url, public_id = upload_audio_to_cloudinary(
                file_data,
                folder=f'messages/{user.user_uuid}/audio'
            )
        elif category == 'document':
            url, public_id = upload_document_to_cloudinary(
                file_data,
                file.filename,
                folder=f'messages/{user.user_uuid}/documents'
            )
        
        if url:
            return jsonify({
                'success': True,
                'url': url,
                'public_id': public_id,
                'thumbnail_url': thumbnail_url,
                'media_type': category,
                'file_size': file_size,
                'file_size_display': format_file_size(file_size),
                'filename': file.filename
            })
        else:
            return jsonify({'error': 'Upload failed'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/upload/profile_pic', methods=['POST'])
@login_required
def upload_profile_pic():
    """Upload profile picture"""
    user = db.session.get(User, session['user_id'])
    
    if 'profile_pic' not in request.files:
        if request.is_json:
            return jsonify({'error': 'No file provided'}), 400
        flash('No file selected', 'error')
        return redirect(url_for('profile'))
    
    file = request.files['profile_pic']
    
    if not file or not file.filename:
        if request.is_json:
            return jsonify({'error': 'No file selected'}), 400
        flash('No file selected', 'error')
        return redirect(url_for('profile'))
    
    if not allowed_file(file.filename):
        if request.is_json:
            return jsonify({'error': 'File type not allowed'}), 400
        flash('Invalid file type. Please use an image file.', 'error')
        return redirect(url_for('profile'))
    
    # Check file size
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_PROFILE_PIC_SIZE:
        if request.is_json:
            return jsonify({'error': f'File too large. Maximum size is {format_file_size(MAX_PROFILE_PIC_SIZE)}'}), 413
        flash(f'File too large. Maximum size is {format_file_size(MAX_PROFILE_PIC_SIZE)}.', 'error')
        return redirect(url_for('profile'))
    
    try:
        file_data = BytesIO(file.read())
        file_data.filename = secure_filename(file.filename)
        
        # Delete old profile picture if exists
        if user.profile_pic_public_id:
            delete_cloudinary_asset(user.profile_pic_public_id)
        
        # Upload new picture
        url, public_id = upload_image_to_cloudinary(
            file_data,
            folder=f'users/{user.user_uuid}/profile'
        )
        
        if url:
            user.profile_pic = url
            user.profile_pic_public_id = public_id
            db.session.commit()
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'url': url,
                    'message': 'Profile picture updated successfully'
                })
            
            flash('Profile picture updated successfully!', 'success')
        else:
            if request.is_json:
                return jsonify({'error': 'Upload failed'}), 500
            flash('Failed to upload profile picture', 'error')
        
        return redirect(url_for('profile'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to update profile picture: {str(e)}', 'error')
        return redirect(url_for('profile'))

  # ============================================
# 16. PROFILE MANAGEMENT ROUTES
# ============================================

@app.route('/profile')
@login_required
def profile():
    """User Profile Page"""
    user = db.session.get(User, session['user_id'])
    
    # Get user statistics
    stats = {
        'total_messages_sent': Message.query.filter_by(sender_id=user.id, is_deleted=False).count(),
        'total_rooms': RoomMember.query.filter_by(user_id=user.id, is_active=True).count(),
        'total_contacts': Contact.query.filter_by(user_id=user.id, is_blocked=False).count(),
        'total_media_shared': Message.query.filter(
            Message.sender_id == user.id,
            Message.media_url.isnot(None),
            Message.is_deleted == False
        ).count(),
        'account_age_days': (datetime.now(timezone.utc) - user.created_at).days if user.created_at else 0
    }
    
    # Get active devices
    devices = UserDevice.query.filter_by(user_id=user.id, is_active=True).all()
    
    # Get blocked users
    blocked = BlockedUser.query.filter_by(user_id=user.id).all()
    blocked_users = []
    for block in blocked:
        blocked_user = db.session.get(User, block.blocked_user_id)
        if blocked_user:
            blocked_users.append({
                **blocked_user.to_dict(),
                'blocked_at': block.blocked_at.isoformat() if block.blocked_at else None,
                'reason': block.reason
            })
    
    return render_template(
        'profile.html',
        user=user,
        stats=stats,
        devices=devices,
        blocked_users=blocked_users
    )

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Update user profile information"""
    user = db.session.get(User, session['user_id'])
    
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form
    
    errors = []
    updated_fields = []
    
    try:
        # Update username
        if 'username' in data and data['username']:
            new_username = data['username'].strip()
            
            if new_username != user.username:
                if len(new_username) < 3:
                    errors.append('Username must be at least 3 characters')
                elif len(new_username) > MAX_USERNAME_LENGTH:
                    errors.append(f'Username must be less than {MAX_USERNAME_LENGTH} characters')
                elif not re.match(r'^[a-zA-Z0-9_]+$', new_username):
                    errors.append('Username can only contain letters, numbers, and underscores')
                elif User.query.filter_by(username=new_username).first():
                    errors.append('Username already taken')
                else:
                    old_username = user.username
                    user.username = new_username
                    updated_fields.append('username')
                    
                    # Update session
                    session['username'] = new_username
                    
                    # Notify contacts about username change
                    contacts = Contact.query.filter_by(contact_id=user.id).all()
                    for contact in contacts:
                        notification = Notification(
                            user_id=contact.user_id,
                            notification_type='contact_update',
                            title='Contact Updated Username',
                            body=f'{old_username} changed their username to {new_username}',
                            data=json.dumps({
                                'user_id': user.id,
                                'old_username': old_username,
                                'new_username': new_username
                            })
                        )
                        db.session.add(notification)
        
        # Update email
        if 'email' in data:
            new_email = data['email'].strip().lower() if data['email'] else None
            
            if new_email != user.email:
                if new_email:
                    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', new_email):
                        errors.append('Invalid email format')
                    elif User.query.filter_by(email=new_email).first():
                        errors.append('Email already registered')
                    else:
                        user.email = new_email
                        updated_fields.append('email')
                else:
                    user.email = None
                    updated_fields.append('email')
        
        # Update phone number
        if 'phone_number' in data:
            new_phone = data['phone_number'].strip() if data['phone_number'] else None
            
            if new_phone != user.phone_number:
                if new_phone:
                    if not validate_phone_number(new_phone):
                        errors.append('Invalid phone number format')
                    elif User.query.filter_by(phone_number=new_phone).first():
                        errors.append('Phone number already registered')
                    else:
                        user.phone_number = new_phone
                        updated_fields.append('phone_number')
                else:
                    user.phone_number = None
                    updated_fields.append('phone_number')
        
        # Update status
        if 'status' in data:
            new_status = data['status'].strip()
            if len(new_status) <= MAX_STATUS_LENGTH:
                user.status = new_status if new_status else 'Hey there! I am using Bantu Halii 🌍'
                updated_fields.append('status')
            else:
                errors.append(f'Status must be less than {MAX_STATUS_LENGTH} characters')
        
        # Update bio
        if 'bio' in data:
            new_bio = data['bio'].strip()
            if len(new_bio) <= MAX_BIO_LENGTH:
                user.bio = new_bio
                updated_fields.append('bio')
            else:
                errors.append(f'Bio must be less than {MAX_BIO_LENGTH} characters')
        
        # Update settings
        if 'notifications_enabled' in data:
            user.notifications_enabled = data['notifications_enabled'] in [True, 'true', '1', 'on']
            updated_fields.append('notifications_enabled')
        
        if 'read_receipts_enabled' in data:
            user.read_receipts_enabled = data['read_receipts_enabled'] in [True, 'true', '1', 'on']
            updated_fields.append('read_receipts_enabled')
        
        if 'last_seen_visible' in data:
            user.last_seen_visible = data['last_seen_visible'] in [True, 'true', '1', 'on']
            updated_fields.append('last_seen_visible')
        
        if 'dark_mode' in data:
            user.dark_mode = data['dark_mode'] in [True, 'true', '1', 'on']
            updated_fields.append('dark_mode')
        
        if 'language' in data:
            new_lang = data['language'].strip()
            if new_lang in ['en', 'sw', 'fr', 'pt', 'ar', 'am', 'zu', 'ha', 'yo', 'ig']:
                user.language = new_lang
                updated_fields.append('language')
        
        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                
                if file_size <= MAX_PROFILE_PIC_SIZE:
                    # Delete old picture
                    if user.profile_pic_public_id:
                        delete_cloudinary_asset(user.profile_pic_public_id)
                    
                    file_data = BytesIO(file.read())
                    file_data.filename = secure_filename(file.filename)
                    
                    url, public_id = upload_image_to_cloudinary(
                        file_data,
                        folder=f'users/{user.user_uuid}/profile'
                    )
                    
                    if url:
                        user.profile_pic = url
                        user.profile_pic_public_id = public_id
                        updated_fields.append('profile_pic')
                else:
                    errors.append(f'Profile picture must be less than {format_file_size(MAX_PROFILE_PIC_SIZE)}')
        
        if errors:
            db.session.rollback()
            if request.is_json:
                return jsonify({'errors': errors}), 400
            
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('profile'))
        
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Emit profile update to connected users
        socketio.emit('profile_updated', {
            'user_id': user.id,
            'updated_fields': updated_fields,
            'user': user.to_dict()
        }, room=f'user_{user.id}')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Profile updated successfully',
                'updated_fields': updated_fields,
                'user': user.to_dict(include_private=True)
            })
        
        flash('Profile updated successfully! ✅', 'success')
        return redirect(url_for('profile'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to update profile: {str(e)}', 'error')
        return redirect(url_for('profile'))

@app.route('/profile/change_password', methods=['POST'])
@login_required
def change_password():
    """Change user password"""
    user = db.session.get(User, session['user_id'])
    
    if request.is_json:
        data = request.get_json()
        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
    else:
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
    
    errors = []
    
    # Verify current password
    if not user.check_password(current_password):
        errors.append('Current password is incorrect')
    
    # Validate new password
    if not new_password:
        errors.append('New password is required')
    elif len(new_password) < PASSWORD_MIN_LENGTH:
        errors.append(f'Password must be at least {PASSWORD_MIN_LENGTH} characters')
    elif PASSWORD_COMPLEXITY:
        if not re.search(r'[A-Z]', new_password):
            errors.append('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', new_password):
            errors.append('Password must contain at least one lowercase letter')
        if not re.search(r'\d', new_password):
            errors.append('Password must contain at least one number')
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            errors.append('Password must contain at least one special character')
    
    if new_password != confirm_password:
        errors.append('Passwords do not match')
    
    if new_password == current_password:
        errors.append('New password must be different from current password')
    
    if errors:
        if request.is_json:
            return jsonify({'errors': errors}), 400
        
        for error in errors:
            flash(error, 'error')
        return redirect(url_for('profile'))
    
    try:
        user.set_password(new_password)
        user.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        # Logout all other devices for security
        UserDevice.query.filter(
            UserDevice.user_id == user.id,
            UserDevice.device_id != request.headers.get('X-Device-ID', '')
        ).update({'is_active': False})
        db.session.commit()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Password changed successfully. Other devices have been logged out.'
            })
        
        flash('Password changed successfully! Other devices have been logged out for security. 🔒', 'success')
        return redirect(url_for('profile'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to change password: {str(e)}', 'error')
        return redirect(url_for('profile'))

@app.route('/profile/delete_account', methods=['POST'])
@login_required
def delete_account():
    """Delete user account (soft delete)"""
    user = db.session.get(User, session['user_id'])
    
    if request.is_json:
        data = request.get_json()
        password = data.get('password', '')
        confirmation = data.get('confirmation', '')
    else:
        password = request.form.get('password', '')
        confirmation = request.form.get('confirmation', '')
    
    # Verify password
    if not user.check_password(password):
        if request.is_json:
            return jsonify({'error': 'Incorrect password'}), 403
        flash('Incorrect password. Account deletion cancelled.', 'error')
        return redirect(url_for('profile'))
    
    # Confirm deletion
    if confirmation != 'DELETE':
        if request.is_json:
            return jsonify({'error': 'Please type DELETE to confirm'}), 400
        flash('Please type DELETE to confirm account deletion.', 'error')
        return redirect(url_for('profile'))
    
    try:
        # Soft delete user
        user.is_deleted = True
        user.deleted_at = datetime.now(timezone.utc)
        user.is_online = False
        user.user_status = UserStatus.OFFLINE.value
        
        # Leave all rooms
        memberships = RoomMember.query.filter_by(user_id=user.id, is_active=True).all()
        for membership in memberships:
            membership.is_active = False
            membership.left_at = datetime.now(timezone.utc)
        
        # Deactivate all devices
        UserDevice.query.filter_by(user_id=user.id).update({'is_active': False})
        
        # Delete all messages (soft delete)
        Message.query.filter(
            or_(Message.sender_id == user.id, Message.receiver_id == user.id)
        ).update({
            'is_deleted': True,
            'deleted_at': datetime.now(timezone.utc),
            'deleted_by': user.id
        })
        
        db.session.commit()
        
        # Clear session
        session.clear()
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Your account has been deleted. You can reactivate it within 30 days by logging in.'
            })
        
        flash('Your account has been deleted. You can reactivate it within 30 days by logging in.', 'info')
        return redirect(url_for('index'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to delete account: {str(e)}', 'error')
        return redirect(url_for('profile'))

@app.route('/profile/devices')
@login_required
def get_devices():
    """Get user's active devices"""
    user = db.session.get(User, session['user_id'])
    
    devices = UserDevice.query.filter_by(user_id=user.id, is_active=True).all()
    
    devices_data = []
    for device in devices:
        devices_data.append({
            'id': device.id,
            'device_id': device.device_id,
            'device_name': device.device_name,
            'device_type': device.device_type,
            'platform': device.platform,
            'ip_address': device.ip_address,
            'last_active': device.last_active.isoformat() if device.last_active else None,
            'is_current': device.device_id == request.headers.get('X-Device-ID', '')
        })
    
    return jsonify(devices_data)

@app.route('/profile/devices/<device_id>/logout', methods=['POST'])
@login_required
def logout_device(device_id):
    """Logout a specific device"""
    user = db.session.get(User, session['user_id'])
    
    device = UserDevice.query.filter_by(
        user_id=user.id,
        device_id=device_id
    ).first()
    
    if not device:
        if request.is_json:
            return jsonify({'error': 'Device not found'}), 404
        flash('Device not found', 'error')
        return redirect(url_for('profile'))
    
    try:
        device.is_active = False
        db.session.commit()
        
        # Emit logout to that device
        socketio.emit('force_logout', {
            'message': 'You have been logged out from this device',
            'device_id': device_id
        }, room=f'device_{device_id}')
        
        if request.is_json:
            return jsonify({'success': True, 'message': 'Device logged out successfully'})
        
        flash('Device logged out successfully', 'success')
        return redirect(url_for('profile'))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to logout device: {str(e)}', 'error')
        return redirect(url_for('profile'))

# ============================================
# 17. NOTIFICATION ROUTES
# ============================================

@app.route('/notifications')
@login_required
def get_notifications():
    """Get user notifications"""
    user = db.session.get(User, session['user_id'])
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    unread_only = request.args.get('unread_only', 'false').lower() == 'true'
    
    query = Notification.query.filter_by(user_id=user.id)
    
    if unread_only:
        query = query.filter_by(is_read=False)
    
    notifications = query.order_by(Notification.created_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return jsonify({
        'notifications': [n.to_dict() for n in notifications.items],
        'has_next': notifications.has_next,
        'has_prev': notifications.has_prev,
        'page': notifications.page,
        'pages': notifications.pages,
        'total': notifications.total,
        'unread_count': Notification.query.filter_by(user_id=user.id, is_read=False).count()
    })

@app.route('/notifications/unread_count')
@login_required
def get_unread_notification_count():
    """Get unread notification count"""
    user = db.session.get(User, session['user_id'])
    
    count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    
    return jsonify({'count': count})

@app.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    user = db.session.get(User, session['user_id'])
    
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=user.id
    ).first()
    
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
    
    try:
        notification.is_read = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Notification marked as read'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/notifications/read_all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read"""
    user = db.session.get(User, session['user_id'])
    
    try:
        Notification.query.filter_by(user_id=user.id, is_read=False).update(
            {'is_read': True}
        )
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'All notifications marked as read'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """Delete a notification"""
    user = db.session.get(User, session['user_id'])
    
    notification = Notification.query.filter_by(
        id=notification_id,
        user_id=user.id
    ).first()
    
    if not notification:
        return jsonify({'error': 'Notification not found'}), 404
    
    try:
        db.session.delete(notification)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Notification deleted'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# ============================================
# 18. SOCKET.IO EVENTS
# ============================================

# Store connected users in memory
connected_users = {}
typing_users = {}

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    if 'user_id' in session:
        user_id = session['user_id']
        user = db.session.get(User, user_id)
        
        if user:
            # Update user status
            user.is_online = True
            user.user_status = UserStatus.ONLINE.value
            user.last_seen = datetime.now(timezone.utc)
            db.session.commit()
            
            # Store connection
            connected_users[request.sid] = {
                'user_id': user_id,
                'username': user.username,
                'connected_at': datetime.now(timezone.utc).isoformat()
            }
            
            # Join personal room
            join_room(f'user_{user_id}')
            
            # Register device if device ID provided
            device_id = request.args.get('device_id')
            if device_id:
                join_room(f'device_{device_id}')
                
                # Update or create device
                existing_device = UserDevice.query.filter_by(
                    user_id=user_id,
                    device_id=device_id
                ).first()
                
                if existing_device:
                    existing_device.is_active = True
                    existing_device.last_active = datetime.now(timezone.utc)
                    existing_device.ip_address = request.remote_addr
                    existing_device.user_agent = request.headers.get('User-Agent', '')
                else:
                    device = UserDevice(
                        user_id=user_id,
                        device_id=device_id,
                        device_name=request.args.get('device_name', 'Unknown Device'),
                        device_type=request.args.get('device_type', 'unknown'),
                        platform=request.args.get('platform', 'web'),
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent', '')
                    )
                    db.session.add(device)
                
                db.session.commit()
            
            # Notify contacts that user is online
            notify_contacts_status(user_id, True)
            
            # Send pending notifications
            pending_notifications = Notification.query.filter_by(
                user_id=user_id,
                is_read=False
            ).order_by(Notification.created_at.desc()).limit(10).all()
            
            if pending_notifications:
                emit('pending_notifications', [n.to_dict() for n in pending_notifications])
            
            # Join active rooms
            memberships = RoomMember.query.filter_by(user_id=user_id, is_active=True).all()
            for membership in memberships:
                join_room(f'room_{membership.room_id}')
                emit('user_joined_room', {
                    'room_id': membership.room_id,
                    'user_id': user_id,
                    'username': user.username,
                    'profile_pic': user.profile_pic,
                    'is_online': True
                }, room=f'room_{membership.room_id}', include_self=False)
            
            print(f'✅ {user.username} connected to Bantu Halii (SID: {request.sid})')
        else:
            emit('error', {'message': 'User not found'})
            disconnect()
            return
    else:
        emit('error', {'message': 'Not authenticated'})
        disconnect()
        return
    
    # Acknowledge connection
    emit('connected', {
        'user_id': user_id,
        'message': 'Connected to Bantu Halii successfully!',
        'server_time': datetime.now(timezone.utc).isoformat()
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    if request.sid in connected_users:
        user_data = connected_users[request.sid]
        user_id = user_data['user_id']
        user = db.session.get(User, user_id)
        
        if user:
            # Check if user has other active connections
            other_connections = [
                sid for sid, data in connected_users.items()
                if data['user_id'] == user_id and sid != request.sid
            ]
            
            if not other_connections:
                # User is completely offline
                user.is_online = False
                user.user_status = UserStatus.OFFLINE.value
                user.last_seen = datetime.now(timezone.utc)
                db.session.commit()
                
                # Notify contacts
                notify_contacts_status(user_id, False)
                
                # Notify rooms
                memberships = RoomMember.query.filter_by(user_id=user_id, is_active=True).all()
                for membership in memberships:
                    leave_room(f'room_{membership.room_id}')
                    emit('user_left_room', {
                        'room_id': membership.room_id,
                        'user_id': user_id,
                        'username': user.username,
                        'is_online': False,
                        'last_seen': user.last_seen.isoformat()
                    }, room=f'room_{membership.room_id}')
            
            # Clean up typing status
            if user_id in typing_users:
                for room_id in typing_users[user_id]:
                    emit('user_stopped_typing', {
                        'user_id': user_id,
                        'username': user.username,
                        'room_id': room_id
                    }, room=f'room_{room_id}')
                del typing_users[user_id]
        
        # Remove from connected users
        del connected_users[request.sid]
        print(f'❌ {user_data.get("username", "Unknown")} disconnected from Bantu Halii')

@socketio.on('join_room')
def handle_join_room(data):
    """Join a specific chat room"""
    if 'user_id' not in session:
        emit('error', {'message': 'Not authenticated'})
        return
    
    user_id = session['user_id']
    room_id = data.get('room_id')
    
    if not room_id:
        emit('error', {'message': 'Room ID is required'})
        return
    
    # Check if user is a member
    membership = RoomMember.query.filter_by(
        room_id=room_id,
        user_id=user_id,
        is_active=True
    ).first()
    
    if not membership:
        emit('error', {'message': 'You are not a member of this room'})
        return
    
    # Join the room
    join_room(f'room_{room_id}')
    
    user = db.session.get(User, user_id)
    room = db.session.get(Room, room_id)
    
    # Mark messages as read
    unread_messages = Message.query.filter_by(
        room_id=room_id,
        receiver_id=user_id,
        is_read=False,
        is_deleted=False
    ).all()
    
    for msg in unread_messages:
        msg.mark_as_read()
    
    # Reset unread count
    unread = UnreadMessage.query.filter_by(user_id=user_id, room_id=room_id).first()
    if unread:
        unread.count = 0
    
    db.session.commit()
    
    # Notify room members
    emit('user_joined_room', {
        'room_id': room_id,
        'user_id': user_id,
        'username': user.username,
        'profile_pic': user.profile_pic,
        'is_online': True
    }, room=f'room_{room_id}', include_self=False)
    
    # Send room info back
    emit('room_joined', {
        'room_id': room_id,
        'room': room.to_dict(user_id=user_id),
        'online_members': get_online_members(room_id)
    })
    
    print(f'🏠 {user.username} joined room {room.name}')

@socketio.on('leave_room')
def handle_leave_room(data):
    """Leave a specific chat room"""
    if 'user_id' not in session:
        emit('error', {'message': 'Not authenticated'})
        return
    
    user_id = session['user_id']
    room_id = data.get('room_id')
    
    if not room_id:
        emit('error', {'message': 'Room ID is required'})
        return
    
    leave_room(f'room_{room_id}')
    
    user = db.session.get(User, user_id)
    room = db.session.get(Room, room_id)
    
    if room and user:
        emit('user_left_room', {
            'room_id': room_id,
            'user_id': user_id,
            'username': user.username,
            'is_online': user.is_online,
            'last_seen': user.last_seen.isoformat() if user.last_seen else None
        }, room=f'room_{room_id}')
        
        print(f'🚪 {user.username} left room {room.name}')

@socketio.on('send_message')
def handle_send_message(data):
    """Handle sending a message"""
    if 'user_id' not in session:
        emit('error', {'message': 'Not authenticated'})
        return
    
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    
    if not user:
        emit('error', {'message': 'User not found'})
        return
    
    room_id = data.get('room_id')
    content = data.get('content', '').strip()
    message_type = data.get('message_type', MessageType.TEXT.value)
    media_url = data.get('media_url')
    media_type = data.get('media_type')
    media_public_id = data.get('media_public_id')
    media_size = data.get('media_size')
    media_duration = data.get('media_duration')
    media_width = data.get('media_width')
    media_height = data.get('media_height')
    thumbnail_url = data.get('thumbnail_url')
    reply_to_id = data.get('reply_to_id')
    
    # Validation
    if not room_id:
        emit('error', {'message': 'Room ID is required'})
        return
    
    if not content and not media_url:
        emit('error', {'message': 'Message cannot be empty'})
        return
    
    if content and len(content) > MAX_MESSAGE_LENGTH:
        emit('error', {'message': f'Message must be less than {MAX_MESSAGE_LENGTH} characters'})
        return
    
    # Check if user is a member of the room
    membership = RoomMember.query.filter_by(
        room_id=room_id,
        user_id=user_id,
        is_active=True
    ).first()
    
    if not membership:
        emit('error', {'message': 'You are not a member of this room'})
        return
    
    # Check if muted
    if membership.is_muted:
        if membership.muted_until and membership.muted_until > datetime.now(timezone.utc):
            emit('error', {'message': 'You are muted in this room'})
            return
    
    # Check if only admins can send
    room = db.session.get(Room, room_id)
    if room.only_admins_can_send:
        is_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user_id).first()
        if not is_admin:
            emit('error', {'message': 'Only admins can send messages in this room'})
            return
    
    # Check if replying to a message
    if reply_to_id:
        reply_message = Message.query.get(reply_to_id)
        if not reply_message or reply_message.is_deleted:
            reply_to_id = None
    
    try:
        # Create message
        message = Message(
            sender_id=user_id,
            room_id=room_id,
            content=content if content else None,
            message_type=message_type,
            media_url=media_url,
            media_public_id=media_public_id,
            media_type=media_type,
            media_size=media_size,
            media_duration=media_duration,
            media_width=media_width,
            media_height=media_height,
            thumbnail_url=thumbnail_url,
            reply_to_id=reply_to_id,
            is_delivered=True,
            delivered_at=datetime.now(timezone.utc)
        )
        
        # Handle disappearing messages
        if room.disappearing_messages > 0:
            message.disappear_at = datetime.now(timezone.utc) + timedelta(seconds=room.disappearing_messages)
        
        db.session.add(message)
        
        # Update room last message time
        room.last_message_at = message.created_at
        
        # Update unread counts for other members
        other_members = RoomMember.query.filter(
            RoomMember.room_id == room_id,
            RoomMember.user_id != user_id,
            RoomMember.is_active == True
        ).all()
        
        for member in other_members:
            # Update or create unread count
            unread = UnreadMessage.query.filter_by(
                user_id=member.user_id,
                room_id=room_id
            ).first()
            
            if unread:
                unread.count += 1
                unread.last_message_id = message.id
            else:
                unread = UnreadMessage(
                    user_id=member.user_id,
                    room_id=room_id,
                    count=1,
                    last_message_id=message.id
                )
                db.session.add(unread)
            
            # Create notification for offline users
            member_user = db.session.get(User, member.user_id)
            if member_user and not member_user.is_online and member_user.notifications_enabled:
                notification = Notification(
                    user_id=member_user.id,
                    notification_type='new_message',
                    title=f'New message in {room.name}',
                    body=f'{user.username}: {content[:100] if content else "Sent a media file"}',
                    data=json.dumps({
                        'room_id': room_id,
                        'message_id': message.id,
                        'sender_id': user_id
                    })
                )
                db.session.add(notification)
        
        db.session.commit()
        
        # Prepare message data
        message_data = message.to_dict()
        
        # Emit message to room
        emit('new_message', message_data, room=f'room_{room_id}')
        
        # Send delivery confirmation to sender
        emit('message_delivered', {
            'message_id': message.id,
            'message_uuid': message.message_uuid,
            'room_id': room_id,
            'delivered_at': message.delivered_at.isoformat()
        })
        
        print(f'💬 Message from {user.username} in room {room.name}: {content[:50] if content else "[Media]"}')
        
    except Exception as e:
        db.session.rollback()
        emit('error', {'message': f'Failed to send message: {str(e)}'})
        print(f'Error sending message: {str(e)}')

@socketio.on('typing')
def handle_typing(data):
    """Handle typing indicator"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    room_id = data.get('room_id')
    
    if not room_id:
        return
    
    user = db.session.get(User, user_id)
    if not user:
        return
    
    # Update typing status
    if user_id not in typing_users:
        typing_users[user_id] = set()
    
    typing_users[user_id].add(room_id)
    
    # Update user's last typing time
    user.last_typing = datetime.now(timezone.utc)
    user.user_status = UserStatus.TYPING.value
    db.session.commit()
    
    # Emit typing event to room
    emit('user_typing', {
        'user_id': user_id,
        'username': user.username,
        'room_id': room_id,
        'is_typing': True
    }, room=f'room_{room_id}', include_self=False)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    """Handle stop typing indicator"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    room_id = data.get('room_id')
    
    if not room_id:
        return
    
    user = db.session.get(User, user_id)
    if not user:
        return
    
    # Clear typing status for this room
    if user_id in typing_users:
        typing_users[user_id].discard(room_id)
        
        if not typing_users[user_id]:
            del typing_users[user_id]
    
    # Update user status
    user.user_status = UserStatus.ONLINE.value if user.is_online else UserStatus.OFFLINE.value
    db.session.commit()
    
    # Emit stop typing event
    emit('user_stopped_typing', {
        'user_id': user_id,
        'username': user.username,
        'room_id': room_id,
        'is_typing': False
    }, room=f'room_{room_id}', include_self=False)

@socketio.on('mark_read')
def handle_mark_read(data):
    """Mark messages as read"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    message_ids = data.get('message_ids', [])
    room_id = data.get('room_id')
    
    if not message_ids:
        return
    
    try:
        # Update message read status
        Message.query.filter(
            Message.id.in_(message_ids),
            Message.is_read == False
        ).update({
            'is_read': True,
            'read_at': datetime.now(timezone.utc)
        }, synchronize_session=False)
        
        # Create read receipts
        for msg_id in message_ids:
            existing = MessageRead.query.filter_by(
                message_id=msg_id,
                user_id=user_id
            ).first()
            
            if not existing:
                read_receipt = MessageRead(
                    message_id=msg_id,
                    user_id=user_id
                )
                db.session.add(read_receipt)
        
        # Reset unread count
        if room_id:
            unread = UnreadMessage.query.filter_by(user_id=user_id, room_id=room_id).first()
            if unread:
                unread.count = 0
        
        db.session.commit()
        
        # Notify room about read receipts
        if room_id:
            emit('messages_read', {
                'message_ids': message_ids,
                'user_id': user_id,
                'room_id': room_id,
                'read_at': datetime.now(timezone.utc).isoformat()
            }, room=f'room_{room_id}')
        
    except Exception as e:
        db.session.rollback()
        print(f'Error marking messages as read: {str(e)}')

@socketio.on('user_status_change')
def handle_user_status_change(data):
    """Handle user status change (online, away, busy)"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    new_status = data.get('status')
    
    if new_status not in [s.value for s in UserStatus]:
        return
    
    user = db.session.get(User, user_id)
    if not user:
        return
    
    user.user_status = new_status
    db.session.commit()
    
    # Notify contacts
    contacts = Contact.query.filter_by(contact_id=user_id).all()
    for contact in contacts:
        emit('contact_status_changed', {
            'user_id': user_id,
            'status': new_status,
            'username': user.username
        }, room=f'user_{contact.user_id}')

@socketio.on('voice_call_start')
def handle_voice_call_start(data):
    """Handle voice call initiation"""
    if 'user_id' not in session:
        emit('error', {'message': 'Not authenticated'})
        return
    
    caller_id = session['user_id']
    receiver_id = data.get('receiver_id')
    room_id = data.get('room_id')
    call_type = data.get('call_type', 'voice')  # voice or video
    
    if not receiver_id:
        emit('error', {'message': 'Receiver ID is required'})
        return
    
    caller = db.session.get(User, caller_id)
    receiver = db.session.get(User, receiver_id)
    
    if not caller or not receiver:
        emit('error', {'message': 'User not found'})
        return
    
    # Check if receiver is blocked
    is_blocked = BlockedUser.query.filter_by(
        user_id=receiver_id,
        blocked_user_id=caller_id
    ).first()
    
    if is_blocked:
        emit('error', {'message': 'You cannot call this user'})
        return
    
    # Generate call room
    call_room_id = f"call_{uuid.uuid4().hex[:8]}"
    
    # Send call notification to receiver
    emit('incoming_call', {
        'caller_id': caller_id,
        'caller_username': caller.username,
        'caller_pic': caller.profile_pic,
        'call_type': call_type,
        'call_room_id': call_room_id,
        'room_id': room_id,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }, room=f'user_{receiver_id}')
    
    # Send call initiated to caller
    emit('call_initiated', {
        'call_room_id': call_room_id,
        'receiver_id': receiver_id,
        'call_type': call_type,
        'status': 'ringing'
    })

@socketio.on('voice_call_answer')
def handle_voice_call_answer(data):
    """Handle voice call answer"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    call_room_id = data.get('call_room_id')
    caller_id = data.get('caller_id')
    
    if not call_room_id or not caller_id:
        return
    
    # Join call room
    join_room(call_room_id)
    
    # Notify caller
    emit('call_answered', {
        'call_room_id': call_room_id,
        'receiver_id': user_id,
        'status': 'connected'
    }, room=f'user_{caller_id}')

@socketio.on('voice_call_reject')
def handle_voice_call_reject(data):
    """Handle voice call rejection"""
    if 'user_id' not in session:
        return
    
    user_id = session['user_id']
    call_room_id = data.get('call_room_id')
    caller_id = data.get('caller_id')
    reason = data.get('reason', 'rejected')
    
    if not caller_id:
        return
    
    # Notify caller
    emit('call_rejected', {
        'call_room_id': call_room_id,
        'receiver_id': user_id,
        'reason': reason,
        'status': 'rejected'
    }, room=f'user_{caller_id}')

@socketio.on('voice_call_end')
def handle_voice_call_end(data):
    """Handle voice call end"""
    if 'user_id' not in session:
        return
    
    call_room_id = data.get('call_room_id')
    duration = data.get('duration', 0)
    
    if call_room_id:
        # Notify all participants
        emit('call_ended', {
            'call_room_id': call_room_id,
            'duration': duration,
            'ended_by': session['user_id'],
            'status': 'ended'
        }, room=call_room_id)
        
        # Clean up call room
        close_room(call_room_id)

@socketio.on('webrtc_signal')
def handle_webrtc_signal(data):
    """Handle WebRTC signaling"""
    if 'user_id' not in session:
        return
    
    call_room_id = data.get('call_room_id')
    signal = data.get('signal')
    signal_type = data.get('signal_type')  # offer, answer, ice-candidate
    
    if call_room_id and signal:
        emit('webrtc_signal', {
            'user_id': session['user_id'],
            'signal': signal,
            'signal_type': signal_type
        }, room=call_room_id, include_self=False)

# ============================================
# 19. HELPER FUNCTIONS FOR SOCKET
# ============================================

def notify_contacts_status(user_id: int, is_online: bool):
    """Notify contacts about user's online status"""
    user = db.session.get(User, user_id)
    if not user:
        return
    
    # Get users who have this user as contact
    contacts = Contact.query.filter_by(contact_id=user_id).all()
    
    for contact in contacts:
        # Emit to contact's personal room
        emit('contact_status_changed', {
            'user_id': user_id,
            'username': user.username,
            'is_online': is_online,
            'last_seen': user.last_seen.isoformat() if user.last_seen and not is_online else None,
            'user_status': user.user_status
        }, room=f'user_{contact.user_id}', namespace='/')

def get_online_members(room_id: int) -> list:
    """Get list of online members in a room"""
    online_members = []
    
    memberships = RoomMember.query.filter_by(room_id=room_id, is_active=True).all()
    
    for membership in memberships:
        user = db.session.get(User, membership.user_id)
        if user and user.is_online and not user.is_deleted:
            online_members.append({
                'user_id': user.id,
                'username': user.username,
                'profile_pic': user.profile_pic,
                'user_status': user.user_status
            })
    
    return online_members

def get_room_participants(room_id: int) -> list:
    """Get all participants in a room"""
    participants = []
    
    memberships = RoomMember.query.filter_by(room_id=room_id, is_active=True).all()
    
    for membership in memberships:
        user = db.session.get(User, membership.user_id)
        if user and not user.is_deleted:
            participants.append({
                'user_id': user.id,
                'username': user.username,
                'profile_pic': user.profile_pic,
                'is_online': user.is_online,
                'user_status': user.user_status,
                'role': membership.role,
                'is_muted': membership.is_muted
            })
    
    return participants

def send_system_message(room_id: int, content: str, sender_id: Optional[int] = None):
    """Send a system message to a room"""
    try:
        message = Message(
            sender_id=sender_id or 0,  # 0 for system
            room_id=room_id,
            content=content,
            message_type=MessageType.SYSTEM.value
        )
        
        db.session.add(message)
        db.session.commit()
        
        # Emit to room
        socketio.emit('new_message', message.to_dict(), room=f'room_{room_id}')
        
    except Exception as e:
        db.session.rollback()
        print(f'Error sending system message: {str(e)}')

def cleanup_disappearing_messages():
    """Clean up expired disappearing messages"""
    try:
        with app.app_context():
            expired = Message.query.filter(
                Message.disappear_at.isnot(None),
                Message.disappear_at <= datetime.now(timezone.utc),
                Message.is_deleted == False
            ).all()
            
            for message in expired:
                message.soft_delete(0)  # 0 for system
                
                # Delete media if exists
                if message.media_public_id:
                    resource_type = 'image'
                    if message.media_type == 'video':
                        resource_type = 'video'
                    elif message.media_type in ['audio', 'document']:
                        resource_type = 'raw'
                    
                    delete_cloudinary_asset(message.media_public_id, resource_type)
            
            if expired:
                db.session.commit()
                print(f'Cleaned up {len(expired)} disappearing messages')
                
    except Exception as e:
        db.session.rollback()
        print(f'Error cleaning up disappearing messages: {str(e)}')

def cleanup_inactive_users():
    """Mark inactive users as offline"""
    try:
        with app.app_context():
            timeout = datetime.now(timezone.utc) - timedelta(minutes=30)
            
            inactive = User.query.filter(
                User.is_online == True,
                User.last_seen < timeout,
                User.id.notin_(
                    db.session.query(UserDevice.user_id).filter(
                        UserDevice.is_active == True,
                        UserDevice.last_active > timeout
                    )
                )
            ).all()
            
            for user in inactive:
                user.is_online = False
                user.user_status = UserStatus.OFFLINE.value
                
                # Notify contacts
                contacts = Contact.query.filter_by(contact_id=user.id).all()
                for contact in contacts:
                    socketio.emit('contact_status_changed', {
                        'user_id': user.id,
                        'username': user.username,
                        'is_online': False,
                        'last_seen': user.last_seen.isoformat()
                    }, room=f'user_{contact.user_id}')
            
            if inactive:
                db.session.commit()
                print(f'Marked {len(inactive)} inactive users as offline')
                
    except Exception as e:
        db.session.rollback()
        print(f'Error cleaning up inactive users: {str(e)}')

# ============================================
# 20. ERROR HANDLERS
# ============================================

@app.errorhandler(400)
def bad_request_error(error):
    """Handle 400 Bad Request"""
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'Bad Request',
            'message': str(error),
            'status_code': 400
        }), 400
    
    return render_template('error.html',
                           error_code=400,
                           error_title='Bad Request',
                           error_message='The request could not be understood by the server.'), 400

@app.errorhandler(401)
def unauthorized_error(error):
    """Handle 401 Unauthorized"""
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'Unauthorized',
            'message': 'You must be logged in to access this resource',
            'status_code': 401
        }), 401
    
    flash('Please log in to access this page', 'info')
    return redirect(url_for('login'))

@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 Forbidden"""
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'Forbidden',
            'message': 'You do not have permission to access this resource',
            'status_code': 403
        }), 403
    
    return render_template('error.html',
                           error_code=403,
                           error_title='Access Denied',
                           error_message='You do not have permission to access this resource.'), 403

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 Not Found"""
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'Not Found',
            'message': 'The requested resource was not found',
            'status_code': 404
        }), 404
    
    return render_template('error.html',
                           error_code=404,
                           error_title='Page Not Found',
                           error_message='The page you are looking for does not exist.'), 404

@app.errorhandler(405)
def method_not_allowed_error(error):
    """Handle 405 Method Not Allowed"""
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'Method Not Allowed',
            'message': 'The method is not allowed for this resource',
            'status_code': 405
        }), 405
    
    flash('Invalid request method', 'error')
    return redirect(url_for('index'))

@app.errorhandler(413)
def request_entity_too_large_error(error):
    """Handle 413 Request Entity Too Large"""
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'File Too Large',
            'message': f'The uploaded file exceeds the maximum allowed size of {format_file_size(app.config["MAX_CONTENT_LENGTH"])}',
            'status_code': 413
        }), 413
    
    flash('The uploaded file is too large', 'error')
    return redirect(request.url)

@app.errorhandler(429)
def too_many_requests_error(error):
    """Handle 429 Too Many Requests"""
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'Too Many Requests',
            'message': 'You have exceeded the rate limit. Please try again later.',
            'status_code': 429
        }), 429
    
    return render_template('error.html',
                           error_code=429,
                           error_title='Too Many Requests',
                           error_message='Please slow down and try again later.'), 429

@app.errorhandler(500)
def internal_server_error(error):
    """Handle 500 Internal Server Error"""
    db.session.rollback()
    
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred. Our team has been notified.',
            'status_code': 500
        }), 500
    
    return render_template('error.html',
                           error_code=500,
                           error_title='Server Error',
                           error_message='Something went wrong on our end. Please try again later.'), 500

@app.errorhandler(503)
def service_unavailable_error(error):
    """Handle 503 Service Unavailable"""
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'error': 'Service Unavailable',
            'message': 'The service is temporarily unavailable. Please try again later.',
            'status_code': 503
        }), 503
    
    return render_template('error.html',
                           error_code=503,
                           error_title='Service Unavailable',
                           error_message='Bantu Halii is currently undergoing maintenance. Please check back soon.'), 503

# ============================================
# 21. ADMIN ROUTES (BASIC)
# ============================================

@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard (basic)"""
    user = db.session.get(User, session['user_id'])
    
    # Check if user has any admin privileges
    is_any_admin = RoomAdmin.query.filter_by(user_id=user.id).first()
    
    if not is_any_admin:
        flash('You do not have admin privileges', 'error')
        return redirect(url_for('chat'))
    
    # Get rooms where user is admin
    admin_rooms = RoomAdmin.query.filter_by(user_id=user.id).all()
    rooms_data = []
    
    for admin in admin_rooms:
        room = db.session.get(Room, admin.room_id)
        if room and not room.is_deleted:
            member_count = RoomMember.query.filter_by(room_id=room.id, is_active=True).count()
            message_count = Message.query.filter_by(room_id=room.id, is_deleted=False).count()
            
            rooms_data.append({
                **room.to_dict(user_id=user.id),
                'member_count': member_count,
                'message_count': message_count,
                'permissions': {
                    'can_manage_members': admin.can_manage_members,
                    'can_manage_settings': admin.can_manage_settings,
                    'can_delete_messages': admin.can_delete_messages
                }
            })
    
    return render_template('admin.html', user=user, admin_rooms=rooms_data)

@app.route('/admin/room/<int:room_id>/members')
@login_required
def admin_room_members(room_id):
    """Manage room members (admin)"""
    user = db.session.get(User, session['user_id'])
    
    # Check admin permissions
    admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user.id).first()
    if not admin or not admin.can_manage_members:
        return jsonify({'error': 'Access denied'}), 403
    
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    
    # Get all members
    memberships = RoomMember.query.filter_by(room_id=room_id).all()
    
    members_data = []
    for membership in memberships:
        member_user = db.session.get(User, membership.user_id)
        if member_user:
            is_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=member_user.id).first()
            
            members_data.append({
                'user_id': member_user.id,
                'username': member_user.username,
                'profile_pic': member_user.profile_pic,
                'phone_number': member_user.phone_number,
                'role': membership.role,
                'is_active': membership.is_active,
                'is_admin': is_admin is not None,
                'is_muted': membership.is_muted,
                'muted_until': membership.muted_until.isoformat() if membership.muted_until else None,
                'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
                'left_at': membership.left_at.isoformat() if membership.left_at else None,
                'admin_permissions': {
                    'can_manage_members': is_admin.can_manage_members if is_admin else False,
                    'can_manage_settings': is_admin.can_manage_settings if is_admin else False,
                    'can_delete_messages': is_admin.can_delete_messages if is_admin else False
                } if is_admin else None
            })
    
    return jsonify({
        'room': room.to_dict(),
        'members': members_data,
        'total_members': len(members_data),
        'active_members': len([m for m in members_data if m['is_active']])
    })

@app.route('/admin/room/<int:room_id>/promote/<int:member_id>', methods=['POST'])
@login_required
def promote_to_admin(room_id, member_id):
    """Promote a member to admin"""
    user = db.session.get(User, session['user_id'])
    
    # Check if current user is admin with manage members permission
    admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user.id).first()
    if not admin or not admin.can_manage_members:
        if request.is_json:
            return jsonify({'error': 'Access denied'}), 403
        flash('You do not have permission to promote members', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    # Check if member exists and is active
    membership = RoomMember.query.filter_by(
        room_id=room_id,
        user_id=member_id,
        is_active=True
    ).first()
    
    if not membership:
        if request.is_json:
            return jsonify({'error': 'Member not found'}), 404
        flash('Member not found', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    # Check if already admin
    existing_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=member_id).first()
    if existing_admin:
        if request.is_json:
            return jsonify({'message': 'User is already an admin'})
        flash('User is already an admin', 'info')
        return redirect(url_for('chat_room', room_id=room_id))
    
    try:
        # Get permissions from request
        can_manage_members = True
        can_manage_settings = True
        can_delete_messages = True
        
        if request.is_json:
            data = request.get_json()
            can_manage_members = data.get('can_manage_members', True)
            can_manage_settings = data.get('can_manage_settings', True)
            can_delete_messages = data.get('can_delete_messages', True)
        
        # Create admin
        new_admin = RoomAdmin(
            room_id=room_id,
            user_id=member_id,
            promoted_by=user.id,
            can_manage_members=can_manage_members,
            can_manage_settings=can_manage_settings,
            can_delete_messages=can_delete_messages
        )
        db.session.add(new_admin)
        
        # Update membership role
        membership.role = 'admin'
        
        # Notify the new admin
        room = db.session.get(Room, room_id)
        notification = Notification(
            user_id=member_id,
            notification_type='promoted_to_admin',
            title=f'Promoted to Admin in {room.name}',
            body=f'{user.username} promoted you to admin in {room.name}',
            data=json.dumps({
                'room_id': room_id,
                'promoted_by': user.id,
                'permissions': {
                    'can_manage_members': can_manage_members,
                    'can_manage_settings': can_manage_settings,
                    'can_delete_messages': can_delete_messages
                }
            })
        )
        db.session.add(notification)
        
        db.session.commit()
        
        # Emit socket event
        socketio.emit('member_promoted', {
            'room_id': room_id,
            'user_id': member_id,
            'promoted_by': user.id,
            'new_role': 'admin'
        }, room=f'room_{room_id}')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Member promoted to admin successfully'
            })
        
        flash('Member promoted to admin successfully', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to promote member: {str(e)}', 'error')
        return redirect(url_for('chat_room', room_id=room_id))

@app.route('/admin/room/<int:room_id>/demote/<int:admin_id>', methods=['POST'])
@login_required
def demote_admin(room_id, admin_id):
    """Demote an admin to regular member"""
    user = db.session.get(User, session['user_id'])
    
    # Check if current user is admin with manage members permission
    admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user.id).first()
    if not admin or not admin.can_manage_members:
        if request.is_json:
            return jsonify({'error': 'Access denied'}), 403
        flash('You do not have permission to demote admins', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    # Cannot demote yourself
    if admin_id == user.id:
        if request.is_json:
            return jsonify({'error': 'Cannot demote yourself'}), 400
        flash('Cannot demote yourself', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    # Cannot demote the owner
    membership = RoomMember.query.filter_by(room_id=room_id, user_id=admin_id).first()
    if membership and membership.role == 'owner':
        if request.is_json:
            return jsonify({'error': 'Cannot demote the room owner'}), 403
        flash('Cannot demote the room owner', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    # Check if user is admin
    target_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=admin_id).first()
    if not target_admin:
        if request.is_json:
            return jsonify({'error': 'User is not an admin'}), 404
        flash('User is not an admin', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    try:
        db.session.delete(target_admin)
        
        # Update membership role
        if membership:
            membership.role = 'member'
        
        # Notify the demoted admin
        room = db.session.get(Room, room_id)
        notification = Notification(
            user_id=admin_id,
            notification_type='demoted_from_admin',
            title=f'Admin Status Removed in {room.name}',
            body=f'Your admin status was removed in {room.name}',
            data=json.dumps({
                'room_id': room_id,
                'demoted_by': user.id
            })
        )
        db.session.add(notification)
        
        db.session.commit()
        
        # Emit socket event
        socketio.emit('admin_demoted', {
            'room_id': room_id,
            'user_id': admin_id,
            'demoted_by': user.id
        }, room=f'room_{room_id}')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Admin demoted successfully'
            })
        
        flash('Admin demoted successfully', 'info')
        return redirect(url_for('chat_room', room_id=room_id))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to demote admin: {str(e)}', 'error')
        return redirect(url_for('chat_room', room_id=room_id))

@app.route('/admin/room/<int:room_id>/mute/<int:member_id>', methods=['POST'])
@login_required
def mute_member(room_id, member_id):
    """Mute a member in the room"""
    user = db.session.get(User, session['user_id'])
    
    # Check if current user is admin
    admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user.id).first()
    if not admin:
        if request.is_json:
            return jsonify({'error': 'Access denied'}), 403
        flash('You do not have permission to mute members', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    # Cannot mute yourself
    if member_id == user.id:
        if request.is_json:
            return jsonify({'error': 'Cannot mute yourself'}), 400
        flash('Cannot mute yourself', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    membership = RoomMember.query.filter_by(
        room_id=room_id,
        user_id=member_id,
        is_active=True
    ).first()
    
    if not membership:
        if request.is_json:
            return jsonify({'error': 'Member not found'}), 404
        flash('Member not found', 'error')
        return redirect(url_for('chat_room', room_id=room_id))
    
    try:
        # Get mute duration from request
        duration_minutes = 60  # Default 1 hour
        
        if request.is_json:
            data = request.get_json()
            duration_minutes = data.get('duration_minutes', 60)
        else:
            duration_minutes = int(request.form.get('duration_minutes', 60))
        
        if membership.is_muted and membership.muted_until and membership.muted_until > datetime.now(timezone.utc):
            # Unmute
            membership.is_muted = False
            membership.muted_until = None
            action = 'unmuted'
        else:
            # Mute
            membership.is_muted = True
            membership.muted_until = datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)
            action = 'muted'
        
        # Notify the member
        room = db.session.get(Room, room_id)
        notification = Notification(
            user_id=member_id,
            notification_type=f'{action}_in_room',
            title=f'{action.capitalize()} in {room.name}',
            body=f'You have been {action} in {room.name}' + 
                 (f' for {duration_minutes} minutes' if action == 'muted' else ''),
            data=json.dumps({
                'room_id': room_id,
                'action': action,
                'duration_minutes': duration_minutes if action == 'muted' else 0,
                'muted_by': user.id
            })
        )
        db.session.add(notification)
        
        db.session.commit()
        
        # Emit socket event
        socketio.emit('member_muted', {
            'room_id': room_id,
            'user_id': member_id,
            'action': action,
            'duration_minutes': duration_minutes if action == 'muted' else 0,
            'muted_by': user.id
        }, room=f'room_{room_id}')
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': f'Member {action} successfully',
                'action': action,
                'duration_minutes': duration_minutes if action == 'muted' else 0
            })
        
        flash(f'Member {action} successfully', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'error': str(e)}), 500
        flash(f'Failed to mute member: {str(e)}', 'error')
        return redirect(url_for('chat_room', room_id=room_id))

# ============================================
# 22. HEALTH CHECK AND API ROUTES
# ============================================

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connection
        db.session.execute(text('SELECT 1'))
        db_status = 'healthy'
    except Exception as e:
        db_status = f'unhealthy: {str(e)}'
    
    # Check Cloudinary connection
    try:
        cloudinary.api.ping()
        cloudinary_status = 'healthy'
    except Exception as e:
        cloudinary_status = f'unhealthy: {str(e)}'
    
    health_data = {
        'status': 'healthy' if db_status == 'healthy' and cloudinary_status == 'healthy' else 'degraded',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'app_name': 'Bantu Halii',
        'version': '1.0.0',
        'services': {
            'database': db_status,
            'cloudinary': cloudinary_status,
            'socket_io': 'healthy' if connected_users else 'degraded'
        },
        'stats': {
            'connected_users': len(connected_users),
            'total_users': User.query.filter_by(is_deleted=False).count(),
            'total_rooms': Room.query.filter_by(is_deleted=False).count(),
            'total_messages': Message.query.filter_by(is_deleted=False).count()
        }
    }
    
    status_code = 200 if health_data['status'] == 'healthy' else 503
    return jsonify(health_data), status_code

@app.route('/api/stats')
@login_required
def get_app_stats():
    """Get application statistics"""
    user = db.session.get(User, session['user_id'])
    
    stats = {
        'user': {
            'total_messages_sent': Message.query.filter_by(sender_id=user.id, is_deleted=False).count(),
            'total_messages_received': Message.query.filter_by(receiver_id=user.id, is_deleted=False).count(),
            'total_rooms': RoomMember.query.filter_by(user_id=user.id, is_active=True).count(),
            'total_contacts': Contact.query.filter_by(user_id=user.id, is_blocked=False).count(),
            'total_media_shared': Message.query.filter(
                Message.sender_id == user.id,
                Message.media_url.isnot(None),
                Message.is_deleted == False
            ).count(),
            'account_age_days': (datetime.now(timezone.utc) - user.created_at).days if user.created_at else 0,
            'unread_messages': Message.query.filter_by(receiver_id=user.id, is_read=False, is_deleted=False).count(),
            'unread_notifications': Notification.query.filter_by(user_id=user.id, is_read=False).count()
        },
        'app': {
            'total_users': User.query.filter_by(is_deleted=False).count(),
            'online_users': User.query.filter_by(is_online=True).count(),
            'total_rooms': Room.query.filter_by(is_deleted=False).count(),
            'total_messages_today': Message.query.filter(
                Message.created_at >= datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
                Message.is_deleted == False
            ).count()
        }
    }
    
    return jsonify(stats)

@app.route('/api/user/<int:user_id>')
@login_required
def get_user_info(user_id):
    """Get public user information"""
    current_user = db.session.get(User, session['user_id'])
    user = db.session.get(User, user_id)
    
    if not user or user.is_deleted:
        return jsonify({'error': 'User not found'}), 404
    
    # Check if blocked
    is_blocked = BlockedUser.query.filter_by(
        user_id=current_user.id,
        blocked_user_id=user_id
    ).first()
    
    if is_blocked:
        return jsonify({'error': 'User is blocked'}), 403
    
    # Get mutual rooms
    current_user_rooms = set([
        m.room_id for m in RoomMember.query.filter_by(user_id=current_user.id, is_active=True).all()
    ])
    user_rooms = set([
        m.room_id for m in RoomMember.query.filter_by(user_id=user_id, is_active=True).all()
    ])
    mutual_rooms = current_user_rooms.intersection(user_rooms)
    
    # Check if in contacts
    is_contact = Contact.query.filter_by(
        user_id=current_user.id,
        contact_id=user_id,
        is_blocked=False
    ).first()
    
    user_data = user.to_dict()
    user_data['mutual_rooms_count'] = len(mutual_rooms)
    user_data['is_contact'] = is_contact is not None
    user_data['is_favorite'] = is_contact.is_favorite if is_contact else False
    
    # Only show last seen if user allows it
    if not user.last_seen_visible:
        user_data['last_seen'] = None
    
    return jsonify(user_data)

@app.route('/api/rooms')
@login_required
def get_user_rooms():
    """Get all rooms for current user"""
    user = db.session.get(User, session['user_id'])
    
    memberships = RoomMember.query.filter_by(
        user_id=user.id,
        is_active=True
    ).order_by(RoomMember.is_pinned.desc(), RoomMember.joined_at.desc()).all()
    
    rooms_data = []
    for membership in memberships:
        room = db.session.get(Room, membership.room_id)
        if room and not room.is_deleted:
            room_data = room.to_dict(user_id=user.id)
            
            # Get unread count
            unread = UnreadMessage.query.filter_by(user_id=user.id, room_id=room.id).first()
            room_data['unread_count'] = unread.count if unread else 0
            room_data['is_pinned'] = membership.is_pinned
            room_data['is_muted'] = membership.is_muted
            room_data['notifications_enabled'] = membership.notifications_enabled
            room_data['my_role'] = membership.role
            
            rooms_data.append(room_data)
    
    return jsonify(rooms_data)

@app.route('/api/room/<int:room_id>/info')
@login_required
def get_room_info(room_id):
    """Get detailed room information"""
    user = db.session.get(User, session['user_id'])
    
    # Check membership
    membership = RoomMember.query.filter_by(
        room_id=room_id,
        user_id=user.id,
        is_active=True
    ).first()
    
    if not membership:
        return jsonify({'error': 'Not a member of this room'}), 403
    
    room = db.session.get(Room, room_id)
    if not room or room.is_deleted:
        return jsonify({'error': 'Room not found'}), 404
    
    # Get room details
    room_data = room.to_dict(user_id=user.id)
    
    # Get members
    members = RoomMember.query.filter_by(room_id=room_id, is_active=True).all()
    members_data = []
    
    for member in members:
        member_user = db.session.get(User, member.user_id)
        if member_user and not member_user.is_deleted:
            is_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=member.user_id).first()
            members_data.append({
                'user_id': member_user.id,
                'username': member_user.username,
                'profile_pic': member_user.profile_pic,
                'is_online': member_user.is_online,
                'role': member.role,
                'is_admin': is_admin is not None,
                'joined_at': member.joined_at.isoformat() if member.joined_at else None
            })
    
    # Get admins
    admins = RoomAdmin.query.filter_by(room_id=room_id).all()
    admins_data = []
    
    for admin in admins:
        admin_user = db.session.get(User, admin.user_id)
        if admin_user and not admin_user.is_deleted:
            admins_data.append({
                'user_id': admin_user.id,
                'username': admin_user.username,
                'profile_pic': admin_user.profile_pic,
                'promoted_at': admin.promoted_at.isoformat() if admin.promoted_at else None,
                'permissions': {
                    'can_manage_members': admin.can_manage_members,
                    'can_manage_settings': admin.can_manage_settings,
                    'can_delete_messages': admin.can_delete_messages
                }
            })
    
    # Get pinned messages
    pinned = PinnedMessage.query.filter_by(room_id=room_id).all()
    pinned_data = []
    
    for pin in pinned:
        message = db.session.get(Message, pin.message_id)
        if message and not message.is_deleted:
            pinned_data.append({
                'message_id': message.id,
                'content': message.content[:100] if message.content else '[Media]',
                'pinned_by': pin.pinned_by,
                'pinned_at': pin.pinned_at.isoformat() if pin.pinned_at else None
            })
    
    room_data['members'] = members_data
    room_data['admins'] = admins_data
    room_data['pinned_messages'] = pinned_data
    room_data['member_count'] = len(members_data)
    room_data['online_count'] = len([m for m in members_data if m['is_online']])
    
    # Check user's permissions
    user_admin = RoomAdmin.query.filter_by(room_id=room_id, user_id=user.id).first()
    room_data['my_permissions'] = {
        'is_admin': user_admin is not None,
        'can_manage_members': user_admin.can_manage_members if user_admin else False,
        'can_manage_settings': user_admin.can_manage_settings if user_admin else False,
        'can_delete_messages': user_admin.can_delete_messages if user_admin else False,
        'can_send_messages': not room.only_admins_can_send or (user_admin is not None)
    }
    
    return jsonify(room_data)

# ============================================
# 23. BACKGROUND TASKS
# ============================================

def start_background_tasks():
    """Start background tasks for maintenance"""
    
    def cleanup_task():
        """Periodic cleanup task"""
        while True:
            try:
                with app.app_context():
                    # Clean up disappearing messages
                    cleanup_disappearing_messages()
                    
                    # Clean up inactive users
                    cleanup_inactive_users()
                    
                    # Clean up old notifications (older than 30 days)
                    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
                    deleted = Notification.query.filter(
                        Notification.created_at < thirty_days_ago,
                        Notification.is_read == True
                    ).delete()
                    
                    if deleted:
                        db.session.commit()
                        print(f'Cleaned up {deleted} old notifications')
                    
                    # Clean up expired media cache
                    expired_cache = MediaCache.query.filter(
                        MediaCache.expires_at < datetime.now(timezone.utc)
                    ).delete()
                    
                    if expired_cache:
                        db.session.commit()
                        print(f'Cleaned up {expired_cache} expired media cache entries')
                    
            except Exception as e:
                print(f'Error in cleanup task: {str(e)}')
                try:
                    db.session.rollback()
                except:
                    pass
            
            # Sleep for 5 minutes
            time.sleep(300)
    
    def ping_task():
        """Keep the app alive (useful for free tier hosting)"""
        while True:
            try:
                with app.app_context():
                    # Simple query to keep database connection alive
                    db.session.execute(text('SELECT 1'))
                    db.session.commit()
                    print(f'Ping task executed at {datetime.now(timezone.utc).isoformat()}')
            except Exception as e:
                print(f'Error in ping task: {str(e)}')
                try:
                    db.session.rollback()
                except:
                    pass
            
            # Sleep for 14 minutes (for services with 15-min timeout)
            time.sleep(840)
    
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True, name='cleanup-thread')
    cleanup_thread.start()
    
    # Start ping thread
    ping_thread = threading.Thread(target=ping_task, daemon=True, name='ping-thread')
    ping_thread.start()
    
    print('Background tasks started successfully')

# ============================================
# 24. DATABASE INITIALIZATION AND MIGRATION
# ============================================

def init_database():
    """Initialize database with tables and default data"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            print('✅ Database tables created successfully')
            
            # Check if we need to create default data
            if not User.query.first():
                print('📝 Creating default data...')
                create_default_data()
            
            # Create indexes for better performance
            create_indexes()
            
            print('✅ Database initialization complete')
            
        except Exception as e:
            print(f'❌ Database initialization error: {str(e)}')
            raise

def create_default_data():
    """Create default data for development/testing"""
    try:
        # Create a system user for system messages
        system_user = User(
            username='BantuHalii',
            email='system@bantuhalii.com',
            profile_pic='https://ui-avatars.com/api/?name=BH&background=4ECDC4&color=fff&size=200&bold=true',
            status='Official Bantu Halii Account 🌍',
            bio='The official system account for Bantu Halii - Connecting Africa'
        )
        system_user.set_password(secrets.token_urlsafe(32))
        db.session.add(system_user)
        
        # Create a welcome room
        welcome_room = Room(
            name='Welcome to Bantu Halii! 🎉',
            description='Welcome to Bantu Halii, the African chat application! This is a public room for all new users.',
            created_by=1,
            room_type=RoomType.GROUP.value,
            is_public=True
        )
        db.session.add(welcome_room)
        db.session.flush()
        
        # Add system user as owner
        system_membership = RoomMember(
            room_id=welcome_room.id,
            user_id=system_user.id,
            role='owner'
        )
        db.session.add(system_membership)
        
        # Make system user admin
        system_admin = RoomAdmin(
            room_id=welcome_room.id,
            user_id=system_user.id,
            promoted_by=system_user.id
        )
        db.session.add(system_admin)
        
        # Create welcome message
        welcome_message = Message(
            sender_id=system_user.id,
            room_id=welcome_room.id,
            content='Welcome to Bantu Halii! 🌍\n\n'
                   'Bantu Halii is a secure and feature-rich messaging app designed for Africa.\n\n'
                   'Features:\n'
                   '✅ Real-time messaging\n'
                   '✅ Media sharing (photos, videos, audio, documents)\n'
                   '✅ Group chats with admin controls\n'
                   '✅ Voice and video calls\n'
                   '✅ End-to-end encryption\n'
                   '✅ Message reactions\n'
                   '✅ Disappearing messages\n\n'
                   'Start by inviting your friends or joining public rooms!\n\n'
                   'Asante sana! 🙏',
            message_type=MessageType.SYSTEM.value
        )
        db.session.add(welcome_message)
        
        db.session.commit()
        print('✅ Default data created successfully')
        
    except Exception as e:
        db.session.rollback()
        print(f'❌ Error creating default data: {str(e)}')

def create_indexes():
    """Create database indexes for better performance"""
    try:
        # These indexes are created automatically by SQLAlchemy for primary keys
        # and unique constraints, but we can add additional indexes here
        
        # Check if running on PostgreSQL
        is_postgresql = 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI']
        
        if is_postgresql:
            # Create composite indexes for common queries
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_messages_room_created 
                ON messages (room_id, created_at DESC)
                WHERE is_deleted = false;
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_messages_sender_created 
                ON messages (sender_id, created_at DESC);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_messages_receiver_read 
                ON messages (receiver_id, is_read)
                WHERE is_deleted = false;
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_room_members_user_active 
                ON room_members (user_id, is_active)
                WHERE is_active = true;
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_notifications_user_read 
                ON notifications (user_id, is_read, created_at DESC);
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_contacts_user_favorite 
                ON contacts (user_id, is_favorite)
                WHERE is_blocked = false;
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_online 
                ON users (is_online)
                WHERE is_deleted = false;
            """))
            
            db.session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_messages_search 
                ON messages USING gin(to_tsvector('english', content))
                WHERE content IS NOT NULL AND is_deleted = false;
            """))
            
            db.session.commit()
            print('✅ Database indexes created successfully')
        
    except Exception as e:
        db.session.rollback()
        print(f'⚠️ Warning: Could not create all indexes: {str(e)}')

# ============================================
# 25. MIDDLEWARE AND REQUEST HOOKS
# ============================================

@app.before_request
def before_request():
    """Execute before each request"""
    # Set default language if not set
    if 'language' not in session and 'user_id' in session:
        user = db.session.get(User, session.get('user_id'))
        if user:
            session['language'] = user.language
    
    # Update last activity time
    if 'user_id' in session:
        g.request_start_time = datetime.now(timezone.utc)

@app.after_request
def after_request(response):
    """Execute after each request"""
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self' https: wss:; " \
                                                   "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.socket.io https://cdnjs.cloudflare.com; " \
                                                   "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com https://fonts.googleapis.com; " \
                                                   "font-src 'self' https://fonts.gstatic.com; " \
                                                   "img-src 'self' data: https: blob:; " \
                                                   "media-src 'self' https: blob:; " \
                                                   "connect-src 'self' https: wss:;"
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    
    # Add CORS headers for API
    if request.path.startswith('/api/'):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Device-ID'
    
    # Log request for monitoring
    if app.debug and 'request_start_time' in g:
        duration = (datetime.now(timezone.utc) - g.request_start_time).total_seconds()
        if duration > 1.0:  # Log slow requests
            app.logger.warning(f'Slow request: {request.method} {request.path} took {duration:.2f}s')
    
    return response

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up database session"""
    if exception:
        db.session.rollback()
    db.session.remove()

@app.teardown_request
def teardown_request(exception=None):
    """Clean up after request"""
    if exception:
        db.session.rollback()

# ============================================
# 26. COMMAND LINE INTERFACE
# ============================================

@app.cli.command('init-db')
def init_db_command():
    """Initialize the database"""
    init_database()
    print('Database initialized.')

@app.cli.command('create-admin')
def create_admin_command():
    """Create an admin user"""
    import click
    
    username = click.prompt('Username', type=str)
    email = click.prompt('Email', type=str)
    phone = click.prompt('Phone number (optional)', type=str, default='')
    password = click.prompt('Password', type=str, hide_input=True)
    
    with app.app_context():
        if User.query.filter_by(username=username).first():
            click.echo(f'User {username} already exists!')
            return
        
        user = User(
            username=username,
            email=email if email else None,
            phone_number=phone if phone else None
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(f'Admin user {username} created successfully!')

@app.cli.command('cleanup')
def cleanup_command():
    """Run cleanup tasks"""
    with app.app_context():
        cleanup_disappearing_messages()
        cleanup_inactive_users()
        print('Cleanup completed.')

@app.cli.command('stats')
def stats_command():
    """Show application statistics"""
    with app.app_context():
        total_users = User.query.filter_by(is_deleted=False).count()
        online_users = User.query.filter_by(is_online=True).count()
        total_rooms = Room.query.filter_by(is_deleted=False).count()
        total_messages = Message.query.filter_by(is_deleted=False).count()
        total_media = Message.query.filter(
            Message.media_url.isnot(None),
            Message.is_deleted == False
        ).count()
        
        print('=' * 50)
        print('BANTU HALII STATISTICS')
        print('=' * 50)
        print(f'Total Users:     {total_users}')
        print(f'Online Users:    {online_users}')
        print(f'Total Rooms:     {total_rooms}')
        print(f'Total Messages:  {total_messages}')
        print(f'Total Media:     {total_media}')
        print('=' * 50)

# ============================================
# 27. APP ENTRY POINT
# ============================================

def create_app():
    """Application factory function"""
    # Initialize database if needed
    init_database()
    
    return app

if __name__ == '__main__':
    # Print banner
    print("=" * 70)
    print("🌍  BANTU HALII - Connecting Africa")
    print("   A Branch of Bantu Africa Ecosystem")
    print("=" * 70)
    print(f"📱  Version: 1.0.0")
    print(f"🐍  Python: {sys.version.split()[0]}")
    print(f"🗄️   Database: {'PostgreSQL' if 'postgresql' in app.config['SQLALCHEMY_DATABASE_URI'] else 'SQLite'}")
    print(f"☁️   Cloudinary: {'Connected' if os.getenv('CLOUDINARY_CLOUD_NAME') else 'Not configured'}")
    print("=" * 70)
    
    # Initialize database
    init_database()
    
    # Start background tasks
    start_background_tasks()
    
    # Get port from environment variable (for Render and other platforms)
    port = int(os.getenv('PORT', 5000))
    
    # Determine debug mode
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Run the application
    print(f"\n🚀 Bantu Halii is running on http://0.0.0.0:{port}")
    print(f"🌍 Ready to connect Africa!\n")
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=False,  # Disable reloader to prevent duplicate background tasks
        allow_unsafe_werkzeug=True
    )

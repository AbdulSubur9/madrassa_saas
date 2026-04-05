"""Database models for the application."""

from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db


class School(db.Model):
    """School model - represents a school in the SaaS platform."""

    __tablename__ = 'schools'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(500))
    logo_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    users = db.relationship('User', backref='school', lazy='dynamic')
    classes = db.relationship('SchoolClass', backref='school', lazy='dynamic')
    students = db.relationship('Student', backref='school', lazy='dynamic')
    payments = db.relationship('Payment', backref='school', lazy='dynamic')

    def __repr__(self):
        return f'<School {self.name}>'


class User(UserMixin, db.Model):
    """User model with role-based access control."""

    __tablename__ = 'users'

    ROLE_SUPER_ADMIN = 'super_admin'
    ROLE_SCHOOL_ADMIN = 'school_admin'
    ROLE_COLLECTOR = 'collector'
    ROLE_ACCOUNTANT = 'accountant'

    ROLES = [ROLE_SUPER_ADMIN, ROLE_SCHOOL_ADMIN, ROLE_COLLECTOR, ROLE_ACCOUNTANT]

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(200), nullable=False, default='')
    email = db.Column(db.String(200), nullable=True)
    profile_picture = db.Column(db.String(500), nullable=True)
    role = db.Column(db.String(20), nullable=False, default=ROLE_COLLECTOR)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    recorded_payments = db.relationship(
        'Payment', backref='recorder', lazy='dynamic',
        foreign_keys='Payment.recorded_by'
    )

    def set_password(self, password):
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Verify the user's password."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self):
        return self.role == self.ROLE_SUPER_ADMIN

    @property
    def is_school_admin(self):
        return self.role == self.ROLE_SCHOOL_ADMIN

    @property
    def is_collector(self):
        return self.role == self.ROLE_COLLECTOR

    @property
    def is_accountant(self):
        return self.role == self.ROLE_ACCOUNTANT

    def __repr__(self):
        return f'<User {self.username}>'


class SchoolClass(db.Model):
    """Class model - represents a class/grade within a school."""

    __tablename__ = 'classes'

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False, index=True)
    class_name = db.Column(db.String(100), nullable=False)

    # Relationships
    students = db.relationship('Student', backref='school_class', lazy='dynamic')

    # Unique constraint: class name must be unique within a school
    __table_args__ = (
        db.UniqueConstraint('school_id', 'class_name', name='uq_school_class_name'),
    )

    def __repr__(self):
        return f'<SchoolClass {self.class_name}>'


class Student(db.Model):
    """Student model."""

    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False, index=True)
    student_id = db.Column(db.String(50), nullable=False, index=True)
    full_name = db.Column(db.String(200), nullable=False, index=True)
    gender = db.Column(db.String(10), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    guardian_name = db.Column(db.String(200))
    guardian_phone = db.Column(db.String(20))
    status = db.Column(db.String(20), default='active', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    payments = db.relationship('Payment', backref='student', lazy='dynamic')

    # Unique constraint: student_id must be unique within a school
    __table_args__ = (
        db.UniqueConstraint('school_id', 'student_id', name='uq_school_student_id'),
    )

    @property
    def is_active(self):
        return self.status == 'active'

    def __repr__(self):
        return f'<Student {self.full_name}>'


class Payment(db.Model):
    """Payment model - tracks weekly student payments."""

    __tablename__ = 'payments'

    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False, default=5.0)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    week_number = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Prevent duplicate payment per student per week per year
    __table_args__ = (
        db.UniqueConstraint('school_id', 'student_id', 'week_number', 'year',
                            name='uq_student_weekly_payment'),
    )

    def __repr__(self):
        return f'<Payment {self.receipt_number}>'


class AuditLog(db.Model):
    """Audit log model - tracks critical user actions."""

    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<AuditLog {self.action}>'

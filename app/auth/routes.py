"""Authentication routes."""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User, AuditLog
from app.auth.forms import LoginForm, CreateUserForm, ChangePasswordForm
from app.utils import role_required

auth_bp = Blueprint('auth', __name__, template_folder='../templates')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Contact your administrator.', 'danger')
                return render_template('login.html', form=form)

            login_user(user)

            # Audit log
            audit = AuditLog(user_id=user.id, action=f'User logged in: {user.username}')
            db.session.add(audit)
            db.session.commit()

            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    audit = AuditLog(user_id=current_user.id, action=f'User logged out: {current_user.username}')
    db.session.add(audit)
    db.session.commit()

    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/users')
@login_required
@role_required('super_admin', 'school_admin')
def list_users():
    """List users for the current school."""
    if current_user.is_super_admin:
        users = User.query.all()
    else:
        users = User.query.filter_by(school_id=current_user.school_id).all()
    return render_template('users.html', users=users)


@auth_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'school_admin')
def create_user():
    """Create a new user."""
    form = CreateUserForm()

    # Super admin can also create super admins
    if current_user.is_super_admin:
        form.role.choices = [
            ('super_admin', 'Super Admin'),
            ('school_admin', 'School Admin'),
            ('collector', 'Collector'),
            ('accountant', 'Accountant')
        ]

    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            full_name=form.full_name.data,
            role=form.role.data,
            school_id=current_user.school_id if not current_user.is_super_admin else current_user.school_id
        )
        user.set_password(form.password.data)

        db.session.add(user)

        # Audit log
        audit = AuditLog(
            user_id=current_user.id,
            action=f'Created user: {user.username} with role: {user.role}'
        )
        db.session.add(audit)
        db.session.commit()

        flash(f'User {user.username} created successfully.', 'success')
        return redirect(url_for('auth.list_users'))

    return render_template('create_user.html', form=form)


@auth_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@role_required('super_admin', 'school_admin')
def toggle_user(user_id):
    """Activate or deactivate a user."""
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('auth.list_users'))

    # Ensure school isolation for school admins
    if not current_user.is_super_admin and user.school_id != current_user.school_id:
        flash('Access denied.', 'danger')
        return redirect(url_for('auth.list_users'))

    user.is_active = not user.is_active
    status = 'activated' if user.is_active else 'deactivated'

    audit = AuditLog(
        user_id=current_user.id,
        action=f'{status.capitalize()} user: {user.username}'
    )
    db.session.add(audit)
    db.session.commit()

    flash(f'User {user.username} has been {status}.', 'success')
    return redirect(url_for('auth.list_users'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change the current user's password."""
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html', form=form)

        current_user.set_password(form.new_password.data)

        audit = AuditLog(
            user_id=current_user.id,
            action='Changed own password'
        )
        db.session.add(audit)
        db.session.commit()

        flash('Password changed successfully.', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('change_password.html', form=form)

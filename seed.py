"""Seed script to create initial data including a super admin user.

Usage:
    python seed.py

This will create:
    - A Super Admin user (username: admin, password: admin123)
    - A sample school
    - A School Admin for the sample school
"""

import os
import sys
import subprocess

# Ensure the app can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User, School, SchoolClass  # noqa: E402


def seed():
    """Seed the database with initial data."""
    app = create_app(os.environ.get('FLASK_CONFIG', 'development'))

    with app.app_context():
        # Run migrations first to ensure schema is up to date
        print('Running database migrations...')
        try:
            from flask_migrate import upgrade as db_upgrade
            db_upgrade()
            print('Migrations completed successfully.')
        except Exception as e:
            print(f'Migration warning: {e}')
            print('Falling back to db.create_all()...')
            db.create_all()

        # Check if super admin already exists
        existing_admin = User.query.filter_by(username='admin').first()
        if existing_admin:
            print('Super Admin user already exists. Skipping seed.')
            return

        # 1. Create Super Admin
        super_admin = User(
            username='admin',
            full_name='System Administrator',
            role=User.ROLE_SUPER_ADMIN,
            school_id=None
        )
        super_admin.set_password('admin123')
        db.session.add(super_admin)
        db.session.flush()
        print('Created Super Admin: username=admin, password=admin123')

        # 2. Create a sample school
        school = School(
            name='Madrassatu Taqwa Islamic School',
            address='Accra, Ghana'
        )
        db.session.add(school)
        db.session.flush()
        print(f'Created School: {school.name} (ID: {school.id})')

        # 3. Create a School Admin for the sample school
        school_admin = User(
            username='schooladmin',
            full_name='School Administrator',
            role=User.ROLE_SCHOOL_ADMIN,
            school_id=school.id
        )
        school_admin.set_password('admin123')
        db.session.add(school_admin)
        print('Created School Admin: username=schooladmin, password=admin123')

        # 4. Create a Collector
        collector = User(
            username='collector1',
            full_name='Payment Collector',
            role=User.ROLE_COLLECTOR,
            school_id=school.id
        )
        collector.set_password('admin123')
        db.session.add(collector)
        print('Created Collector: username=collector1, password=admin123')

        # 5. Create an Accountant
        accountant = User(
            username='accountant1',
            full_name='School Accountant',
            role=User.ROLE_ACCOUNTANT,
            school_id=school.id
        )
        accountant.set_password('admin123')
        db.session.add(accountant)
        print('Created Accountant: username=accountant1, password=admin123')

        # 6. Create sample classes
        class_names = ['Level 1', 'Level 2', 'Level 3', 'Level 4', 'Tahfeez A', 'Tahfeez B']
        for name in class_names:
            school_class = SchoolClass(school_id=school.id, class_name=name)
            db.session.add(school_class)
        print(f'Created {len(class_names)} classes: {", ".join(class_names)}')

        db.session.commit()
        print('\nDatabase seeded successfully!')
        print('\n--- Login Credentials ---')
        print('Super Admin:   admin / admin123')
        print('School Admin:  schooladmin / admin123')
        print('Collector:     collector1 / admin123')
        print('Accountant:    accountant1 / admin123')
        print('-------------------------')


if __name__ == '__main__':
    seed()

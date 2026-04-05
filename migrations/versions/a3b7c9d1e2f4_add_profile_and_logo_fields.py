"""Add profile and logo fields

Revision ID: a3b7c9d1e2f4
Revises: 950fe487cd77
Create Date: 2026-04-05 11:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3b7c9d1e2f4'
down_revision = '950fe487cd77'
branch_labels = None
depends_on = None


def upgrade():
    # Add logo_path to schools table
    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('logo_path', sa.String(length=500), nullable=True))

    # Add email and profile_picture to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('profile_picture', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('profile_picture')
        batch_op.drop_column('email')

    with op.batch_alter_table('schools', schema=None) as batch_op:
        batch_op.drop_column('logo_path')

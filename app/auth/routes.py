from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from app.auth import bp
from app.models import User


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        expected_username = current_app.config['APP_USERNAME']
        expected_password = current_app.config['APP_PASSWORD']

        if username == expected_username and password == expected_password:
            user = User(id=1, username=username)
            login_user(user, remember=True)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))

        flash('Invalid username or password.', 'error')

    return render_template('auth/login.html')


@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

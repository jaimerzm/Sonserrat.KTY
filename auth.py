from flask import Blueprint, render_template, redirect, url_for, request, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from models import User, db
from datetime import timedelta
from authlib.integrations.flask_client import OAuth
import os
import secrets
import string

auth = Blueprint('auth', __name__)

# Configuración de OAuth
oauth = OAuth()

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Por favor verifica tus credenciales e intenta nuevamente.')
            return redirect(url_for('auth.login'))

        # Configurar duración de la sesión
        session.permanent = True
        login_user(user, remember=remember, duration=timedelta(days=31))
        
        # Guardar información adicional en la sesión
        session['user_id'] = user.id
        session['username'] = user.username
        session['last_login'] = str(user.created_at)

        # Obtener la página a la que el usuario intentaba acceder
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('index')
            
        return redirect(next_page)

    return render_template('login.html')

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')

        # Validaciones
        if not email or not username or not password:
            flash('Todos los campos son requeridos')
            return redirect(url_for('auth.register'))

        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres')
            return redirect(url_for('auth.register'))

        user = User.query.filter_by(email=email).first()
        if user:
            flash('El email ya está registrado')
            return redirect(url_for('auth.register'))

        user = User.query.filter_by(username=username).first()
        if user:
            flash('El nombre de usuario ya está en uso')
            return redirect(url_for('auth.register'))

        new_user = User(email=email, username=username)
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
            
            # Iniciar sesión automáticamente después del registro
            login_user(new_user, remember=True, duration=timedelta(days=31))
            session.permanent = True
            
            flash('¡Registro exitoso!')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash('Error al registrar el usuario. Por favor, intenta nuevamente.')
            return redirect(url_for('auth.register'))

    return render_template('register.html')

@auth.route('/login/google')
def login_google():
    # Registrar Google OAuth en la primera solicitud
    if 'google' not in oauth._clients:
        # Obtener credenciales de Google OAuth
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        
        # Verificar que las credenciales existan
        if not client_id or not client_secret:
            flash('Error: Credenciales de Google OAuth no configuradas correctamente.')
            return redirect(url_for('auth.login'))
            
        # Configurar cliente de Google OAuth
        google = oauth.register(
            name='google',
            client_id=client_id,
            client_secret=client_secret,
            access_token_url='https://accounts.google.com/o/oauth2/token',
            access_token_params=None,
            authorize_url='https://accounts.google.com/o/oauth2/auth',
            authorize_params=None,
            api_base_url='https://www.googleapis.com/oauth2/v1/',
            userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
            client_kwargs={'scope': 'email profile'},
        )
    
    # Generar URL de redirección dinámica que funcione tanto en desarrollo como en producción
    # Esto generará la URL correcta basada en el entorno actual
    redirect_uri = url_for('auth.google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth.route('/login/google/callback')
def google_callback():
    try:
        # Obtener token de acceso y datos del usuario
        token = oauth.google.authorize_access_token()
        user_info = oauth.google.get('userinfo').json()
        
        # Verificar si el usuario ya existe por google_id
        user = User.query.filter_by(google_id=user_info['id']).first()
        
        if not user:
            # Verificar si existe un usuario con el mismo email
            user = User.query.filter_by(email=user_info['email']).first()
            
            if user:
                # Actualizar usuario existente con google_id
                user.google_id = user_info['id']
            else:
                # Crear nuevo usuario
                username = user_info.get('name', '').replace(' ', '') or user_info.get('email').split('@')[0]
                # Asegurar que el username sea único
                base_username = username
                count = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}{count}"
                    count += 1
                
                # Generar contraseña aleatoria (no será usada pero es requerida)
                password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
                
                user = User(
                    email=user_info['email'],
                    username=username,
                    google_id=user_info['id']
                )
                user.set_password(password)
                db.session.add(user)
        
        # Actualizar y guardar cambios
        db.session.commit()
        
        # Iniciar sesión
        login_user(user, remember=True, duration=timedelta(days=31))
        session.permanent = True
        session['user_id'] = user.id
        session['username'] = user.username
        
        return redirect(url_for('index'))
    except Exception as e:
        flash(f'Error al iniciar sesión con Google: {str(e)}')
        return redirect(url_for('auth.login'))

@auth.route('/guest-login')
def guest_login():
    # Generar nombre de usuario único para invitado
    guest_username = f"guest_{secrets.token_hex(4)}"
    guest_email = f"{guest_username}@guest.local"
    
    # Crear usuario invitado
    guest_user = User(
        username=guest_username,
        email=guest_email,
        is_guest=True
    )
    
    # Generar contraseña aleatoria
    password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
    guest_user.set_password(password)
    
    try:
        db.session.add(guest_user)
        db.session.commit()
        
        # Iniciar sesión como invitado
        login_user(guest_user, remember=False)
        session['is_guest'] = True
        session['user_id'] = guest_user.id
        session['username'] = guest_user.username
        
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error al iniciar sesión como invitado: {str(e)}')
        return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
    # Limpiar toda la información de sesión
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))

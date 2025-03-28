# app/routes.py
from flask import Blueprint, render_template, redirect, session, url_for, flash, request, jsonify, Response
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf.csrf import generate_csrf  # Add this import
from .models import User, Note, Board, Access, UserPreferences, Reply
from .forms import LoginForm, RegisterForm, NoteForm
from . import db, login_manager
import os
from flask import current_app
from sqlalchemy.exc import OperationalError, SQLAlchemyError

app = Blueprint('app', __name__)

@app.route('/', methods=['GET', 'POST'])
def authentication():
    # Make session permanent to prevent premature expiration
    session.permanent = True
    
    # Force session initialization
    if 'csrf_token' not in session:
        session['csrf_token'] = generate_csrf()
        # Force the session to be saved
        session.modified = True

    print("Form data:", request.form)  # Debug to show all form data received
    
    if current_user.is_authenticated:
        return redirect(url_for('app.notes'))

    login_form = LoginForm()
    register_form = RegisterForm()

    if request.method == 'POST':
        if 'login' in request.form:
            if login_form.validate_on_submit():
                response = process_login(login_form)
                if response:
                    return response
                else:
                    flash('Login failed. Please check your credentials.', 'alert-loginfail')
            else:
                flash('Login failed. Please check your credentials.', 'alert-loginfail')
            return render_template('authentication.html', login_form=login_form, register_form=register_form, form_type='login')

        elif 'register' in request.form:
            existing_user = User.query.filter_by(email=register_form.email.data).first()
            if existing_user:
                flash('Email already registered. Please log in or use a different email.', 'alert-registerfail')
                return render_template('authentication.html', login_form=LoginForm(), register_form=register_form, form_type='register')
            
            if register_form.validate_on_submit():
                response = register_user(register_form)
                if response:
                    return response
                else:
                    flash('Registration failed. Please check your input.', 'alert-registerfail')
            else:
                flash('Registration failed. Please check your input.', 'alert-registerfail')
            return render_template('authentication.html', login_form=login_form, register_form=register_form, form_type='register')

    return render_template('authentication.html', login_form=login_form, register_form=register_form)


@app.route('/notes', methods=['GET', 'POST'])
@login_required
def notes():
    form = NoteForm()
    board_id = session.get('active_board_id')
    print(f"Current active board ID: {board_id}")  # Debug statement

    owned_boards = Board.query.filter_by(owner_id=current_user.id)
    granted_access_boards = Board.query.join(Access).filter(Access.user_id == current_user.id)
    boards = owned_boards.union(granted_access_boards).all()
    current_board = Board.query.get(board_id) if board_id else None
    current_board_title = current_board.title if current_board else "Your Notes"

    if request.method == 'POST' and form.validate_on_submit():
        if board_id:
            new_note = Note(content=form.content.data, user_id=current_user.id, board_id=board_id)
            db.session.add(new_note)
            db.session.commit()
            flash('Note added successfully!', 'alert-success')
        else:
            flash('No board selected.', 'error')
            
    notes = Note.query.filter_by(board_id=board_id).all() if board_id else []
    
    # Fetch user information for formatting
    notes_with_user_data = [
        {
            'note': note,
            'user_name': note.user.preferences.username if note.user.preferences else note.user.email,
            'user_photo': note.user.preferences.profile_picture if note.user.preferences and note.user.preferences.profile_picture else url_for('static', filename='images/default-avatar.jpg')
        }
        for note in notes
    ]
        
    return render_template('notes.html', notes=notes_with_user_data, form=form, boards=boards, current_board_title=current_board_title, user_id=current_user.id)


def process_login(form):
    user = User.query.filter_by(email=form.email.data).first()
    if user and check_password_hash(user.password, form.password.data):
        login_user(user, remember=True)
        if not user.boards:
            # Create a default board if the user has none
            default_board = Board(title='Default Board', owner=user)
            db.session.add(default_board)
            db.session.commit()
            session['active_board_id'] = default_board.id
        else:
            session['active_board_id'] = user.boards[0].id 
        flash('Login successful!', 'alert-success')
        return redirect(url_for('app.notes'))
    else:
        return None

def register_user(form):
    try:
        # Create user
        new_user = User(email=form.email.data, password=generate_password_hash(form.password.data))
        db.session.add(new_user)
        db.session.flush()  # Get the user ID without committing yet
        
        # Create default preferences
        preferences = UserPreferences(user_id=new_user.id)
        db.session.add(preferences)
        
        # Create default board
        default_board = Board(title='Default Board', owner=new_user)
        db.session.add(default_board)
        
        # Commit all changes to database
        db.session.commit()
        
        # Log in the user automatically
        login_user(new_user, remember=True)
        
        # Set active board in session
        session['active_board_id'] = default_board.id
        
        # Flash success message
        flash('Welcome to TaskHub! Your account has been created successfully.', 'alert-success')
        
        # Redirect to notes page instead of login
        return redirect(url_for('app.notes'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during registration: {e}")
        flash('Registration failed. Please try again.', 'alert-registerfail')
        return None

@app.route('/logout')
@login_required
def logout():
    try:
        # Store a reference to whether user was logged in
        was_logged_in = current_user.is_authenticated
        
        # Attempt to log the user out
        logout_user()
        
        # Only flash a message if the user was actually logged in
        if (was_logged_in):
            flash('You have been logged out.', 'success')
        
        return redirect(url_for('app.authentication'))
    except (OperationalError, SQLAlchemyError) as e:
        # Log the error
        current_app.logger.error(f"Database error during logout: {e}")
        
        # Clear the session manually since logout_user() failed
        session.clear()
        
        # Redirect to login page with a message
        flash('You have been logged out. (Session cleared manually)', 'info')
        return redirect(url_for('app.authentication'))

@login_manager.unauthorized_handler
def unauthorized():
    flash('You must be logged in to view that page.', 'alert-error')
    return redirect(url_for('app.authentication'))


@app.route('/notes/add', methods=['POST'])
@login_required
def add_note():
    content = request.form.get('content')
    color = request.form.get('color')
    board_id = session.get('active_board_id')
    
    if not board_id:
        return jsonify({"error": "No active board selected"}), 400
        
    new_note = Note(
        content=content,
        color=color,
        user_id=current_user.id,
        board_id=board_id
    )
    
    db.session.add(new_note)
    db.session.commit()
    
    # Return more complete data
    return jsonify({
        'id': new_note.id,
        'content': new_note.content,
        'color': new_note.color,
        'created_at': new_note.created_at.strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/notes')
@login_required
def get_notes():
    notes = Note.query.filter_by(user_id=current_user.id).all()
    return render_template('notes.html', notes=notes)

@app.route('/notes/delete/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash('Permission denied', 'alert-error')
        return redirect(url_for('get_notes'))
    db.session.delete(note) 
    db.session.commit()
    flash('Note deleted successfully!', 'alert-success')
    return redirect(url_for('app.notes'))

@app.route('/notes/update/<int:note_id>', methods=['POST'])
@login_required
def update_note_position_and_size(note_id):
    note = Note.query.get(note_id)
    if note is None:
        return jsonify({"error": "Note not found"}), 404
    
    board = Board.query.get(note.board_id)
    access = Access.query.filter_by(user_id=current_user.id, board_id=note.board_id).first()
    if board.owner_id != current_user.id and (access is None or not access.can_edit):
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    note.position_x = data.get('position_x', note.position_x)
    note.position_y = data.get('position_y', note.position_y)
    note.width = data.get('width', note.width)
    note.height = data.get('height', note.height)
    if 'color' in data:
        note.color = data['color']
    if 'content' in data:
        note.content = data['content']

    db.session.commit()
    return jsonify({"message": "Note updated successfully"}), 200

@app.route('/save_preferences', methods=['POST'])
def save_preferences():
    if not current_user.is_authenticated:
        return jsonify({"message": "User not logged in"}), 401

    try:
        data = request.get_json()
        print("Received data:", data)

        # Validate the JSON payload
        if not data:
            return jsonify({"message": "No data provided"}), 400

        required_fields = [
            'designTheme', 'designBackColor', 'designSideBarColor',
            'timezone', 'enableEmailNotif', 'enableEmailNotifReply', 
            'enableEmailNotifBoard', 'enableEmailNotifOwn', 'enableEmailNotifStar',
            'privacy', 'profilePicture', 'username', 'lightDarkMode', 'noteColour'
        ]
        
        # Check for missing fields
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            print(f"Missing fields: {missing_fields}")
            return jsonify({"message": f"Missing fields: {missing_fields}"}), 400

        user_id = current_user.id
        preferences = UserPreferences.query.filter_by(user_id=user_id).first()

        if not preferences:
            preferences = UserPreferences(user_id=user_id)

        # Assign preferences
        preferences.designTheme = data['designTheme']
        preferences.designBackColor = data['designBackColor']
        preferences.designSideBarColor = data['designSideBarColor']
        preferences.timezone = data['timezone']
        preferences.enable_email_notif = data['enableEmailNotif']
        preferences.enable_email_notif_reply = data['enableEmailNotifReply']
        preferences.enable_email_notif_board = data['enableEmailNotifBoard']
        preferences.enable_email_notif_own = data['enableEmailNotifOwn']
        preferences.enable_email_notif_star = data['enableEmailNotifStar']
        preferences.privacy = data['privacy']
        preferences.profile_picture = data['profilePicture']
        preferences.username = data['username']
        preferences.light_dark_mode = data['lightDarkMode']
        preferences.note_colour = data['noteColour']

        db.session.add(preferences)
        db.session.commit()
        return jsonify({"message": "Preferences saved successfully"}), 200
    except Exception as e:
        print("Error:", e)  # Debugging
        return jsonify({"message": "Failed to save preferences", "error": str(e)}), 400

@app.route('/get_preferences', methods=['GET'])
def get_preferences():
    if not current_user.is_authenticated:
        return jsonify({"message": "User not logged in"}), 401

    user_id = current_user.id
    preferences = UserPreferences.query.filter_by(user_id=user_id).first()
    
    # Create default preferences if not found
    if not preferences:
        preferences = UserPreferences(user_id=user_id)
        db.session.add(preferences)
        db.session.commit()

    # Fix profile picture URL bug
    profile_picture = preferences.profile_picture
    if not profile_picture:
        profile_picture = url_for('static', filename='images/default-avatar.jpg')

    return jsonify({
        'designTheme': preferences.designTheme,
        'designBackColor': preferences.designBackColor,
        'designSideBarColor': preferences.designSideBarColor,
        'timezone': preferences.timezone,
        'enableEmailNotif': preferences.enable_email_notif,
        'enableEmailNotifReply': preferences.enable_email_notif_reply,
        'enableEmailNotifBoard': preferences.enable_email_notif_board,
        'enableEmailNotifOwn': preferences.enable_email_notif_own,
        'enableEmailNotifStar': preferences.enable_email_notif_star,
        'privacy': preferences.privacy,
        'profilePicture': profile_picture,
        'username': preferences.username,
        'lightDarkMode': preferences.light_dark_mode,
        'noteColour': preferences.note_colour
    }), 200

@app.route('/notes/update/color/<int:note_id>', methods=['POST'])
@login_required
def update_note_color(note_id):
    note = Note.query.get(note_id)
    if note is None:
        return jsonify({"error": "Note not found"}), 404

    if note.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    note.color = data.get('color', note.color)
    db.session.commit()
    return jsonify({"message": "Note color updated successfully"}), 200

@app.route('/boards/list', methods=['GET'])
@login_required
def list_boards():
    boards = Board.query.filter_by(owner_id=current_user.id).all()
    return render_template('notes.html', boards=boards)

@app.route('/boards/switch/<int:board_id>', methods=['POST'])
@login_required
def switch_board(board_id):
    board = Board.query.get_or_404(board_id)
    access = Access.query.filter_by(user_id=current_user.id, board_id=board_id).first()

    if board.owner_id != current_user.id and not access:
        return jsonify({'success': False, 'message': 'No Access'}), 403

    session['active_board_id'] = board_id
    print(f"Switched to board ID: {session['active_board_id']}")  # Debug 
    return jsonify({'success': True, 'board_id': board_id})

@app.route('/boards/share', methods=['POST'])
@login_required
def share_board():
    try:
        board_id = request.form.get('board_id')
        email = request.form.get('email')

        print(f"Debug: Board ID = {board_id}, Email = {email}")  # Debug 

        user = User.query.filter_by(email=email).first()
        if not user:
            print("Debug: No user found with that email.")  # Debug 
            return jsonify({'success': False, 'message': 'User not found'}), 404

        board = Board.query.get(board_id)
        if not board:
            print("Debug: No board found with that ID.")  # Debug 
            return jsonify({'success': False, 'message': 'Board not found'}), 404

        if board.owner_id != current_user.id:
            print("Debug: Current user does not own the board.")  # Debug 
            return jsonify({'success': False, 'message': 'No access to this board'}), 403

        access = Access.query.filter_by(user_id=user.id, board_id=board_id).first()
        if access:
            db.session.delete(access)
            db.session.commit()
            print("Debug: Access revoked.")  # Debug 
            return jsonify({'success': True, 'message': 'Access revoked'}), 200
        else:
            new_access = Access(user_id=user.id, board_id=board_id, can_edit=True) 
            db.session.add(new_access)
            db.session.commit()
            print("Debug: Access granted.")  # Debug 
            return jsonify({'success': True, 'message': 'Access granted'}), 200

    except Exception as e:
        print(f"Error: {str(e)}")  # Exception output
        return jsonify({'success': False, 'message': 'Internal Server Error', 'error': str(e)}), 500

@app.route('/boards/details/<int:board_id>', methods=['GET'])
@login_required
def board_details(board_id):
    board = Board.query.get_or_404(board_id)
    access = Access.query.filter_by(user_id=current_user.id, board_id=board_id).first()

    if board.owner_id != current_user.id and not access:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({'id': board.id, 'title': board.title})

@app.route('/create_board', methods=['POST'])
@login_required
def create_board():
    title = request.form.get('title', 'New Board').strip()
    if not title:
        return jsonify({'success': False, 'message': 'Board title is required'}), 400

    try:
        new_board = Board(title=title, owner_id=current_user.id)
        db.session.add(new_board)
        db.session.commit()
        return jsonify({'success': True, 'board_id': new_board.id, 'title': new_board.title}), 201
    except Exception as e:
        db.session.rollback() 
        print("Error creating board:", str(e)) 
        return jsonify({'success': False, 'message': 'Failed to create the board', 'error': str(e)}), 500

@app.route('/notes/get_by_board/<int:board_id>', methods=['GET'])
@login_required
def get_notes_by_board(board_id):
    board = Board.query.get(board_id)
    access = Access.query.filter_by(user_id=current_user.id, board_id=board_id).first()

    if board.owner_id != current_user.id and not access:
        return jsonify({"error": "Unauthorized"}), 403

    notes = Note.query.filter_by(board_id=board_id).all()
    notes_data = [{'id': note.id, 'content': note.content, 'color': note.color, 
                   'position_x': note.position_x, 'position_y': note.position_y, 
                   'width': note.width, 'height': note.height} for note in notes]
    return jsonify(notes_data)

@app.route('/debug/notes')
def debug_notes():
    notes = Note.query.all()  # Gets all notes
    notes_data = [{'id': note.id, 'content': note.content, 'board_id': note.board_id} for note in notes]
    return jsonify(notes_data) 
@app.route('/debug/boards')
def debug_boards():
    boards = Board.query.all()  # Gets all boards
    boards_data = [{'id': board.id, 'title': board.title, 'owner_id': board.owner_id} for board in boards]
    return jsonify(boards_data)

@app.route('/debug/user_boards')
@login_required
def debug_user_boards():
    users_data = []
    users = User.query.all()
    for user in users:
        accessed_boards = Board.query.join(Access, Access.board_id == Board.id).filter(Access.user_id == user.id).all()
        accessed_boards = [{'board_id': board.id, 'title': board.title, 'type': 'access_granted'} for board in accessed_boards]

        users_data.append({
            'user_id': user.id,
            'username': user.email,
            'boards': accessed_boards  # Only show boards where access has been granted
        })

    return jsonify(users_data)
@app.route('/notes/<int:note_id>/add_reply', methods=['POST'])
@login_required
def add_reply(note_id):
    note = Note.query.get_or_404(note_id)
    data = request.get_json()
    reply = Reply(content=data['content'], user_id=current_user.id, note_id=note.id)
    db.session.add(reply)
    db.session.commit()
    return jsonify(reply.to_dict()), 201

@app.route('/notes/<int:note_id>/replies', methods=['GET'])
def get_replies(note_id):
    replies = Reply.query.filter_by(note_id=note_id).all()
    return jsonify([reply.to_dict() for reply in replies])

# Add this temporary route - REMOVE AFTER USING ONCE
@app.route('/admin/reset_db/<secret_key>')
def reset_db(secret_key):
    # Check if secret key matches to prevent unauthorized access
    if secret_key != os.environ.get('ADMIN_SECRET', 'temporary_development_key'):
        return "Unauthorized", 401
    
    try:
        # Drop all tables and recreate them
        db.drop_all()
        db.create_all()
        return "Database schema reset successfully. You can now register accounts."
    except Exception as e:
        current_app.logger.error(f"Database reset error: {e}")
        return f"Error: {str(e)}", 500

@app.route('/update_preferences', methods=['POST'])
@login_required
def update_preferences():
    try:
        data = request.get_json()
        
        # Debug what we received
        current_app.logger.info(f"Received preference update: {str(data.keys() if data else 'None')}")
        
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400
            
        # Get the current user's preferences
        user_prefs = current_user.preferences
        if not user_prefs:
            # Create preferences if they don't exist
            user_prefs = UserPreferences(user_id=current_user.id)
            db.session.add(user_prefs)
        
        # Update fields from the request
        if 'username' in data:
            user_prefs.username = data['username']
        
        if 'light_dark_mode' in data:
            user_prefs.light_dark_mode = data['light_dark_mode']
            
        if 'note_colour' in data:
            user_prefs.note_colour = data['note_colour']
            
        # Handle profile picture (base64 encoded image)
        if 'profile_picture' in data and data['profile_picture']:
            # Make sure it's a valid data URL
            if data['profile_picture'].startswith('data:image'):
                # Check the size of the base64 string
                base64_size = len(data['profile_picture'])
                if base64_size > 5000000:  # ~5MB limit
                    return jsonify({'success': False, 'message': 'Image too large. Please use a smaller image.'}), 400
                
                user_prefs.profile_picture = data['profile_picture']
        
        # Save changes
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating preferences: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/notes/<int:note_id>', methods=['GET'])
@login_required
def get_note(note_id):
    note = Note.query.get_or_404(note_id)
    
    # Check if user has access to this note
    if note.user_id != current_user.id:
        # Check if the note is on a board the user has access to
        access = Access.query.filter_by(user_id=current_user.id, board_id=note.board_id).first()
        if not access and note.board.owner_id != current_user.id:
            return jsonify({"error": "Unauthorized"}), 403
    
    # Get user info for the note
    user = User.query.get(note.user_id)
    user_prefs = UserPreferences.query.filter_by(user_id=user.id).first()
    
    # Get replies
    replies = Reply.query.filter_by(note_id=note.id).all()
    replies_data = []
    
    for reply in replies:
        reply_user = User.query.get(reply.user_id)
        reply_user_prefs = UserPreferences.query.filter_by(user_id=reply_user.id).first()
        
        replies_data.append({
            'id': reply.id,
            'content': reply.content,
            'timestamp': reply.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'username': reply_user_prefs.username if reply_user_prefs else reply_user.email
        })
    
    # Return complete note data
    return jsonify({
        'id': note.id,
        'content': note.content,
        'color': note.color,
        'position_x': note.position_x,
        'position_y': note.position_y,
        'width': note.width,
        'height': note.height,
        'created_at': note.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': note.user_id,
        'user_name': user_prefs.username if user_prefs else user.email,
        'user_photo': user_prefs.profile_picture if user_prefs and user_prefs.profile_picture else '/static/images/default-avatar.jpg',
        'replies': replies_data
    })

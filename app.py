import os
import random
import subprocess
import tempfile
import platform
from datetime import datetime, timedelta, date
from functools import wraps

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from gtts import gTTS

from models import db, User, Vocabulary, PracticeSession, DailySuggestion
from forms import RegistrationForm, LoginForm, VocabularyForm

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///language_learner.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Audio playback configuration
AUDIO_PLAYER_AVAILABLE = False
PLAYER_TYPE = None


# Try different audio playback methods
def init_audio_player():
    global AUDIO_PLAYER_AVAILABLE, PLAYER_TYPE

    # Method 1: Try pygame
    try:
        import pygame
        pygame.init()
        pygame.mixer.init()
        AUDIO_PLAYER_AVAILABLE = True
        PLAYER_TYPE = 'pygame'
        print("✅ Audio player initialized: pygame")
        return
    except ImportError:
        print("⚠️ pygame not installed")
    except Exception as e:
        print(f"⚠️ pygame initialization failed: {e}")

    # Method 2: Try playsound (lightweight alternative)
    try:
        from playsound import playsound
        AUDIO_PLAYER_AVAILABLE = True
        PLAYER_TYPE = 'playsound'
        print("✅ Audio player initialized: playsound")
        return
    except ImportError:
        print("⚠️ playsound not installed")

    # Method 3: Try simpleaudio
    try:
        import simpleaudio as sa
        AUDIO_PLAYER_AVAILABLE = True
        PLAYER_TYPE = 'simpleaudio'
        print("✅ Audio player initialized: simpleaudio")
        return
    except ImportError:
        print("⚠️ simpleaudio not installed")

    # Method 4: Windows native (winsound)
    if platform.system() == 'Windows':
        try:
            import winsound
            AUDIO_PLAYER_AVAILABLE = True
            PLAYER_TYPE = 'winsound'
            print("✅ Audio player initialized: winsound (Windows native)")
            return
        except ImportError:
            print("⚠️ winsound not available")

    # Method 5: macOS native (afplay)
    if platform.system() == 'Darwin':  # macOS
        AUDIO_PLAYER_AVAILABLE = True
        PLAYER_TYPE = 'afplay'
        print("✅ Audio player initialized: afplay (macOS native)")
        return

    # Method 6: Linux native (aplay/paplay)
    if platform.system() == 'Linux':
        AUDIO_PLAYER_AVAILABLE = True
        PLAYER_TYPE = 'aplay'
        print("✅ Audio player initialized: aplay (Linux native)")
        return

    print("❌ No audio player available")


# Initialize audio player on startup
init_audio_player()


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Create database tables
def create_tables():
    with app.app_context():
        db.create_all()
        print("✅ Database tables created successfully!")


# Sample word database (expanded)
WORD_DATABASE = {
    'Spanish': [
        {'word': 'hola', 'translation': 'hello'},
        {'word': 'gracias', 'translation': 'thank you'},
        {'word': 'por favor', 'translation': 'please'},
        {'word': 'adiós', 'translation': 'goodbye'},
        {'word': 'buenos días', 'translation': 'good morning'},
        {'word': 'buenas noches', 'translation': 'good night'},
        {'word': 'casa', 'translation': 'house'},
        {'word': 'perro', 'translation': 'dog'},
        {'word': 'gato', 'translation': 'cat'},
        {'word': 'agua', 'translation': 'water'},
        {'word': 'comida', 'translation': 'food'},
        {'word': 'amigo', 'translation': 'friend'},
    ],
    'French': [
        {'word': 'bonjour', 'translation': 'hello'},
        {'word': 'merci', 'translation': 'thank you'},
        {'word': 's\'il vous plaît', 'translation': 'please'},
        {'word': 'au revoir', 'translation': 'goodbye'},
        {'word': 'maison', 'translation': 'house'},
        {'word': 'chien', 'translation': 'dog'},
        {'word': 'chat', 'translation': 'cat'},
        {'word': 'eau', 'translation': 'water'},
        {'word': 'nourriture', 'translation': 'food'},
        {'word': 'ami', 'translation': 'friend'},
    ],
    'Italian': [
        {'word': 'ciao', 'translation': 'hello/goodbye'},
        {'word': 'grazie', 'translation': 'thank you'},
        {'word': 'per favore', 'translation': 'please'},
        {'word': 'arrivederci', 'translation': 'goodbye'},
        {'word': 'casa', 'translation': 'house'},
        {'word': 'cane', 'translation': 'dog'},
        {'word': 'gatto', 'translation': 'cat'},
        {'word': 'acqua', 'translation': 'water'},
        {'word': 'cibo', 'translation': 'food'},
        {'word': 'amico', 'translation': 'friend'},
    ],
    'German': [
        {'word': 'hallo', 'translation': 'hello'},
        {'word': 'danke', 'translation': 'thank you'},
        {'word': 'bitte', 'translation': 'please'},
        {'word': 'auf wiedersehen', 'translation': 'goodbye'},
        {'word': 'haus', 'translation': 'house'},
        {'word': 'hund', 'translation': 'dog'},
        {'word': 'katze', 'translation': 'cat'},
        {'word': 'wasser', 'translation': 'water'},
        {'word': 'essen', 'translation': 'food'},
        {'word': 'freund', 'translation': 'friend'},
    ],
    'Japanese': [
        {'word': 'こんにちは', 'translation': 'hello'},
        {'word': 'ありがとう', 'translation': 'thank you'},
        {'word': 'お願いします', 'translation': 'please'},
        {'word': 'さようなら', 'translation': 'goodbye'},
        {'word': '家', 'translation': 'house'},
        {'word': '犬', 'translation': 'dog'},
        {'word': '猫', 'translation': 'cat'},
        {'word': '水', 'translation': 'water'},
        {'word': '食べ物', 'translation': 'food'},
        {'word': '友達', 'translation': 'friend'},
    ],
    'Korean': [
        {'word': '안녕하세요', 'translation': 'hello'},
        {'word': '감사합니다', 'translation': 'thank you'},
        {'word': '주세요', 'translation': 'please'},
        {'word': '안녕히 계세요', 'translation': 'goodbye'},
        {'word': '집', 'translation': 'house'},
        {'word': '개', 'translation': 'dog'},
        {'word': '고양이', 'translation': 'cat'},
        {'word': '물', 'translation': 'water'},
        {'word': '음식', 'translation': 'food'},
        {'word': '친구', 'translation': 'friend'},
    ]
}


# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return render_template('index.html', user=current_user)
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            user = User(
                username=form.username.data,
                email=form.email.data,
                native_language=form.native_language.data,
                target_language=form.target_language.data
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()

            # Generate initial daily suggestions
            generate_daily_suggestions(user.id)

            flash(f'🎉 Welcome {user.username}! Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
            print(f"Registration error: {e}")

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=True)
            next_page = request.args.get('next')
            flash(f'👋 Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/vocabulary', methods=['GET', 'POST'])
@login_required
def vocabulary():
    form = VocabularyForm()
    if form.validate_on_submit():
        vocab = Vocabulary(
            user_id=current_user.id,
            word=form.word.data.lower(),
            translation=form.translation.data,
            context=form.context.data,
            proficiency=form.proficiency.data,
            language=current_user.target_language
        )
        db.session.add(vocab)
        db.session.commit()
        flash(f'✨ "{form.word.data}" added to your vocabulary!', 'success')
        return redirect(url_for('vocabulary'))

    user_vocab = Vocabulary.query.filter_by(user_id=current_user.id).order_by(Vocabulary.created_at.desc()).all()
    return render_template('vocabulary.html', form=form, vocabulary=user_vocab)


@app.route('/vocabulary/delete/<int:word_id>')
@login_required
def delete_word(word_id):
    word = Vocabulary.query.get_or_404(word_id)
    if word.user_id == current_user.id:
        word_name = word.word
        db.session.delete(word)
        db.session.commit()
        flash(f'🗑️ "{word_name}" deleted from your vocabulary.', 'success')
    return redirect(url_for('vocabulary'))


@app.route('/daily-words')
@login_required
def daily_words():
    # Get today's suggestions
    today = date.today()
    suggestions = DailySuggestion.query.filter_by(
        user_id=current_user.id,
        date=today
    ).all()

    # If no suggestions for today, generate them
    if not suggestions:
        suggestions = generate_daily_suggestions(current_user.id)

    return render_template('daily_words.html', suggestions=suggestions)


def generate_daily_suggestions(user_id):
    """Generate 5 daily word suggestions based on user's target language"""
    user = User.query.get(user_id)
    today = date.today()

    # Clear old suggestions
    DailySuggestion.query.filter_by(user_id=user_id, date=today).delete()

    # Get language-specific words
    language_words = WORD_DATABASE.get(user.target_language, WORD_DATABASE['Spanish'])

    # Get words user already knows to avoid repetition
    known_words = Vocabulary.query.filter_by(user_id=user_id).with_entities(Vocabulary.word).all()
    known_words_list = [w.word for w in known_words]

    # Filter out known words
    available_words = [w for w in language_words if w['word'] not in known_words_list]

    # If no new words available, use all words
    if len(available_words) < 5:
        available_words = language_words

    # Randomly select up to 5 words
    selected_words = random.sample(available_words, min(5, len(available_words)))

    suggestions = []
    for word_data in selected_words:
        suggestion = DailySuggestion(
            user_id=user_id,
            word=word_data['word'],
            translation=word_data['translation'],
            date=today
        )
        db.session.add(suggestion)
        suggestions.append(suggestion)

    db.session.commit()
    return suggestions


@app.route('/pronunciation')
@login_required
def pronunciation():
    # Check if audio is available
    if not AUDIO_PLAYER_AVAILABLE:
        flash('⚠️ Audio playback is not available. You can still practice by reading words aloud.', 'warning')

    # Get words that need practice (low proficiency)
    words_to_practice = Vocabulary.query.filter_by(
        user_id=current_user.id
    ).filter(Vocabulary.proficiency < 3).order_by(Vocabulary.last_reviewed).limit(10).all()

    # If no vocabulary words, use daily suggestions
    if not words_to_practice:
        today = date.today()
        suggestions = DailySuggestion.query.filter_by(
            user_id=current_user.id,
            date=today
        ).all()
        words_to_practice = suggestions

    return render_template('pronunciation.html', words=words_to_practice, audio_available=AUDIO_PLAYER_AVAILABLE)


def play_audio_with_playsound(filename):
    """Play audio using playsound"""
    from playsound import playsound
    playsound(filename)
    return True


def play_audio_with_simpleaudio(filename):
    """Play audio using simpleaudio"""
    import simpleaudio as sa
    wave_obj = sa.WaveObject.from_wave_file(filename)
    play_obj = wave_obj.play()
    play_obj.wait_done()
    return True


def play_audio_with_winsound(filename):
    """Play audio using winsound (Windows)"""
    import winsound
    winsound.PlaySound(filename, winsound.SND_FILENAME)
    return True


def play_audio_with_system(filename):
    """Play audio using system commands"""
    system = platform.system()
    if system == 'Darwin':  # macOS
        subprocess.run(['afplay', filename])
        return True
    elif system == 'Linux':
        # Try different players
        players = ['aplay', 'paplay', 'mpg123']
        for player in players:
            try:
                subprocess.run([player, filename], check=True)
                return True
            except (subprocess.SubprocessError, FileNotFoundError):
                continue
    return False


@app.route('/speak/<word>')
@login_required
def speak_word(word):
    """Text-to-speech endpoint with multiple playback options"""

    if not AUDIO_PLAYER_AVAILABLE:
        return jsonify({
            'success': False,
            'error': 'Audio playback is not available on this system',
            'fallback': 'Try reading the word aloud yourself!'
        })

    temp_filename = None
    try:
        # Get user's target language
        lang_code = {
            'Spanish': 'es',
            'French': 'fr',
            'German': 'de',
            'Italian': 'it',
            'Japanese': 'ja',
            'Korean': 'ko',
            'Chinese': 'zh-cn'
        }.get(current_user.target_language, 'es')

        # Generate speech
        tts = gTTS(text=word, lang=lang_code, slow=False)

        # Save to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as fp:
            temp_filename = fp.name
            tts.save(temp_filename)

        # Play audio based on available player
        play_success = False

        if PLAYER_TYPE == 'pygame':
            try:
                import pygame
                pygame.mixer.music.load(temp_filename)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
                play_success = True
            except Exception as e:
                print(f"Pygame playback failed: {e}")

        elif PLAYER_TYPE == 'playsound':
            try:
                play_audio_with_playsound(temp_filename)
                play_success = True
            except Exception as e:
                print(f"Playsound playback failed: {e}")

        elif PLAYER_TYPE == 'simpleaudio':
            try:
                play_audio_with_simpleaudio(temp_filename)
                play_success = True
            except Exception as e:
                print(f"Simpleaudio playback failed: {e}")

        elif PLAYER_TYPE == 'winsound':
            try:
                play_audio_with_winsound(temp_filename)
                play_success = True
            except Exception as e:
                print(f"Winsound playback failed: {e}")

        elif PLAYER_TYPE in ['afplay', 'aplay']:
            try:
                play_audio_with_system(temp_filename)
                play_success = True
            except Exception as e:
                print(f"System playback failed: {e}")

        # Clean up
        if temp_filename and os.path.exists(temp_filename):
            os.unlink(temp_filename)

        if play_success:
            return jsonify({
                'success': True,
                'message': f'🔊 Playing pronunciation for "{word}"'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Could not play audio with any available method'
            })

    except Exception as e:
        # Clean up on error
        if temp_filename and os.path.exists(temp_filename):
            try:
                os.unlink(temp_filename)
            except:
                pass
        return jsonify({'success': False, 'error': str(e)})


@app.route('/practice-result', methods=['POST'])
@login_required
def practice_result():
    """Record pronunciation practice results"""
    data = request.json
    word = data.get('word')
    correct = data.get('correct', False)

    # Update vocabulary proficiency
    vocab = Vocabulary.query.filter_by(
        user_id=current_user.id,
        word=word.lower()
    ).first()

    if vocab:
        vocab.review_count += 1
        if correct:
            vocab.proficiency = min(5, vocab.proficiency + 0.5)
            message = 'Great job!'
        else:
            vocab.proficiency = max(0, vocab.proficiency - 0.2)
            message = 'Keep practicing!'
        vocab.last_reviewed = datetime.utcnow()
        db.session.commit()
    else:
        message = 'Practice recorded!'

    # Update daily suggestion if applicable
    today = date.today()
    suggestion = DailySuggestion.query.filter_by(
        user_id=current_user.id,
        word=word.lower(),
        date=today
    ).first()

    if suggestion:
        suggestion.practiced = True
        db.session.commit()

    # Create practice session record
    session_record = PracticeSession(
        user_id=current_user.id,
        words_practiced=1,
        correct_pronunciations=1 if correct else 0,
        session_duration=10  # placeholder, you can calculate actual duration
    )
    db.session.add(session_record)
    db.session.commit()

    return jsonify({'success': True, 'message': message})


@app.route('/statistics')
@login_required
def statistics():
    # Get vocabulary statistics
    total_words = Vocabulary.query.filter_by(user_id=current_user.id).count()

    proficiency_distribution = {
        'Beginner (0-2)': Vocabulary.query.filter_by(user_id=current_user.id).filter(
            Vocabulary.proficiency <= 2).count(),
        'Intermediate (2-4)': Vocabulary.query.filter_by(user_id=current_user.id).filter(Vocabulary.proficiency > 2,
                                                                                         Vocabulary.proficiency <= 4).count(),
        'Advanced (4-5)': Vocabulary.query.filter_by(user_id=current_user.id).filter(Vocabulary.proficiency > 4).count()
    }

    # Words added over time (last 7 days)
    last_week = datetime.utcnow() - timedelta(days=7)
    recent_words = Vocabulary.query.filter_by(
        user_id=current_user.id
    ).filter(Vocabulary.created_at >= last_week).count()

    # Practice statistics
    total_practice_sessions = PracticeSession.query.filter_by(user_id=current_user.id).count()
    total_words_practiced = db.session.query(db.func.sum(PracticeSession.words_practiced)).filter_by(
        user_id=current_user.id).scalar() or 0

    # Words by language
    words_by_language = {
        current_user.target_language: total_words
    }

    # Daily streak (simplified)
    last_practice = PracticeSession.query.filter_by(user_id=current_user.id).order_by(
        PracticeSession.session_date.desc()).first()

    return render_template('statistics.html',
                           total_words=total_words,
                           proficiency_distribution=proficiency_distribution,
                           recent_words=recent_words,
                           total_practice_sessions=total_practice_sessions,
                           total_words_practiced=total_words_practiced,
                           words_by_language=words_by_language,
                           last_practice=last_practice)


@app.route('/api/search-word', methods=['POST'])
@login_required
def search_word():
    """Simple word search"""
    data = request.json
    word = data.get('word', '').lower().strip()

    if not word:
        return jsonify({'exists': False, 'error': 'No word provided'})

    # Search in user's vocabulary
    existing = Vocabulary.query.filter_by(
        user_id=current_user.id,
        word=word
    ).first()

    # Search in word database
    language_words = WORD_DATABASE.get(current_user.target_language, [])
    word_data = next((w for w in language_words if w['word'] == word), None)

    response = {
        'exists': bool(existing or word_data),
        'word': word
    }

    if word_data:
        response['translation'] = word_data['translation']

    if existing:
        response['in_vocabulary'] = True
        response['proficiency'] = existing.proficiency

    return jsonify(response)


if __name__ == '__main__':
    create_tables()
    print(f"🚀 Language Learning Partner starting up...")
    print(f"🎯 Audio player: {PLAYER_TYPE if PLAYER_TYPE else 'None'}")
    print(f"🌐 Server: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
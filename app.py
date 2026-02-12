import os
import random
from datetime import datetime, timedelta, date
from functools import wraps
from gtts import gTTS
import pygame
import tempfile

from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

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

# Initialize pygame for audio playback
pygame.init()
pygame.mixer.init()


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Sample word database (in production, use a real API or database)
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
    ],
    # Add more languages as needed
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

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
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
        flash('Word added to vocabulary!', 'success')
        return redirect(url_for('vocabulary'))

    user_vocab = Vocabulary.query.filter_by(user_id=current_user.id).order_by(Vocabulary.created_at.desc()).all()
    return render_template('vocabulary.html', form=form, vocabulary=user_vocab)


@app.route('/vocabulary/delete/<int:word_id>')
@login_required
def delete_word(word_id):
    word = Vocabulary.query.get_or_404(word_id)
    if word.user_id == current_user.id:
        db.session.delete(word)
        db.session.commit()
        flash('Word deleted successfully!', 'success')
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

    # Randomly select 5 words
    selected_words = random.sample(language_words, min(5, len(language_words)))

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
    # Get words that need practice (low proficiency)
    words_to_practice = Vocabulary.query.filter_by(
        user_id=current_user.id
    ).filter(Vocabulary.proficiency < 3).limit(10).all()

    # If no vocabulary words, use daily suggestions
    if not words_to_practice:
        today = date.today()
        suggestions = DailySuggestion.query.filter_by(
            user_id=current_user.id,
            date=today
        ).all()
        words_to_practice = suggestions

    return render_template('pronunciation.html', words=words_to_practice)


@app.route('/speak/<word>')
@login_required
def speak_word(word):
    """Text-to-speech endpoint"""
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

        # Play audio
        pygame.mixer.music.load(temp_filename)
        pygame.mixer.music.play()

        # Clean up after playback
        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)

        os.unlink(temp_filename)

        return jsonify({'success': True, 'message': 'Playing pronunciation'})
    except Exception as e:
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
        else:
            vocab.proficiency = max(0, vocab.proficiency - 0.2)
        vocab.last_reviewed = datetime.utcnow()

        db.session.commit()

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

    return jsonify({'success': True})


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

    return render_template('statistics.html',
                           total_words=total_words,
                           proficiency_distribution=proficiency_distribution,
                           recent_words=recent_words,
                           total_practice_sessions=total_practice_sessions,
                           total_words_practiced=total_words_practiced,
                           words_by_language=words_by_language)


@app.route('/api/search-word', methods=['POST'])
@login_required
def search_word():
    """Simple word search - in production, use a real dictionary API"""
    data = request.json
    word = data.get('word', '').lower()

    # Search in database
    existing = Vocabulary.query.filter_by(
        user_id=current_user.id,
        word=word
    ).first()

    # Search in word database
    language_words = WORD_DATABASE.get(current_user.target_language, [])
    word_data = next((w for w in language_words if w['word'] == word), None)

    return jsonify({
        'exists': bool(existing or word_data),
        'translation': word_data['translation'] if word_data else None,
        'word': word
    })


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
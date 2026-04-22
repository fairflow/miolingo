# Developer Guide - Miolingo Multi-Language Pronunciation Trainer

**Version 7.8.3** | Last Updated: April 2026

This guide is for developers who want to contribute to, modify, or understand the Miolingo pronunciation trainer codebase.

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [Getting Started](#getting-started)
- [Architecture](#architecture)
- [Development Workflow](#-development-workflow)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Contributing](#-contributing)

---

## 🎯 Project Overview

### What Is This?

A Streamlit web application for practicing pronunciation in multiple languages (Portuguese, French, Dutch, Flemish, German, Italian, Spanish) with real-time feedback using AI speech recognition. Users can select their language and voice/dialect in the sidebar; all practice features work identically for every supported language.

### Tech Stack

- **Frontend**: Streamlit (Python web framework)
- **Speech Recognition**: OpenAI Whisper (ML model)
- **Text-to-Speech**: Google Cloud TTS / gTTS / eSpeak NG
- **Audio Processing**: ffmpeg, soundfile, numpy
- **Database**: MySQL over SSH tunnel (auth, progress, sessions)
- **Auth**: Argon2 password hashing
- **Deployment**: Self-hosted (can also run locally or via Docker)

### Repository Structure

```
miolingo/
├── src/                            # Python source code
│   ├── app.py                      # Main Streamlit application (~2800 lines)
│   ├── miolingo-admin.py          # Admin dashboard
│   ├── app_mysql.py               # Database layer (auth, progress, sessions)
│   ├── app_language_materials.py  # Language materials browser
│   ├── config.py                  # Constants, LANGUAGE_CONFIG, settings
│   ├── translation.py             # Translation providers + LLM translation
│   ├── scoring/                   # Scoring algorithms (comparison, phonemes, practice)
│   ├── audio/                     # TTS and ASR modules
│   └── [other modules]            # Session manager, connection pool, etc.
├── docs/                           # Documentation
│   ├── app-docs/                  # User and developer guides (this dir)
│   ├── dev-docs/                  # Development documentation
│   │   ├── GOLDEN.md              # Matthew↔Claude collaboration overview
│   │   └── SCRIPTS_WORKFLOW.md    # Canonical script and PR workflow
│   └── archive/                   # Historical documentation
├── scripts/                        # Utility scripts
│   ├── bump_version.py            # App version bumping + changelog
│   ├── create-pr.sh               # Push branch + raise PR
│   └── language-generation/       # Language content generation pipeline
├── language_materials/             # Language learning content
│   ├── pt/ fr/ nl/ de/ es/ it/   # 6 language directories
│   └── [level]/                   # Organized by CEFR level (A–D)
├── config/                         # Configuration templates
├── .streamlit/                     # Streamlit configuration
├── AGENTS.md                       # Canonical AI assistant reference
├── APP_CHANGELOG.md                # App version history
├── requirements.txt                # Python dependencies
└── README.md                       # Project overview
```

### Key Files

| File | Purpose |
|------|---------|
| `src/app.py` | Main Streamlit application |
| `src/miolingo-admin.py` | Admin dashboard for monitoring |
| `src/app_mysql.py` | Database layer — always use `get_connection()`, never open new tunnels |
| `scripts/bump_version.py` | Automated version bumping + changelog |
| `scripts/create-pr.sh` | Push branch and raise PR to `claude/dev-swept` |
| `requirements.txt` | Python package dependencies |
| `APP_CHANGELOG.md` | App-specific version history |
| `AGENTS.md` | Canonical project reference for AI assistants and contributors |
| `docs/dev-docs/SCRIPTS_WORKFLOW.md` | Git workflow and script usage reference |

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+** (3.10+ recommended)
- **Git**
- **ffmpeg** (for audio conversion)
  - macOS: `brew install ffmpeg` or `port install ffmpeg`
  - Linux: `apt-get install ffmpeg`
  - Windows: Download from ffmpeg.org
- **portaudio** (for audio recording)
  - macOS: `brew install portaudio` or `port install portaudio`
  - Linux: `apt-get install portaudio19-dev`
  - Windows: Usually handled by pip packages
- **eSpeak NG** (included in repo, but may need compilation)
  - macOS: `brew install espeak-ng` or `port install espeak-ng`
  - Linux: `apt-get install espeak-ng`
  - Windows: Download from GitHub releases

### Initial Setup

#### 1. Clone the Repository

```bash
git clone https://github.com/fairflow/miolingo.git
cd miolingo
```

#### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: First run will download Whisper model (~150MB for `base` model).

#### 4. Verify eSpeak

```bash
espeak --version
```

**Note**: The binary is `espeak`, not `espeak-ng`. If not found, install via:
- macOS: `brew install espeak-ng` or `port install espeak-ng`
- Linux: `apt-get install espeak-ng`

#### 5. Run the App Locally

```bash
streamlit run src/app.py
```

App will open at `http://localhost:8501`

For the admin dashboard:
```bash
streamlit run src/miolingo-admin.py --server.port 8505
```

### Development Environment

Recommended tools:
- **IDE**: VS Code with Python extension
- **Linting**: Pylint or Ruff
- **Formatting**: Black
- **Type Checking**: mypy (optional)

#### VS Code Settings

Create `.vscode/settings.json`:

```json
{
  "python.linting.enabled": true,
  "python.formatting.provider": "black",
  "editor.formatOnSave": true
}
```

---

## 🏗️ Architecture

### Application Flow

```
User Input (Browser)
    ↓
Streamlit Interface (app.py)
    ↓
┌─────────────────────────────────────────────┐
│  Practice Session State                     │
│  - Current phrase                           │
│  - User recordings                          │
│  - Settings (language, voice/dialect, etc.) │
└─────────────────────────────────────────────┘
    ↓
Text-to-Speech (eSpeak NG, gTTS)
    ↓
Audio Generation (per selected language/voice)
    ↓
Optional: MP3→WAV Conversion (ffmpeg)
    ↓
User Records Audio
    ↓
Speech Recognition (Whisper)
    ↓
Phoneme Comparison (Edit Distance)
    ↓
Scoring & Feedback
    ↓
History Storage (JSON)
```

### Key Components

#### 1. Session State Management

Streamlit uses `st.session_state` to persist data across reruns:

```python
# Initialize session state
if 'settings' not in st.session_state:
    st.session_state.settings = load_settings()

if 'current_session' not in st.session_state:
    st.session_state.current_session = {
        "practices": [],
        "start_time": time.time()
    }
```

#### 2. Text-to-Speech Pipeline

```python
def speak_text_gtts(text: str, lang: str = "pt-br", use_wav: bool = False) -> tuple[bytes, str]:
    """
    Generate audio from text using gTTS.
    
    Args:
        text: Text to synthesize
        lang: Language code
        use_wav: Convert to WAV format (for iOS Safari)
        
    Returns:
        (audio_bytes, format) tuple
    """
    # Generate MP3 with gTTS
    tts = gTTS(text=text, lang=lang, slow=False)
    
    if use_wav:
        # Convert MP3→WAV with ffmpeg
        # CRITICAL: Use subprocess.DEVNULL to prevent deadlock
        result = subprocess.run(
            ['ffmpeg', '-i', mp3_path, '-acodec', 'pcm_s16le', 
             '-ar', '22050', '-y', wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return wav_bytes, "wav"
    
    return mp3_bytes, "mp3"
```

**Important**: The `subprocess.DEVNULL` is critical to prevent pipe buffer deadlock with ffmpeg's verbose output.

#### 3. Speech Recognition

```python
def recognize_speech_whisper(audio_file: str, model_name: str = "base") -> str:
    """
    Transcribe audio using OpenAI Whisper.
    
    Args:
        audio_file: Path to audio file (WAV format)
        model_name: Whisper model size (tiny/base/small/medium/large)
        
    Returns:
        Transcribed text
    """
    model = whisper.load_model(model_name)
    result = model.transcribe(
        audio_file,
        language="pt",
        fp16=False  # Disable for CPU compatibility
    )
    return result["text"]
```

#### 4. Phoneme Comparison & Scoring

Two algorithms available:

**Edit Distance (Recommended)**:
```python
def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.
    Handles insertions, deletions, substitutions.
    """
    # Dynamic programming implementation
    # Returns minimum number of edits needed
```

**Positional Matching (Deprecated)**:
```python
def compare_phonemes_positional(target: str, spoken: str) -> dict:
    """
    Character-by-character comparison.
    Less forgiving of minor errors.
    """
```

#### 5. Settings Persistence

```python
def save_settings(settings: Dict):
    """Save settings to practice_config.json"""
    with open("practice_config.json", 'w') as f:
        json.dump(settings, f, indent=2)

def load_settings() -> Dict:
    """Load settings with defaults"""
    default_settings = {
        "speed": 140,
        "pitch": 35,
        "voice": "pt-br",
        "whisper_model_size": "base",
        "duration": 3,
        "comparison_algorithm": "edit_distance",
        "silence_threshold": 0.01,
        "use_wav_audio": False
    }
    # Merge saved settings with defaults
    return merged_settings
```

---

## 🔄 Development Workflow

### Git Workflow

The full, authoritative workflow is in
[`docs/dev-docs/SCRIPTS_WORKFLOW.md`](../dev-docs/SCRIPTS_WORKFLOW.md).
Read that before making any changes.

**Short version:**

- All work lands via PRs targeting `claude/dev-swept` (never push directly to it).
- Branch from `origin/claude/dev-swept` using the explicit form:
  ```bash
  git switch -c claude/<descriptive-name> origin/claude/dev-swept
  ```
- Commit your changes, then bump the version, then create the PR via `create-pr.sh`.
- PRs are reviewed and merged by the maintainer.

### Versioning

We use **Semantic Versioning** (MAJOR.MINOR.PATCH) via `scripts/bump_version.py`:

```bash
# Patch (bug fixes):
python scripts/bump_version.py patch --suffix claude-dev --tag \
  --notes "One-line description of what changed"

# Minor (new features):
python scripts/bump_version.py minor --suffix claude-dev --tag \
  --notes "Description"
```

The script updates `src/config.py`, prepends an entry to `APP_CHANGELOG.md`,
commits, and tags locally. See `SCRIPTS_WORKFLOW.md` for full flag reference.

### Code Style

Follow PEP 8:
- 4 spaces for indentation
- Max line length: 88 characters (Black default)
- Use type hints where helpful
- Document complex functions

### Testing Locally

Before pushing:

1. **Run the app**:
```bash
streamlit run src/app.py
```

2. **Test all practice modes**
3. **Test language materials browser** with all 6 languages
4. **Test on different browsers** (if possible)
5. **Check console for errors** (F12 → Console tab)
6. **Verify database connectivity** (if using MySQL features)

---

## 🧪 Testing

### Manual Testing

See `app-docs/TESTING_GUIDE.md` for comprehensive testing checklist.

### Automated Testing

A unit test suite lives in `tests/`. Run with:

```bash
venv/bin/pytest tests/ -q
```

### CCS Testing Framework

For advanced state-based UI testing, the CCS (Component/Cursor/State)
framework is integrated into the app via `src/ccs_test_framework.py` and
`src/ccs_test_integration.py`. Reference docs are in
`docs/dev-docs/archive/CCS_TESTING_README.md`.

---

## 🚀 Deployment

### Local Development

```bash
source venv/bin/activate
streamlit run src/app.py          # Main app on :8501
streamlit run src/miolingo-admin.py --server.port 8505  # Admin
```

Or use the helper script (handles port management):
```bash
bash scripts/dev_server.sh        # Start on port 8601
bash scripts/dev_server.sh stop   # Stop
```

### Docker

A `docker-compose.yml` is included for containerised deployment (port 8601).

### Production

The app is self-hosted. DB credentials and SSH tunnel config go in
`.streamlit/secrets.toml` (never committed — use `secrets_template.toml`
as a starting point).

---

## 🤝 Contributing

### Before You Start

1. Read this guide thoroughly
2. Check existing issues/feature requests
3. Discuss major changes first (create an issue)

### Contribution Types

#### Bug Fixes

1. Reproduce the bug
2. Create bugfix branch: `git checkout -b bugfix/fix-audio-playback`
3. Fix and test thoroughly
4. Update `APP_CHANGELOG.md` if user-facing
5. Submit for review

#### New Features

1. Discuss feature first (GitHub issue or direct contact)
2. Create feature branch: `git checkout -b feature/spaced-repetition`
3. Implement with tests
4. Update documentation (`USER_GUIDE.md`, etc.)
5. Update `APP_CHANGELOG.md`
6. Submit for review

#### Documentation

- Always welcome!
- Especially helpful: clarifying confusing sections
- Add examples, screenshots, troubleshooting tips

### Pull Request Guidelines

**Good PR**:
- Clear description of what changed and why
- References related issue (if exists)
- Tested on at least one device/browser
- Documentation updated (if user-facing)
- Commit messages are clear

**Example PR description**:
```
## Add spaced repetition practice mode

### Changes
- New "Smart Review" mode that prioritizes low-scoring words
- Stores difficulty ratings in practice history
- Shows recommended next practice time

### Testing
- Tested on Chrome (Mac) and Safari (iPhone)
- Verified settings persistence
- Checked backward compatibility with old history files

### Documentation
- Updated USER_GUIDE.md with new mode instructions
- Added section to TESTING_GUIDE.md
- Updated APP_CHANGELOG.md

Fixes #42
```

### Code Review Process

1. **Submit PR** to `main` branch
2. **Automated checks** (if configured)
3. **Manual review** by maintainer
4. **Address feedback**
5. **Merge** when approved

---

## 📚 Additional Resources

### Internal Documentation

- [`AGENTS.md`](../../AGENTS.md) - Canonical project reference (module map, architecture, DB rules)
- [`docs/dev-docs/SCRIPTS_WORKFLOW.md`](../dev-docs/SCRIPTS_WORKFLOW.md) - Git workflow and script reference
- [`APP_CHANGELOG.md`](../../APP_CHANGELOG.md) - Version history
- [`docs/dev-docs/archive/CCS_TESTING_README.md`](../dev-docs/archive/CCS_TESTING_README.md) - CCS testing framework reference

### External Documentation

- [Streamlit docs](https://docs.streamlit.io/)
- [OpenAI Whisper](https://github.com/openai/whisper)
- [eSpeak NG](https://github.com/espeak-ng/espeak-ng)
- [gTTS](https://gtts.readthedocs.io/)

### Common Issues

#### Whisper Model Not Loading

```python
# Make sure model name is valid
valid_models = ["tiny", "base", "small", "medium", "large"]
```

#### Audio Format Issues

- iOS Safari requires WAV format
- Android/Desktop work with MP3
- Use `use_wav` parameter to toggle

#### ffmpeg Deadlock

```python
# ALWAYS use subprocess.DEVNULL with ffmpeg
subprocess.run(
    ffmpeg_command,
    stdout=subprocess.DEVNULL,  # Critical!
    stderr=subprocess.DEVNULL   # Critical!
)
```

---

## 📞 Contact

For questions or collaboration:

- **Issues**: [github.com/fairflow/miolingo/issues](https://github.com/fairflow/miolingo/issues)
- **Pull Requests**: [github.com/fairflow/miolingo/pulls](https://github.com/fairflow/miolingo/pulls)
- **Email**: io@miolingo.io
- **Live App**: [miolingo3.streamlit.app](https://miolingo3.streamlit.app)
- Maintainer: Matthew & Contributors

---

## 📄 License

GPL-3.0 (inherited from eSpeak NG)

---

**Happy coding! 🚀**

*Last updated: Version 7.8.3 (April 2026)*

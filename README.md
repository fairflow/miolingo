# Miolingo

**Version 6.4.0** - Multi-language pronunciation trainer with real-time AI feedback.

🌐 **Try it live:** [miolingo3.streamlit.app](https://miolingo3.streamlit.app)

## Features

- **Multi-language support**: Portuguese (PT-BR, PT-PT), French, Dutch, Flemish, German, Italian, Spanish
- **Real-time feedback**: AI-powered pronunciation analysis using Whisper ASR
- **Text-to-Speech**: High-quality pronunciation examples using eSpeak NG and gTTS
- **Progress tracking**: Database-backed user progress and history
- **Admin dashboard**: Monitor usage, manage users, track costs
- **Practice modes**: Words, phrases, conversations, and stories
- **Language materials browser**: Explore curated learning content by language and level

## Quick Start

### Try Online

Visit [miolingo3.streamlit.app](https://miolingo3.streamlit.app) to use the app without installation.

### Local Installation

#### Prerequisites

- Python 3.8+ (3.10+ recommended)
- eSpeak NG (for text-to-speech)
- ffmpeg (for audio conversion)
- portaudio (for audio recording)
- MySQL database (local or remote)

#### Installation from GitHub

```bash
# 1. Clone the repository
git clone https://github.com/fairflow/miolingo.git
cd miolingo

# 2. Configure environment
./configure

# 3. Activate virtual environment
source venv/bin/activate

# 4. Install dependencies
make install

# 5. Configure secrets
cp .streamlit/secrets_template.toml .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your credentials

# 6. Run the app
make run
```

### Admin Dashboard

```bash
make run-admin
```

Visit http://localhost:8505

## Documentation

- [User Guide](docs/app-docs/USER_GUIDE.md) - How to use the app
- [Developer Guide](docs/app-docs/DEVELOPER_GUIDE.md) - Development setup
- [Admin Guide](docs/admin-docs/ADMIN_GUIDE.md) - Admin dashboard
- [Version Workflow](VERSION_WORKFLOW.md) - Versioning and releases
- [Local Build Guide](LOCAL-BUILD.md) - Building eSpeak NG locally

## eSpeak NG Integration

Miolingo uses eSpeak NG for text-to-speech. You can:

1. Use system-installed eSpeak NG: `brew install espeak-ng` or `port install espeak-ng`
2. Build eSpeak NG locally (see [LOCAL-BUILD.md](LOCAL-BUILD.md))
3. Point to custom installation in `config/.miolingo.config`

See [ESPEAK_USAGE.md](ESPEAK_USAGE.md) for detailed integration guide.

## Development

```bash
# Install with development dependencies
make install-dev

# Run tests
make test
```

### Version Management

Miolingo uses automated version bumping scripts:

```bash
# Activate virtual environment first
source venv/bin/activate

# Bump version (patch/minor/major)
python scripts/bump_app.py patch        # Development: just update files
python scripts/bump_app.py minor tag    # Release: update + commit + tag
python scripts/bump_app.py major tag push  # Full release: update + commit + tag + push

# Admin dashboard versioning
python scripts/bump_admin.py patch
python scripts/bump_admin.py minor tag push
```

**Note:** Patch versions are typically not tagged. See [BUMP_GUIDE.md](BUMP_GUIDE.md) for detailed workflow and [VERSION_WORKFLOW.md](VERSION_WORKFLOW.md) for versioning strategy.

## Architecture

```files
miolingo/
├── src/                      # Python source code
│   ├── app.py                # Main Streamlit application
│   ├── miolingo-admin.py     # Admin dashboard
│   └── app_*.py              # App modules (audio, database, materials)
├── docs/                     # Documentation
│   ├── app-docs/             # User and developer guides
│   ├── admin-docs/           # Admin dashboard documentation
│   │   └── sources/          # Admin module sources (email_monitor, etc.)
│   ├── dev-docs/             # Development documentation
│   └── archive/              # Historical documentation
├── scripts/                  # Utility scripts
│   ├── bump_app.py           # App version bumping
│   ├── bump_admin.py         # Admin version bumping
│   └── language-generation/  # Language content generation scripts
├── data/                     # Data files
│   └── practice-sets/        # Practice phrases and word lists
├── language_materials/       # Language learning content (6 languages)
│   ├── pt/ fr/ nl/ de/ es/ it/  # Language-specific directories
│   └── [level]/              # Organized by CEFR level (A1, A2, B1, B2, C1, C2)
├── config/                   # Configuration templates
├── .streamlit/               # Streamlit configuration and secrets
└── tests/                    # Test suite (coming soon)
```

## Technology Stack

- **Framework**: Streamlit
- **Speech Recognition**: OpenAI Whisper
- **Text-to-Speech**: eSpeak NG, gTTS
- **Database**: MySQL
- **Audio Processing**: ffmpeg, soundfile, numpy
- **Deployment**: Streamlit Cloud, local

## License

Miolingo is licensed under GPL-3.0. See [COPYING.md](COPYING.md) for full license information.

## Contributing

See [DEVELOPER_GUIDE.md](docs/app-docs/DEVELOPER_GUIDE.md) for contribution guidelines.

## Support

- Documentation: See `docs/` directory
- Issues: GitHub Issues
- Email: <io@miolingo.io>

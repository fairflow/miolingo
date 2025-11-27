# Miolingo

Multi-language pronunciation trainer with real-time AI feedback.

## Features

- **Multi-language support**: Portuguese (PT-BR, PT-PT), French, Dutch, Flemish
- **Real-time feedback**: AI-powered pronunciation analysis using Whisper ASR
- **Text-to-Speech**: High-quality pronunciation examples using eSpeak NG and gTTS
- **Progress tracking**: Database-backed user progress and history
- **Admin dashboard**: Monitor usage, manage users, track costs
- **Practice modes**: Words, phrases, conversations, and stories

## Quick Start

### Prerequisites

- Python 3.8+ (3.10+ recommended)
- eSpeak NG (for text-to-speech)
- ffmpeg (for audio conversion)
- portaudio (for audio recording)
- MySQL database (local or remote)

### Installation

```bash
# 1. Configure environment
./configure

# 2. Activate virtual environment
source venv/bin/activate

# 3. Install dependencies
make install

# 4. Configure secrets
cp .streamlit/secrets_template.toml .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your credentials

# 5. Run the app
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

# Version management
source venv/bin/activate
python scripts/bump_app.py minor tag push
python scripts/bump_admin.py patch tag push
```

See [BUMP_GUIDE.md](BUMP_GUIDE.md) for version management details.

## Architecture

```
miolingo/
├── src/              # Python source code
├── docs/             # Documentation
│   ├── app-docs/     # App documentation
│   └── admin-docs/   # Admin documentation
├── scripts/          # Utility scripts
├── config/           # Configuration templates
├── language_materials/  # Language content
├── .streamlit/       # Streamlit configuration
└── tests/            # Test suite
```

## Technology Stack

- **Framework**: Streamlit
- **Speech Recognition**: OpenAI Whisper
- **Text-to-Speech**: eSpeak NG, gTTS
- **Database**: MySQL
- **Audio Processing**: ffmpeg, soundfile, numpy
- **Deployment**: Streamlit Cloud, local

## License

See [COPYING](COPYING) files for license information.

## Contributing

See [DEVELOPER_GUIDE.md](docs/app-docs/DEVELOPER_GUIDE.md) for contribution guidelines.

## Support

- Documentation: See `docs/` directory
- Issues: GitHub Issues
- Email: io@miolingo.io

# OneMCP

A dynamic orchestrator for MCP Servers.

## Quick Start

### Step 1: Install Development Dependencies (Run Once)

```bash
sudo apt-get install python3 python3-venv git
```

This will:

- Install Python 3
- Install Python venv for virtual environments
- Install Git for version control

### Step 2: Clone This Repository (Run Once)

```bash
git clone https://github.com/ppenna/onemcp.git
cd onemcp
```

### Step 3: Setup Your Development Environment (Run Once)

```bash
./scripts/setup.sh
```

This will:

- Create a virtual environment
- Install dependencies
- Set up pre-push Git hooks
- Configure the development environment

### Step 4: Activate the Virtual Environment (Run Each Session)

```bash
source .venv/bin/activate
```

### Step 5: Run Tests to Verify Setup (Optional)

```bash
pytest
```

### Step 6: Start OneMCP

```bash
python -m onemcp.server
```

The server will start and listen OneMCP for MCP client connections via stdin/stdout.

## Development

### Setup Your Development Environment

```bash
# Initial setup (run once)
./scripts/setup.sh

# Activate virtual environment (run each session)
source .venv/bin/activate
```

### Development Commands

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=onemcp --cov-report=html

# Lint code
ruff check src tests

# Format code
ruff format src tests

# Type checking
mypy src

# Run all quality checks (same as pre-push hook)
ruff format --check src tests && ruff check src tests && mypy src && pytest
```

### Project Structure

```text
├── src/onemcp/              # Main package
│   ├── __init__.py          # Package initialization
│   └── server.py            # MCP server implementation
├── tests/                   # Test suite
│   ├── __init__.py
│   └── test_server.py       # Server tests
├── scripts/                 # Development scripts
│   ├── setup.sh             # Main setup script
│   └── install-hooks.sh     # Git hooks installer
├── hooks/                   # Git hooks
│   └── pre-push             # Pre-push quality checks
├── .github/                 # GitHub configuration
│   ├── workflows/           # CI/CD workflows
├── pyproject.toml          # Project configuration
├── requirements.txt        # Dependencies
└── .editorconfig           # Editor configuration
```

## Code Quality

This project maintains high code quality through:

- **Linting**: Ruff for fast Python linting
- **Formatting**: Ruff formatter for consistent code style
- **Type Checking**: MyPy for static type analysis
- **Testing**: Pytest with async support and coverage reporting
- **Pre-push Hooks**: Automatic quality checks before pushing
- **CI/CD**: GitHub Actions for continuous integration

### Pre-push Hooks

Before each push, the following checks run automatically:

1. Code formatting verification
2. Linting checks
3. Type checking
4. Full test suite

## Testing

The project includes comprehensive tests covering:

- MCP resource handling
- Tool implementations
- Error conditions
- Edge cases

Run tests with:

```bash
# All tests
pytest

# Specific test file
pytest tests/test_server.py

# Specific test
pytest tests/test_server.py::TestTools::test_say_hello_english -v

# With coverage
pytest --cov=onemcp --cov-report=term-missing
```

## CI/CD

### GitHub Actions Workflows

- **CI Pipeline** (`.github/workflows/ci.yml`):
  - Tests on Python 3.9, 3.10, 3.11, 3.12
  - Code quality checks
  - Security scanning
  - Coverage reporting

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run quality checks: `pytest && ruff check src tests && mypy src`
5. Commit your changes: `git commit -m "feat: add your feature"`
6. Push to the branch: `git push origin feature/your-feature`
7. Create a Pull Request

### Development Guidelines

- Follow the existing code style (enforced by Ruff)
- Add tests for new functionality
- Update documentation as needed
- Ensure all quality checks pass

## Usage Statement

This project is a prototype. As such, we provide no guarantees that it will work and you are
assuming any risks with using the code. We welcome comments and feedback. Please send any questions
or comments to any of the following maintainers of the project:

- [Pedro Henrique Penna](ppenna@microsoft.com)

| By sending feedback, you are consenting that it may be used in the further development of this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

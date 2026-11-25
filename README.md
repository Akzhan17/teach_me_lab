

# Teach Me

Teach Me — оқу материалынан автоматты түрде сұрақтар мен жауаптар түріндегі үш flashcard жасайтын Django веб-қосымшасы.

Қосымшаның мақсаты — студенттерге оқу мәтіндерін қайталауға және негізгі ақпаратты есте сақтауға көмектесу.

## Features

- Оқу материалының атауы мен мәтінін енгізу.
- Үш flashcard генерациялау.
- Сұрақ, жауап және бастапқы мәтіннен алынған дәйексөзді көрсету.
- DEMO режимінде алдын ала анықталған үш карточканы пайдалану.
- Қосымша LIVE режимінде Gemini API арқылы карточкалар генерациялау.
- Жасалған материалды базаға сақтау.
- Сақталған материалдың жеке бетінде карточкаларды қарау.

## Technologies

- Python
- Django
- SQLite
- python-dotenv
- Gemini API (optional, LIVE mode)

## Project structure

```text
teachme/
├── config/
├── study/
│   ├── migrations/
│   ├── templates/
│   ├── models.py
│   ├── views.py
│   ├── forms.py
│   ├── services.py
│   ├── demo.py
│   ├── urls.py
│   └── tests.py
├── manage.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Installation and setup

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd teachme
```

### 2. Create a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

Windows and macOS:

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root directory, where `manage.py` is located.

Copy the example configuration:

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

**macOS:**

```bash
cp .env.example .env
```

The example configuration:

```env
TEACHME_MODE=demo

GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite

GEMINI_TIMEOUT_SECONDS=25
```

## Application modes

### DEMO mode

DEMO is the default configuration in `.env.example`.

```env
TEACHME_MODE=demo
```

In DEMO mode, the application uses predefined sample data from `study/demo.py`.

It generates three predefined flashcards without requiring a Gemini API key or an external AI request.

This mode is useful for demonstrating and testing the application without an API connection.

### LIVE mode (optional)

LIVE mode is intended to generate flashcards using the Gemini API.

To configure it, update the `.env` file:

```env
TEACHME_MODE=live
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_TIMEOUT_SECONDS=25
```

Replace `your_gemini_api_key` with your actual API key.

The model name is configurable through `GEMINI_MODEL`.

LIVE mode requires a valid API key and a working connection to the Gemini service.

**Important:** LIVE mode has not been verified in the currently available test results.

## Security

- Never publish your `.env` file.
- Do not commit your Gemini API key to GitHub.
- Keep `.env` in `.gitignore`.
- Use `.env.example` to document configuration variables without exposing secret values.

## Database setup

Run migrations to prepare the database:

```bash
python manage.py migrate
```

## Run the development server

Start the Django development server:

```bash
python manage.py runserver 127.0.0.1:8000
```

Open the application in your browser:

```text
http://127.0.0.1:8000/
```

## Testing and validation

The following commands can be executed by the student to check the project.

### 1. Django system check

```bash
python manage.py check
```

Checks the Django project configuration for common problems.

### 2. Run application tests

```bash
python manage.py test study
```

Runs the tests defined in the `study` application.

### 3. Check migration changes

```bash
python manage.py makemigrations --check --dry-run
```

Checks whether model changes require new migrations without creating migration files.

These commands are verification steps. Their successful completion must be confirmed from the student's own terminal output.


## Verification status

The following checks were executed successfully:

| Check | Result |
|---|---|
| `python manage.py check` | No issues identified |
| `python manage.py test study` | All 6 tests passed |
| `python manage.py makemigrations --check --dry-run` | No changes detected |

Test output:

```text
Found 6 test(s).
Ran 6 tests in 0.033s

OK
```

The test suite completed successfully, including the database rollback test.

LIVE mode has not yet been independently verified.

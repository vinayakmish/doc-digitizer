# 🔍 DocDigitizer — AI-Powered Document Digitization & Data Extraction

<p align="center">
  <strong>Upload any document → Get structured data (JSON & CSV)</strong><br>
  Powered by Google Gemini AI with intelligent local fallback
</p>

---

## ✨ Features

- **15+ File Formats** — PDF, DOCX, XLSX, CSV, PPTX, images (JPG/PNG/BMP/TIFF/WebP), TXT, RTF, ODT, XLS
- **AI-Powered Extraction** — Uses Google Gemini 2.5 Flash for intelligent document understanding
- **Smart Fallback** — Local regex-based text analyzer when AI is unavailable
- **Structured Output** — Key-value pairs, named entities, tables, document classification
- **Export Options** — Download results as clean JSON or CSV
- **OCR Support** — Tesseract OCR fallback for scanned documents and images
- **Modern UI** — Dark glassmorphic design with drag-and-drop upload
- **Real-time Processing** — Live progress tracking with stage-by-stage updates

## 🏗️ Architecture

```
Upload → Format Detection → Preprocessing/Parsing → AI Extraction → JSON/CSV Output
                                                          ↓ (fallback)
                                                   Local Text Analyzer
```

| Component | Technology |
|-----------|-----------|
| Backend API | FastAPI + Uvicorn |
| AI Engine | Google Gemini 2.5 Flash (with 2.0 Flash fallback) |
| OCR | Tesseract (optional) |
| Document Parsing | PyMuPDF, pdfplumber, python-docx, openpyxl, pandas |
| Image Processing | OpenCV, Pillow |
| Frontend | Vanilla HTML/CSS/JS with glassmorphism design |

## 📁 Project Structure

```
doc-digitizer/
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Configuration & settings
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example            # Environment template
│   ├── models/
│   │   └── schemas.py          # Pydantic data models
│   ├── routers/
│   │   └── documents.py        # API endpoints
│   ├── services/
│   │   ├── ai_extractor.py     # Gemini AI extraction engine
│   │   ├── document_parser.py  # Multi-format parser
│   │   ├── format_detector.py  # File format detection
│   │   ├── image_preprocessor.py # OpenCV preprocessing
│   │   ├── ocr_engine.py       # Tesseract OCR fallback
│   │   ├── output_generator.py # JSON/CSV output
│   │   ├── pipeline.py         # Master orchestrator
│   │   └── text_analyzer.py    # Local regex fallback
│   └── utils/
│       └── helpers.py          # Utility functions
├── frontend/
│   ├── index.html              # Main UI
│   ├── css/styles.css          # Dark theme styles
│   └── js/
│       ├── app.js              # App controller
│       ├── upload.js           # File upload handler
│       ├── processing.js       # Progress animations
│       └── results.js          # Results display
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** — [Download](https://www.python.org/downloads/)
- **Google Gemini API Key** (free) — [Get one here](https://aistudio.google.com/apikey)
- **Tesseract OCR** (optional, for scanned documents) — [Download](https://github.com/UB-Mannheim/tesseract/wiki)

### 1. Clone the Repository

```bash
git clone https://github.com/vinayakmish/doc-digitizer.git
cd doc-digitizer
```

### 2. Set Up Python Environment

```bash
cd backend
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy the example env file
cp .env.example .env    # Linux/macOS
copy .env.example .env  # Windows

# Edit .env and add your Gemini API key:
# GEMINI_API_KEY=your_api_key_here
```

### 4. Run the Server

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5. Open the App

Navigate to **http://localhost:8000** in your browser.

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Frontend UI |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/formats` | List supported formats |
| `POST` | `/api/upload` | Upload & process a document |
| `GET` | `/api/status/{job_id}` | Check processing status |
| `GET` | `/api/result/{job_id}` | Get extraction results |
| `GET` | `/api/download/{job_id}/{format}` | Download JSON/CSV output |
| `GET` | `/docs` | Interactive API docs (Swagger) |

### Example: Upload via cURL

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@resume.pdf"
```

### Example Response (JSON)

```json
{
  "job_id": "abc123",
  "filename": "resume.pdf",
  "document_type": "resume",
  "key_value_pairs": [
    {"key": "Name", "value": "Vinayak Mishra"},
    {"key": "Email", "value": "vinayak@example.com"},
    {"key": "Phone", "value": "+91 7992474956"},
    {"key": "CGPA", "value": "9.29 / 10.0"}
  ],
  "entities": [
    {"entity_type": "PERSON", "value": "Vinayak Mishra"},
    {"entity_type": "EMAIL", "value": "vinayak@example.com"},
    {"entity_type": "ORGANIZATION", "value": "CMRIT, Bengaluru"}
  ],
  "tables": [],
  "summary": "Software Developer resume..."
}
```

### Example CSV Output

```csv
key,value
Name,Vinayak Mishra
Email,vinayak@example.com
Phone,+91 7992474956
CGPA,9.29 / 10.0
```

## 🔧 Configuration

All settings are in `backend/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `UPLOAD_DIR` | `uploads` | Upload directory |
| `OUTPUT_DIR` | `outputs` | Output directory |
| `MAX_FILE_SIZE` | `52428800` (50MB) | Max upload size |
| `TESSERACT_CMD` | `C:\Program Files\Tesseract-OCR\tesseract.exe` | Tesseract path |

## 📋 Supported Formats

| Category | Extensions |
|----------|-----------|
| **Images** | `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`, `.webp` |
| **Documents** | `.pdf`, `.doc`, `.docx`, `.txt`, `.rtf`, `.odt` |
| **Spreadsheets** | `.xls`, `.xlsx`, `.csv` |
| **Presentations** | `.ppt`, `.pptx` |

**Excluded:** Audio (`.mp3`, `.wav`, etc.) and Video (`.mp4`, `.avi`, etc.)

## 🧠 How It Works

1. **Upload** — User uploads a document via drag-and-drop or file picker
2. **Format Detection** — File type is identified using magic bytes and extension
3. **Parsing** — Document content is extracted using format-specific parsers
4. **AI Analysis** — Text/document is sent to Gemini for structured extraction
5. **Fallback** — If Gemini is unavailable, local regex analyzer extracts data
6. **Output** — Results are returned as structured JSON and downloadable CSV

## 🛠️ Tech Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, Uvicorn
- **AI:** Google Gemini API (`google-genai` SDK)
- **OCR:** Tesseract (`pytesseract`)
- **Parsing:** PyMuPDF, pdfplumber, python-docx, openpyxl, pandas, python-pptx, odfpy, striprtf
- **Image Processing:** OpenCV, Pillow
- **Frontend:** Vanilla HTML5, CSS3 (glassmorphism), JavaScript (ES6+)

## 📄 License

MIT License — feel free to use, modify, and distribute.

---

<p align="center">
  Built with ❤️ by <a href="https://github.com/vinayakmish">Vinayak Mishra</a>
</p>

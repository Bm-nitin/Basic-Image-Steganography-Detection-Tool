# Basic Image Steganography Detection Tool

> A Web-Based Digital Image Forensics and Steganalysis Application for Cybersecurity Research and Education.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask%203.x-lightgrey.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Deployment](https://img.shields.io/badge/Deploy-Render-success.svg)](https://render.com/)

---

## 1. Project Overview

The **Basic Image Steganography Detection Tool** is a web-based cybersecurity digital forensics application designed to analyze digital images (`.png`, `.bmp`, `.jpg`, `.jpeg`, `.webp`) and detect signs of embedded steganographic payloads.

In digital steganography, secret data or malware payloads are hidden within innocent-looking carrier images by manipulating pixel least significant bits (spatial domain) or appending data past standard file termination markers. This application provides a multi-layered forensic inspection engine that evaluates images through file structure carving, visual bit-plane decomposition, and mathematical statistical tests.

### Key Features
- **Application Factory Pattern**: Clean modular Flask backend decoupled from forensic calculation modules.
- **Cybersecurity Dark UI**: High-contrast, responsive dashboard built with Bootstrap 5.
- **Drag-and-Drop Ingestion**: Client-side validated file upload portal with real-time analysis status updates.
- **Multi-Tier Detection**: Structural/EOF carving, visual bit planes, Shannon entropy, Chi-Square attack, and Sample Pair Analysis (SPA).
- **Heuristic Suspicion Scoring**: Combines individual tests into a transparent 0–100 suspicion score and Low/Medium/High risk classification.
- **Forensic PDF Reports**: Instantly generates downloadable, court-style forensic summary reports using ReportLab.
- **Zero Heavy Infrastructure**: Runs entirely with standard scientific Python packages; no database, Docker, or Node.js required.

---

## 2. Multi-Layer Detection Architecture

The application applies a 5-layer forensic pipeline:

```
[Uploaded Image]
       │
       ├── Layer 1: Structural & Metadata Analysis
       │     ├── File signature & magic bytes verification
       │     ├── MD5 & SHA-256 integrity hash calculation
       │     ├── EXIF & metadata tag extraction
       │     └── Appended trailing data detection (past JPEG FFD9, PNG IEND, BMP declared size)
       │
       ├── Layer 2: Visual Bit-Plane Analysis
       │     ├── Bit-plane decomposition (Bit 0 LSB through Bit 7 MSB)
       │     ├── Color channels (Red, Green, Blue) & Grayscale LSB extraction
       │     └── Visual noise uniformity and parity distribution metrics
       │
       ├── Layer 3: Statistical Steganalysis
       │     ├── Shannon Entropy (Global, channel-wise, and LSB plane)
       │     ├── Westfeld's Chi-Square Attack on Pairs of Values (PoVs)
       │     ├── Adjacent Pixel Correlation (Horizontal, Vertical, Diagonal)
       │     ├── Sample Pair Analysis (SPA) for LSB message rate estimation
       │     └── Pixel intensity distribution histogram (Matplotlib Agg backend)
       │
       ├── Layer 4: Heuristic Risk Scoring
       │     ├── Weighted aggregation of detector results
       │     ├── Steganography Suspicion Index (0 - 100)
       │     └── Risk Classification (Low, Medium, High Risk)
       │
       └── Layer 5: Visualization & PDF Reporting
             ├── Interactive web dashboard with tabbed bit-plane viewer
             └── Exportable digital forensic PDF report (ReportLab)
```

---

## 3. Implemented Detection Methods & Theory

### 1. Structural & EOF Carving
Naive steganography tools (and many CTF challenges) append secret files directly after the valid image byte sequence (`cat payload.zip >> cover.png` or `copy /b cover.jpg + secret.txt`).
- **JPEG**: Inspects bytes after the End-of-Image (EOI) marker `\xFF\xD9`.
- **PNG**: Inspects bytes after the terminal `IEND` chunk (`49 45 4E 44 AE 42 60 82`).
- **BMP**: Compares actual byte count against the declared header size at offset `0x02`.

### 2. Visual Bit-Plane Slicing
In uncompressed 8-bit image representations:
- **MSB (Bit 7)** contains primary edges and recognizable geometry.
- **LSB (Bit 0)** in natural imagery contains subtle sensor noise that retains faint object contours.
- **Stego Detection**: Pseudorandom or encrypted payloads replace Bit 0 with uniformly distributed entropy, turning the plane into pure "salt and pepper" white noise devoid of visual correlation.

### 3. Westfeld's Chi-Square Attack (Pairs of Values - PoVs)
Theoretical Basis: LSB replacement pairs values $(2k, 2k+1)$ for $k \in [0, 127]$. Under embedding, observed counts $n_{2k}$ and $n_{2k+1}$ equalize toward their arithmetic mean:
$$E_{2k} = E_{2k+1} = \frac{n_{2k} + n_{2k+1}}{2}$$
The Chi-Square statistic $\chi^2 = \sum \frac{(n_{2k} - E_{2k})^2}{E_{2k}}$ is evaluated with degrees of freedom $df$. When $p = \text{sf}(\chi^2, df)$ approaches $1.0$, it indicates unnatural PoV symmetry characteristic of spatial LSB substitution.

### 4. Shannon Entropy Analysis
Measures information density and randomness:
$$H(X) = -\sum_{i=0}^{255} P(x_i) \log_2 P(x_i)$$
In natural uncompressed images, lower bit-plane entropy exhibits natural bias. Encrypted or compressed payloads force LSB entropy towards the theoretical maximum ($1.0$ bit/pixel).

### 5. Sample Pair Analysis (SPA)
Evaluates finite differences between adjacent pixel pairs to mathematically estimate the secret message length $p \in [0.0, 1.0]$ embedded in the carrier.

---

## 4. Security Considerations & Hardening

1. **Magic Byte / Signature Verification**: Strictly verifies the file header signature (e.g. `\x89PNG\r\n\x1a\n` or `\xff\xd8\xff`), rejecting spoofed extensions (e.g. malicious `.exe` renamed to `.png`).
2. **Decompression Bomb Protection**: Enforces `Image.MAX_IMAGE_PIXELS = 25_000_000` and dimensions $\le 4096 \times 4096$ to prevent memory exhaustion and DoS via pixel floods.
3. **Upload Size Ceiling**: Enforces `MAX_CONTENT_LENGTH = 10 * 1024 * 1024` (10 MB).
4. **Secure Filename Handling**: Uses `werkzeug.utils.secure_filename` combined with session UUIDs.
5. **Safe Memory Processing**: Images are processed in-memory and temporary caches are purged every 30 minutes, preventing disk accumulation.
6. **Thread-Safe Plotting**: Matplotlib uses the headless `'Agg'` backend and explicitly closes figures to prevent memory leaks.

---

## 5. Technology Stack

- **Backend**: Python 3.10+, Flask 3.x, Werkzeug, Gunicorn
- **Scientific Computing**: NumPy, SciPy
- **Image Processing**: Pillow (PIL), OpenCV Headless (`opencv-python-headless`)
- **Visuals & Reporting**: Matplotlib (Agg backend), ReportLab
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla ES6), Bootstrap 5.3, Bootstrap Icons
- **Testing**: Pytest

---

## 6. Local Setup and Installation

### Prerequisites
- Python 3.10 or higher installed
- Git

### Installation Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/Basic-Image-Steganography-Detection-Tool.git
   cd Basic-Image-Steganography-Detection-Tool
   ```

2. **Create and Activate a Virtual Environment**:
   ```bash
   # Linux/macOS
   python3 -m venv venv
   source venv/bin/activate

   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Generate Controlled Test Samples**:
   ```bash
   python generate_test_samples.py
   ```
   This generates:
   - `tests/test_samples/clean_sample.png` (Clean carrier baseline)
   - `tests/test_samples/stego_lsb_sample.png` (Pseudorandom spatial LSB payload)
   - `tests/test_samples/stego_eof_sample.jpg` (Appended trailing data past EOF)

5. **Run the Test Suite**:
   ```bash
   pytest -v tests/
   ```

6. **Start the Flask Application**:
   ```bash
   python wsgi.py
   ```
   Access the web application in your browser at:
   ```
   http://127.0.0.1:5000
   ```

---

## 7. Render Deployment Guide

The application is fully prepared for zero-configuration deployment on **Render**:

1. **Push to GitHub**:
   Ensure all files are committed and pushed to your GitHub repository.

2. **Create New Web Service on Render**:
   - Go to the [Render Dashboard](https://dashboard.render.com/) and click **New + > Web Service**.
   - Connect your GitHub repository.

3. **Configure Settings**:
   - **Name**: `stego-detector` (or your preferred name)
   - **Region**: Closest to your users (e.g., Frankfurt, Oregon, Singapore)
   - **Environment**: `Python 3`
   - **Branch**: `main`
   - **Build Command**:
     ```bash
     pip install --upgrade pip && pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     gunicorn wsgi:app --workers 2 --threads 2 --timeout 120
     ```

4. **Environment Variables**:
   Add in the Render Environment Variables tab:
   - `FLASK_ENV` = `production`
   - `SECRET_KEY` = `<your-secure-random-string>`
   - `MAX_CONTENT_LENGTH` = `10485760`

5. **Deploy**:
   Click **Create Web Service**. Render will automatically build the environment, install the dependencies, and start the Gunicorn server.

---

## 8. Academic & Forensic Disclaimer

> **IMPORTANT FORENSIC NOTICE:**
> The **Steganography Suspicion Index** produced by this tool is a **heuristic indicator** developed for triage and academic demonstration. Statistical tests (such as Chi-Square PoVs and Shannon Entropy) can be influenced by natural factors including high-frequency image textures, non-standard lossy compression, camera sensor noise, and synthetic graphic patterns. Therefore, a high suspicion score indicates statistical anomalies requiring further manual investigation, not definitive mathematical proof of steganography.

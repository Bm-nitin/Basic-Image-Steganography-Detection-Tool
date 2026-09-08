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
- **Multi-Tier Detection**: Structural/EOF carving, static file/container forensics, visual bit planes, Shannon entropy, Chi-Square attack, and Sample Pair Analysis (SPA).
- **File & Container Forensics**: Identifies foreign embedded archive/executable signatures, trailing bytes, and potential polyglot structures without executing untrusted data.
- **Heuristic Suspicion Scoring**: Combines individual tests into a normalized, weighted 0–100 suspicion score and Low/Medium/High risk classification.
- **Forensic PDF Reports**: Instantly generates downloadable, court-style forensic summary reports using ReportLab.
- **Zero Heavy Infrastructure**: Runs entirely with standard scientific Python packages; no database, Docker, or Node.js required.

---

## 2. Multi-Layer Detection Architecture

The application applies a multi-layer forensic pipeline:

```
[Uploaded Image]
       │
       ├── Layer 0: Authoritative Ingestion & Security Validation
       │     ├── Extension whitelisting & magic-byte validation (PNG, JPEG, BMP, WebP)
       │     ├── Upload size ceiling (10 MB) & dimension constraints (4096px, 25 MP)
       │     └── Pillow raster decompression-bomb protection
       │
       ├── Layer 1: Structural & Metadata Analysis
       │     ├── MD5 & SHA-256 integrity hash calculation
       │     ├── EXIF & metadata tag extraction
       │     └── Format & MIME consistency verification
       │
       ├── Layer 1B: File & Container Forensics
       │     ├── Appended trailing data detection (past JPEG FFD9, PNG IEND, BMP size, WebP RIFF)
       │     ├── Embedded container signature scanning (ZIP, PDF, RAR, 7z, PE, ELF, GZIP, TAR, Java, SQLite)
       │     ├── Heuristic false-positive suppression for compressed raster streams
       │     └── Conservative polyglot container structure assessment
       │
       ├── Layer 2: Visual Bit-Plane Analysis
       │     ├── Bit-plane decomposition (Bit 0 LSB through Bit 7 MSB)
       │     ├── Color channels (Red, Green, Blue) & Grayscale LSB extraction
       │     └── Visual noise uniformity and parity distribution metrics
       │
       ├── Layer 3: Advanced Statistical Steganalysis
       │     ├── Shannon Entropy (Global, channel-wise, and LSB plane)
       │     ├── Westfeld's Chi-Square Attack on Pairs of Values (PoVs)
       │     ├── Adjacent Pixel Correlation (Horizontal, Vertical, Diagonal)
       │     ├── Dumitrescu-Wu-Wang Sample Pair Analysis (SPA) quadratic rate estimation
       │     ├── Fridrich Regular-Singular (RS) Steganalysis with dual flipping masks
       │     ├── Safe static JPEG structural & quantization table analysis (DQT, SOF, SOS)
       │     ├── Multi-channel (Red, Green, Blue) and Alpha channel independence analysis
       │     └── Pixel intensity distribution histogram (Matplotlib Agg backend)
       │
       ├── Layer 4: Normalized Heuristic Risk Scoring
       │     ├── Category weights: Structural (20%), Metadata (10%), Statistical (50%), Visual (20%)
       │     ├── Dynamic statistical budget: 50.0 pt max with automatic JPEG / non-JPEG redistribution
       │     ├── Steganography Suspicion Index (0 - 100)
       │     └── Calibrated Risk Classification (Low, Medium, High Risk)
       │
       └── Layer 5: Visualization & PDF Reporting
             ├── Interactive web dashboard with tabbed bit-plane viewer
             └── Exportable digital forensic PDF report (ReportLab)
```

---

## 3. Implemented Detection Methods & Theory

### 1. Structural Carving & Container Forensics
Performs safe static inspection of raw image bytes to identify appended data and foreign container signatures:
- **EOF Boundary Analysis**: Inspects bytes past legitimate termination markers:
  - **JPEG**: Evaluates bytes after the End-of-Image (EOI) marker `\xFF\xD9`.
  - **PNG**: Evaluates bytes after the terminal `IEND` chunk (`49 45 4E 44 AE 42 60 82`).
  - **BMP**: Compares actual byte count against the declared header size at offset `0x02`.
  - **WebP**: Evaluates bytes after declared RIFF container length (`offset 0x04`).
- **Embedded Container Signatures**: Detects secondary container headers embedded within or appended to the carrier:
  - Archive containers: ZIP (`PK\x03\x04`), RAR (`Rar!\x1a\x07`), 7-Zip (`7z\xbc\xaf\x27\x1c`), TAR (`ustar`), GZIP (`\x1f\x8b`).
  - Document & database formats: PDF (`%PDF-`), SQLite (`SQLite format 3`).
  - Executable & binary formats: Windows PE (`MZ`), Linux ELF (`\x7fELF`), Java Bytecode (`\xca\xfe\xba\xbe`).
- **False-Positive Suppression**: Carrier headers at offset `0` are excluded. Two-byte heuristic signatures (`MZ`, `\x1f\x8b`) require secondary structural verification (e.g. `e_lfanew` PE pointer, DEFLATE compression method) to suppress coincidental matches in compressed raster streams.
- **Polyglot Detection**: Flags files where legitimate image headers coexist with secondary executable or archive containers, indicating potential polyglot constructs.
- **Safe Static Inspection**: All forensic analysis is non-destructive and static; untrusted embedded payloads are never executed, unzipped, or invoked.

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

### 5. Regular-Singular (RS) Steganalysis
Introduced by Fridrich, Goljan, and Du (2001), RS steganalysis detects spatial LSB embedding by measuring the smoothness of pixel groups under invertible flipping operations:
- **Grouping**: Partitions pixels into disjoint horizontal groups $G = (x_1, x_2, x_3, x_4)$ of size $n=4$.
- **Smoothness Discrimination**: Evaluates local variation:
  $$f(G) = \sum_{i=1}^{n-1} |x_{i+1} - x_i|$$
- **Dual Flipping Operations**:
  - $F_1(x) = x \oplus 1$ (standard LSB toggle)
  - $F_{-1}(x) = x - 1$ if $x$ is even else $x + 1$ (with $[0, 255]$ clamping)
  - $F_0(x) = x$ (identity)
- **Masks**: Positive mask $M = [0, 1, 1, 0]$ and negative mask $-M = [0, -1, -1, 0]$.
- **Classification**: Groups are classified into Regular ($f(F(G)) > f(G)$) and Singular ($f(F(G)) < f(G)$).
- **Embedding Rate Estimation**: In clean natural images, $R_M \approx R_{-M}$ and $S_M \approx S_{-M}$ with $R_M > S_M$. Under random LSB embedding, $R_M$ and $S_M$ converge while $R_{-M}$ and $S_{-M}$ diverge. The Fridrich quadratic equation is solved to compute the estimated embedding rate $p \in [0.0, 1.0]$.

### 6. Sample Pair Analysis (SPA)
Formulated by Dumitrescu, Wu, and Wang (2003), Sample Pair Analysis evaluates adjacent horizontal and vertical pixel pairs $(u, v)$:
- Partitions pairs into trace multisets: $C_0$ (pairs in the same PoV $\lfloor u/2 \rfloor = \lfloor v/2 \rfloor$) and $C_1$ (adjacent PoVs).
- Evaluates subsets $X$ ($u \bmod 2 \ne v \bmod 2$) and $Y$ ($u \bmod 2 = v \bmod 2$, i.e. $u=v$).
- Solves the Dumitrescu-Wu-Wang quadratic equation for embedding rate $p \in [0.0, 1.0]$, with fallback to the calibrated PoV parity asymmetry ratio $1.0 - |X - Y| / (X + Y)$.

### 7. Safe Static JPEG Structural Analysis
Inspects genuine JPEG container markers without faking DCT coefficients:
- **DQT Markers**: Extracts luminance and chrominance quantization tables, estimating the compression quality factor $Q \in [1, 100]$ against IJG standard baseline tables.
- **SOF Markers**: Identifies component precision and chroma subsampling ratios (e.g. 4:2:0, 4:2:2, 4:4:4).
- **SOS Markers & Stream Entropy**: Evaluates the Shannon entropy of the entropy-coded scan data stream.
- **Non-JPEG Handling**: Returns `available: False, reason: "not_jpeg"` for non-JPEG formats (PNG, BMP, WebP), dynamically redistributing statistical scoring weights.

### 8. Multi-Channel & Alpha Channel Analysis
- Evaluates Red, Green, and Blue channels independently for LSB density, bit-plane entropy, and variance.
- Computes cross-channel Pearson correlations ($r_{RG}, r_{GB}, r_{RB}$) and cross-channel LSB difference (XOR) entropies $H(R_{LSB} \oplus G_{LSB})$.
- Evaluates the Alpha channel (when present) to distinguish uniform opacity or valid transparency masks from modulated pseudorandom noise payloads.

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

## 8. Interpretation and Limitations

Digital steganalysis is an inherently probabilistic science with distinct boundaries:

### 1. Heuristic Nature of Statistical Indicators
The individual indicators ($I \in [0.0, 1.0]$) and the composite **Steganography Suspicion Index** (0–100) are triage metrics. They measure structural, metadata, or statistical anomalies compared against standard photographic carrier distributions. An elevated indicator signifies that the image deviates from baseline continuous-tone expectations, warranting deeper forensic review. It **does not prove** the existence of hidden data, espionage, or malware.

### 2. Natural Image Variations and False Positives
Statistical steganalysis algorithms can be influenced by legitimate carrier characteristics:
- **High-Frequency Natural Textures**: Natural imagery featuring complex, chaotic textures (e.g. dense foliage, rough stone, fur, grass, or turbulent water) naturally exhibits high entropy and reduced adjacent-pixel correlation.
- **Synthetic & Vector Artwork**: Non-photographic computer graphics, logos, charts, and digital illustrations contain sharp synthetic edges and large areas of uniform color. These lack natural sensor noise and may trigger non-representative PoV parity ratios in Sample Pair Analysis.
- **Dithering & Half-Toning**: Pre-press dithering or error diffusion algorithms intentionally toggle low-order bits to simulate color depth, mimicking LSB modifications.
- **Recompression Artifacts**: Multiple lossy compression cycles introduce high-frequency blocking and quantization ringing that alter spatial bit-plane properties.

### 3. Model Dependency of Embedding Rate Estimators
Both Regular-Singular (RS) Steganalysis and Sample Pair Analysis (SPA) rely on specific mathematical models:
- **Spatial LSB Replacement Assumption**: These estimators model message embedding as random bit substitution in the spatial domain.
- **Adaptive Steganography**: Modern adaptive stego algorithms (e.g., WOW, S-UNIWARD, HUGO) concentrate payloads exclusively along complex edges and textured regions while avoiding smooth areas. Standard uniform RS and SPA models under-estimate or misclassify such content.
- **JPEG Carriers**: Decompressed JPEG carriers exhibit quantized DCT characteristics in the spatial domain; estimating spatial LSB rates on JPEG imagery produces model-distorted outputs. For JPEG files, the tool dynamically activates container structural inspection and suppresses invalid spatial assumptions.

### 4. Scientific Ground Truth and Benchmark Calibration
Empirical detection accuracy, true positive rates, and receiver operating characteristic (ROC) curves cannot be scientifically asserted without evaluation against labeled, standardized image corpora (such as BOSSbase, BOWS2, or ALASKA). The threshold calibrations in this application are tuned for educational demonstration and triage on general imagery.

---

## 9. Academic & Forensic Disclaimer

> **IMPORTANT FORENSIC NOTICE:**
> The **Steganography Suspicion Index** produced by this tool is a **heuristic indicator** developed for triage and academic demonstration. Statistical tests (such as Chi-Square PoVs, RS Steganalysis, and Shannon Entropy) can be influenced by natural factors including high-frequency image textures, non-standard lossy compression, camera sensor noise, and synthetic graphic patterns. Therefore, a high suspicion score indicates statistical anomalies requiring further manual investigation, not definitive mathematical proof of steganography.

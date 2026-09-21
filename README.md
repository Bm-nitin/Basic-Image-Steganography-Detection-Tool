# Basic Image Steganography Detection Tool

> A Web-Based Digital Image Forensics and Steganalysis Application for Cybersecurity Research and Education.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Flask%203.x-lightgrey.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Deployment](https://img.shields.io/badge/Deploy-Render-success.svg)](https://basic-image-steganography-detection-tool.onrender.com/)

---

## 1. Project Overview & Motivation

The **Basic Image Steganography Detection Tool** is a web-based cybersecurity digital forensics application designed to analyze digital images (`.png`, `.bmp`, `.jpg`, `.jpeg`, `.webp`) and detect indicators of embedded steganographic payloads and image tampering.

In digital steganography, secret data or malware payloads are hidden within innocent-looking carrier images by manipulating pixel least significant bits (spatial domain) or appending data past standard file termination markers. This application provides a multi-layered forensic inspection engine that evaluates images through file structure carving, visual bit-plane decomposition, mathematical statistical tests, and explainable tampering detectors.

### Key Capabilities
- **Application Factory Pattern**: Clean modular Flask backend decoupled from forensic calculation modules.
- **Cybersecurity Dark UI**: High-contrast, mobile-responsive dashboard built with Bootstrap 5.
- **Drag-and-Drop Ingestion**: Client-side validated file upload portal with real-time analysis status updates.
- **Multi-Tier Detection**: Structural/EOF carving, static file/container forensics, visual bit planes, Shannon entropy, Chi-Square attack, Sample Pair Analysis (SPA), Regular-Singular (RS) steganalysis, and safe JPEG structural inspection.
- **Image Tampering Forensics**: Independent evaluation of Error Level Analysis (ELA), local noise consistency (MAD estimator), texture variance, edge discontinuities, and block copy-move matching.
- **Heuristic Suspicion Scoring**: Combines individual tests into a normalized, weighted 0–100 suspicion score and Low/Medium/High risk classification.
- **Forensic Evidence & Explainability**: Standardized evidence abstraction and dual-dimension plain-English summaries answering *"Why did this image receive this score?"*
- **Forensic PDF Reports**: Instantly generates downloadable, court-style forensic summary reports using ReportLab.
- **Zero Heavy Infrastructure**: Runs entirely with standard scientific Python packages; no database, Docker, OpenCV, or machine learning models required.

---

## 2. Multi-Tier Forensic Architecture

The application executes an end-to-end multi-layer forensic inspection pipeline:

```
[Uploaded Image Stream]
       │
       ├── Layer 0: Authoritative Ingestion & Security Validation
       │     ├── Extension whitelisting & magic-byte validation (PNG, JPEG, BMP, WebP)
       │     ├── Upload size ceiling (10 MB) & dimension constraints (4096px, 25 MP)
       │     ├── Path traversal and filename sanitation (secure_filename)
       │     └── Pillow raster decompression-bomb protection (Image.MAX_IMAGE_PIXELS)
       │
       ├── Layer 1: Structural & Metadata Analysis
       │     ├── MD5 & SHA-256 integrity hash calculation
       │     ├── EXIF & metadata tag extraction
       │     └── Format & MIME consistency verification (spoofing detection)
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
       ├── Layer 4: Image Tampering & Manipulation Forensics (Phase D)
       │     ├── Error Level Analysis (ELA) with controlled recompression & base64 preview
       │     ├── Local residual noise consistency using robust MAD estimator
       │     ├── Localized texture variance consistency analysis
       │     ├── Directional edge discontinuity & high-frequency gradient inspection
       │     ├── Copy-move block duplicate matching via cKDTree & rigid displacement clustering
       │     └── Independent manipulation indicator (0.0 pts to steganography score)
       │
       ├── Layer 5: Normalized Heuristic Risk Scoring & Explainability (Phase E)
       │     ├── Fixed weights: Structural (20%), Metadata (10%), Statistical (50%), Visual (20%)
       │     ├── Dynamic statistical budget: 50.0 pt max with automatic JPEG / non-JPEG redistribution
       │     ├── Steganography Suspicion Index (0 - 100) & Independent Tampering Score (0 - 100)
       │     ├── Calibrated Risk Classification (Low, Medium, High Risk)
       │     ├── Standardized forensic evidence collation (EvidenceCollector)
       │     └── Dual-dimension plain-English assessments (ExplainabilityEngine)
       │
       └── Layer 6: Visualization & PDF Reporting
             ├── Interactive web dashboard with tabbed bit-plane viewer
             ├── REST API JSON endpoint (/api/analyze)
             └── Exportable digital forensic PDF report with tampering & evidence sections (ReportLab)
```

---

## 3. Detection Methods & Theoretical Foundations

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

### 9. Image Tampering & Manipulation Forensics (Phase D)
Operates as an independent forensic inspection layer designed to identify localized tampering, splicing, and cloning anomalies:
- **Error Level Analysis (ELA)**: Recompresses JPEG image streams at a controlled quality factor ($Q=90$) in-memory and evaluates pixel-level error distributions. Foreign spliced patches with divergent compression histories exhibit discordant error levels. Generates a bounded ($512\text{px}$) amplified difference preview. For non-JPEG formats, gracefully reports `available: False`.
- **Local Residual Noise Analysis**: Computes high-frequency spatial residuals via $3 \times 3$ smoothing (`residual = original - smoothed`). Evaluates local noise dispersion using the **Median Absolute Deviation (MAD)** estimator:
  $$\sigma_{\text{MAD}} = \frac{\text{median}(|\text{residual} - \text{median}(\text{residual})|)}{0.6745}$$
  Unlike standard deviation, MAD suppresses false alarms on sharp geometric edges in synthetic graphics while sensitively flagging spliced camera sensor patches.
- **Local Texture Variance Consistency**: Partitions luminance into bounded blocks ($32 \times 32$, stride 16) and identifies statistical outlier blocks where local texture energy abruptly departs from carrier baselines.
- **Edge Discontinuity & Gradients**: Uses directional SciPy Sobel operators to inspect local gradient densities. Hard cut-and-paste seams without edge feathering trigger elevated boundary gradient density outliers.
- **Copy-Move Duplicate Matching**: Implements block-based duplicate detection using compact 8D descriptors and `scipy.spatial.cKDTree` nearest-neighbor search ($O(N \log N)$). Filters out flat regions ($\sigma < 10.0$) and 1D straight lines via anisotropy thresholds. Groups candidate matches into rigid displacement vector clusters ($\vec{v} = (\Delta x, \Delta y)$). Matches with consistent translation vectors flag duplicated/cloned regions.
- **Strict Forensic Independence**: Tampering detectors contribute exactly `points_added = 0.0` to the Steganography Suspicion Index, exposing tampering results on their own independent 0–100 scale.

---

## 4. Heuristic Suspicion Scoring & Risk Triage Model

The application synthesizes forensic findings into an interpretable **Steganography Suspicion Index** normalized to the $[0.0, 100.0]$ range.

### Category Scoring Budget
The 100-point composite score is allocated across four forensic categories:
- **Structural / File Forensics (20% / Max 20.0 pts)**:
  - Appended trailing data past EOF: up to 20.0 pts (scaled by payload size).
  - Embedded container/payload signatures (ZIP, PDF, PE, ELF): up to 20.0 pts.
- **Metadata & Container Consistency (10% / Max 10.0 pts)**:
  - Extension spoofing (mismatch with magic bytes): up to 10.0 pts.
  - MIME type discrepancies and missing headers: up to 5.0 pts.
- **Advanced Statistical Steganalysis (50% / Max 50.0 pts)**:
  - Non-JPEG images (PNG, BMP, WebP):
    - RS Steganalysis: up to 18.0 pts
    - Sample Pair Analysis (SPA): up to 16.0 pts
    - Chi-Square PoVs Attack: up to 10.0 pts
    - LSB Shannon Entropy: up to 6.0 pts
  - JPEG images:
    - JPEG Structural & Quantization Inconsistency: up to 18.0 pts
    - Chi-Square PoVs Attack: up to 14.0 pts
    - LSB Shannon Entropy: up to 10.0 pts
    - Scan Stream High Entropy: up to 8.0 pts
- **Visual Bit-Plane Analysis (20% / Max 20.0 pts)**:
  - LSB visual noise uniformity and contour erasure: up to 14.0 pts.
  - Multi-channel LSB parity asymmetry: up to 6.0 pts.

### Tampering Independence
Image tampering and manipulation forensics (ELA, Local Noise MAD, Texture Variance, Edge Discontinuity, Copy-Move) operate on an **independent 0–100 scale**. They are reported in the detailed detector breakdown with `points_added = 0.0` to preserve mathematical integrity and prevent spatial editing from skewing steganographic carrier assessment.

### Risk Classification Triage Levels
- **Low Risk (`0.0 - 19.9`)**: Characteristics conform strictly to clean, unmodified photographic imagery.
- **Medium Risk (`20.0 - 59.9`)**: Moderate forensic or structural anomalies detected; manual analyst review recommended.
- **High Risk (`60.0 - 100.0`)**: Strong suspicious indicators observed across multiple independent detector layers.

---

## 5. Security Hardening & Safe Ingestion Architecture

The ingestion pipeline (`app/core/image_validator.py`) enforces strict defense-in-depth controls:

1. **Magic-Byte File Header Verification**: Inspects leading bytes against authoritative image format signatures (`\x89PNG\r\n\x1a\n`, `\xff\xd8\xff`, `BM`, `RIFF...WEBP`), rejecting disguised executables or scripts.
2. **Decompression Bomb & Pixel-Flood Defense**: Enforces `Image.MAX_IMAGE_PIXELS = 25_000_000` (25 MP ceiling) and maximum dimensions $\le 4096 \times 4096$ pixels, preventing memory exhaustion and denial-of-service (DoS) via malicious compression ratios.
3. **Strict Upload Size Ceiling**: Enforces `MAX_CONTENT_LENGTH = 10 * 1024 * 1024` (10 MB). Oversized payloads are terminated before memory ingestion.
4. **Filename Sanitization & Path Traversal Prevention**: Strips relative path specifiers (`../`, `..\`) via `werkzeug.utils.secure_filename` and isolates analysis with unique UUIDs.
5. **Production Secret Key Enforcement**: In production (`FLASK_ENV=production`), `ProductionConfig` strictly requires `SECRET_KEY` from the system environment and raises a fatal `RuntimeError` if unset, preventing insecure default sessions.
6. **Thread-Safe Headless Plotting**: Matplotlib uses the headless `'Agg'` backend and explicitly closes all figure canvases (`plt.close('all')`) to eliminate memory leaks.
7. **Ephemeral In-Memory Storage**: Image processing operates in-memory; cached analysis results are automatically purged after 30 minutes.

---

## 6. Technology Stack & Minimal Dependencies

The application relies on lightweight, well-maintained scientific computing packages without heavy frameworks, machine learning models, or external databases:

| Layer | Technology | Purpose |
|---|---|---|
| **Web Framework** | Flask 3.x, Werkzeug | Modular application factory, routing, CSRF protection |
| **WSGI Server** | Gunicorn | Multi-worker HTTP server for production deployment |
| **Image Processing** | Pillow (PIL) | Pure-Python image decoding, format inspection, pixel extraction |
| **Scientific Computing** | NumPy, SciPy | Spatial matrix algebra, fast KD-Tree search, convolution, Chi-Square |
| **Visualization** | Matplotlib (`Agg`) | Thread-safe pixel intensity histograms and distribution curves |
| **Forensic Reporting** | ReportLab | Court-style, multi-page vector PDF forensic reports |
| **Frontend UI** | Bootstrap 5.3, Bootstrap Icons | Responsive cyber dark theme, tabbed viewers, mobile navigation |
| **Testing** | Pytest | Comprehensive test suite (134+ automated tests) |

> **Dependency Hygiene**: This project intentionally excludes OpenCV (`cv2`) and machine learning libraries (TensorFlow, PyTorch) to ensure rapid cold starts, small deployment slugs (<100 MB), and zero native compilation issues.

---

## 7. Evidence Aggregation & Explainability Engine (Phase E)

Phase E introduces a standardized forensic evidence abstraction and explainability engine to provide transparent, traceable answers to: **"Why did this image receive this score?"**

### Standardized Evidence Representation (`app/core/evidence.py`)
All detectors across structural, metadata, statistical, visual, and tampering layers report observations through a standardized dataclass:
- `category`: Forensic domain (`structural`, `metadata`, `statistical`, `visual`, `tampering`)
- `detector`: Technical detector name (e.g., `RS Steganalysis`, `Error Level Analysis`)
- `severity`: Normalized anomaly rank (`anomaly` > `suspicious` > `clean` > `info`)
- `indicator`: Quantitative anomaly metric normalized to $[0.0, 1.0]$
- `observed_value`: Human-readable technical observation (e.g., `75.4% estimated capacity`)
- `threshold`: Forensic reference baseline for continuous-tone photography (e.g., `< 25.0% estimated capacity`)
- `explanation`: Explainable, non-conclusive forensic statement detailing why the metric is considered normal or anomalous
- `supporting_details`: Dictionary containing raw metric components without sensitive filesystem paths or system secrets

### Dual-Dimension Explainability Engine (`app/core/explainability.py`)
Synthesizes evidence into human-readable assessments while keeping Steganography and Tampering strictly independent:
- **Steganography Assessment**: Synthesizes suspicion score (0–100), calibrated risk level (Low/Medium/High), dynamic metric-traced summary, and mathematical detector contribution breakdown.
- **Tampering Assessment**: Synthesizes independent tampering score (0–100), status (`SUSPICIOUS` / `NOT SUSPICIOUS`), dynamic summary detailing specific localized indicators (copy-move, ELA, noise inconsistency), and detector contributions (contributing 0.0 pts to steganography score).
- **Primary vs. Supporting Evidence**: Automatically segments findings into primary anomalies/suspicious items requiring analyst attention versus supporting baseline checks.

### UI & Reporting Integration
- **Web UI (`app/templates/results.html`)**: Interactive "Forensic Evidence & Explainable Assessment" card featuring side-by-side Steganography and Tampering assessment badges and a responsive primary evidence table.
- **PDF Report (`app/core/report_generator.py`)**: Dedicated Section 5 "Forensic Evidence & Explainable Assessment" and Section 6 "Detector Contribution Breakdown" in official downloadable forensic reports.
- **REST API (`/api/analyze`)**: JSON payload includes top-level `"evidence"` and `"explainability"` objects.

---

## 8. Controlled Evaluation Framework & Ground-Truth Benchmarks

The repository includes a reproducible evaluation harness for evaluating detector sensitivity, specificity, and false-alarm rates against ground-truth controlled samples.

### Dataset Generator (`tests/evaluation/sample_generator.py`)
Deterministically creates synthetic and semi-synthetic benchmark samples with known ground truth:
1. `clean_carrier.png`: Clean photographic carrier with smooth gradients and geometric shapes (0 trailing bytes).
2. `clean_carrier.jpg`: High-quality JPEG carrier (Q90) with standard format termination.
3. `stego_lsb_low.png`: Spatial LSB embedding at ~15% capacity with pseudorandom sequence.
4. `stego_lsb_medium.png`: Spatial LSB embedding at ~50% capacity.
5. `stego_lsb_high.png`: Spatial LSB embedding at 100% capacity.
6. `stego_eof.jpg`: Valid JPEG with 780 bytes of appended secret payload past the EOF marker.
7. `tamper_copymove.png`: Photographic carrier with an identical 48x48 textured block translated and duplicated.
8. `tamper_spliced_noise.png`: Photographic carrier with an 80x80 localized gaussian noise patch injected.

### Running the Evaluation Harness
Execute the evaluation runner from the command line:
```bash
python -m tests.evaluation.evaluator
```
The evaluator outputs performance metrics and writes a machine-readable report to `tests/evaluation/evaluation_report.json`:
- Confusion matrices (True Positives, False Positives, True Negatives, False Negatives)
- Accuracy, Sensitivity / Recall, Specificity, False Positive Rate (FPR), and Precision
- Sample-by-sample forensic breakdown and explainability summaries

> **Academic Note on Evaluation:**
> *In the project's controlled 8-sample synthetic evaluation set, the implemented thresholds achieved 100% accuracy, sensitivity, and specificity. These preliminary results are from a **Controlled Synthetic Evaluation** and are not representative of general or real-world detector accuracy. Real-world performance varies significantly depending on carrier entropy, natural textures, compression history, and adaptive steganography schemes.*

---

## 9. Local Setup and Installation Instructions

### Prerequisites
- Python 3.10 or higher installed
- Git

### Installation Steps

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/Bm-nitin/Basic-Image-Steganography-Detection-Tool.git
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
   python -m tests.evaluation.sample_generator
   ```

5. **Run the Automated Test Suite**:
   ```bash
   pytest -v tests/
   ```

6. **Start the Flask Application**:
   ```bash
   python wsgi.py
   ```
   Access the web dashboard in your browser at:
   ```
   http://127.0.0.1:5000
   ```

---

## 10. REST API Specification

The application provides a programmatic JSON REST API for automated forensic analysis pipelines and CI/CD security scanning.

### Health Check Endpoint
- **URL**: `/health`
- **Method**: `GET`
- **Response** (`200 OK`):
  ```json
  {
    "service": "Basic Image Steganography Detection Tool",
    "status": "healthy",
    "version": "1.0.0"
  }
  ```

### Forensic Analysis Endpoint
- **URL**: `/api/analyze`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Body**: `image` (binary file upload)

#### Example cURL Request:
```bash
curl -X POST -F "image=@evidence.png" http://127.0.0.1:5000/api/analyze
```

#### Successful JSON Response (`200 OK`):
```json
{
  "filename": "evidence.png",
  "scoring": {
    "suspicion_score": 70.0,
    "risk_level": "High",
    "risk_badge": "danger",
    "risk_summary": "Strong suspicious indicators detected; multiple forensic anomalies observed.",
    "tampering_score": 0.0,
    "tampering_indicator": 0.0,
    "tampering_suspicious": false,
    "category_scores": {
      "structural": 0.0,
      "metadata": 0.0,
      "statistical": 50.0,
      "visual": 20.0,
      "tampering": 0.0
    },
    "detector_breakdown": [
      {
        "category": "Statistical Steganalysis",
        "detector": "RS Steganalysis",
        "status": "Anomaly",
        "points_added": 18.0,
        "details": "Regular-Singular difference convergence indicates spatial LSB embedding."
      }
    ]
  },
  "metadata": {
    "dimensions": [300, 300],
    "format": "PNG",
    "sha256": "4a5c...78e9"
  },
  "file_forensics": {
    "trailing_data": {"has_trailing_data": false, "size": 0},
    "embedded_payloads": {"detected": false}
  },
  "evidence": {
    "primary_anomalies": [...],
    "supporting_evidence": [...]
  },
  "explainability": {
    "steganography": {
      "score": 70.0,
      "risk": "HIGH",
      "summary": "High steganography suspicion index driven by elevated statistical and visual anomalies."
    },
    "tampering": {
      "score": 0.0,
      "status": "NOT SUSPICIOUS",
      "summary": "No localized tampering or manipulation patterns detected."
    }
  }
}
```

#### Error Responses:
| HTTP Status | Error Code | Description |
|---|---|---|
| `400 Bad Request` | `MISSING_FILE` | Form body did not include the `image` file field. |
| `400 Bad Request` | `EMPTY_FILE` | Uploaded file contains 0 bytes. |
| `400 Bad Request` | `UNSUPPORTED_EXTENSION` | Extension is not in `.png, .bmp, .jpg, .jpeg, .webp`. |
| `400 Bad Request` | `INVALID_MAGIC_BYTES` | File header signature does not match accepted image formats. |
| `400 Bad Request` | `IMAGE_DIMENSION_LIMIT` | Image width or height exceeds 4096px. |
| `400 Bad Request` | `PIXEL_COUNT_LIMIT` | Total pixel count exceeds 25,000,000 pixels. |
| `400 Bad Request` | `CORRUPT_IMAGE` | Corrupt or truncated image stream. |
| `413 Payload Too Large` | `FILE_TOO_LARGE` | File exceeds maximum upload limit of 10 MB. |

---

## 11. Deployment Architecture & Production Readiness

The application is fully prepared for containerless, zero-configuration production deployment on **Render**, **Railway**, or any standard Linux VPS:

### Production Entrypoint
- **WSGI Module**: `wsgi.py` exposes `app = create_app(os.environ.get('FLASK_ENV', 'development'))`.
- **Gunicorn Procfile**:
  ```procfile
  web: gunicorn wsgi:app --workers 2 --threads 2 --timeout 120
  ```

### Production Environment Variables
| Variable | Value | Description |
|---|---|---|
| `FLASK_ENV` | `production` | Enables production security safeguards. |
| `SECRET_KEY` | `<secure-random-string>` | **Mandatory** session encryption secret. In production, missing key raises `RuntimeError`. |
| `MAX_CONTENT_LENGTH` | `10485760` | 10 MB maximum request ceiling. |
| `PORT` | `5000` (or injected by host) | Server listening port. |

### Render Deployment Steps
1. Push repository commits to GitHub.
2. In the [Render Dashboard](https://dashboard.render.com/), click **New + > Web Service** and select this repository.
3. Set **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
4. Set **Start Command**: `gunicorn wsgi:app --workers 2 --threads 2 --timeout 120`
5. In **Environment Variables**, set `FLASK_ENV=production` and generate a cryptographically strong `SECRET_KEY`.
6. Click **Create Web Service**.

---

## 12. Comprehensive Forensic Limitations & Interpretation

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

## 13. Image Tampering Interpretation & Operational Boundaries

The **Image Tampering & Manipulation Forensics** layer provides explainable heuristic evidence for detecting localized tampering, splicing, retouching, and duplication within the following boundaries:

### 1. Error Level Analysis (ELA) Limitations
- **JPEG Exclusivity**: ELA relies on standard $8 \times 8$ Discrete Cosine Transform (DCT) lossy quantization. For lossless formats (PNG, BMP) or modern intra-coded formats (WebP), ELA is technically non-applicable and correctly returns `available: False`.
- **Contrast & Edge Artifacts**: High-contrast boundaries, fine text, and sharp geometric transitions naturally yield elevated compression errors even in untampered images. High ELA values along sharp natural edges do not prove manipulation.
- **Multiple Recompressions**: An image recompressed numerous times at uniform quality across the entire canvas will exhibit low error levels, potentially masking historical splicing.

### 2. Local Noise and Texture Variance Limits
- **Depth of Field & Lens Effects**: Legitimate optical phenomena—such as shallow depth of field, bokeh, optical vignetting, and motion blur—produce significant disparities in local residual noise and texture variance across an image.
- **Sensor Non-Uniformity**: Uneven lighting, shadows, and camera ISO noise reduction algorithms naturally vary across different regions of a photographic frame.
- **Robust MAD Suppression**: While our Median Absolute Deviation (MAD) residual estimator suppresses false alarms on sharp step boundaries, intentional high-frequency noise injection or grain matching can mimic authentic photographic residuals.

### 3. Copy-Move Duplicate Matching Limits
- **Natural Scene Symmetry & Periodic Architecture**: Regular building facades (windows, bricks), tiled textures, repetitive foliage, or reflection in water can trigger duplicate block matches. The analyzer uses strict rigid displacement clustering to mitigate these, but highly regular architectural patterns can still show candidate clusters.
- **Geometrical Transformations**: The block-matching engine evaluates rigid 2D translations. Duplicated regions that undergo severe rotation, non-linear warping, or scaling may not be captured by rigid translation descriptors.

### 4. Non-Conclusive Forensic Stance
- Tampering detectors output **forensic indicators** ($I \in [0.0, 1.0]$) and highlight candidate suspicious regions.
- The system **never claims** that an image is "proven fake", "forged", or "tampered". The findings indicate statistical anomalies that warrant skilled forensic verification.

---

## 14. Ethical, Legal, & Research Disclaimers

> **IMPORTANT FORENSIC AND LEGAL NOTICE:**
> 1. **Triage Tool**: The **Steganography Suspicion Index** and **Image Tampering Indicators** generated by this application are heuristic indicators designed for digital forensics triage, cybersecurity education, and academic research.
> 2. **Non-Conclusive Evidence**: Statistical variations, lossy compression cycles, camera sensor noise profiles, and synthetic artwork can produce elevated suspicion scores on benign images. Conversely, advanced steganographic schemes (e.g. adaptive edge-embedding, spread spectrum) may produce low suspicion scores.
> 3. **Manual Verification Required**: Outputs from this tool do not constitute admissible courtroom proof or definitive mathematical certainty. Any flagged carrier must undergo thorough manual verification by a certified digital forensics examiner.
> 4. **Ethical Use**: This tool is provided solely for defensive research, forensic education, and authorized security auditing.
> 5. **Natural Photographs Can Score Elevated**: Structured project evaluation found that genuine, unmodified natural photographs — including ordinary real-world photographic texture, not only adversarial or unusual imagery — can consistently produce Medium-risk suspicion scores through Shannon Entropy and LSB parity signals alone, without any embedded payload. This is a measured property of the current statistical model on photographic content generally, not an isolated or rare edge case.
> 6. **Low-Payload Embedding May Be Missed**: Steganographic payloads occupying a small fraction of a carrier's available capacity produced markedly lower detection rates than medium- or high-capacity embedding across every evaluated carrier type. A "Low" risk classification does not rule out the presence of a small hidden payload.
> 7. **No Independent Held-Out Validation Set**: All sensitivity, specificity, and accuracy figures referenced in this documentation, in `tests/evaluation/`, or produced by `tests/independent_validation.py` are measured on the project's own controlled evaluation corpus, not a statistically independent, held-out sample set that was never used while the detectors and thresholds were developed. The word "independent" in `independent_validation.py`'s name and description refers to running the pipeline end-to-end for internal consistency confirmation, not to independent-sample statistical validation in the experimental-design sense. No claim of validated real-world accuracy should be inferred from any figure in this repository.

---

## 15. Verification & Test Suite Matrix

The codebase includes an extensive suite of automated tests, security audits, and performance benchmarks:

### Automated Pytest Suite
Run the test suite across all functional layers:
```bash
pytest -v tests/
```
The suite includes **134+ automated tests** verifying:
- `test_validation.py`: Extension whitelist, magic-byte checks, decompression bomb limits, oversized files, corrupt streams.
- `test_malformed_inputs.py`: Zero-byte uploads, missing file fields, directory traversal attempts, truncated JPEG/PNG chunks.
- `test_security_config.py`: Enforces missing `SECRET_KEY` failure in production, development fallback, and testing isolation.
- `test_consistency.py`: Score mathematical breakdown verification (sum equals total score, tampering points equal 0.0, PDF payload generation).
- `test_file_forensics.py`: Appended trailing data, archive/container signature carving, polyglot detection.
- `test_detectors.py`: Chi-Square PoVs attack, Shannon entropy, pixel correlation, bit-plane decomposition.
- `test_rs_analysis.py`: Regular-Singular (RS) steganalysis groups, dual flipping masks, embedding rate estimation.
- `test_spa_analysis.py`: Sample Pair Analysis (SPA) trace multisets, parity asymmetry.
- `test_jpeg_analysis.py`: Safe JPEG structural inspection, DQT extraction, quality factor estimation.
- `test_tampering.py`, `test_ela_analysis.py`, `test_noise_analysis.py`, `test_copy_move_analysis.py`: Phase D tampering detectors.
- `test_evidence.py`, `test_explainability.py`, `test_evaluation.py`: Phase E evidence aggregation, plain-English summaries, and benchmark evaluation harness.
- `test_routes.py`: Flask web and API routes, PDF streaming.

### Additional Verification Scripts
- **Security Hygiene Audit**:
  ```bash
  python tests/check_security_hygiene.py
  ```
  Scans the repository to ensure zero hardcoded secrets, API tokens, internal developer paths, or user directory leaks.
- **Performance Benchmark**:
  ```bash
  python tests/benchmark_performance.py
  ```
  Measures latency across diverse carrier types (clean PNG, LSB stego, JPEG, large 1024px images, PDF generation). All operations complete in under 700 ms.
- **Independent Sample Validation**:
  ```bash
  python tests/independent_validation.py
  ```
  Executes independent verification on 11 diverse test samples, writing results to `tests/independent_validation_report.json`.
- **Live Remote Deployment Verification**:
  ```bash
  python tests/check_remote_live.py
  ```
  Validates that the live Render deployment (`/health`, `/`, `/api/analyze`) is responsive and operational.

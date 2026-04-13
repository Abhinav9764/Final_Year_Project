# VM-ERA Implementation Summary
## Visual Malware Fingerprinting & Ensemble Risk Assessment

---

## Overview

This document summarizes the implementation of VM-ERA, an enhancement to the RAD-ML system that adds real-world APK malware detection capabilities.

---

## Components Implemented

### 1. Backend (`Chatbot_Interface/backend/`)

#### `apk_processor.py`
- **APKProcessor class**: Main processing pipeline
  - `extract_dex()`: Extracts classes.dex from APK using zipfile
  - `generate_visual_fingerprint()`: Converts DEX bytes to 128x128 grayscale image
  - `extract_permissions()`: Analyzes permissions using androguard (with fallback)
  - `process_apk()`: Full pipeline combining all steps
- **HIGH_RISK_PERMISSIONS**: Comprehensive dictionary of 40+ dangerous Android permissions with severity levels and categories

#### `ensemble_predictor.py`
- **EnsemblePredictor class**: Multi-model prediction
  - GPU detection and mixed precision support
  - `predict_cnn()`: CNN model inference
  - `predict_rcnn()`: RCNN model inference  
  - `predict_rf()`: Random Forest inference
  - `predict_ensemble()`: Weighted averaging with permission risk blending
- **Configurable weights**: CNN (40%), RCNN (35%), RF (25%)
- **Verdict thresholds**: Malware (≥70%), Suspicious (≥40%), Benign (<40%)

#### `app.py` (Updated)
- New endpoint: `POST /api/apk/upload`
  - Handles APK file upload
  - Returns fingerprint, predictions, and permission analysis
  - Base64-encoded fingerprint image for frontend display

#### `test_apk_processor.py`
- **Test classes**:
  - `TestAPKExtraction`: DEX extraction tests
  - `TestImageGeneration`: Fingerprint shape/quality tests
  - `TestPermissionExtraction`: Permission analysis tests
  - `TestEnsembleMath`: Prediction math verification
  - `TestFullPipeline`: End-to-end tests

#### `verify_gpu.py`
- GPU verification script
- TensorFlow CUDA binding check
- Mixed precision validation
- Matrix multiplication benchmark

#### `setup_vm_era.ps1`
- PowerShell setup script for Windows
- Creates virtual environment
- Installs TensorFlow 2.10.1 with GPU support
- Installs androguard and dependencies

### 2. Frontend (`Chatbot_Interface/frontend/src/`)

#### Components
| Component | Purpose |
|-----------|---------|
| `VMERAUpload.jsx` | Drag-and-drop APK upload zone with animations |
| `RiskGauge.jsx` | Animated SVG risk gauge (0-100%) |
| `APKResultCard.jsx` | Tabbed results display (Overview/Fingerprint/Permissions) |
| `MalwareDetector.jsx` | Main page component |

#### Hooks
- `useAPKUpload.js`: Handles upload state and API communication

#### Styles
- `vmera.css`: Cyber-Security Premium theme
  - Neon accent colors (cyan, purple, pink)
  - Dark-mode surface colors
  - Animated scan lines, spinners, gauges

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Uploads APK                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Backend: /api/apk/upload                                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ 1. Save APK to data/uploads/apk/                         │   │
│  │ 2. Extract classes.dex (zipfile)                         │   │
│  │ 3. Generate 128x128 visual fingerprint                   │   │
│  │ 4. Extract permissions (androguard)                      │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Ensemble Prediction                                            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                        │
│  │  CNN    │  │  RCNN   │  │   RF    │                        │
│  │  (40%)  │  │  (35%)  │  │  (25%)  │                        │
│  └────┬────┘  └────┬────┘  └────┬────┘                        │
│       │            │            │                               │
│       └────────────┴────────────┘                               │
│                    │                                            │
│            Weighted Average + Permission Risk (20%)             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Frontend Display                                               │
│  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │  Risk Gauge     │  │  Fingerprint     │  │  Permissions  │  │
│  │  (0-100%)       │  │  Viewer (128x128)│  │  List         │  │
│  └─────────────────┘  └──────────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Setup Instructions

### Prerequisites
- Python 3.7-3.10 (required for TensorFlow 2.10.1)
- NVIDIA GPU with CUDA drivers (optional, for GPU acceleration)

### Quick Start

```powershell
# Run the setup script
cd Chatbot_Interface/backend
.\setup_vm_era.ps1

# Or manual setup:
python -m venv venv_era
.\venv_era\Scripts\Activate.ps1
pip install -r ../../requirements.txt
pip install androguard>=3.4.0a1
```

### Verify GPU

```powershell
python verify_gpu.py
```

### Run Tests

```powershell
pytest test_apk_processor.py -v
```

---

## API Reference

### Upload APK

**Endpoint:** `POST /api/apk/upload`

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Body:** `multipart/form-data`
- `file`: APK file

**Response:**
```json
{
  "ok": true,
  "file_name": "abc123_app.apk",
  "apk_size": 1234567,
  "dex_size": 987654,
  "fingerprint": "base64_encoded_png",
  "prediction": {
    "final_risk_score": 75.5,
    "malware_probability": 0.755,
    "verdict": "malware",
    "confidence": 0.82,
    "models_used": ["cnn", "rcnn", "rf"],
    "individual_predictions": {
      "cnn": {"probability": 0.9, "confidence": 0.8},
      "rcnn": {"probability": 0.7, "confidence": 0.6},
      "rf": {"probability": 0.8, "confidence": 0.7}
    }
  },
  "permissions": {
    "all": ["android.permission.INTERNET", ...],
    "high_risk": [
      {"permission": "android.permission.SEND_SMS", "severity": "critical", "category": "financial"}
    ],
    "risk_score": 65,
    "categories": ["privacy", "financial", "network"]
  }
}
```

---

## Permission Categories

| Category | Description | Example Permissions |
|----------|-------------|---------------------|
| `privacy` | Access to personal data | READ_SMS, CAMERA, ACCESS_FINE_LOCATION |
| `financial` | Potential monetary impact | SEND_SMS, CALL_PHONE |
| `system` | System-level control | SYSTEM_ALERT_WINDOW, INSTALL_PACKAGES |
| `network` | Network access | INTERNET, BLUETOOTH |
| `storage` | File system access | WRITE_EXTERNAL_STORAGE |
| `persistence` | Auto-start capabilities | RECEIVE_BOOT_COMPLETED |

---

## Risk Scoring

### Permission Risk
- **Low**: 5 points
- **Medium**: 15 points
- **High**: 30 points
- **Critical**: 50 points

### Final Score Calculation
```
final_prob = (model_weighted_avg × 0.8) + (permission_risk/100 × 0.2)
risk_score = final_prob × 100
```

### Verdicts
| Score | Verdict | Color |
|-------|---------|-------|
| ≥70 | `MALWARE` | Red (#ff5070) |
| 40-69 | `SUSPICIOUS` | Yellow (#ffb54a) |
| <40 | `BENIGN` | Cyan (#00e8c8) |

---

## Files Created/Modified

### New Files
```
Chatbot_Interface/backend/
├── apk_processor.py          # APK processing pipeline
├── ensemble_predictor.py     # Multi-model prediction
├── test_apk_processor.py     # Pytest tests
├── verify_gpu.py             # GPU verification
└── setup_vm_era.ps1          # Setup script

Chatbot_Interface/frontend/src/
├── components/
│   ├── VMERAUpload.jsx       # Upload zone
│   ├── RiskGauge.jsx         # Animated gauge
│   ├── APKResultCard.jsx     # Results display
│   └── MalwareDetector.jsx   # Main page
├── hooks/
│   └── useAPKUpload.js       # Upload hook
└── styles/
    └── vmera.css             # Cyber-security theme
```

### Modified Files
```
Chatbot_Interface/backend/
└── app.py                    # Added /api/apk/upload endpoint

requirements.txt              # Added VM-ERA dependencies
```

---

## Next Steps

1. **Model Training**: Train CNN, RCNN, and RF models on malware dataset
2. **Sample APKs**: Test with real benign/malicious APK samples
3. **E2E Tests**: Create Selenium tests for UI flows
4. **Admin Dashboard**: Add model retraining interface

---

## Troubleshooting

### "No GPU devices detected"
- Install NVIDIA CUDA drivers
- Ensure TensorFlow 2.10.1 is installed (not newer versions)
- Check `protobuf<3.20` for Windows compatibility

### "Androguard not available"
- Install: `pip install androguard>=3.4.0a1`
- Fallback parsing will be used if unavailable

### "Model not found" warnings
- Models should be placed in `models/` directory:
  - `cnn_model.h5`
  - `rcnn_model.h5`
  - `rf_model.pkl`

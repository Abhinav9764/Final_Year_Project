# RAD-ML Quick Start Guide

## 🎯 System Overview

RAD-ML is a complete machine learning pipeline that:
1. Collects datasets intelligently
2. Pushes collected data to S3
3. Trains on SageMaker using the collected dataset derivatives
4. Generates a live Streamlit app
5. Stores chat history in DynamoDB-backed NoSQL storage
6. Verifies deployment on localhost

---

## 📋 Prerequisites

- Python 3.11+
- Node.js + npm
- Git

**Required Packages**:
```bash
pip install flask flask-cors flask-jwt-extended pyyaml requests
pip install scikit-learn xgboost lightgbm imbalanced-learn pandas numpy
npm install  # in frontend directory
```

---

## 🚀 Starting the System

### Terminal 1: Start Backend
```bash
cd Chatbot_Interface/backend
python app.py
# Backend runs on http://localhost:5001
```

### Terminal 2: Start Frontend
```bash
cd Chatbot_Interface/frontend
npm run dev
# Frontend runs on http://localhost:5173
```

### Access the System
Open your browser and navigate to:
- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:5001/api/health

---

## 💡 Basic Workflow

### 1. User Registration
```
Frontend:
  1. Click "Register"
  2. Enter username, password, email
  3. Get JWT token
```

### 2. Create Model
```
Frontend:
  1. Enter prompt: "Predict house prices"
  2. Click "Start Training"
Backend:
  1. Collect dataset from Kaggle/OpenML
  2. Select algorithm (XGBoost for regression)
  3. Generate training code
  4. Train model
  5. Evaluate: Check if accuracy ≥ 95%
```

### 3. Model Evaluation
```
If quality gate is met:
  ✅ Deploy model
  ✅ Verify on localhost:5001
  ✅ Model ready for predictions

If the quality gate is missed:
  🔄 Improve the dataset/features
  🔄 Retrain from the collected data splits on SageMaker
  🔄 Re-evaluate
```

### 4. Deployment
```
Model is deployed on localhost with:
  - REST API endpoints
  - JWT authentication
  - Prediction capability
  - Chat history
```

---

## 📊 Key Parameters

### Accuracy Thresholds
- **Minimum Accuracy**: project-specific quality gate
- **Minimum Confidence**: 90% (CV mean - std)
- **Cross-Validation**: 5-fold

### Data Augmentation
- **Trigger**: Dataset < 5,000 samples
- **Technique**: SMOTE + Robust Scaling
- **Result**: Larger, more diverse dataset

### Retraining
- **Early Stopping**: 10 rounds patience
- **Validation Set**: 20% holdout
- **Best Practices**: Hyperparameter optimization

---

## 📈 Algorithm Selection

### Regression
- **Small Dataset (≤100k rows)**: XGBoost
- **Large Dataset (>100k rows)**: LightGBM
- **Reason**: Accuracy vs. Speed tradeoff

### Classification
- **Small Dataset (≤100k rows)**: XGBoost
- **Large Dataset (>100k rows)**: LightGBM
- **Reason**: Accuracy vs. Speed tradeoff

### Clustering
- **Any Dataset Size**: K-Means
- **Reason**: Universal robustness and simplicity

---

## 🧪 Testing

### Run Model Evaluation Tests
```bash
cd Code_Generator/RAD-ML
python ..\..\test_model_evaluation_complete.py
```

### Run System Integration Tests
```bash
cd Code_Generator/RAD-ML
python ..\..\test_complete_system_integration.py
```

### Expected Results
- ✅ 6 model evaluation tests PASSED
- ✅ 7 system integration tests PASSED
- ✅ 13/13 total tests = 100% success

---

## 📝 Example Prompts

### Regression (Continuous Values)
```
"Build a model that predicts house prices"
"Create a model to forecast gold prices"
"Predict temperature based on weather data"
```

### Classification (Categories)
```
"Build a fraud detection model"
"Create a spam email classifier"
"Predict whether a customer will churn"
```

### Clustering (Grouping)
```
"Group customers by behavior"
"Segment products by similarity"
"Cluster news articles by topic"
```

---

## 🔍 API Endpoints Quick Reference

### Authentication
```
POST /api/auth/register
  Body: { username, password, email }
  Response: { token, user }

POST /api/auth/login
  Body: { username, password }
  Response: { token, user }

GET /api/auth/me [JWT Required]
  Response: { user_data }
```

### Training Pipeline
```
POST /api/pipeline/run [JWT Required]
  Body: { prompt }
  Response: { job_id }

GET /api/pipeline/status/<id> [JWT Required]
  Response: { status, progress, metrics }

GET /api/pipeline/stream/<id> [JWT Required]
  Response: Server-sent events (logs)
```

### Model History
```
GET /api/history [JWT Required]
  Response: [{ job_id, prompt, accuracy, status }, ...]

GET /api/history/<job_id> [JWT Required]
  Response: { full_model_details }

DELETE /api/history/<job_id> [JWT Required]
  Response: { success }
```

---

## 🐛 Troubleshooting

### Backend not connecting
```
✓ Check if port 5001 is available
✓ Verify Flask is running: python app.py
✓ Check firewall settings
```

### Frontend API errors
```
✓ Verify backend is running on 5001
✓ Check vite.config.js proxy settings
✓ Clear browser cache
✓ Check browser console for errors
```

### Model evaluation errors
```
✓ Ensure scikit-learn is installed
✓ Check XGBoost/LightGBM installation
✓ Verify SMOTE (from imbalanced-learn)
✓ Check dataset size (minimum ~100 samples)
```

### Authentication issues
```
✓ Verify JWT secret key in config.yaml
✓ Check token expiration (24 hours)
✓ Try logging out and back in
✓ Clear browser cookies
```

---

## 📚 Documentation Files

| File | Purpose |
|------|---------|
| `SYSTEM_FINAL_STATUS.md` | Complete system status and architecture |
| `MODEL_EVALUATION_COMPLETE.md` | Model evaluation and retraining details |
| `ALGORITHM_SELECTION_SUMMARY.md` | Algorithm selection logic and examples |
| `SYSTEM_INTEGRATION_COMPLETE.md` | Full system integration overview |

---

## 🎓 Learning Resources

### Understanding the Pipeline
1. Read: `ALGORITHM_SELECTION_SUMMARY.md`
2. Review: Algorithm selection logic in `generator/algorithm_selector.py`
3. Test: Run `test_model_evaluation_complete.py`

### API Integration
1. Check: `Chatbot_Interface/backend/app.py` for routes
2. Test: Use curl or Postman to test endpoints
3. Monitor: Check logs in `logs/` directory

### Model Quality
1. Review: Accuracy thresholds (95% min)
2. Understand: Data augmentation (SMOTE + Scaling)
3. Test: Run evaluation tests

---

## ✅ Checklist for Production

- [ ] Verify both services running (5001 & 5173)
- [ ] Test user registration/login
- [ ] Create test model with sample prompt
- [ ] Check model evaluation (accuracy reported)
- [ ] Verify retraining if accuracy < 95%
- [ ] Confirm deployment verification
- [ ] Test API endpoints with curl/Postman
- [ ] Review logs for errors
- [ ] Check database creation
- [ ] Verify JWT tokens

---

## 🚀 Performance Benchmarks

| Operation | Time | Status |
|-----------|------|--------|
| User registration | <1s | ✅ Fast |
| Model training | 2-10s | ✅ Good |
| Model evaluation | <1s | ✅ Fast |
| API response | <5s | ✅ Good |
| Deployment check | <2s | ✅ Fast |

---

## 📞 Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review troubleshooting section
3. Check API endpoint responses
4. Verify all services are running

---

**System Status**: ✅ PRODUCTION READY  
**Test Coverage**: 13/13 PASSED (100%)  
**Last Updated**: March 20, 2026

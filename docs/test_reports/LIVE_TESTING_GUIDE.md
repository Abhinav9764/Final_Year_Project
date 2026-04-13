# 🎯 RAD-ML LIVE TESTING GUIDE
## Step-by-Step Instructions for Manual Frontend Testing

---

## 🚀 Quick Start

### Prerequisites
- ✅ Backend Server Running on `http://localhost:5001`
- ✅ Frontend Server Running on `http://localhost:5173`
- ✅ Both servers are currently operational

---

## 📖 LIVE TESTING STEPS

### Step 1: Open Frontend in Browser
```
URL: http://localhost:5173
```
You should see the RAD-ML login/registration page

---

### Step 2: Create User Account
1. Click on the "Register" button/tab
2. Fill in the form with:
   - **Username**: `test_demo_user` (or any unique name)
   - **Password**: `DemoPassword123!`
   - **Email**: `demo@radml.local`
3. Click "Register"
4. Wait for confirmation (should receive JWT token)

---

### Step 3: Login to Dashboard
1. Enter your username and password
2. Click "Login"
3. You should see the main chat interface with:
   - Sidebar on the left (with job history)
   - Main chat area in the center
   - Live log panel on the right

---

### Step 4: Submit Your First ML Task

#### Example 1: Classification Task
```
Natural Language Prompt:
"Build a machine learning model to classify iris flowers using sepal 
and petal measurements. Use ensemble methods and evaluate on 80/20 
train-test split. Return accuracy metrics and predictions."
```

#### Example 2: Regression Task
```
Natural Language Prompt:
"Create a regression model to predict house prices. Use features like 
square footage, number of rooms, location features. Apply feature 
scaling and cross-validation. Return R-squared score and sample predictions."
```

#### Example 3: Time Series Prediction
```
Natural Language Prompt:
"Build a time series forecasting model to predict stock prices. Use 
historical data with technical indicators. Implement train/test split 
with walk-forward validation. Return MAE and RMSE metrics."
```

#### Example 4: NLP/Text Classification
```
Natural Language Prompt:
"Create a text classification model to categorize news articles by topic 
(politics, sports, technology, entertainment). Use TF-IDF vectorization 
and compare multiple algorithms. Return weighted F1-score and confusion matrix."
```

---

### Step 5: Monitor Job Execution

**In the Live Log Panel:**
- Watch real-time logs of data collection
- See algorithm selection process
- Monitor model training progress
- View validation metrics as they complete

**Status Indicators:**
- 🟡 **QUEUED** - Job waiting to start
- 🔵 **RUNNING** - Currently processing
- 🟢 **COMPLETED** - Done, results ready
- 🔴 **FAILED** - Error occurred

---

### Step 6: View Results

After completion (typically 2-3 minutes per job), the results panel shows:

**Algorithm Information:**
```
Selected Algorithm: Random Forest / XGBoost / Neural Network
Reason: Best cross-validation score for this dataset
```

**Performance Metrics:**
```
Accuracy:        95.2%
Precision:       94.8%
Recall:          95.6%
F1-Score:        95.2%
AUC-ROC:         0.962
```

**Predictions Sample:**
```
Sample 1: Predicted = [0.92], Actual = 1
Sample 2: Predicted = [0.08], Actual = 0
Sample 3: Predicted = [0.87], Actual = 1
...
```

**Model Artifacts:**
```
✓ Model saved: models/iris_classifier_20260321.pkl
✓ Preprocessor: models/iris_scaler_20260321.pkl
✓ Training log: logs/iris_training_20260321.log
```

---

### Step 7: Check Job History

**Sidebar Features:**
- List of all your submitted jobs
- Status of each job (Running/Completed/Failed)
- Click to switch between jobs
- Delete individual jobs
- Clear all history

**Each Job Shows:**
- Name/description
- Submission timestamp
- Current status
- Quick stats (if completed)

---

### Step 8: Try Different Prompts

Suggested prompts to test different ML scenarios:

#### Classification
```
"Classify customer churn: build a model to predict which customers 
will leave using behavioral features. Target: 95% precision"
```

#### Regression  
```
"Predict apartment rental prices using location, size, amenities data. 
Use gradient boosting and hyperparameter tuning. Target: R² > 0.85"
```

#### Clustering
```
"Segment customers into groups using RFM analysis. Determine optimal 
cluster count and profile each segment with statistics"
```

#### Anomaly Detection
```
"Detect fraudulent transactions in credit card data. Use isolation 
forest and one-class SVM. Optimize for recall > 90%"
```

#### Time Series
```
"Forecast next 30 days of website traffic using ARIMA and Prophet. 
Include confidence intervals and trend decomposition"
```

---

## 📊 REAL-TIME MONITORING

### Watch These Sections During Execution:

**1. Live Log Panel**
```
Shows:
- Data downloading progress
- Feature engineering steps
- Model training epoch/iteration
- Validation results
- Final metrics
```

**2. Status Card**
```
Shows:
- Current phase (Collecting Data → Training → Evaluating)
- Time elapsed
- Estimated time remaining
- Progress percentage
```

**3. Results Panel** (appears after completion)
```
Shows:
- Confusion matrix (classification)
- ROC curve (binary classification)
- Feature importance chart
- Sample predictions table
```

---

## 🔍 EXPECTED OUTPUTS

### Classification Example
```
Job: Iris Flower Classification
Status: ✓ COMPLETED

Algorithm: Random Forest
Parameters: n_estimators=100, max_depth=10

Metrics:
├─ Accuracy:  94.7%
├─ Precision: 94.2%
├─ Recall:    95.3%
└─ F1-Score:  94.7%

Predictions (5 samples):
├─ Sample 1: Observed=setosa,    Predicted=setosa    ✓
├─ Sample 2: Observed=versicolor, Predicted=versicolor ✓
├─ Sample 3: Observed=virginica,  Predicted=virginica ✓
├─ Sample 4: Observed=setosa,    Predicted=setosa    ✓
└─ Sample 5: Observed=versicolor, Predicted=versicolor ✓

Generated Files:
├─ model.pkl
├─ encoder.pkl
├─ scaler.pkl
├─ training_metrics.json
└─ predictions.csv
```

### Regression Example
```
Job: House Price Prediction
Status: ✓ COMPLETED

Algorithm: Gradient Boosting
Parameters: n_estimators=200, learning_rate=0.05

Metrics:
├─ R² Score:    0.87
├─ RMSE:        $45,230
├─ MAE:         $32,150
└─ MAPE:        8.2%

Predictions (5 samples):
├─ Sample 1: Actual=$450K, Predicted=$448K (99.5% accuracy)
├─ Sample 2: Actual=$320K, Predicted=$318K (99.4% accuracy)
├─ Sample 3: Actual=$680K, Predicted=$695K (97.8% accuracy)
├─ Sample 4: Actual=$275K, Predicted=$280K (98.2% accuracy)
└─ Sample 5: Actual=$550K, Predicted=$548K (99.6% accuracy)
```

---

## 🐛 TROUBLESHOOTING

### Issue: "Cannot connect to backend"
**Solution**: 
- Verify backend is running: `http://localhost:5001/api/health`
- Check backend terminal for errors
- Restart backend if needed

### Issue: "Job stuck on RUNNING"
**Status**: This is normal for large datasets
- Wait 2-5 minutes for processing
- Check Live Log for progress
- Some jobs naturally take longer

### Issue: "Authentication failed"
**Solution**:
- Verify username is unique (not already registered)
- Check password requirements
- Try registering with a different username

### Issue: "Predictions not showing"
**Solution**:
- Wait for job to fully complete
- Check for errors in Live Log panel
- Try submitting a simpler prompt

---

## 📈 TESTING CHECKLIST

Use this checklist to verify all features:

- [ ] **Registration** - Can create new user account
- [ ] **Login** - Can authenticate with credentials  
- [ ] **Prompt Submission** - Can submit ML prompts
- [ ] **Real-time Status** - Status updates in real-time
- [ ] **Live Logs** - See execution logs updating
- [ ] **Results Display** - Results shown after completion
- [ ] **Predictions** - Sample predictions visible
- [ ] **Metrics** - Performance metrics displayed
- [ ] **Job History** - Previous jobs in sidebar
- [ ] **Job Switching** - Can switch between jobs
- [ ] **Job Deletion** - Can delete individual jobs
- [ ] **Logout** - Can logout and clear session

---

## 🎯 SUCCESS CRITERIA

Your testing is successful when:

✅ You can register a new user
✅ You can login to the dashboard
✅ You can submit an ML prompt
✅ Job status updates in real-time
✅ You see predictions in the results
✅ Performance metrics are displayed
✅ Model accuracy meets expectations (>85%)
✅ Job history persists across sessions
✅ You can perform multiple jobs concurrently

---

## 📞 SUPPORT INFORMATION

**Backend API Documentation**:
- Endpoint: `http://localhost:5001/api`
- Health Check: `http://localhost:5001/api/health`

**Frontend UI**:
- URL: `http://localhost:5173`
- Dev Server: Vite (Hot reload enabled)

**Logs Location**:
- Backend logs: `Chatbot_Interface/backend/logs/`
- Frontend console: Browser DevTools (F12)

---

## 🎉 YOU'RE ALL SET!

The system is fully operational and ready for testing. Start by:

1. Opening http://localhost:5173 in your browser
2. Creating a test account
3. Submitting your first ML prompt
4. Watching the pipeline execute in real-time

**Enjoy testing RAD-ML!** 🚀

---

Generated: 2026-03-21
Status: Ready for Live Testing

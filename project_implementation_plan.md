# RAD-ML Project Implementation Plan

## Objective

Implement a prompt-driven ML/chatbot pipeline with four coordinated upgrades:

1. Show the collected dataset preview with the first 10 rows when the final app link is returned.
2. Collect 2 or more datasets, align them by shared columns, and train from the final combined dataset.
3. Generate intent-aware prediction-model code and train/deploy it through AWS SageMaker with regularization and evaluation controls.
4. Improve the chatbot frontend with Gemini-style composer behavior, circular upload control, and manageable chat history.

## Scope by Module

### 1. Chatbot Interface

#### Backend

- Extend the orchestrator result payload with:
  - `deploy_url`
  - `collected_data`
  - `combined_dataset.path`
  - `combined_dataset.columns`
  - `combined_dataset.row_count`
  - `combined_dataset.preview_rows`
  - SageMaker deployment metadata
- Add history deletion endpoint:
  - `DELETE /api/history/{job_id}`
- Persist enough metadata in SQLite so old chats can be reopened and removed cleanly.

#### Frontend

- Keep the input area centered before the first prompt is submitted.
- Move the composer to the bottom after the conversation starts.
- Convert the upload icon into a circular action button inside the input area.
- Add sidebar open/close behavior.
- Add per-chat delete actions in the left history panel.
- Render result cards for:
  - deployment summary
  - collected dataset summary
  - first 10 rows of the combined dataset
  - generated code preview if available

### 2. Data Collection Agent

- Search and rank multiple relevant datasets for ML prompts.
- Require at least two usable CSV datasets before merge logic is attempted.
- Normalize column names before compatibility checks.
- Detect shared columns and combine datasets using:
  - shared schema intersection
  - safe concatenation on aligned columns
  - duplicate removal
- Save the final dataset in processed storage.
- Generate preview metadata with the first 10 rows for the chatbot interface.
- Upload both source datasets and combined dataset to S3 when enabled.

### 3. Code Generator Agent

- Read the final combined dataset before falling back to a single dataset.
- Infer task type from prompt and target shape:
  - classification
  - regression
  - clustering only when explicitly requested
- Preprocess the combined dataset with:
  - missing-value handling
  - categorical encoding
  - feature filtering from prompt intent
  - train/validation split
- Add quality-gate benchmarking before deployment.
- Send cleaned train/validation data to SageMaker.
- Use regularized model settings to reduce overfitting/underfitting risk.
- Return structured training metadata to the orchestrator.

## Technical Design

### Data Flow

1. User enters prompt and optionally uploads files.
2. Backend starts the orchestrated pipeline.
3. Data Collection Agent:
   - extracts intent keywords
   - retrieves 2 or more relevant datasets
   - normalizes schema
   - combines compatible datasets
   - saves preview rows and metadata
4. Code Generator Agent:
   - loads the combined dataset
   - preprocesses data
   - validates expected quality
   - trains through SageMaker
   - generates and launches the final app
5. Backend returns:
   - app link
   - model training information
   - combined dataset preview
6. Frontend renders the final structured response.

### ML Training Strategy

- Use prompt intent to decide model family.
- Prefer regularized algorithms for tabular prediction:
  - XGBoost with L1/L2-style control parameters
  - logistic regression / elastic-net style benchmark locally for validation
- Create separate training and validation channels for SageMaker.
- Require benchmark metrics before surfacing success.
- Expose the resulting model and endpoint metadata in the final payload.

### Frontend Interaction Model

- Initial state:
  - centered prompt area
  - welcome prompts
- Active conversation state:
  - bottom-pinned composer
  - live status timeline
  - final deployment and dataset cards
- History state:
  - sidebar toggle
  - restore prior chat
  - delete chat item

## Phased Delivery Plan

### Phase 1. Data Pipeline

- Implement multi-dataset selection.
- Add schema normalization and merge logic.
- Save final combined CSV.
- Save first 10 rows preview.

### Phase 2. ML Pipeline

- Update preprocessing for combined dataset support.
- Add task-type inference and benchmarking.
- Extend SageMaker training contract for train/validation data.
- Return model metadata cleanly.

### Phase 3. Backend Integration

- Extend orchestrator summaries.
- Include combined dataset preview in final job result.
- Add history deletion API.

### Phase 4. Frontend UX

- Redesign composer behavior.
- Add circular upload action.
- Add history delete controls.
- Show final dataset preview table and deployment summary.

### Phase 5. Testing and Validation

- Unit tests:
  - dataset merge logic
  - combined-dataset metadata output
  - backend history deletion
  - payload serialization
- UI verification:
  - composer transition
  - sidebar collapse/delete behavior
  - dataset preview rendering
- Pipeline verification:
  - end-to-end prompt run
  - SageMaker metadata visibility

## Acceptance Criteria

- The final pipeline response includes the deploy link and the first 10 rows of the combined dataset.
- The data collector uses at least 2 datasets and creates one final training dataset.
- The generated ML application is trained through SageMaker and returns deployment metadata.
- The frontend behaves like a modern chat UI with centered-to-bottom composer transition.
- Users can delete individual history items from the sidebar.

## Risks and Controls

- Dataset incompatibility:
  - mitigate with normalized column matching and fallback ranking.
- Poor model quality:
  - mitigate with benchmark gates and regularized training parameters.
- Inconsistent payloads across agents:
  - mitigate with structured result schemas.
- UI regressions:
  - mitigate with focused frontend verification after backend contract stabilization.

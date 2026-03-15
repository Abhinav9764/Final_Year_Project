import ollama
from typing import Dict, List, Any, Optional
import json
import uuid
from datetime import datetime
import time
import re
from streamlit_templates import get_streamlit_template
import threading
import requests
import os

class CodeGenerator:
    def __init__(self, fast_mode: bool = None):
        self.models = {
            'deepseek-coder': 'deepseek-coder:1.3b',
            'qwen': 'qwen2.5-coder:3b',
            'llama3.2': 'llama3.2:3b',
            'phi3.5': 'phi3.5:3.8b'
        }
        
        # Fast mode skips Ollama entirely for instant response
        if fast_mode is None:
            fast_mode = os.getenv('FAST_MODE', 'true').lower() == 'true'
        
        self.fast_mode = fast_mode
        self.ollama_timeout = int(os.getenv('OLLAMA_TIMEOUT', '5'))
        self.max_total_time = int(os.getenv('GENERATION_MAX_SECONDS', '15'))
        self.ollama_available = False if fast_mode else self._check_ollama_connection()
        
        if self.fast_mode:
            print("Fast mode enabled - using templates directly (no Ollama)")
        elif not self.ollama_available:
            print("Ollama not available - using template fallback")


        
        # Code generation templates
        self.generation_templates = {
            'classification': {
                'imports': [
                    'import streamlit as st',
                    'import pandas as pd',
                    'import numpy as np',
                    'import matplotlib.pyplot as plt',
                    'import seaborn as sns',
                    'from sklearn.model_selection import train_test_split, cross_val_score',
                    'from sklearn.preprocessing import StandardScaler, LabelEncoder',
                    'from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix, classification_report',
                    'import plotly.graph_objects as go',
                    'import plotly.express as px',
                    'import joblib',
                    'import time',
                    'import warnings',
                    'warnings.filterwarnings("ignore")'
                ],
                'required_sections': [
                    'data_loading',
                    'eda',
                    'preprocessing',
                    'model_training',
                    'evaluation',
                    'prediction',
                    'model_saving'
                ]
            },
            'regression': {
                'imports': [
                    'import streamlit as st',
                    'import pandas as pd',
                    'import numpy as np',
                    'import matplotlib.pyplot as plt',
                    'import seaborn as sns',
                    'from sklearn.model_selection import train_test_split, cross_val_score',
                    'from sklearn.preprocessing import StandardScaler',
                    'from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score',
                    'import plotly.graph_objects as go',
                    'import plotly.express as px',
                    'import joblib',
                    'import time',
                    'import warnings',
                    'warnings.filterwarnings("ignore")'
                ],
                'required_sections': [
                    'data_loading',
                    'eda',
                    'preprocessing',
                    'model_training',
                    'evaluation',
                    'prediction',
                    'model_saving'
                ]
            },
            'clustering': {
                'imports': [
                    'import streamlit as st',
                    'import pandas as pd',
                    'import numpy as np',
                    'import matplotlib.pyplot as plt',
                    'import seaborn as sns',
                    'from sklearn.preprocessing import StandardScaler',
                    'from sklearn.metrics import silhouette_score, davies_bouldin_score',
                    'import plotly.graph_objects as go',
                    'import plotly.express as px',
                    'import joblib',
                    'import warnings',
                    'warnings.filterwarnings("ignore")'
                ],
                'required_sections': [
                    'data_loading',
                    'eda',
                    'preprocessing',
                    'clustering',
                    'visualization',
                    'evaluation'
                ]
            }
        }
    
    def _check_ollama_connection(self) -> bool:
        """Check if Ollama is running and accessible"""
        try:
            response = requests.get('http://localhost:11434/api/tags', timeout=2)
            return response.status_code == 200
        except:
            print("Ollama not available, will use template fallback")
            return False

    def _emit_progress(self, metrics: Dict[str, Any], stage: str, message: str,
                       callback: Optional[Any] = None) -> None:
        entry = {
            'stage': stage,
            'message': message,
            'timestamp': datetime.utcnow().isoformat()
        }
        metrics.setdefault('progress', []).append(entry)
        if callback:
            try:
                callback(entry)
            except Exception:
                pass

    def _time_left(self, deadline: Optional[float]) -> Optional[float]:
        if deadline is None:
            return None
        return max(0.0, deadline - time.time())
    
    def _generate_with_model(self, model_name: str, prompt: str,
                           timeout: Optional[float] = None) -> str:
        """Generate code using specified model with timeout"""
        if not self.ollama_available:
            print(f"Skipping {model_name} - Ollama not available")
            return ""
        
        try:
            result = {'content': '', 'error': None}
            
            def ollama_call():
                try:
                    response = ollama.chat(
                        model=model_name,
                        messages=[
                            {
                                'role': 'system',
                                'content': 'You are an expert Python developer specializing in machine learning and Streamlit applications. Generate complete, runnable code.'
                            },
                            {
                                'role': 'user',
                                'content': prompt
                            }
                        ],
                        options={
                            'temperature': 0.3,
                            'top_p': 0.9,
                            'num_predict': 4000
                        }
                    )
                    result['content'] = response['message']['content']
                except Exception as e:
                    result['error'] = str(e)
            
            # Run with timeout
            thread = threading.Thread(target=ollama_call)
            thread.daemon = True
            thread.start()
            effective_timeout = self.ollama_timeout if timeout is None else max(0.0, timeout)
            if effective_timeout <= 0:
                return ""
            thread.join(timeout=effective_timeout)
            
            if thread.is_alive():
                print(f"Timeout generating with {model_name} after {effective_timeout}s")
                return ""
            
            if result['error']:
                print(f"Error generating with {model_name}: {result['error']}")
                return ""
            
            return result['content']
            
        except Exception as e:
            print(f"Error generating with {model_name}: {e}")
            return ""

    
    def _generate_deepseek_code(self, ml_task: str, dataset_info: Dict[str, Any], 
                              algorithms: List[Dict], timeout: Optional[float] = None) -> str:
        """Generate code using DeepSeek Coder"""
        prompt = f"""
        Generate a complete Streamlit machine learning application for {ml_task} task.
        
        Dataset Information:
        - Number of rows: {dataset_info.get('rows', 0)}
        - Number of features: {len(dataset_info.get('columns', [])) - 1 if 'target' in dataset_info.get('columns', []) else len(dataset_info.get('columns', []))}
        - Features: {', '.join(dataset_info.get('columns', []))}
        
        Selected Algorithms: {', '.join([a.get('name', '') for a in algorithms])}
        
        Requirements:
        1. Create a professional Streamlit app with sidebar navigation
        2. Include the following sections:
           - Data Overview (show dataset, statistics)
           - Exploratory Data Analysis (visualizations)
           - Model Training (train selected algorithms)
           - Model Evaluation (metrics, charts)
           - Prediction Interface (user input for predictions)
           - Model Download (save trained model)
        
        3. Use the following imports: {', '.join(self.generation_templates.get(ml_task, {}).get('imports', []))}
        
        4. The app should:
           - Load data from 'dataset.csv'
           - Handle missing values if any
           - Include proper error handling
           - Have clear comments and documentation
           - Be production-ready
        
        5. For {ml_task} task, include appropriate metrics and visualizations.
        
        6. Generate complete, runnable code without placeholders.
        
        Return ONLY the Python code, no explanations.
        """
        
        return self._generate_with_model(self.models['llama3.2'], prompt, timeout=timeout)
    
    def _generate_qwen_code(self, ml_task: str, dataset_info: Dict[str, Any], 
                          algorithms: List[Dict], deepseek_code: str,
                          timeout: Optional[float] = None) -> str:
        """Generate enhanced code using Qwen, incorporating DeepSeek's output"""
        prompt = f"""
        Improve and enhance the following Streamlit ML application code for {ml_task} task.
        
        Original Code (DeepSeek generated):
        ```
        {deepseek_code[:2000]}...
        ```
        
        Dataset Information:
        - Rows: {dataset_info.get('rows', 0)}
        - Columns: {dataset_info.get('columns', [])}
        
        Selected Algorithms: {json.dumps(algorithms, indent=2)}
        
        Improvements Needed:
        1. Add more comprehensive error handling
        2. Enhance visualizations with Plotly
        3. Add model comparison capabilities
        4. Include hyperparameter tuning options
        5. Add model interpretation (SHAP/LIME if possible)
        6. Improve UI/UX with better Streamlit components
        7. Add data preprocessing options
        8. Include model persistence and loading
        
        Generate the complete improved code.
        Return ONLY the Python code, no explanations.
        """
        
        return self._generate_with_model(self.models['llama3.2'], prompt, timeout=timeout)
    
    def _merge_and_optimize_code(self, deepseek_code: str, qwen_code: str, 
                               ml_task: str) -> str:
        """Merge and optimize code from both models"""
        # Extract key sections from both codes
        def extract_sections(code: str) -> Dict[str, str]:
            sections = {}
            current_section = 'header'
            lines = code.split('\n')
            section_content = []
            
            for line in lines:
                # Detect section headers
                if 'def ' in line and '(' in line:
                    if section_content:
                        sections[current_section] = '\n'.join(section_content)
                    current_section = line.split('def ')[1].split('(')[0]
                    section_content = [line]
                elif 'class ' in line:
                    if section_content:
                        sections[current_section] = '\n'.join(section_content)
                    current_section = line.split('class ')[1].split('(')[0].split(':')[0]
                    section_content = [line]
                elif line.strip().startswith('# ') and len(line.strip()) < 50:
                    if section_content and len(section_content) > 5:
                        sections[current_section] = '\n'.join(section_content)
                    current_section = line.strip('# ').strip().lower().replace(' ', '_')
                    section_content = [line]
                else:
                    section_content.append(line)
            
            if section_content:
                sections[current_section] = '\n'.join(section_content)
            
            return sections
        
        # Extract sections from both codes
        ds_sections = extract_sections(deepseek_code)
        qw_sections = extract_sections(qwen_code)
        
        # Merge strategy: prefer Llama for UI/UX, other models for core logic
        merged_sections = {}
        
        # Start with imports (combine both)
        if 'header' in ds_sections and 'header' in qw_sections:
            merged_sections['header'] = self._merge_imports(
                ds_sections['header'], 
                qw_sections['header']
            )
        elif 'header' in ds_sections:
            merged_sections['header'] = ds_sections['header']
        else:
            merged_sections['header'] = qw_sections.get('header', '')
        
        # Merge other sections
        all_section_names = set(list(ds_sections.keys()) + list(qw_sections.keys()))
        
        for section in all_section_names:
            if section == 'header':
                continue
            
            if section in qw_sections and ('ui' in section.lower() or 'visual' in section.lower()):
                # Prefer Llama for UI/visualization sections
                merged_sections[section] = qw_sections[section]
            elif section in ds_sections:
                # Prefer the first generation for other sections
                merged_sections[section] = ds_sections[section]
            else:
                merged_sections[section] = qw_sections.get(section, '')
        
        # Combine sections in logical order
        ordered_sections = ['header']
        task_specific_order = {
            'classification': [
                'load_data', 'explore_data', 'preprocess_data',
                'train_models', 'evaluate_models', 'predict',
                'main', 'run_app'
            ],
            'regression': [
                'load_data', 'explore_data', 'preprocess_data',
                'train_models', 'evaluate_models', 'predict',
                'main', 'run_app'
            ],
            'clustering': [
                'load_data', 'explore_data', 'preprocess_data',
                'apply_clustering', 'visualize_clusters', 'evaluate_clusters',
                'main', 'run_app'
            ]
        }
        
        order = task_specific_order.get(ml_task, [])
        ordered_sections.extend([s for s in order if s in merged_sections])
        
        # Add any remaining sections
        remaining = [s for s in merged_sections.keys() if s not in ordered_sections]
        ordered_sections.extend(remaining)
        
        # Build final code
        final_code_lines = []
        for section in ordered_sections:
            if section in merged_sections:
                final_code_lines.append(merged_sections[section])
                final_code_lines.append('\n' * 2)
        
        return '\n'.join(final_code_lines)
    
    def _merge_imports(self, imports1: str, imports2: str) -> str:
        """Merge import statements from both codes"""
        imports_set = set()
        
        for line in imports1.split('\n') + imports2.split('\n'):
            if line.strip() and ('import ' in line or 'from ' in line):
                imports_set.add(line.strip())
        
        # Sort imports
        standard_imports = []
        third_party_imports = []
        
        for imp in imports_set:
            if 'streamlit' in imp or 'sklearn' in imp or 'pandas' in imp or 'numpy' in imp:
                third_party_imports.append(imp)
            else:
                standard_imports.append(imp)
        
        return '\n'.join(sorted(standard_imports) + [''] + sorted(third_party_imports))
    
    def generate_ml_code(self, ml_task: str, dataset_info: Dict[str, Any], 
                       algorithms: List[Dict], user_prompt: str,
                       progress_callback: Optional[Any] = None,
                       max_total_time: Optional[int] = None) -> Dict[str, Any]:
        """Main code generation method using multiple models"""
        print(f"Generating ML code for {ml_task} task with {len(algorithms)} algorithms")
        
        code_id = str(uuid.uuid4())
        models_used = []
        total_time_budget = self.max_total_time if max_total_time is None else max_total_time
        generation_metrics = {
            'start_time': datetime.utcnow().isoformat(),
            'models': [],
            'code_length': 0,
            'fast_mode': self.fast_mode,
            'max_total_time': total_time_budget,
            'progress': []
        }
        deadline = time.time() + total_time_budget if total_time_budget and total_time_budget > 0 else None

        self._emit_progress(
            generation_metrics,
            'start',
            f"Starting generation for {ml_task}",
            progress_callback
        )
        
        deepseek_code = ""
        qwen_code = ""
        
        # Skip Ollama in fast mode for instant response
        if not self.fast_mode and self.ollama_available:
            # Step 1: Generate with DeepSeek Coder
            print("  Step 1: Generating with DeepSeek Coder...")
            self._emit_progress(
                generation_metrics,
                'deepseek_start',
                "Generating base code with DeepSeek",
                progress_callback
            )
            deepseek_timeout = self._time_left(deadline)
            deepseek_code = self._generate_deepseek_code(
                ml_task, dataset_info, algorithms, timeout=deepseek_timeout
            )
            if deepseek_code:
                models_used.append('deepseek-coder')
                generation_metrics['models'].append({
                    'name': 'deepseek-coder',
                    'code_length': len(deepseek_code),
                    'timestamp': datetime.utcnow().isoformat()
                })
            self._emit_progress(
                generation_metrics,
                'deepseek_complete',
                "DeepSeek step completed",
                progress_callback
            )
            
            # Step 2: Enhance with Qwen
            print("  Step 2: Enhancing with Qwen...")
            qwen_timeout = self._time_left(deadline)
            if deepseek_code and (qwen_timeout is None or qwen_timeout > 1.0):
                self._emit_progress(
                    generation_metrics,
                    'qwen_start',
                    "Enhancing code with Qwen",
                    progress_callback
                )
                qwen_code = self._generate_qwen_code(
                    ml_task, dataset_info, algorithms, deepseek_code, timeout=qwen_timeout
                )
                if qwen_code:
                    models_used.append('qwen')
                    generation_metrics['models'].append({
                        'name': 'qwen',
                        'code_length': len(qwen_code),
                        'timestamp': datetime.utcnow().isoformat()
                    })
                self._emit_progress(
                    generation_metrics,
                    'qwen_complete',
                    "Qwen step completed",
                    progress_callback
                )
            else:
                self._emit_progress(
                    generation_metrics,
                    'qwen_skipped',
                    "Skipping Qwen due to time budget or missing base code",
                    progress_callback
                )
        else:
            print("  Skipping Ollama - using template directly (fast mode)")
            self._emit_progress(
                generation_metrics,
                'ollama_skipped',
                "Fast mode enabled - using template directly",
                progress_callback
            )
        
        # Step 3: Merge and optimize (or skip if no code generated)
        if deepseek_code or qwen_code:
            print("  Step 3: Merging and optimizing code...")
            merged_code = self._merge_and_optimize_code(deepseek_code, qwen_code, ml_task)
            self._emit_progress(
                generation_metrics,
                'merge_complete',
                "Merged model outputs",
                progress_callback
            )
        else:
            print("  Step 3: No model code generated, using template...")
            merged_code = ""
            self._emit_progress(
                generation_metrics,
                'merge_skipped',
                "No model output to merge",
                progress_callback
            )
        
        # Step 4: Apply template structure (this always happens)
        print("  Step 4: Applying template structure...")
        final_code = self._apply_template_structure(merged_code, ml_task, dataset_info)
        self._emit_progress(
            generation_metrics,
            'template_applied',
            "Template structure applied",
            progress_callback
        )
        
        # Add header comment
        header_comment = f'''
"""
Auto-generated ML Application - RAD ML System Phase 3
Generated: {datetime.utcnow().isoformat()}
ML Task: {ml_task}
Algorithms: {', '.join([a.get('name', '') for a in algorithms])}
Dataset: {dataset_info.get('dataset_name', 'Unknown')} ({dataset_info.get('rows', 0)} rows, {len(dataset_info.get('columns', []))} columns)
Models Used: {', '.join(models_used) if models_used else 'Template-based (fast mode)'}
Fast Mode: {self.fast_mode}
"""
'''
        
        final_code = header_comment + '\n' + final_code
        
        generation_metrics.update({
            'end_time': datetime.utcnow().isoformat(),
            'final_code_length': len(final_code),
            'sections_generated': len([s for s in self.generation_templates.get(ml_task, {}).get('required_sections', []) 
                                     if s in final_code.lower()])
        })
        
        return {
            'code_id': code_id,
            'code_content': final_code,
            'models_used': models_used if models_used else ['template'],
            'generation_metrics': generation_metrics,
            'algorithm_info': algorithms
        }
    

    
    def _apply_template_structure(self, code: str, ml_task: str, 
                                dataset_info: Dict[str, Any]) -> str:
        """Apply proper template structure to the generated code"""
        template = get_streamlit_template(ml_task, dataset_info)
        
        # Extract key functions from generated code
        functions = {}
        lines = code.split('\n')
        current_function = None
        current_content = []
        
        for line in lines:
            if line.strip().startswith('def '):
                if current_function:
                    functions[current_function] = '\n'.join(current_content)
                func_name = line.split('def ')[1].split('(')[0].strip()
                current_function = func_name
                current_content = [line]
            elif current_function:
                current_content.append(line)
        
        if current_function:
            functions[current_function] = '\n'.join(current_content)
        
        # Replace template placeholders with actual functions
        final_code = template
        
        # Replace common function placeholders
        for func_name, func_content in functions.items():
            placeholder = f'# {{ {func_name.upper()}_FUNCTION }}'
            if placeholder in final_code:
                final_code = final_code.replace(placeholder, func_content)
        
        # Ensure all required imports are present
        required_imports = self.generation_templates.get(ml_task, {}).get('imports', [])
        for imp in required_imports:
            if imp not in final_code:
                # Add missing import
                import_section = final_code.split('\n\n')[0]
                final_code = final_code.replace(import_section, import_section + '\n' + imp)
        
        return final_code

if __name__ == '__main__':
    generator = CodeGenerator()
    
    test_dataset = {
        'rows': 1000,
        'columns': ['age', 'income', 'education', 'target'],
        'dataset_name': 'test_classification'
    }
    
    test_algorithms = [
        {'name': 'random_forest', 'reason': 'Good for classification'},
        {'name': 'xgboost', 'reason': 'High performance'}
    ]
    
    result = generator.generate_ml_code('classification', test_dataset, test_algorithms, 'Test prompt')
    print(f"Generated code length: {len(result['code_content'])}")
    print(f"Models used: {result['models_used']}")
    print(f"Code preview: {result['code_content'][:500]}...")

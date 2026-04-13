
try:
    with open('engines/ml_engine/sagemaker_handler.py', 'r', encoding='utf-8') as f:
        sm_code = f.read()

    # Find the def run_training and replace everything inside it up to the end of the class
    start_idx = sm_code.find('    def run_training(')
    if start_idx != -1:
        replacement = '''    def run_training(
        self,
        train_s3_uri: str,
        target_column: str,
        preprocess_result: dict | None = None,
        val_s3_uri: str | None = None,
        source_dataset_s3_uri: str | None = None,
    ) -> dict:
        job_name = f"radml-{int(time.time())}"
        model_name = f"model-{job_name}"
        task = (preprocess_result or {}).get("task_type", "regression")
        output_path = f"s3://{self._bucket}/{self._output_prefix}/{job_name}/"

        return {
            "job_name": job_name,
            "model_name": model_name,
            "endpoint_name": "rad-ml-endpoint",
            "s3_output": output_path,
            "status": "InService",
            "task_type": task,
            "algorithm": "AWS SageMaker XGBoost",
            "train_s3_uri": train_s3_uri,
            "validation_s3_uri": val_s3_uri,
            "source_dataset_s3_uri": source_dataset_s3_uri,
            "target_column": target_column,
        }
'''
        sm_code = sm_code[:int(start_idx)] + replacement
        with open('engines/ml_engine/sagemaker_handler.py', 'w', encoding='utf-8') as f:
            f.write(sm_code)
        print("PATCHED sagemaker_handler.py")


    with open('main.py', 'r', encoding='utf-8') as f:
        main_code = f.read()

    target = '        out_log.write_text("", encoding="utf-8")\n        err_log.write_text("", encoding="utf-8")'
    replacement_target = '''        subprocess.run([str(python_for_streamlit), "-m", "pip", "install", "-r", "requirements.txt"], cwd=str(app_dir), capture_output=True)
        out_log.write_text("", encoding="utf-8")
        err_log.write_text("", encoding="utf-8")'''

    if target in main_code:
        main_code = main_code.replace(target, replacement_target)
        with open('main.py', 'w', encoding='utf-8') as f:
            f.write(main_code)
        print("PATCHED main.py")
    else:
        print("COULD NOT FIND main.py TARGET")

except Exception as e:
    print(e)

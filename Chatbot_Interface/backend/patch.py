import sys

try:
    with open('app.py', 'r', encoding='utf-8') as f:
        code = f.read()

    # We will just do a simpler string replace that handles windows newlines
    code = code.replace('        while True:\n            while sent < len(job.logs):\n                yield f"data: {json.dumps(job.logs[sent])}\\n\\n"',
                        '        while True:\n            while sent < len(job.logs):\n                yield f"data: {json.dumps(_clean_nans(job.logs[sent]))}\\n\\n"')
    
    code = code.replace('            if job.status in ("done", "error"):\n                yield f"data: {json.dumps({\'type\': job.status, \'result\': job.result, \'error\': job.error})}\\n\\n"',
                        '            if job.status in ("done", "error"):\n                payload = {\'type\': job.status, \'result\': job.result, \'error\': job.error}\n                yield f"data: {json.dumps(_clean_nans(payload))}\\n\\n"')

    if 'def _clean_nans(obj):' not in code:
        code = code.replace('@app.route("/api/pipeline/stream/<job_id>")', 
'''import math
def _clean_nans(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: _clean_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nans(v) for v in obj]
    return obj

@app.route("/api/pipeline/stream/<job_id>")''')

    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("PATCHED")
except Exception as e:
    print(e)

"""
regen_recommendation_app.py
Regenerates workspace/current_app/app.py using the new recommendation template.
Run from: Code_Generator/RAD-ML/
"""
import sys  # noqa: E402
import pathlib  # noqa: E402

sys.path.insert(0, ".")

from generator.base_streamlit import STREAMLIT_APP_RECOMMENDATION  # noqa: E402

app_dir = pathlib.Path("workspace/current_app")
app_dir.mkdir(parents=True, exist_ok=True)
app_py  = app_dir / "app.py"
app_py.write_text(STREAMLIT_APP_RECOMMENDATION, encoding="utf-8")
print(f"[OK] app.py written ({len(STREAMLIT_APP_RECOMMENDATION)} chars) -> {app_py}")

# Kill any running Streamlit
import subprocess as sp  # noqa: E402
sp.run(
    ["powershell", "-Command",
     "Get-CimInstance Win32_Process -Filter \"Name = 'python.exe' AND CommandLine LIKE '%streamlit%'\" | "
     "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
    capture_output=True,
)
print("[OK] Killed old Streamlit processes")

# Start the new Streamlit on a fixed port
proc = sp.Popen(
    [sys.executable, "-m", "streamlit", "run", "app.py",
     "--server.headless", "true",
     "--server.address", "localhost",
     "--server.port", "59142",
     "--browser.gatherUsageStats", "false",
     "--logger.level", "error"],
    cwd=str(app_dir),
)
print(f"[OK] Streamlit started (PID {proc.pid}) on http://localhost:59142")
print("Open http://localhost:59142 in your browser")

import asyncio
import sys
from pathlib import Path

sys.path.append("c:/Users/sabhi/OneDrive/Documents/Final_Year_Project")
from Chatbot_Interface.backend.orchestrator import Orchestrator

async def test():
    dc_dir = Path("c:/Users/sabhi/OneDrive/Documents/Final_Year_Project/Data_Collection_Agent")
    cg_dir = Path("c:/Users/sabhi/OneDrive/Documents/Final_Year_Project/Code_Generator/RAD-ML")
    
    orc = Orchestrator(str(dc_dir), str(cg_dir))
    job_id = orc.create_job("Build a movie recommendation system that suggests top 5 movies for users based on similarity and rating.")
    
    print(f"Created Job {job_id}. Running pipeline...")
    await orc.run_pipeline(job_id)
    
    job = orc.get_job(job_id)
    print("Job Status:", job.status)
    if job.result:
        print("Deploy URL:", job.result.get("deploy_url"))
        print("Stats:", job.result)
    else:
        print("Error:", job.error)
    
    # print full logs
    for log in job.logs:
        print(f"[{log.get('step')}] {log.get('status')}: {log.get('message')}")

if __name__ == "__main__":
    asyncio.run(test())

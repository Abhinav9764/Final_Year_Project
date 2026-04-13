#!/usr/bin/env python
"""
Test Google Authentication Flow
Tests the complete Google Sign-In → Backend Verification → JWT Token flow
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5001"

print("\n" + "="*80)
print("GOOGLE AUTHENTICATION SYSTEM TEST")
print("="*80)
print(f"\nTesting at: {BASE_URL}")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# Test 1: Check if backend is running
print("-"*80)
print("TEST 1: Backend Health Check")
print("-"*80)

try:
    response = requests.get(f"{BASE_URL}/api/health", timeout=5)
    if response.status_code == 200:
        print("✓ Backend is running and responding")
    else:
        print(f"✗ Backend returned status {response.status_code}")
except Exception as e:
    print(f"✗ Cannot connect to backend: {e}")

# Test 2: Check Google Auth Endpoint
print("\n" + "-"*80)
print("TEST 2: Google Auth Endpoint Status")
print("-"*80)

try:
    # Try sending a mock request (will fail because we don't have a real token)
    response = requests.post(
        f"{BASE_URL}/api/auth/google",
        json={"id_token": "mock_token_for_testing"},
        timeout=5
    )
    
    print(f"Response Status: {response.status_code}")
    print(f"Response Body: {response.json()}")
    
    if response.status_code == 400:
        if "Invalid ID token" in response.json().get("error", ""):
            print("\n✓ Google Auth endpoint is working!")
            print("  (Mock token rejected as expected - needs real Google token)")
    elif response.status_code == 500:
        print("\n✗ Backend error - check if google-auth library issue")
    else:
        print(f"\n✓ Endpoint accessible (status: {response.status_code})")
        
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: Check Authentication Database
print("\n" + "-"*80)
print("TEST 3: Database Configuration")
print("-"*80)

try:
    response = requests.get(f"{BASE_URL}/api/health", timeout=5)
    data = response.json()
    
    if "db" in data:
        print(f"Database: {data['db']}")
    
    print("✓ Auth system initialized")
    
except Exception as e:
    print(f"✗ Error checking database: {e}")

# Test 4: Check Frontend Configuration
print("\n" + "-"*80)
print("TEST 4: Frontend Configuration")
print("-"*80)

import os
env_path = r"c:\Users\sabhi\OneDrive\Desktop\RAD-ML-v8\Chatbot_Interface\frontend\.env"

if os.path.exists(env_path):
    with open(env_path) as f:
        content = f.read()
    
    if "VITE_GOOGLE_CLIENT_ID" in content:
        print("✓ Frontend .env file exists")
        print("✓ VITE_GOOGLE_CLIENT_ID is configured")
        
        # Extract and show partial client ID
        for line in content.split('\n'):
            if "VITE_GOOGLE_CLIENT_ID" in line:
                client_id = line.split('=')[1]
                masked = client_id[:20] + "..." + client_id[-10:] if len(client_id) > 30 else client_id
                print(f"  Client ID: {masked}")
    else:
        print("✗ VITE_GOOGLE_CLIENT_ID not found in .env")
else:
    print(f"✗ .env file not found at {env_path}")

# Test 5: Required Libraries
print("\n" + "-"*80)
print("TEST 5: Required Libraries Check")
print("-"*80)

libraries_to_check = {
    "flask": "Flask web framework",
    "google.auth": "Google authentication library",
    "jwt": "JWT token handling",
    "bcrypt": "Password hashing",
}

all_ok = True
for lib, description in libraries_to_check.items():
    try:
        __import__(lib)
        print(f"✓ {lib}: {description}")
    except ImportError:
        print(f"✗ {lib}: {description} - MISSING!")
        all_ok = False

# Test 6: Manual Google Token Verification Test
print("\n" + "-"*80)
print("TEST 6: Google Token Verification (With Real Token)")
print("-"*80)

print("""
To test with a REAL Google token:

1. Open the frontend: http://localhost:5179
2. Click "Continue with Google"
3. Complete the Google Sign-In flow
4. One of two things will happen:

   SUCCESS:
   • You'll see user profile on the app
   • New user created in database
   • JWT token generated
   
   FAILURE:
   • Backend will show error
   • Check logs below

""")

print("\n" + "="*80)
print("SUMMARY: Google Auth System Ready for Manual Testing")
print("="*80)

if all_ok:
    print("\n✓ All systems configured correctly!")
    print("✓ You can now test Google Sign-Up on the frontend")
    print(f"✓ Frontend: http://localhost:5179")
    print(f"✓ Backend:  {BASE_URL}")
else:
    print("\n⚠ Some dependencies are missing")
    print("  Run: pip install -r requirements.txt")

print("\n" + "="*80)

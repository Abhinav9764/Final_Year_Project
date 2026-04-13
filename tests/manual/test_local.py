import requests, json, time

if __name__ == "__main__":
    auth_res = requests.post('http://localhost:5001/api/auth/login', json={'username': 'Abhinav', 'password': 'password'})
    token = auth_res.json().get('token')
    hist_res = requests.get('http://localhost:5001/api/history', headers={'Authorization': 'Bearer ' + token})
    with open("history.json", "w") as f:
        json.dump(hist_res.json(), f, indent=2)
    print("Finished writing to history.json")

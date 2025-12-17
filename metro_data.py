import requests
import json

# KEEP YOUR API KEY HERE
API_KEY = "c53cb0be42a44223bd50e608d5428b03"

# E05 is the code for Georgia Ave-Petworth
STATION_CODE = "E05" 

def get_trains():
    headers = {
        'api_key': API_KEY,
    }

    try:
        url = f"https://api.wmata.com/StationPrediction.svc/json/GetPrediction/{STATION_CODE}"
        
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if 'Trains' in data:
            print(f"--- Trains at Georgia Ave-Petworth ({STATION_CODE}) ---")
            
            # Sort trains by arrival time just in case WMATA sends them out of order
            trains = data['Trains']
            
            # Filter out "No Passenger" trains if you want
            valid_trains = [t for t in trains if t['Destination'] != "No Passenger"]

            for train in valid_trains:
                line = train['Line']
                dest = train['Destination']
                minutes = train['Min']
                
                # Check for "Arriving" or "Boarding" status
                if minutes == 'ARR':
                    time_str = "ARRIVING"
                elif minutes == 'BRD':
                    time_str = "BOARDING"
                else:
                    time_str = f"{minutes} min"

                print(f"[{line}] to {dest}: {time_str}")
        else:
            print("Error: Could not find train data.")

    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    get_trains()
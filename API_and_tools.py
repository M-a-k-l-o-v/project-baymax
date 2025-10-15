import requests
from datetime import datetime
import os

import os
# tools
def get_location():
    try:
        ip_info = requests.get("https://ipapi.co/json/").json() 
        # this returns a dictionary with network based location so vpn would switch
        # things up, try using device hardware location later.
        
        city = ip_info.get("city")
        country = ip_info.get("country_name")
        latitude = ip_info.get("latitude")
        longitude = ip_info.get("longitude")
        return city, country, latitude, longitude
    except Exception as e:
        print("Error getting location:", e)
        return None
    
def get_weather():
    location = get_location() # API calls cant be made to often so lets try to have it be called once and only update every 30 mins
    if location:
        city, country, latitude, longitude = location
        print(f"{city}, {country} ({latitude}, {longitude})")
    
        url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current_weather=true"
        response = requests.get(url)
        print("Raw weather response:", response.text)
        data = response.json()
        if "current_weather" not in data:
            print("No current_weather field found")
            return None
        return data["current_weather"]
    else :
        print("Error getting location:")
    

def get_time():
    """Return the current local time as a formatted string."""
    now = datetime.now()
    return now.strftime("%H:%M:%S")  # 24-hour format

def get_date():
    """Return today's date as a formatted string."""
    today = datetime.now()
    return today.strftime("%A, %B %d, %Y")  # e.g., "Friday, October 10, 2025"

def shut_down():
    """Shuts down the operating system."""
    os.system('shutdown -s')
    return True
def shut_down():
    os.system("sudo shutdown -h now")
    return True

#tool dictionary
TOOLS = {
    "get_location": get_location,
    "get_weather": get_weather,
    "get_time": get_time,
    "get_date": get_date,
    "shut_down": shut_down,
    
}

print(get_date(), get_time())
weather = get_weather()
print(weather)

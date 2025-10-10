import requests
import os
# tools
def get_location():
    try:
        ip_info = requests.get("https://ipapi.co/json/").json() 
        # this returns a dictionary with network based location so vpn would switch
        # things up, try using device hardware location later.
        
        city = ip_info.get("city")
        country = ip_info.get("country_name")
        print([city, country])
        return [city, country]
    except Exception as e:
        print("Error getting location:", e)
        return None
    
def get_weather(city, country):

    return True
def get_time():
    return True
def get_date():
    return True
def shut_down():
    os.system("sudo shutdown -h now")
    return True

#tool dictionary
TOOLS = {

    
}

get_location()
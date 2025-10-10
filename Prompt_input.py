import pyaudio
import speech_recognition as sr #running mine with wit.ai

# --- API Keys ---
WIT_AI_KEY = "WITWM2DF3D6X5TD67X32EFAVGKD3R5SF"

# --- Initialize ---
recognizer = sr.Recognizer()

# ---- simmiar keyword ----- 
# later ima try to have Wit send text 
# transcription and basic meaning so the
# robustness of keywords is not limited.
affirmative_words = ['yes','sure', 'yea', 'yeah']
rejection_words = ['no', 'nah', 'nay', 'nevermind','na','nothing']
error_log = {
    'ERROR1': "No speech detected",
    'ERROR2': "Could not understand audio.",

      }

#modules
def listener():
    print("Voice assistant activated. Speak when ready...")
    with sr.Microphone() as source:
            print("Listening...")
            prompt = "hey (base prompt)"
            try: # 1st listen attempt
                prompt = recognizer.listen(source, timeout=3)
            except sr.WaitTimeoutError: 
                print(f"{error_log['ERROR1']}, did you say something?")
                try: # low amplitude failsafe
                    listener_check_audio = recognizer.listen(source, timeout=3)
                    listener_check_text = transcriber(listener_check_audio)
                    print(listener_check_text)
                    if listener_check_text.lower() in affirmative_words:
                        print("what did you say?")
                        prompt = recognizer.listen(source, timeout=3)
                    elif listener_check_text.lower() in rejection_words:
                        print("okay")                    
                    else:
                        print(error_log['ERROR2'])
                except sr.WaitTimeoutError:
                    print(error_log['ERROR1'])
    return prompt

def transcriber(audio_data):
    try:
        text = recognizer.recognize_wit(audio_data, WIT_AI_KEY)
        print(f'You said: "{text}"')
    except sr.UnknownValueError:
        print(error_log['ERROR2'])
    except sr.RequestError as error:
                print(f"Wit.ai error: {error}")

    return text


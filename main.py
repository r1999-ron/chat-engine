import re
from datetime import datetime

import requests
import speech_recognition as sr  # For converting audio to text
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pydub import AudioSegment  # For handling audio files
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import os

load_dotenv()
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
app = Flask(__name__)

# SQLite database setup
DATABASE = "employees.db"  # Replace with your actual database file name

# Twilio WhatsApp Sandbox number
TWILIO_WHATSAPP_NUMBER = TWILIO_WHATSAPP_NUMBER
API_URL = "https://4162-49-205-242-177.ngrok-free.app/query"

# Speech-to-text recognizer
recognizer = sr.Recognizer()

CORS(app, supports_credentials=True)


def execute_query(query):
    payload = {"query": query}
    headers = {"Content-Type": "application/json", "x-api-key": "abcdef"}

    try:
        response = requests.post(API_URL, json=payload, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            return response_data  # Successfully executed query (SELECT or other)
        else:
            print("Error:", response_data.get("error"))
            return None
    except requests.exceptions.RequestException as e:
        print("Request failed:", str(e))
        return None


# Check if the phone number exists in the employee table
def get_employee(phone_number):
    print(phone_number)
    phone_number = phone_number[-10:]  # Extract the last 10 digits
    query_result = execute_query(f"SELECT * FROM employee WHERE phone LIKE '%{phone_number}%'")
    print(query_result)
    return query_result


def get_attendance(employee_id, date_to_mark):
    if '\'' in date_to_mark:
        date_to_mark = date_to_mark.replace('\'', '')
    query_result = execute_query(
        f"SELECT status FROM attendance WHERE empId={employee_id} and date='{date_to_mark}'")
    print(query_result)
    return query_result[0]["status"] if query_result else None


def add_attendance(employee_id, today, status):
    # Ensure the date is properly formatted for SQL
    today = f"'{today}'"  # Wrap in single quotes for SQL

    # Check if the attendance record already exists
    query_result = get_attendance(employee_id, today)

    print(query_result)  # Debugging: Prints the query result

    if query_result:
        execute_query(
            f"UPDATE attendance SET status='{status}' WHERE empId={employee_id} AND date={today}"
        )
    else:
        execute_query(
            f"INSERT INTO attendance (empId, date, status) VALUES ({employee_id}, {today}, '{status}')"
        )
    return status  # Return the inserted status


# Download audio file from Twilio
def download_audio(media_url):
    try:
        account_sid = TWILIO_ACCOUNT_SID  # Replace with your Twilio Account SID
        auth_token = TWILIO_AUTH_TOKEN  # Replace with your Twilio Auth Token
        response = requests.get(media_url, auth=(account_sid, auth_token))
        response.raise_for_status()
        audio_file_path = "temp_audio.ogg"
        with open(audio_file_path, "wb") as f:
            f.write(response.content)
        print(f"Audio file downloaded: {audio_file_path}")
        return audio_file_path
    except Exception as e:
        print(f"Error downloading audio file: {e}")
        return None


# Convert audio to text
def convert_audio_to_text(audio_file_path):
    try:
        audio = AudioSegment.from_file(audio_file_path)
        wav_file_path = "temp_audio.wav"
        audio.export(wav_file_path, format="wav")
        with sr.AudioFile(wav_file_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
        print(f"Converted audio to text: {text}")
        return text
    except Exception as e:
        print(f"Error converting audio to text: {e}")
        return None


# Call Ronak's service
def call_docuseek_api(message):
    # API endpoint
    url = "https://information-retrieval-service.onrender.com/query"

    # Headers
    headers = {
        "token": "abcdef",
        "Content-Type": "application/json"
    }

    # Request payload
    data = {
        "question": message

    }
    response = requests.post(url, json=data, headers=headers)
    # Extracting the "answer" field
    if response.status_code == 200:
        response_json = response.json()
        answer = response_json.get("answer", "No answer found")  # Default if key is missing
        return answer
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return response.json()


@app.route("/webhook", methods=["POST"])
def webhook():
    # Validate API Key via Query Parameter
    api_key = request.args.get("x_api_key")
    if api_key != "abcdef":
        return jsonify({"error": "Unauthorized"}), 401
    incoming_message = request.form.get("Body")
    sender_number = request.form.get("From")
    num_media = int(request.form.get("NumMedia", 0))

    print(f"Received message: {incoming_message} from {sender_number}")

    employee = get_employee(sender_number[-10:])
    if not employee:
        return str(MessagingResponse().message("You are not authorized to use this service."))

    final_message = incoming_message
    if num_media > 0:
        media_url = request.form.get("MediaUrl0")
        media_type = request.form.get("MediaContentType0")
        if media_type.startswith("audio/"):
            print("Received an audio message.")
            audio_file_path = download_audio(media_url)
            if audio_file_path:
                final_message = convert_audio_to_text(audio_file_path)
                print("Converted audio file to text. ", final_message)

    if "today" in final_message.lower() and "attendance" in final_message.lower():
        today = datetime.today().strftime("%Y-%m-%d")
        employee_id = employee[0].get("id")
        attendance_status = get_attendance(employee_id, date_to_mark=today)
        print(attendance_status)
        if attendance_status:
            reply = f"Your attendance for today ({today}) is: {attendance_status}"
        else:
            reply = f"No record found for {today}"
    elif final_message.strip().upper() in ["PRESENT", "ABSENT"]:
        today = datetime.today().strftime("%Y-%m-%d")
        employee_id = employee[0].get("id")
        attendance_status = add_attendance(employee_id, today, final_message.strip().upper())
        reply = f"Attendance recorded: {attendance_status}"
    else:
        if final_message.strip().lower().startswith("custom") and "manager" in employee[0].get("role").lower():
            final_message = re.sub(r'(?i)custom', '', final_message)
            sql_message = (
                f"you are a SQL expert for writing queries in sqlite3 python, always write query case insensitive, "
                f"you have to only give the exact query for MySQL so that the result of yours,"
                f"I can directly fire in DB. You have the Employee and Attendance table information: "
                f"Employee with columns (id, name, email, phone, role (engineer, HR, tester, manager, and founder), "
                f"level (integer 1,2,3), reportsTo (id of manager who is also an employee), skills (string)); "
                f"Attendance with columns (id, empId, date(yyyy-mm-dd), status(PRESENT/ABSENT)). if you are using "
                f"CURRENT_DATE() for date in Attendance table use yyyy-mm-dd as date, if today then today's date in "
                f"yyyy-mm-dd. Make sure you just return the query if you can"
                f"think of one, or just return NotSure if you are not able to make sql query for - write a SQL query to "
                f"{final_message}")
            response_from_service_b = call_docuseek_api(sql_message)
            print(f"AI's response for query {response_from_service_b}")
            query = re.search(r"```sql\s*(.*?)\s*```", response_from_service_b, re.DOTALL)
            if query:
                query = query.group(1).strip()
                print(f"final sql query {query}")
            query = " ".join(query.split())
            print(f"Query after removing new lines {query}")
            if not "notsure" in query.lower():
                result = execute_query(query)
                # final_response = call_ronak_api(
                #      f"Answer {final_message} from result {result}")
                # print(final_response)
                # reply = final_response if final_response else "Oops, currently I don't have that information."
                reply = f"Your result is \n {result}"
        else:
            response_from_service_b = call_docuseek_api(final_message)
            print(response_from_service_b)
            reply = response_from_service_b if response_from_service_b else "Oops, currently I don't have that information."

    try:
        print("Reply:", reply)

        # Create a TwiML response
        twiml_response = MessagingResponse()
        twiml_response.message(body=reply)

        # Convert the TwiML response to a string
        twiml_response_str = str(twiml_response)
        print("TwiML response:", twiml_response_str)

        # Return the response with the correct content type
        return Response(twiml_response_str, content_type="text/xml")
    except Exception as e:
        print(f"An error occurred: {e}")
        return Response(str(e), status=500, content_type="text/plain")


@app.route("/execute_query", methods=["POST"])
def execute_query_api():
    if request.headers.get("x-api-key") != "abcdef": return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    query = data.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    result = execute_query(query)
    if result is not None:
        return jsonify(result), 200
    else:
        return jsonify({"error": "Query execution failed"}), 500


# Run the Flask app
if __name__ == "__main__":  # Add initial attendance entries
    app.run(debug=True)
import re
from datetime import datetime
import requests
import speech_recognition as sr
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from pydub import AudioSegment
from twilio.twiml.messaging_response import MessagingResponse
from dotenv import load_dotenv
import os
from gtts import gTTS
from twilio.rest import Client

# Load environment variables
load_dotenv()
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
API_URL = os.getenv("API_URL")

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Database configuration
DATABASE = "employees.db"

# Speech-to-text recognizer
recognizer = sr.Recognizer()

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def execute_query(query):
    """Execute SQL query through API"""
    payload = {"query": query}
    headers = {"Content-Type": "application/json", "x-api-key": "abcdef"}

    try:
        response = requests.post(API_URL + "/query", json=payload, headers=headers)
        response_data = response.json()

        if response.status_code == 200:
            return response_data
        else:
            print("Error:", response_data.get("error"))
            return None
    except requests.exceptions.RequestException as e:
        print("Request failed:", str(e))
        return None


def get_employees(phone_number):
    """Get employee details by phone number"""
    phone_number = phone_number[-10:]  # Extract last 10 digits

    url = API_URL + "/employees"
    params = {"phone": f"{phone_number}"}  # Optional filter
    headers = {"x-api-key": "abcdef"}

    response = requests.post(url, params=params, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error: No employee found with this phone number {phone_number}")


def get_employee_by_id(empId):
    headers = {"x-api-key": "abcdef"}

    try:
        response = requests.post(  # POST method
            API_URL+f"/employees/{empId}",
            headers=headers
        )

        if response.status_code == 200:
            employee_data = response.json()
            print("Employee details:", employee_data)
            return employee_data
        elif response.status_code == 404:
            print("Error: Employee not found")
        else:
            print(f"Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Request failed: {str(e)}")


def get_attendance(employee_id, date_to_mark):
    url = API_URL + f"/{employee_id}/attendance_by_date"
    headers = {"x-api-key": "abcdef"}
    params = {"date": date_to_mark}

    response = requests.post(url, headers=headers, params=params)
    return response.json()


def add_attendance(employee_id, today, status):
    # Convert the date string to datetime object for validation
    datetime_obj = datetime.strptime(today, "%Y-%m-%d")
    # Convert back to string for JSON serialization
    date_str = datetime_obj.strftime("%Y-%m-%d")

    url = API_URL + "/attendance"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": "abcdef"
    }
    data = {
        "empId": employee_id,
        "date": date_str,  # Now using string instead of datetime object
        "status": status
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error marking attendance: {e}")
        return None


def get_attendance_filter(emp_id, days=None, from_date=None, to_date=None):
    """
    Calls the attendance API endpoint

    Args:
        emp_id: Employee ID (integer)
        days: Number of days to look back (optional)
        from_date: Start date as 'YYYY-MM-DD' string (optional)
        to_date: End date as 'YYYY-MM-DD' string (optional)

    Returns:
        Dictionary with attendance data and leave statistics
    """
    # Prepare headers with authentication
    headers = {
        "x-api-key": "abcdef",
        "Content-Type": "application/json"
    }

    # Build query parameters
    params = {}
    if days:
        params["days"] = days
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    # Make the POST request
    response = requests.post(
        f"{API_URL}/attendance/{emp_id}",
        headers=headers,
        params=params
    )

    # Handle response
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()  # Raises exception for 4XX/5XX errors


def format_calendar(data):
    # Collect all dates with their status
    date_status = {}
    for status, dates in data["attendance"].items():
        for date in dates:
            date_status[date] = status

    # Group by month
    months = {}
    for date_str in sorted(date_status.keys()):
        date = datetime.strptime(date_str, "%Y-%m-%d")
        month_key = date.strftime("%Y-%m")
        if month_key not in months:
            months[month_key] = []
        months[month_key].append((date.day, date_status[date_str]))

    # Build calendar
    calendar = []
    for month, days in months.items():
        month_header = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        calendar.append(f"\n📅 {month_header}")
        calendar.append("Su Mo Tu We Th Fr Sa")

        # Find first day of month
        first_date = datetime.strptime(f"{month}-01", "%Y-%m-%d")
        first_weekday = first_date.weekday()  # Monday is 0

        # Add leading spaces
        week = ["  "] * first_weekday

        for day, status in days:
            # Emoji representation
            emoji = {
                "PRESENT": "✅",
                "ABSENT": "❌",
                "WFH": "🏠"
            }.get(status, " ")

            week.append(f"{emoji}{day:2}")

            # New week
            if len(week) == 7:
                calendar.append(" ".join(week))
                week = []

        if week:  # Add remaining days
            calendar.append(" ".join(week))

    return "\n".join(calendar)


def get_my_requests(employee_id, status="", request_type="all"):
    api_url = API_URL + "/employees/{}/requests".format(employee_id)

    headers = {
        "Content-Type": "application/json",
        "x-api-key": "abcdef"  # Your API key
    }

    params = {"type": request_type}
    response = requests.post(api_url, headers=headers, params=params)

    if response.status_code == 200:
        total_requests = response.json()

        # Filter by status if status parameter is not empty
        if status:
            filtered_requests = [
                req for req in total_requests
                if req['requestStatus'] == status.upper()
            ]
            print(f"Filtered requests (status={status}):", filtered_requests)
            return filtered_requests
        else:
            print("All requests:", total_requests)
            return total_requests
    else:
        print("Error:", response.json())
        return None

def get_request_by_id(request_id):
    # params = {
    #     "requesterEmpId": 123,          # Filter by employee who made request
    #     "approverEmpId": 456,           # Filter by who needs to approve
    #     "requestType": "LEAVE",         # "LEAVE" or "WFH"
    #     "requestStatus": "PENDING",     # "PENDING", "APPROVED", or "REJECTED"
    #     "fromDate": "2023-01-01",       # Start date range (YYYY-MM-DD)
    #     "toDate": "2023-12-31"          # End date range (YYYY-MM-DD)
    # }

    headers = {"Content-Type": "application/json", "x-api-key": "abcdef"}

    params = {
         "id": request_id,
    }
    try:
        response = requests.post(
            API_URL+"/get-all-request",
            params=params,
            headers=headers,

        )

        if response.status_code == 200:
            requests_data = response.json()
            print("Fetched requests:", requests_data)
            return requests_data
        else:
            print(f"Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Request failed: {str(e)}")

def update_request_status(request_id, new_status, user_id, api_key="abcdef"):
    """
    Update the status of a request approval

    Args:
        request_id: ID of the request to update
        new_status: New status (APPROVED/REJECTED/PENDING)
        api_key: API key for authentication

    Returns:
        Dictionary with response data if successful, None if failed
    """
    api_url = f"{API_URL}/request-approvals/{request_id}"

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    data = {
        "requestStatus": new_status.upper(),
        "userId": user_id
    }

    try:
        response = requests.put(api_url, json=data, headers=headers)

        if response.status_code == 200:
            print("Request status updated successfully")
            return response.json()
        else:
            print(f"Error updating request: {response.status_code}", response.json())
            return None

    except Exception as e:
        print(f"Request failed: {str(e)}")
        return None


def parse_leave_request(message: str) -> tuple:
    """
    Parse leave/WFH request from message
    Format: "[WFH/LEAVE] from yyyy-mm-dd to yyyy-mm-dd"
    Returns: (request_type, from_date, to_date) or (None, None, None) if invalid
    """
    pattern = r"^(wfh|leave)\s+from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})$"
    match = re.match(pattern, message.lower())
    if not match:
        return None, None, None

    request_type = match.group(1).upper()  # "WFH" or "LEAVE"
    from_date = match.group(2)
    to_date = match.group(3)

    # Validate dates
    try:
        datetime.strptime(from_date, "%Y-%m-%d")
        datetime.strptime(to_date, "%Y-%m-%d")
        return request_type, from_date, to_date
    except ValueError:
        return None, None, None


def create_request_approval(
        emp_id: int,
        request_type: str,
        from_date: str,  # YYYY-MM-DD format
        to_date: str,    # YYYY-MM-DD format
        api_key: str = "abcdef"
):
    """
    Create a new request approval (LEAVE/WFH)

    Args:
        emp_id: Employee ID making the request
        request_type: 'LEAVE' or 'WFH'
        from_date: Start date (YYYY-MM-DD)
        to_date: End date (YYYY-MM-DD)
        api_key: API key for authentication
        base_url: Base URL of the API service

    Returns:
        Dictionary with response data or error message
    """
    url = f"{API_URL}/request-approvals"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key
    }

    data = {
        "empId": emp_id,
        "requestType": request_type.upper(),
        "fromDate": from_date,
        "toDate": to_date
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()  # Raises exception for 4XX/5XX responses
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        # Handle API-specific error messages
        try:
            error_data = response.json()
            return {
                "success": False,
                "error": error_data.get("error", "Unknown error"),
                "details": error_data
            }
        except:
            return {
                "success": False,
                "error": str(http_err)
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def download_audio(media_url):
    """Download audio file from Twilio"""
    try:
        response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        response.raise_for_status()
        audio_file_path = "temp_audio.ogg"
        with open(audio_file_path, "wb") as f:
            f.write(response.content)
        return audio_file_path
    except Exception as e:
        print(f"Error downloading audio file: {e}")
        return None


def convert_audio_to_text(audio_file_path):
    """Convert audio to text using Google Speech Recognition"""
    try:
        audio = AudioSegment.from_file(audio_file_path)
        wav_file_path = "temp_audio.wav"
        audio.export(wav_file_path, format="wav")
        with sr.AudioFile(wav_file_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
        return text
    except Exception as e:
        print(f"Error converting audio to text: {e}")
        return None


def text_to_speech(text):
    """Convert text to speech audio file"""
    try:
        tts = gTTS(text=text, lang='en')
        audio_path = "reply.mpeg"
        tts.save(audio_path)
        return audio_path
    except Exception as e:
        print(f"Error in text-to-speech: {e}")
        return None


def upload_audio_file(file_path):
    """Upload audio file to temporary hosting service"""
    try:
        files = {'file': open(file_path, 'rb')}
        response = requests.post('https://tmpfiles.org/api/v1/upload', files=files)
        print(f"Response from audio file {response.json()['data']}")
        if response.status_code == 200:
            return response.json()['data']['url']
        return None
    except Exception as e:
        print(f"Error uploading audio file: {e}")
        return None


def call_docuseek_api(message, employee_type):
    """Call external API for document search"""
    url = f"https://information-retrieval-service.onrender.com/query?employee_type={employee_type}"
    headers = {
        "token": "abcdef",
        "Content-Type": "application/json"
    }
    data = {"question": message}

    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return response.json().get("answer", "No answer found")
    else:
        print(f"Error: {response.status_code}, {response.text}")
        return None


def process_attendance_message(message):
    # Normalize the message (remove extra spaces, make uppercase)
    message = message.strip().upper()

    # Define patterns to match
    patterns = [
        r'^(PRESENT|ABSENT|WFH)\s*(\d{4}-\d{2}-\d{2})?$',  # "PRESENT" or "PRESENT 2023-12-15"
        r'^(PRESENT|ABSENT|WFH)(\d{4}-\d{2}-\d{2})$'  # "PRESENT2023-12-15"
    ]

    status = None
    date = None

    for pattern in patterns:
        match = re.match(pattern, message)
        if match:
            status = match.group(1)
            date_str = match.group(2) if len(match.groups()) > 1 else None
            break

    if not status:
        return None, None  # Invalid format

    # Set default date to today if not provided
    date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else datetime.today().date()

    return status, date.strftime("%Y-%m-%d")


def sendReply(client, reply, sender_number):
    client.messages.create(
        body=reply,
        from_=TWILIO_WHATSAPP_NUMBER,
        to=sender_number
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    """Main webhook handler for Twilio WhatsApp messages"""
    # Validate API Key
    api_key = request.args.get("x_api_key")
    if api_key != "abcdef":
        return jsonify({"error": "Unauthorized"}), 401

    # Get incoming message details
    incoming_message = request.form.get("Body", "")
    sender_number = request.form.get("From", "")
    num_media = int(request.form.get("NumMedia", 0))
    is_audio_received = num_media > 0 and request.form.get("MediaContentType0", "").startswith("audio/")

    print(f"Received message: {incoming_message} from {sender_number}")

    # Check employee authorization
    employee = get_employees(sender_number[-10:])
    if not employee:
        return str(MessagingResponse().message("You are not authorized to use this service."))
    print("employee", employee[0])
    employee_type = employee[0].get("employeeType")
    final_message = incoming_message

    # Handle audio messages
    if is_audio_received:
        media_url = request.form.get("MediaUrl0")
        audio_file_path = download_audio(media_url)
        if audio_file_path:
            final_message = convert_audio_to_text(audio_file_path) or incoming_message
            print("Converted audio to text:", final_message)

    # Process different message types
    if "today" in final_message.lower() and "attendance" in final_message.lower():
        today = datetime.today().strftime("%Y-%m-%d")
        employee_id = employee[0].get("id")
        attendance_status = get_attendance(employee_id, today)
        reply = f"Your attendance for today ({today}) is: {attendance_status}" if attendance_status else f"No record found for {today}"

    elif any(keyword in final_message.upper() for keyword in ["PRESENT", "ABSENT", "WFH"]) and "from" not in final_message.lower() and "to" not in final_message.lower():
        status, date = process_attendance_message(final_message)

        if not status:
            reply = "Invalid attendance format. Use: PRESENT/ABSENT/WFH [YYYY-MM-DD]"
        else:
            employee_id = employee[0].get("id")
            attendance = add_attendance(employee_id, date, status)

            if attendance:
                reply = f"Marked {status} for {date}"
            else:
                reply = "Failed to mark attendance"

    elif final_message.lower().startswith("my attendance"):
        employee_id = employee[0].get("id")
        date_parts = final_message.split()
        from_index = date_parts.index("from")
        to_index = date_parts.index("to")

        from_date = date_parts[from_index + 1]
        to_date = date_parts[to_index + 1]

        reply = format_calendar(get_attendance_filter(emp_id=employee_id, from_date=from_date, to_date=to_date))

    elif final_message.lower() == "my request history":
        employee_id = employee[0].get("id")

        request_raised_by_me = get_my_requests(employee_id, "", "created")

        if request_raised_by_me:
            request_list = "\n".join(
                f"{req['id']}: {req['requestType']} ({req['fromDate']} to {req['toDate']}) - {req['requestStatus']}"
                for req in request_raised_by_me
            )
            reply = (
                "requests raised by me:\n"
                f"{request_list}\n\n"
            )
        else:
            reply = "No requests raised by me"

    elif final_message.lower() == "my active request":
        employee_id = employee[0].get("id")

        active_request_raised_by_me = get_my_requests(employee_id, "PENDING", "created")

        if active_request_raised_by_me:
            request_list = "\n".join(
                f"{req['id']}: {req['requestType']} ({req['fromDate']} to {req['toDate']}) - {req['requestStatus']}"
                for req in active_request_raised_by_me
            )
            reply = (
                "active requests raised by me:\n"
                f"{request_list}\n\n"
            )
        else:
            reply = "No active requests raised by me"

    elif final_message.lower() == "request on me":
        employee_id = employee[0].get("id")

        requests_on_me = get_my_requests(employee_id, "", "approval")

        if requests_on_me:
            request_list = "\n".join(
                f"{req['id']}: {req['requestType']} ({req['fromDate']} to {req['toDate']}) - {req['requestStatus']}"
                for req in requests_on_me
            )
            reply = (
                "Requests raised to you:\n"
                f"{request_list}\n\n"
                "Reply with 'accept request <ID>' to approve"
            )
        else:
            reply = "No requests require your approval"

    elif final_message.lower() == "active request on me":
        employee_id = employee[0].get("id")

        pending_requests_on_me = get_my_requests(employee_id, "PENDING", "approval")

        if pending_requests_on_me:
            request_list = "\n".join(
                f"{req['id']}: {req['requestType']} ({req['fromDate']} to {req['toDate']}) - {req['requestStatus']}"
                for req in pending_requests_on_me
            )
            reply = (
                "Pending requests needing approval:\n"
                f"{request_list}\n\n"
                "Reply with 'accept request <ID>' to approve"
            )
        else:
            reply = "No pending requests require your approval"

    elif final_message.lower().startswith("accept request"):

        parts = final_message.lower().split()
        employee_id = employee[0].get("id")

        if len(parts) > 2:  # "accept request 123"
            try:
                request_id = int(parts[2])
                result = update_request_status(
                    request_id=request_id,
                    new_status="APPROVED",
                    user_id=employee_id
                )
                print(f"Updated request status: {result}")

                if result and result.get("success", True):
                    req = get_request_by_id(request_id)
                    reqType = req[0]["requestType"]
                    from_date = req[0]["fromDate"]
                    to_date = req[0]["toDate"]
                    req_status = req[0]["requestStatus"]
                    requesterEmpId = req[0]["requesterEmpId"]
                    emp = get_employee_by_id(requesterEmpId)
                    replyTo = emp['phone']
                    reply = f"Request {request_id} of {reqType} from {from_date} to {to_date} {req_status}"
                    sendReply(client, reply, "whatsapp:+91" + replyTo)
                else:
                    reply = "Failed to approve request"

            except ValueError:
                reply = "Invalid request ID. Please use format 'accept request <ID>'"

        else:  # Just "accept request"
            pending_requests_on_me = get_my_requests(
                employee_id=employee_id,
                status="PENDING",
                request_type="approval"
            )

            if pending_requests_on_me:
                request_list = "\n".join(
                    f"{req['id']}: {req['requestType']} ({req['fromDate']} to {req['toDate']})"
                    for req in pending_requests_on_me
                )
                reply = (
                    "Pending requests needing approval:\n"
                    f"{request_list}\n\n"
                    "Reply with 'accept request <ID>' to approve"
                )
            else:
                reply = "No pending requests require your approval"

    elif final_message.lower().startswith("reject request"):
        parts = final_message.lower().split()
        employee_id = employee[0].get("id")

        if len(parts) > 2:  # "reject request 123"
            try:
                request_id = int(parts[2])
                result = update_request_status(
                    request_id=request_id,
                    new_status="REJECTED",
                    user_id=employee_id
                )
                print(f"Updated request status: {result}")

                if result and result.get("success", True):
                    req = get_request_by_id(request_id)
                    reqType = req[0]["requestType"]
                    from_date = req[0]["fromDate"]
                    to_date = req[0]["toDate"]
                    req_status = req[0]["requestStatus"]
                    requesterEmpId = req[0]["requesterEmpId"]
                    emp = get_employee_by_id(requesterEmpId)
                    replyTo = emp['phone']
                    reply = f"Request {request_id} of {reqType} from {from_date} to {to_date} {req_status}"
                    sendReply(client, reply, "whatsapp:+91" + replyTo)
                else:
                    reply = "Failed to reject request"

            except ValueError:
                reply = "Invalid request ID. Please use format 'reject request <ID>'"

        else:  # Just "reject request"
            pending_requests_on_me = get_my_requests(
                employee_id=employee_id,
                status="PENDING",
                request_type="approval"
            )

            if pending_requests_on_me:
                request_list = "\n".join(
                    f"{req['id']}: {req['requestType']} ({req['fromDate']} to {req['toDate']})"
                    for req in pending_requests_on_me
                )
                reply = (
                    "Pending requests needing approval:\n"
                    f"{request_list}\n\n"
                    "Reply with 'accept request <ID>' to approve"
                )
            else:
                reply = "No pending requests require your approval"

    elif final_message.lower().startswith(("wfh", "leave")) and "from" in final_message.lower() and "to" in final_message.lower():
        request_type, from_date, to_date = parse_leave_request(final_message)

        if not request_type:
            reply = "Invalid format. Use: '[WFH/LEAVE] from yyyy-mm-dd to yyyy-mm-dd'"
        else:
            employee_id = employee[0].get("id")
            employee_reports_to_id = employee[0].get("reportsTo")
            employee_name = employee[0].get("name")
            emp_reports_to_response = get_employee_by_id(employee_reports_to_id)
            employee_reports_to_number = emp_reports_to_response['phone']
            result = create_request_approval(
                emp_id=employee_id,
                request_type=request_type,
                from_date=from_date,
                to_date=to_date
            )

            if result.get("success", True):
                reply = (
                    f"{request_type.capitalize()} request submitted!\n"
                    f"From: {from_date}\n"
                    f"To: {to_date}\n"
                    f"Request ID: {result.get('requestId')}"
                )
                reply_to_manager = (
                    f"{request_type.capitalize()} request submitted by {employee_name}!\n"
                    f"From: {from_date}\n"
                    f"To: {to_date}\n"
                    f"Request ID: {result.get('requestId')}")

                print(f"employee reports to number {employee_reports_to_number}")
                sendReply(client, reply_to_manager, f"whatsapp:+91{employee_reports_to_number}")
            else:
                reply = f"Failed to submit request: {result.get('error')}"
                if "conflictDates" in result.get("details", {}):
                    reply += f"\nConflicts on: {', '.join(result['details']['conflictDates'])}"
                elif "leaves_taken" in result.get("details", {}):
                    remaining = 15 - result["details"]["leaves_taken"] - result["details"]["pending_leaves"]
                    reply += f"\nYou have only {remaining} leave days remaining"
    elif final_message.strip().lower().startswith("find contact of "):
        final_message = re.sub(r'(?i)find contact of', '', final_message)

        query = f"SELECT name, email, phone FROM employee WHERE LOWER(name) LIKE \'%{final_message.lower()}%\' "
        reply = execute_query(query)
    else:
        if final_message.strip().lower().startswith("custom employee") and employee[0].get("level", "0") >= 5:
            final_message = re.sub(r'(?i)custom', '', final_message)
            sql_message = (
                f"you are a SQL expert for writing queries in sqlite3 python, always write query case insensitive, "
                f"you have to only give the exact query for MySQL so that the result of yours,"
                f"I can directly fire in DB. You have the Employee and Attendance table information: "
                f"Employee with columns (id, name, email, phone, role (engineer, HR, tester, manager, and founder), "
                f"level (integer 1,2,3), clientCompany(string), location(string), employeeType(can have values A, B, C), reportsTo (id of manager who is also an employee), skills (string)); "
                f"Attendance with columns (id, empId, date(yyyy-mm-dd), status(PRESENT/ABSENT)), requestId(integer value), Now tell me the query for - {final_message}")
            response_from_service_b = call_docuseek_api(sql_message, employee_type)
            query = re.search(r"```sql\s*(.*?)\s*```", response_from_service_b or "", re.DOTALL)
            if query:
                query = query.group(1).strip()
                query = " ".join(query.split())
                if "notsure" not in query.lower():
                    result = execute_query(query)
                    if result:
                        formatted_response = "Employee Details:\n" + "\n".join(
                            f"• {emp['name']} ({emp['clientCompany']})"
                            f"\n  📧 {emp['email']}"
                            f"\n  📞 {emp['phone']}"
                            f"\n  📍 {emp['location']} (Level {emp['level']})"
                            for emp in result
                        )
                    else:
                        formatted_response = "No employee data found"
                    reply = f"{formatted_response}"
            else:
                reply = "Could not generate proper SQL query"
        elif final_message.strip().lower().startswith("custom") and employee[0].get("level", "0") >= 5:
                final_message = re.sub(r'(?i)custom', '', final_message)
                sql_message = (
                    f"you are a SQL expert for writing queries in sqlite3 python, always write query case insensitive, "
                    f"you have to only give the exact query for MySQL so that the result of yours,"
                    f"I can directly fire in DB. You have the Employee and Attendance table information: "
                    f"Employee with columns (id, name, email, phone, role (engineer, HR, tester, manager, and founder), "
                    f"level (integer 1,2,3), clientCompany(string), location(string), employeeType(can have values A, B, C), reportsTo (id of manager who is also an employee), skills (string)); "
                    f"Attendance with columns (id, empId, date(yyyy-mm-dd), status(PRESENT/ABSENT)), requestId(integer value), Now tell me the query for - {final_message}")
                response_from_service_b = call_docuseek_api(sql_message, employee_type)
                query = re.search(r"```sql\s*(.*?)\s*```", response_from_service_b or "", re.DOTALL)
                if query:
                    query = query.group(1).strip()
                    query = " ".join(query.split())
                    if "notsure" not in query.lower():
                        result = execute_query(query)
                        if result:
                            formatted_response = result
                        else:
                            formatted_response = "No employee data found"
                        reply = f"{formatted_response}"
                else:
                    reply = "Could not generate proper SQL query"
        else:
            response_from_service_b = call_docuseek_api(final_message, employee_type)
            print("Response from service:", response_from_service_b)
            reply = response_from_service_b or "Oops, currently I don't have that information."

    # Prepare response - audio if received audio, otherwise text
    twiml_response = MessagingResponse()

    if is_audio_received:
        audio_path = text_to_speech(reply)
        print(f"Audio path: {audio_path}")
        if audio_path:
            audio_url = upload_audio_file(audio_path)
            if audio_url:
                twiml_response.message().media(audio_url)
                # Clean up temporary files
                for file in [audio_path, "temp_audio.ogg", "temp_audio.wav"]:
                    print(f"Audio file: {file}")
                    if os.path.exists(file):
                        os.remove(file)
                return Response(str(twiml_response), content_type="audio/mpeg")

    # Fallback to text response
    twiml_response.message(body=reply)
    return Response(str(twiml_response), content_type="text/xml")


@app.route("/execute_query", methods=["POST"])
def execute_query_api():
    """API endpoint for direct query execution"""
    if request.headers.get("x-api-key") != "abcdef":
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    query = data.get("query")
    if not query:
        return jsonify({"error": "Query is required"}), 400

    result = execute_query(query)
    if result is not None:
        return jsonify(result), 200
    else:
        return jsonify({"error": "Query execution failed"}), 500


if __name__ == "__main__":
    app.run(debug=True)
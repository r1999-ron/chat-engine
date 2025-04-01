# WhatsApp Employee Management System

## Overview
This is a WhatsApp-based employee management system that allows employees and managers to interact with HR services through WhatsApp messages. The system supports both text and voice messages, and provides features like attendance tracking, leave/WFH requests, employee directory, and custom HR queries.

## Key Features
### Attendance Management:
- Mark yourself as **PRESENT/ABSENT/WFH**
- Check your attendance history with a calendar view

### Leave/WFH Requests:
- Submit new requests via natural language
- Approve/reject requests (for managers)
- Check request status and history

### Employee Directory:
- Find contact details of colleagues
- Custom employee searches (for HR/managers)

### Role-Based Access:
- Different features available based on employee level
- Manager approval workflows

## 🔔 Key Notification Feature: Manager Alerts

**Automated Manager Notifications**  
When an employee submits a leave/WFH request, the system automatically:
1. Sends an immediate WhatsApp notification to their manager
2. Includes all request details:
   - Employee name
   - Request type (Leave/WFH)
   - Date range
   - Request ID
3. Provides quick-action instructions:
   - "Reply 'accept request [ID]' to approve"
   - "Reply 'reject request [ID]' to deny"


## Technical Architecture
- **Flask** web application serving as the backend
- **Twilio WhatsApp API** integration
- **Google Speech Recognition** for voice-to-text
- **gTTS (Google Text-to-Speech)** for audio responses
- **External API** integration for database operations
- **SQL Query** support for custom HR queries

## Setup Instructions
### Prerequisites
- Python 3.7+
- Twilio account with WhatsApp sandbox
- Google Cloud credentials for speech recognition (optional)

### Installation
#### Clone the repository:
```bash
git clone https://github.com/yourusername/whatsapp-hr-bot.git
cd whatsapp-hr-bot
```
#### Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
#### Install dependencies:
```bash
pip install -r requirements.txt
```
#### Create a `.env` file with your credentials:
```
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
API_URL=https://your-api-endpoint.com
```
#### Run the application:
```bash
python app.py
```
#### Set up ngrok for local testing:
```bash
ngrok http 5000
```
Use the ngrok URL in your Twilio webhook configuration.

## Usage Examples
### Basic Commands
#### Attendance:
```text
PRESENT  # Mark today as present
WFH 2023-12-15  # Mark specific date as work from home
my attendance from 2023-12-01 to 2023-12-31  # View attendance calendar
```

#### Leave/WFH Requests:
```text
WFH from 2023-12-20 to 2023-12-22
LEAVE from 2024-01-05 to 2024-01-08
```

#### Request Management:
```text
my request history  # View all your requests
request on me  # View requests needing your approval
accept request 123  # Approve a specific request
```

#### Employee Directory:
```text
find contact of John Doe
custom employee who are engineers in Bangalore  # (HR/managers only)
```

## API Documentation
The system provides these API endpoints:
- **`POST /webhook`** - Main Twilio webhook endpoint
- **`POST /execute_query`** - For direct SQL query execution (authenticated)

## Security
- All requests require a valid API key (`x-api-key: abcdef`)
- Employee authorization is verified by phone number
- Role-based access control for sensitive operations

## Limitations
- Currently supports **English language only**
- Currently text-only interface (no voice support)
- Voice recognition accuracy may vary
- Requires a **stable internet connection**

## Future Enhancements
- Multi-language support
- Enhanced natural language processing
- Integration with more HR systems
- Analytics dashboard

## License
This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

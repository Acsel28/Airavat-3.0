import random
import smtplib
from email.mime.text import MIMEText

# Store OTPs temporarily (for demo)
otp_store = {}

EMAIL = "parth.palekar23@spit.ac.in"
APP_PASSWORD = "sizc niln moqf xkem"


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(to_email, otp):
    msg = MIMEText(f"Your OTP for KYC verification is: {otp}")
    msg["Subject"] = "KYC Verification OTP"
    msg["From"] = EMAIL
    msg["To"] = to_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL, APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Email Error:", e)
        return False


def store_otp(email, otp):
    otp_store[email] = otp


def verify_otp(email, otp):
    return otp_store.get(email) == otp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(receiver_email,body):
 # Email credentials
 sender_email = "kammarirachana2@gmail.com"
 password = "kgrs takd besc kcwp"

 # Create the email
 message = MIMEMultipart()
 message["From"] = sender_email
 message["To"] = receiver_email
 message["Subject"] = "OTP for Password Reset"
 message.attach(MIMEText(body, "plain"))

 # Connect to SMTP server
 try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()  # Secure connection
    server.login(sender_email, password)
    
    # Send email
    server.send_message(message)
    print("Email sent successfully!")

 except Exception as e:
    print("Error:", e)

 finally:
    server.quit()
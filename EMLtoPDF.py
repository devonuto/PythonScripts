import os
import email
import pdfkit

# Set the directory containing the .eml files
directory = r"%USERPROFILE%\Downloads"

# Function to convert .eml to .pdf
def eml_to_pdf(eml_file_path):
    with open(eml_file_path, 'r', encoding='utf-8') as file:
        # Read the .eml file
        msg = email.message_from_file(file)
        
        # Extract the subject and body
        subject = msg['subject'] if msg['subject'] else 'No Subject'
        body = ""
        
        # Get the email body
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_payload(decode=True).decode(part.get_content_charset())
                    break
        else:
            body = msg.get_payload(decode=True).decode(msg.get_content_charset())
        
        # Create a simple HTML structure
        html_content = "<h1>{}</h1><p>{}</p>".format(subject, body.replace('\n', '<br>'))

        # Define the output PDF file name
        pdf_file_path = os.path.splitext(eml_file_path)[0] + '.pdf'
        
        # Convert HTML to PDF
        pdfkit.from_string(html_content, pdf_file_path)
        print(f"Converted: {eml_file_path} to {pdf_file_path}")

# Iterate over all files in the directory
for filename in os.listdir(directory):
    if filename.endswith('.eml'):
        eml_file_path = os.path.join(directory, filename)
        eml_to_pdf(eml_file_path)

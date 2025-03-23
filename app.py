import pdfplumber
import re
import time
import csv
from flask import Flask, request, redirect, url_for, send_file, render_template_string
from werkzeug.utils import secure_filename
import os
from datetime import datetime

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pdf'}

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def normalize_text(text):
    """Normalize whitespace in the text by removing extra spaces and newlines."""
    return re.sub(r'\s+', ' ', text).strip()

def parse_foreclosure_records(pdf_path):
    # Step 1: Parse the PDF file into an array of foreclosure records
    foreclosure_records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            print(f"🔍 Extracting text from page {page_num + 1}...")
            if text:
                # Normalize the text
                text = normalize_text(text)
                # Split the text into individual foreclosure notices based on "(Mortgage Foreclosure)"
                records = re.split(r"\([Mm]ortgage Foreclosure\)", text)
                print(f"📄 Found {len(records) - 1} foreclosure records on page {page_num + 1}.")
                # Add "(Mortgage Foreclosure)" back to maintain formatting
                for record in records[1:]:  # Skip the first split (before the first foreclosure notice)
                    foreclosure_records.append("(Mortgage Foreclosure)" + record.strip())
    print(f"📊 Total foreclosure records found: {len(foreclosure_records)}")
    return foreclosure_records

def extract_names(pdf_path):
    # Extract names separately
    names = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            print(f"🔍 Extracting names from page {page_num + 1}...")
            if text:
                # Normalize the text
                text = normalize_text(text)
                name_pattern = r'([\w\s\.]+)\(Mortgage Foreclosure\)'
                name_matches = re.findall(name_pattern, text)
                # Remove newline characters from names
                name_matches = [name.replace('\n', ' ').strip() for name in name_matches]
                names.extend(name_matches)
    print(f"📊 Total names found: {len(names)}")
    print(names)
    return names

def extract_details(record):
    # Step 2: Extract details from one foreclosure record
    print(f"🔍 Extracting details from record: {record[:100]}...")  # Print the first 100 characters for context

    address_pattern = r'\b\d{1,5}\s[\w\s]+(?:\s[A-Za-z]+)*,\s*(?:#\d{1,5},\s*)?[A-Za-z\s]+,\s[A-Za-z]{2}\s\d{5}(?:-\d{4})?\b'
    address_match = re.search(address_pattern, record)
    address = address_match.group(0).strip() if address_match else "Not available"
    print(f"📍 Address: {address}")

    loan_amount_pattern_1 = r'Amount claimed due.*?\$([\d,\.]+)'  # Handles line breaks
    loan_amount_pattern_2 = r'There is claimed to be due at the date \$([\d,\.]+)'  # Handles specific pattern
    loan_amount_pattern_3 = r'\$(\d{1,3}(?:,\d{3})*\.\d{2})'  # Handles currency format
    loan_amount_pattern = fr'{loan_amount_pattern_1}|{loan_amount_pattern_2}|{loan_amount_pattern_3}'
    loan_match = re.search(loan_amount_pattern_3, record)
    loan_amount = loan_match.group(1).strip() if loan_match else "Not available"
    #if loan_match:
    #    loan_amount = loan_match.group(0).strip()
    #else:
    #   loan_amount = "Not available"
        #print(f"⚠️ Loan amount not found in record: {record[:100]}...")
    #print(f"💰 Loan Amount: {loan_amount}")

    auction_date_pattern = r'starting promptly at\s*(\d{1,2}:\d{2} (?:AM|PM), on [A-Za-z]+\s\d{1,2},\s\d{4})'
    auction_date_match = re.search(auction_date_pattern, record)
    auction_date = auction_date_match.group(0).strip() if auction_date_match else "Not available"
    print(f"🔔 Auction Date: {auction_date}")

    return {
        "Address": address,
        "Loan Amount": loan_amount,
        "Auction Date": auction_date
    }

def process_pdf(pdf_path):
    # Step 3: Process the PDF and print the summary
    start_time = time.time()  # Start timer
    print(f"📂 Processing PDF: {pdf_path}")
    foreclosure_records = parse_foreclosure_records(pdf_path)
    names = extract_names(pdf_path)
    
    if len(names) != len(foreclosure_records):
        print("⚠️ Warning: The number of names does not match the number of foreclosure records.")
        return []

    detailed_results = []
    full_records_count = 0
    today_date = datetime.today().strftime('%Y-%m-%d')

    for record_num, (record, name) in enumerate(zip(foreclosure_records, names), start=1):
        print(f"🔹 Processing record {record_num}/{len(foreclosure_records)}")
        details = extract_details(record)
        details["Name"] = name  # Add the name to the details
        details["Today's Date"] = today_date  # Add today's date to the details
        detailed_results.append(details)
        if all(details.values()):
            full_records_count += 1

    # Print summary
    total_records = len(detailed_results)
    partial_records_count = total_records - full_records_count
    full_records_percentage = (full_records_count / total_records) * 100 if total_records > 0 else 0

    print(f"✅ Total records processed: {total_records}")
    print(f"✅ Full records (all 4 attributes): {full_records_count}")
    print(f"✅ Partial records: {partial_records_count}")
    print(f"✅ Percentage of full records: {full_records_percentage:.2f}%")

    end_time = time.time()  # End timer
    elapsed_time = end_time - start_time
    print(f"⏱️ Total time taken: {elapsed_time:.2f} seconds")

    return detailed_results

@app.route('/')
def upload_file():
    return render_template_string('''
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Upload PDF for Foreclosure Records Extraction</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: #f4f4f9;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }
            .container {
                text-align: center;
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0px 0px 10px rgba(0, 0, 0, 0.1);
            }
            h1 {
                color: #333;
            }
            form {
                margin-top: 20px;
            }
            input[type="file"] {
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-bottom: 10px;
            }
            input[type="submit"] {
                background-color: #007bff;
                color: #fff;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            input[type="submit"]:hover {
                background-color: #0056b3;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Upload PDF for Foreclosure Records Extraction</h1>
            <form method="POST" enctype="multipart/form-data">
                <input type="file" name="file" accept=".pdf" required>
                <br>
                <input type="submit" value="Upload">
            </form>
        </div>
    </body>
    </html>
    ''')

@app.route('/', methods=['POST'])
def upload_file_post():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        detailed_results = process_pdf(file_path)
        if not detailed_results:
            return "Error processing the PDF file."

        # Write results to a CSV file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = os.path.join(app.config['UPLOAD_FOLDER'], f'foreclosure_records_{timestamp}.csv')
        with open(csv_file, mode='w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=["Name", "Address", "Loan Amount", "Auction Date", "Today's Date"])
            writer.writeheader()
            writer.writerows(detailed_results)
        return redirect(url_for('download_file', filename=f'foreclosure_records_{timestamp}.csv'))
    return redirect(request.url)

@app.route('/uploads/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    #app.run(port=5000, debug=True)
    app.run()

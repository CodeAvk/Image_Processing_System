import os
import csv
import uuid
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image
import requests
from io import BytesIO, StringIO
from concurrent.futures import ThreadPoolExecutor
from pymongo import MongoClient
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'processed_images'
OUTPUT_CSV_FOLDER = 'output_csv'
ALLOWED_EXTENSIONS = {'csv'}
MONGODB_URI = 'mongodb://localhost:27017/'
DB_NAME = 'image_processor'

# MongoDB connection
client = MongoClient(MONGODB_URI)
db = client[DB_NAME]
requests_collection = db['processing_requests']
products_collection = db['products']

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_CSV_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(image_url):
    try:
        # Download image
        response = requests.get(image_url)
        img = Image.open(BytesIO(response.content))
        
        # Process image (compress by 50%)
        output_filename = f"{uuid.uuid4()}.jpg"
        output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Save with 50% quality
        img.save(output_path, 'JPEG', quality=50)
        
        # In a real application, you would upload this to a cloud storage
        return f"/processed_images/{output_filename}"
    except Exception as e:
        logger.error(f"Error processing image {image_url}: {str(e)}")
        return None

def generate_output_csv(request_id):
    # Get all products for this request
    products = products_collection.find({'request_id': request_id}).sort('serial_number', 1)
    
    # Create output CSV
    output_filename = f"output_{request_id}.csv"
    output_path = os.path.join(OUTPUT_CSV_FOLDER, output_filename)
    
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        # Write header
        writer.writerow(['S. No.', 'Product Name', 'Input Image URLs', 'Output Image URLs'])
        
        # Write data
        for product in products:
            writer.writerow([
                product['serial_number'],
                product['product_name'],
                ','.join(product['input_urls']),
                ','.join(product['output_urls'])
            ])
    
    return output_path

def process_csv_row(row, request_id):
    try:
        serial_number = row['S. No.']
        product_name = row['Product Name']
        input_urls = [url.strip() for url in row['Input Image URLs'].split(',')]
        
        # Process each image
        output_urls = []
        for url in input_urls:
            output_url = process_image(url)
            if output_url:
                output_urls.append(output_url)
        
        # Store in MongoDB
        product_doc = {
            'request_id': request_id,
            'serial_number': int(serial_number),
            'product_name': product_name,
            'input_urls': input_urls,
            'output_urls': output_urls,
            'created_at': datetime.utcnow()
        }
        products_collection.insert_one(product_doc)
        
        return True
    except Exception as e:
        logger.error(f"Error processing row: {str(e)}")
        return False

def process_csv_file(file_path, request_id):
    try:
        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                process_csv_row(row, request_id)
        
        # Generate output CSV
        output_csv_path = generate_output_csv(request_id)
        
        # Update status to completed
        requests_collection.update_one(
            {'request_id': request_id},
            {
                '$set': {
                    'status': 'completed',
                    'completed_at': datetime.utcnow(),
                    'output_csv_path': output_csv_path
                }
            }
        )
        
        # Trigger webhook (if configured)
        trigger_webhook(request_id)
        
    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        requests_collection.update_one(
            {'request_id': request_id},
            {
                '$set': {
                    'status': 'failed',
                    'error': str(e),
                    'completed_at': datetime.utcnow()
                }
            }
        )
    finally:
        # Clean up the uploaded file
        if os.path.exists(file_path):
            os.remove(file_path)

def trigger_webhook(request_id):
    try:
        # Fetch request details from the database
        request_doc = requests_collection.find_one({'request_id': request_id})
        if not request_doc or 'webhook_url' not in request_doc:
            return  # No webhook registered

        webhook_url = request_doc['webhook_url']
        status = request_doc['status']
        output_csv_url = f"/download/{request_id}" if status == 'completed' else None

        # Prepare payload
        payload = {
            'request_id': request_id,
            'status': status,
            'output_csv_url': output_csv_url
        }

        # Send webhook notification
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        logger.info(f"Webhook triggered successfully: {response.status_code}")
    except Exception as e:
        logger.error(f"Error triggering webhook: {str(e)}")



# Update /upload endpoint to accept webhook URL
@app.route('/upload', methods=['POST', 'OPTIONS'])
def upload_file():
    if request.method == 'OPTIONS':
        return '', 204

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    webhook_url = request.form.get('webhook_url')  
    
    if file and allowed_file(file.filename):
        try:
            request_id = str(uuid.uuid4())
            filename = secure_filename(file.filename)
            file_path = os.path.join(UPLOAD_FOLDER, f"{request_id}_{filename}")
            file.save(file_path)
            
            request_doc = {
                'request_id': request_id,
                'status': 'processing',
                'created_at': datetime.utcnow(),
                'filename': filename,
                'webhook_url': webhook_url
            }
            requests_collection.insert_one(request_doc)
            
            with ThreadPoolExecutor() as executor:
                executor.submit(process_csv_file, file_path, request_id)
            
            return jsonify({
                'request_id': request_id,
                'status': 'processing'
            })
            
        except Exception as e:
            logger.error(f"Error processing upload: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/status/<request_id>', methods=['GET'])
def get_status(request_id):
    try:
        # Get request status
        request_doc = requests_collection.find_one({'request_id': request_id})
        
        if not request_doc:
            return jsonify({'error': 'Request ID not found'}), 404
        
        status = request_doc['status']
        response_data = {
            'request_id': request_id,
            'status': status
        }
        
        # If processing is complete, add link to download CSV
        if status == 'completed' and 'output_csv_path' in request_doc:
            response_data['output_csv_url'] = f"/download/{request_id}"
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<request_id>', methods=['GET'])
def download_csv(request_id):
    try:
        request_doc = requests_collection.find_one({'request_id': request_id})
        if not request_doc or 'output_csv_path' not in request_doc:
            return jsonify({'error': 'Output CSV not found'}), 404
            
        return send_file(
            request_doc['output_csv_path'],
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'processed_results_{request_id}.csv'
        )
    except Exception as e:
        logger.error(f"Error downloading CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
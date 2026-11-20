from flask import Flask, request, jsonify, send_from_directory, send_file
import os
import threading
from werkzeug.utils import secure_filename
from script_official import process_and_save_results, update_progress
import shutil
import json
from flask_cors import CORS
import zipfile
from io import BytesIO
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = BACKEND_ROOT / 'upload'
RESULTS_FOLDER = BACKEND_ROOT / 'results'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['RESULTS_FOLDER'] = str(RESULTS_FOLDER)
UPLOAD_FOLDER.mkdir(exist_ok=True)
RESULTS_FOLDER.mkdir(exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Endpoint to clear working folders
@app.route('/clean_folders', methods=['POST'])
def clean_folders():
    try:
        if os.path.exists(app.config['UPLOAD_FOLDER']):
            shutil.rmtree(app.config['UPLOAD_FOLDER'])
        os.makedirs(app.config['UPLOAD_FOLDER'])

        if os.path.exists(app.config['RESULTS_FOLDER']):
            shutil.rmtree(app.config['RESULTS_FOLDER'])
        os.makedirs(app.config['RESULTS_FOLDER'])

        # Reset the progress file
        progress_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'progress.json')
        if os.path.exists(progress_file):
            os.remove(progress_file)
        with open(progress_file, 'w') as f:
            json.dump({'current': 0, 'total': 1, 'percentage': 0}, f)

        return jsonify({'message': 'Folders cleaned successfully'}), 200
    except Exception as e:
        print(f'Error while cleaning folders: {e}')
        return jsonify({'error': 'Error while cleaning folders'}), 500

# Endpoint to upload files for inference
@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files in the request'}), 400

    files = request.files.getlist('files')

    if not files:
        return jsonify({'error': 'No files selected'}), 400

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    # Start image processing on a background thread
    processing_thread = threading.Thread(target=process_images_thread)
    processing_thread.start()

    return jsonify({'message': 'Files uploaded successfully.'}), 200

def process_images_thread():
    folder_path = os.path.abspath(os.path.dirname(__file__))
    upload_path = os.path.join(folder_path, 'upload')
    progress_file = os.path.join(folder_path, 'progress.json')

    # Reset progress to zero
    update_progress(progress_file, 0, 1)

    process_and_save_results(folder_path, upload_path, progress_file)

# Endpoint to fetch processing progress
@app.route('/progress', methods=['GET'])
def get_progress():
    progress_file = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'progress.json')
    if os.path.exists(progress_file):
        with open(progress_file, 'r') as f:
            progress = json.load(f)
        return jsonify(progress)
    else:
        return jsonify({'current': 0, 'total': 1, 'percentage': 0})

# Endpoint to fetch processed images
@app.route('/get_results', methods=['GET'])
def get_results():
    results_list = []
    for root, dirs, files in os.walk(app.config['RESULTS_FOLDER']):
        for file in files:
            if file.endswith('_pipeline.jpg'):
                relative_path = os.path.relpath(os.path.join(root, file), app.config['RESULTS_FOLDER'])
                results_list.append(relative_path.replace('\\', '/'))
    return jsonify({'results': results_list})

# Endpoint to fetch aggregated summary results
@app.route('/get_summary_results', methods=['GET'])
def get_summary_results():
    summary_file = os.path.join(app.config['RESULTS_FOLDER'], 'summary_results.json')
    if os.path.exists(summary_file):
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        return jsonify(summary)
    else:
        return jsonify({'error': 'No summary available'}), 404

# Endpoint to download results as a ZIP
@app.route('/download_results', methods=['GET'])
def download_results():
    try:
        if not os.path.exists(app.config['RESULTS_FOLDER']):
            return jsonify({'error': 'No results available for download.'}), 404

        # Create the ZIP file in memory
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(app.config['RESULTS_FOLDER']):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, app.config['RESULTS_FOLDER'])
                    zipf.write(file_path, arcname=relative_path)
        memory_file.seek(0)

        # Determine Flask version to pick the right parameter name
        import flask
        flask_version = flask.__version__.split('.')
        major_version = int(flask_version[0])

        if major_version >= 2:
            return send_file(
                memory_file,
                mimetype='application/zip',
                as_attachment=True,
                download_name='results.zip'  # Flask >= 2.0
            )
        else:
            return send_file(
                memory_file,
                mimetype='application/zip',
                as_attachment=True,
                attachment_filename='results.zip'  # Flask < 2.0
            )
    except Exception as e:
        print(f'Error while downloading results: {e}')
        return jsonify({'error': str(e)}), 500

# Endpoint to serve generated result files
@app.route('/results/<path:filepath>', methods=['GET'])
def serve_results(filepath):
    return send_from_directory(app.config['RESULTS_FOLDER'], filepath)

if __name__ == '__main__':
    app.run(port=3001, debug=False)

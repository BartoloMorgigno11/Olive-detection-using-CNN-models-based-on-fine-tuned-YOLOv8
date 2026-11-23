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
from PIL import Image, UnidentifiedImageError

BACKEND_ROOT = Path(__file__).resolve().parent
app = Flask(__name__)
# The development UI is local; do not expose a permissive cross-origin API.
CORS(app, resources={r"/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}})

UPLOAD_FOLDER = BACKEND_ROOT / 'upload'
RESULTS_FOLDER = BACKEND_ROOT / 'results'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config['UPLOAD_FOLDER'] = str(UPLOAD_FOLDER)
app.config['RESULTS_FOLDER'] = str(RESULTS_FOLDER)
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20 MiB per request
JOB_LOCK = threading.Lock()
JOB_RUNNING = False

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_runtime_folders():
    """Create runtime directories at use time, not while importing the app."""
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    Path(app.config['RESULTS_FOLDER']).mkdir(parents=True, exist_ok=True)

# Endpoint to clear working folders
@app.route('/clean_folders', methods=['POST'])
def clean_folders():
    if not JOB_LOCK.acquire(blocking=False):
        return jsonify({'error': 'An analysis is running; results cannot be cleaned.'}), 409
    try:
        clean_runtime_folders()
        return jsonify({'message': 'Folders cleaned successfully'}), 200
    except Exception as e:
        print(f'Error while cleaning folders: {e}')
        return jsonify({'error': 'Error while cleaning folders'}), 500
    finally:
        JOB_LOCK.release()

def has_runtime_artifacts():
    ensure_runtime_folders()
    return any(Path(app.config['UPLOAD_FOLDER']).iterdir()) or any(Path(app.config['RESULTS_FOLDER']).iterdir())

def validate_image_file(file, filename):
    if not filename or not allowed_file(filename):
        return 'Only PNG and JPEG image files are accepted.'
    try:
        with Image.open(file.stream) as image:
            image.verify()
        file.stream.seek(0)
    except (UnidentifiedImageError, OSError):
        return 'One or more uploaded files are not decodable images.'
    return None

# Endpoint to upload files for inference
@app.route('/upload', methods=['POST'])
def upload_files():
    global JOB_RUNNING
    if 'files' not in request.files:
        return jsonify({'error': 'No files in the request'}), 400

    files = request.files.getlist('files')

    if not files:
        return jsonify({'error': 'No files selected'}), 400

    valid_files = []
    for file in files:
        filename = secure_filename(file.filename or '')
        error = validate_image_file(file, filename)
        if error:
            return jsonify({'error': error}), 400
        valid_files.append((file, filename))

    if not JOB_LOCK.acquire(blocking=False):
        return jsonify({'error': 'An analysis is already running.'}), 409
    lock_transferred_to_worker = False
    try:
        ensure_runtime_folders()
        if has_runtime_artifacts():
            return jsonify({'error': 'Clear the completed local analysis before starting a new one.'}), 409
        for file, filename in valid_files:
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        JOB_RUNNING = True
        processing_thread = threading.Thread(target=process_images_thread, daemon=True)
        processing_thread.start()
        # The worker releases the lock when the analysis has reached a terminal state.
        lock_transferred_to_worker = True
        return jsonify({'message': 'Files uploaded successfully.'}), 200
    except Exception:
        JOB_RUNNING = False
        raise
    finally:
        # This covers validation of an already-completed run, failed file saving and
        # failures while creating/starting the worker thread.
        if not lock_transferred_to_worker:
            JOB_LOCK.release()

def process_images_thread():
    global JOB_RUNNING
    folder_path = os.path.abspath(os.path.dirname(__file__))
    upload_path = os.path.join(folder_path, 'upload')
    progress_file = os.path.join(folder_path, 'progress.json')

    try:
        # Reset progress to zero. This remains inside the protected section so
        # a filesystem error cannot strand the process-wide job lock.
        update_progress(progress_file, 0, 1)
        process_and_save_results(folder_path, upload_path, progress_file)
    except Exception as error:
        try:
            update_progress(progress_file, 0, 1, error=str(error))
        except Exception:
            app.logger.exception('Could not record olive-analysis failure status')
        app.logger.exception('Olive analysis failed')
    finally:
        JOB_RUNNING = False
        JOB_LOCK.release()

def clean_runtime_folders():
    shutil.rmtree(app.config['UPLOAD_FOLDER'], ignore_errors=True)
    shutil.rmtree(app.config['RESULTS_FOLDER'], ignore_errors=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)
    progress_file = BACKEND_ROOT / 'progress.json'
    update_progress(progress_file, 0, 1)

@app.errorhandler(413)
def request_too_large(_error):
    return jsonify({'error': 'Upload exceeds the 20 MiB request limit.'}), 413

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
    if JOB_RUNNING:
        return jsonify({'error': 'Analysis is still running.'}), 409
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
    if JOB_RUNNING:
        return jsonify({'error': 'Analysis is still running.'}), 409
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

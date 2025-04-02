from flask import Flask, render_template, request, jsonify, send_from_directory
import base64
import os
import time
import subprocess

VIDEO_OUTPUT_DIR = "animations"

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process_video', methods=['POST'])
def process_video():
    data = request.get_json()
    image_data = data['image']
    video_path = data['video']
    uuid_str = data['uuid']

    save_input_data(image_data, video_path, uuid_str)

    try:
        process_video_with_ffmpeg(uuid_str) # Replace with your video processing function.
        return jsonify({'status': 'processing'})
    except Exception as e:
        print(f"Error during video processing: {e}")
        with open(os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_status.txt"), "w") as f:
            f.write("error")
        return jsonify({'status': 'error'})

def save_input_data(image_data, video_path, uuid_str):
    image_filename = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_input.png")
    if "base64" in image_data:
        image_data = image_data.split(',')[1]
        with open(image_filename, "wb") as fh:
            fh.write(base64.b64decode(image_data))
    else:
        import requests
        img_data = requests.get(image_data).content
        with open(image_filename, 'wb') as f:
            f.write(img_data)
    # Save the video path chnages to the absolute path
    video_path = os.path.join("/LivePortrait/assets/examples/driving", video_path)
    with open(os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_video_path.txt"), "w") as f:
        f.write(video_path)

def process_video_with_ffmpeg(uuid_str):
    """
    Example using FFmpeg. Replace with your video processing logic.
    """
    input_image = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_input.png")
    input_video_path = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_video_path.txt")
    output_video = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_input_output.mp4")

    with open(input_video_path, 'r') as f:
        video_file_path = f.read().strip()

    # python  -s assets/examples/source/s9.jpg -d assets/examples/driving/d0.mp4

    # Example FFmpeg command (you'll need to adjust this)
    print(f"Processing video with FFmpeg: {input_image} -> {video_file_path}")
    command = [
        "python",
        "inference.py",  # Loop the image
        "-s", input_image,
        "-d", video_file_path
    ]

    subprocess.run(command, check=True) # Will raise an exception if the command fails

    with open(os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_status.txt"), "w") as f:
        f.write("ready")

@app.route('/video_status/<uuid_str>', methods=['GET'])
def video_status(uuid_str):
    status_file = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_status.txt")
    output_video_filename = f"{uuid_str}_input_output.mp4"
    output_video_path = os.path.join(VIDEO_OUTPUT_DIR, output_video_filename)

    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            status = f.read().strip()
        if status == "ready":
            return jsonify({'status': 'ready', 'video_path': f"/video_output/{output_video_filename}"}) # changed path to serve static.
        elif status == "error":
            return jsonify({'status': 'error'})
        else:
            return jsonify({'status': 'processing'})
    else:
        return jsonify({'status': 'processing'})

@app.route('/video_output/<uuid_str>', methods=['GET'])
def serve_video(uuid_str):
    print(f"Serving video for UUID: {uuid_str}")
    return send_from_directory(VIDEO_OUTPUT_DIR, uuid_str, mimetype='video/mp4')

if __name__ == '__main__':
    app.run(debug=True)

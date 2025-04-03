from flask import Flask, render_template, request, jsonify, send_from_directory
import base64
import os
import subprocess
import tyro
from src.config.argument_config import ArgumentConfig
from src.config.inference_config import InferenceConfig
from src.config.crop_config import CropConfig
from src.live_portrait_pipeline import LivePortraitPipeline

VIDEO_OUTPUT_DIR = "animations"

app = Flask(__name__)

# Initialize LivePortraitPipeline outside of request handling to load assets once
def partial_fields(target_class, kwargs):
    return target_class(**{k: v for k, v in kwargs.items() if hasattr(target_class, k)})

def fast_check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except:
        return False

def fast_check_args(args: ArgumentConfig):
    if not os.path.exists(args.source):
        raise FileNotFoundError(f"source info not found: {args.source}")
    if not os.path.exists(args.driving):
        raise FileNotFoundError(f"driving info not found: {args.driving}")

# Load the model once when the app starts
try:
    tyro.extras.set_accent_color("bright_cyan")
    args = tyro.cli(ArgumentConfig, args=[])  # Empty list to avoid tyro parsing command-line args

    ffmpeg_dir = os.path.join(os.getcwd(), "ffmpeg")
    if os.path.exists(ffmpeg_dir):
        os.environ["PATH"] += (os.pathsep + ffmpeg_dir)

    if not fast_check_ffmpeg():
        raise ImportError(
            "FFmpeg is not installed. Please install FFmpeg (including ffmpeg and ffprobe) before running this script. https://ffmpeg.org/download.html"
        )

    # specify configs for inference
    inference_cfg = partial_fields(InferenceConfig, args.__dict__)
    crop_cfg = partial_fields(CropConfig, args.__dict__)

    live_portrait_pipeline = LivePortraitPipeline(
        inference_cfg=inference_cfg,
        crop_cfg=crop_cfg
    )
except Exception as e:
    print(f"Error initializing LivePortraitPipeline: {e}")
    live_portrait_pipeline = None  # Set to None if initialization fails

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process_video', methods=['POST'])
def process_video():
    if live_portrait_pipeline is None:
      return jsonify({'status': 'error','message':'Live Portrait Pipeline initialization failed'})

    data = request.get_json()
    image_data = data['image']
    video_path = data['video']
    uuid_str = data['uuid']

    save_input_data(image_data, video_path, uuid_str)

    # try:
    process_video_with_live_portrait(uuid_str, live_portrait_pipeline)
    return jsonify({'status': 'processing'})
    # except Exception as e:
    #     print(f"Error during video processing: {e}")
    #     with open(os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_status.txt"), "w") as f:
    #         f.write("error")
    #     return jsonify({'status': 'error'})

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

def process_video_with_live_portrait(uuid_str, live_portrait_pipeline):
    """
    Process video using the LivePortraitPipeline.
    """
    input_image = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_input.png")
    input_video_path_file = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_video_path.txt")
    output_video = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_input_output.mp4")

    with open(input_video_path_file, 'r') as f:
        video_file_path = f.read().strip()

    # Create ArgumentConfig from the loaded data
    args = ArgumentConfig(source=input_image, driving=video_file_path)

    try:
        live_portrait_pipeline.execute(args)
        with open(os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_status.txt"), "w") as f:
            f.write("ready")
    except Exception as e:
        print(f"Error in LivePortraitPipeline execution: {e}")
        with open(os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_status.txt"), "w") as f:
            f.write("error")
        raise

@app.route('/video_status/<uuid_str>', methods=['GET'])
def video_status(uuid_str):
    status_file = os.path.join(VIDEO_OUTPUT_DIR, f"{uuid_str}_status.txt")
    output_video_filename = f"{uuid_str}_input_output.mp4"
    output_video_path = os.path.join(VIDEO_OUTPUT_DIR, output_video_filename)

    if os.path.exists(status_file):
        with open(status_file, "r") as f:
            status = f.read().strip()
        if status == "ready":
            return jsonify({'status': 'ready', 'video_path': f"/video_output/{output_video_filename}"})
        elif status == "error":
            return jsonify({'status': 'error'})
        else:
            return jsonify({'status': 'processing'})
    else:
        return jsonify({'status': 'processing'})

@app.route('/video_output/<uuid_str>', methods=['GET'])
def serve_video(uuid_str):
    print(f"Serving video for UUID: {uuid_str}")
    return send_from_directory(VIDEO_OUTPUT_DIR, f"{uuid_str}", mimetype='video/mp4')

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=9898, ssl_context='adhoc')

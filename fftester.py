import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import subprocess
import tempfile
import re
import json
from PIL import Image, ImageTk
import cv2
import time
import shutil
from collections import defaultdict

class FFtester:
    def __init__(self, root, ffmpeg_path):
        self.ffmpeg_path = ffmpeg_path

        self.root = root
        self.root.title("FFtester")
        self.root.geometry("1200x900")
        
        # Video variables
        self.input_video_path = None
        self.encoded_video_path = None
        self.cap_original = None
        self.cap_encoded = None
        self.is_playing = False
        self.playing_thread = None
        self.temp_dir = tempfile.mkdtemp()
        
        # FFmpeg info
        self.video_codecs = []
        self.audio_codecs = []
        self.containers = []
        self.codec_presets = defaultdict(list)
        self.codec_crf_ranges = defaultdict(lambda: {"min": 0, "max": 51, "default": 23})
        self.codec_pixel_formats = defaultdict(list)
        
        # Media info
        self.video_info = {}
        self.audio_info = {}
        
        # Status variable for all tabs
        self.status_var = tk.StringVar(value="Ready")
        
        # **NEW: Initialize fullscreen and image attributes**
        self.is_fullscreen = False
        self.original_img = None 
        self.encoded_img = None
        
        # Load FFmpeg capabilities
        self.load_ffmpeg_info()
        
        # Create UI
        self.create_ui()
        
        # Bind closing event to cleanup function
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup)
    
    def load_ffmpeg_info(self):
        self.status_var.set("Loading FFmpeg information...")
        
        # Get video codecs
        try:
            result = subprocess.run([self.ffmpeg_path, '-encoders'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            lines = result.stdout.split('\n')
            
            # Process video encoders
            video_codecs = []
            audio_codecs = []
            for line in lines:
                if re.match(r'^\s+[.VASEFL]+\s+\w+\s+.*$', line):
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        codec_type, codec_name = parts[0], parts[1]
                        if 'V' in codec_type:  # Video codec
                            video_codecs.append(codec_name)
                        elif 'A' in codec_type:  # Audio codec
                            audio_codecs.append(codec_name)
            
            self.video_codecs = sorted(video_codecs)
            self.audio_codecs = sorted(audio_codecs)
            
            # Get common presets for popular codecs
            popular_video_codecs = ["libx264", "libx265", "h264_nvenc", "hevc_nvenc", "libvpx-vp9", "libaom-av1"]
            for codec in popular_video_codecs:
                # Set default presets for libx264 and similar codecs
                if codec in ["libx264", "libx265", "h264_nvenc", "hevc_nvenc"]:
                    self.codec_presets[codec] = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
                elif codec == "libvpx-vp9":
                    self.codec_presets[codec] = ["0", "1", "2", "3", "4", "5", "6"]
                elif codec == "libaom-av1":
                    self.codec_presets[codec] = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
                
                # CRF ranges
                if codec in ["libx264", "h264_nvenc"]:
                    self.codec_crf_ranges[codec] = {"min": 0, "max": 51, "default": 23}
                elif codec in ["libx265", "hevc_nvenc"]:
                    self.codec_crf_ranges[codec] = {"min": 0, "max": 51, "default": 28}
                elif codec == "libvpx-vp9":
                    self.codec_crf_ranges[codec] = {"min": 0, "max": 63, "default": 31}
                elif codec == "libaom-av1":
                    self.codec_crf_ranges[codec] = {"min": 0, "max": 63, "default": 30}
            
            # Get pixel formats
            result = subprocess.run([self.ffmpeg_path, '-pix_fmts'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            lines = result.stdout.split('\n')
            pixel_formats = []
            for line in lines:
                if re.match(r'^[IO.]{3} \w+.*$', line):
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        pixel_formats.append(parts[1])
            
            # Common pixel formats for each codec
            self.pixel_formats = sorted(pixel_formats)
            for codec in popular_video_codecs:
                if codec in ["libx264", "h264_nvenc"]:
                    self.codec_pixel_formats[codec] = ["yuv420p", "yuv422p", "yuv444p", "yuvj420p", "yuvj422p", "yuvj444p"]
                elif codec in ["libx265", "hevc_nvenc"]:
                    self.codec_pixel_formats[codec] = ["yuv420p", "yuv422p", "yuv444p", "gbrp", "gbrap"]
                elif codec in ["libvpx-vp9", "libaom-av1"]:
                    self.codec_pixel_formats[codec] = ["yuv420p", "yuv422p", "yuv444p", "yuva420p"]
            
            # Get containers
            result = subprocess.run([self.ffmpeg_path, '-formats'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            lines = result.stdout.split('\n')
            containers = []
            for line in lines:
                if re.match(r'^\s*[DE ]{2}\s+\w+\s+.*$', line):
                    parts = line.strip().split()
                    if len(parts) >= 3 and 'E' in parts[0]:  # Encodable format
                        containers.append(parts[1])
            
            # Filter common container formats
            common_containers = ["mp4", "mkv", "webm", "mov", "avi", "flv", "ts", "mxf", "mpg"]
            self.containers = [c for c in common_containers if c in containers]
            
            self.status_var.set("Ready")
            
        except Exception as e:
            print(f"Error loading FFmpeg info: {e}")
            # Set some default values if FFmpeg query fails
            self.video_codecs = ["libx264", "libx265", "h264_nvenc", "hevc_nvenc", "libvpx-vp9", "libaom-av1"]
            self.audio_codecs = ["aac", "libmp3lame", "libopus", "flac", "pcm_s16le"]
            self.containers = ["mp4", "mkv", "webm", "mov", "avi"]
            
            self.codec_presets["libx264"] = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"]
            self.codec_crf_ranges["libx264"] = {"min": 0, "max": 51, "default": 23}
            self.codec_pixel_formats["libx264"] = ["yuv420p", "yuv422p", "yuv444p"]
            
            self.status_var.set("Error loading FFmpeg information")
    
    def create_ui(self):
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Main tab
        main_tab = ttk.Frame(self.notebook)
        self.notebook.add(main_tab, text="Main")
        
        # Media Info tab
        media_info_tab = ttk.Frame(self.notebook)
        self.notebook.add(media_info_tab, text="Media Info")
        
        # Advanced settings tab
        advanced_tab = ttk.Frame(self.notebook)
        self.notebook.add(advanced_tab, text="Advanced Settings")
        
        # Command view tab
        command_tab = ttk.Frame(self.notebook)
        self.notebook.add(command_tab, text="FFmpeg Command")
        
        # Create UI for main tab
        self.create_main_tab(main_tab)
        
        # Create UI for media info tab
        self.create_media_info_tab(media_info_tab)
        
        # Create UI for advanced tab
        self.create_advanced_tab(advanced_tab)
        
        # Create UI for command tab
        self.create_command_tab(command_tab)
        
        # Status bar (shared across all tabs)
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=5)
    
    def create_main_tab(self, parent):
        # Main frame
        main_frame = ttk.Frame(parent, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top control panel
        control_frame = ttk.LabelFrame(main_frame, text="Video Controls", padding=10)
        control_frame.pack(fill=tk.X, pady=5)
        
        # File selection
        file_frame = ttk.Frame(control_frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        self.file_path_var = tk.StringVar()
        ttk.Label(file_frame, text="Video File:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(file_frame, textvariable=self.file_path_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Browse...", command=self.select_video).pack(side=tk.LEFT, padx=5)
        
        # Basic encoding settings frame
        settings_frame = ttk.LabelFrame(main_frame, text="Basic Encoding Settings", padding=10)
        settings_frame.pack(fill=tk.X, pady=5)
        
        # Container format
        container_frame = ttk.Frame(settings_frame)
        container_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(container_frame, text="Container:").pack(side=tk.LEFT, padx=5)
        self.container_var = tk.StringVar(value="mp4")
        container_dropdown = ttk.Combobox(container_frame, textvariable=self.container_var, 
                                         values=self.containers, width=10)
        container_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Video codec selection
        codec_frame = ttk.Frame(settings_frame)
        codec_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(codec_frame, text="Video Codec:").pack(side=tk.LEFT, padx=5)
        self.video_codec_var = tk.StringVar(value="libx264")
        self.video_codec_dropdown = ttk.Combobox(codec_frame, textvariable=self.video_codec_var, 
                                               values=self.video_codecs, width=15)
        self.video_codec_dropdown.pack(side=tk.LEFT, padx=5)
        self.video_codec_dropdown.bind("<<ComboboxSelected>>", self.update_codec_dependent_options)
        
        # Audio codec selection
        ttk.Label(codec_frame, text="Audio Codec:").pack(side=tk.LEFT, padx=5)
        self.audio_codec_var = tk.StringVar(value="aac")
        audio_codec_dropdown = ttk.Combobox(codec_frame, textvariable=self.audio_codec_var, 
                                           values=self.audio_codecs, width=15)
        audio_codec_dropdown.pack(side=tk.LEFT, padx=5)
        
        # CRF/Quality
        quality_frame = ttk.Frame(settings_frame)
        quality_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(quality_frame, text="CRF/Quality:").pack(side=tk.LEFT, padx=5)
        self.crf_var = tk.StringVar(value="23")
        self.crf_scale = ttk.Scale(quality_frame, from_=0, to=51, orient=tk.HORIZONTAL, 
                                  variable=self.crf_var, length=200)
        self.crf_scale.pack(side=tk.LEFT, padx=5)
        self.crf_entry = ttk.Entry(quality_frame, textvariable=self.crf_var, width=4)
        self.crf_entry.pack(side=tk.LEFT, padx=5)
        
        # Preset
        ttk.Label(quality_frame, text="Preset:").pack(side=tk.LEFT, padx=5)
        self.preset_var = tk.StringVar(value="medium")
        self.preset_dropdown = ttk.Combobox(quality_frame, textvariable=self.preset_var, 
                                           values=self.codec_presets["libx264"], width=10)
        self.preset_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Resolution scaling
        resolution_frame = ttk.Frame(settings_frame)
        resolution_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(resolution_frame, text="Resolution:").pack(side=tk.LEFT, padx=5)
        self.width_var = tk.StringVar(value="")
        self.height_var = tk.StringVar(value="")
        ttk.Entry(resolution_frame, textvariable=self.width_var, width=5).pack(side=tk.LEFT)
        ttk.Label(resolution_frame, text="x").pack(side=tk.LEFT)
        ttk.Entry(resolution_frame, textvariable=self.height_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(resolution_frame, text="(leave empty for original)").pack(side=tk.LEFT)
        
        # FPS
        ttk.Label(resolution_frame, text="FPS:").pack(side=tk.LEFT, padx=5)
        self.fps_var = tk.StringVar(value="")
        ttk.Entry(resolution_frame, textvariable=self.fps_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(resolution_frame, text="(leave empty for original)").pack(side=tk.LEFT)
        
        # Encode button
        encode_frame = ttk.Frame(main_frame)
        encode_frame.pack(fill=tk.X, pady=10)
        ttk.Button(encode_frame, text="Encode Video", command=self.encode_video).pack(pady=5)
        
        # Video display area
        video_frame = ttk.Frame(main_frame)
        video_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Original video canvas
        original_frame = ttk.LabelFrame(video_frame, text="Original Video")
        original_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.original_canvas = tk.Canvas(original_frame, bg="black")
        self.original_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Encoded video canvas
        encoded_frame = ttk.LabelFrame(video_frame, text="Encoded Video")
        encoded_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        self.encoded_canvas = tk.Canvas(encoded_frame, bg="black")
        self.encoded_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Playback controls
        playback_frame = ttk.Frame(main_frame)
        playback_frame.pack(fill=tk.X, pady=5)

        self.play_btn = ttk.Button(playback_frame, text="Play", command=self.toggle_playback)
        self.play_btn.pack(side=tk.LEFT, padx=5)

        self.reset_btn = ttk.Button(playback_frame, text="Reset", command=self.reset_playback)
        self.reset_btn.pack(side=tk.LEFT, padx=5)

        # Fullscreen button (or other trigger)
        fullscreen_frame = ttk.Frame(main_frame)
        fullscreen_frame.pack(fill=tk.X, pady=5)
        self.fullscreen_btn = ttk.Button(fullscreen_frame, text="Fullscreen", command=self.toggle_fullscreen)
        self.fullscreen_btn.pack(side=tk.LEFT, padx=5)

        # Bind canvas resize event for proper scaling
        self.original_canvas.bind("<Configure>", self.resize_original_video)
        self.encoded_canvas.bind("<Configure>", self.resize_encoded_video)
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(main_frame, text="Video Statistics", padding=10)
        stats_frame.pack(fill=tk.X, pady=5)
        
        # Original video stats
        original_stats_frame = ttk.Frame(stats_frame)
        original_stats_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(original_stats_frame, text="Original File Size:").pack(side=tk.LEFT, padx=5)
        self.original_size_var = tk.StringVar(value="N/A")
        ttk.Label(original_stats_frame, textvariable=self.original_size_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(original_stats_frame, text="Original Resolution:").pack(side=tk.LEFT, padx=5)
        self.original_res_var = tk.StringVar(value="N/A")
        ttk.Label(original_stats_frame, textvariable=self.original_res_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(original_stats_frame, text="Original FPS:").pack(side=tk.LEFT, padx=5)
        self.original_fps_var = tk.StringVar(value="N/A")
        ttk.Label(original_stats_frame, textvariable=self.original_fps_var).pack(side=tk.LEFT, padx=5)
        
        # Encoded video stats
        encoded_stats_frame = ttk.Frame(stats_frame)
        encoded_stats_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(encoded_stats_frame, text="Encoded File Size:").pack(side=tk.LEFT, padx=5)
        self.encoded_size_var = tk.StringVar(value="N/A")
        ttk.Label(encoded_stats_frame, textvariable=self.encoded_size_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(encoded_stats_frame, text="Encoded Resolution:").pack(side=tk.LEFT, padx=5)
        self.encoded_res_var = tk.StringVar(value="N/A")
        ttk.Label(encoded_stats_frame, textvariable=self.encoded_res_var).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(encoded_stats_frame, text="Size Reduction:").pack(side=tk.LEFT, padx=5)
        self.size_reduction_var = tk.StringVar(value="N/A")
        ttk.Label(encoded_stats_frame, textvariable=self.size_reduction_var).pack(side=tk.LEFT, padx=5)
        
        self.root.bind("<Escape>", self.toggle_fullscreen)

    def create_media_info_tab(self, parent):
        # Media info frame
        media_frame = ttk.Frame(parent, padding=10)
        media_frame.pack(fill=tk.BOTH, expand=True)
        
        # Video Information Section
        video_info_frame = ttk.LabelFrame(media_frame, text="Video Stream Information", padding=10)
        video_info_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.video_info_text = scrolledtext.ScrolledText(video_info_frame, height=10, width=80, wrap=tk.WORD)
        self.video_info_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Audio Information Section
        audio_info_frame = ttk.LabelFrame(media_frame, text="Audio Stream Information", padding=10)
        audio_info_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.audio_info_text = scrolledtext.ScrolledText(audio_info_frame, height=10, width=80, wrap=tk.WORD)
        self.audio_info_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Container Information Section
        container_info_frame = ttk.LabelFrame(media_frame, text="Container Information", padding=10)
        container_info_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.container_info_text = scrolledtext.ScrolledText(container_info_frame, height=6, width=80, wrap=tk.WORD)
        self.container_info_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Refresh button
        refresh_frame = ttk.Frame(media_frame)
        refresh_frame.pack(fill=tk.X, pady=5)
        ttk.Button(refresh_frame, text="Refresh Media Info", command=self.refresh_media_info).pack(side=tk.RIGHT)
    
    def create_advanced_tab(self, parent):
        # Advanced settings frame
        advanced_frame = ttk.Frame(parent, padding=10)
        advanced_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create left and right columns for advanced settings
        left_column = ttk.Frame(advanced_frame)
        left_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        right_column = ttk.Frame(advanced_frame)
        right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # ===== Video Advanced Settings (Left Column) =====
        video_settings = ttk.LabelFrame(left_column, text="Advanced Video Settings", padding=10)
        video_settings.pack(fill=tk.X, pady=5)
        
        # Video bitrate
        video_bitrate_frame = ttk.Frame(video_settings)
        video_bitrate_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(video_bitrate_frame, text="Video Bitrate:").pack(side=tk.LEFT, padx=5)
        self.video_bitrate_var = tk.StringVar(value="")
        ttk.Entry(video_bitrate_frame, textvariable=self.video_bitrate_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(video_bitrate_frame, text="(e.g., 5M, 2000k, leave empty for CRF)").pack(side=tk.LEFT)
        
        # Pixel format
        pixel_format_frame = ttk.Frame(video_settings)
        pixel_format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(pixel_format_frame, text="Pixel Format:").pack(side=tk.LEFT, padx=5)
        self.pixel_format_var = tk.StringVar(value="yuv420p")
        self.pixel_format_dropdown = ttk.Combobox(pixel_format_frame, textvariable=self.pixel_format_var, 
                                                values=self.codec_pixel_formats["libx264"], width=15)
        self.pixel_format_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Profile
        profile_frame = ttk.Frame(video_settings)
        profile_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(profile_frame, text="Profile:").pack(side=tk.LEFT, padx=5)
        self.profile_var = tk.StringVar(value="")
        self.profile_dropdown = ttk.Combobox(profile_frame, textvariable=self.profile_var, 
                                           values=["", "baseline", "main", "high"], width=10)
        self.profile_dropdown.pack(side=tk.LEFT, padx=5)
        
        # Level
        ttk.Label(profile_frame, text="Level:").pack(side=tk.LEFT, padx=5)
        self.level_var = tk.StringVar(value="")
        self.level_dropdown = ttk.Combobox(profile_frame, textvariable=self.level_var, 
                                         values=["", "3.0", "3.1", "4.0", "4.1", "4.2", "5.0", "5.1", "5.2"], width=5)
        self.level_dropdown.pack(side=tk.LEFT, padx=5)
        
        # GOP size
        gop_frame = ttk.Frame(video_settings)
        gop_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(gop_frame, text="GOP Size:").pack(side=tk.LEFT, padx=5)
        self.gop_var = tk.StringVar(value="")
        ttk.Entry(gop_frame, textvariable=self.gop_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(gop_frame, text="(frames between keyframes)").pack(side=tk.LEFT)
        
        # ===== Audio Advanced Settings (Right Column) =====
        audio_settings = ttk.LabelFrame(right_column, text="Advanced Audio Settings", padding=10)
        audio_settings.pack(fill=tk.X, pady=5)
        
        # Audio bitrate
        audio_bitrate_frame = ttk.Frame(audio_settings)
        audio_bitrate_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(audio_bitrate_frame, text="Audio Bitrate:").pack(side=tk.LEFT, padx=5)
        self.audio_bitrate_var = tk.StringVar(value="128k")
        ttk.Entry(audio_bitrate_frame, textvariable=self.audio_bitrate_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(audio_bitrate_frame, text="(e.g., 128k, 192k)").pack(side=tk.LEFT)
        
        # Audio sample rate
        sample_rate_frame = ttk.Frame(audio_settings)
        sample_rate_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(sample_rate_frame, text="Sample Rate:").pack(side=tk.LEFT, padx=5)
        self.sample_rate_var = tk.StringVar(value="")
        sample_rate_dropdown = ttk.Combobox(sample_rate_frame, textvariable=self.sample_rate_var, 
                                           values=["", "44100", "48000", "96000", "192000"], width=10)
        sample_rate_dropdown.pack(side=tk.LEFT, padx=5)
        ttk.Label(sample_rate_frame, text="Hz (leave empty for original)").pack(side=tk.LEFT)
        
        # Audio channels
        channels_frame = ttk.Frame(audio_settings)
        channels_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(channels_frame, text="Audio Channels:").pack(side=tk.LEFT, padx=5)
        self.channels_var = tk.StringVar(value="")
        channels_dropdown = ttk.Combobox(channels_frame, textvariable=self.channels_var, 
                                        values=["", "1", "2", "6"], width=5)
        channels_dropdown.pack(side=tk.LEFT, padx=5)
        ttk.Label(channels_frame, text="(1=mono, 2=stereo, 6=5.1, empty=original)").pack(side=tk.LEFT)
        
        # Audio sample format
        sample_format_frame = ttk.Frame(audio_settings)
        sample_format_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(sample_format_frame, text="Sample Format:").pack(side=tk.LEFT, padx=5)
        self.sample_format_var = tk.StringVar(value="")
        sample_format_dropdown = ttk.Combobox(sample_format_frame, textvariable=self.sample_format_var, 
                                             values=["", "s16", "s32", "flt", "fltp"], width=10)
        sample_format_dropdown.pack(side=tk.LEFT, padx=5)
        
        # ===== Additional Parameters (Bottom) =====
        additional_frame = ttk.LabelFrame(advanced_frame, text="Additional Parameters", padding=10)
        additional_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Additional FFmpeg parameters
        ttk.Label(additional_frame, text="Additional FFmpeg Parameters:").pack(anchor=tk.W, padx=5, pady=5)
        self.additional_params_var = tk.StringVar()
        ttk.Entry(additional_frame, textvariable=self.additional_params_var, width=80).pack(fill=tk.X, padx=5, pady=5)
    
    def create_command_tab(self, parent):
        # Command display frame
        command_frame = ttk.Frame(parent, padding=10)
        command_frame.pack(fill=tk.BOTH, expand=True)
        
        # Preview button
        ttk.Button(command_frame, text="Generate Command Preview", command=self.preview_command).pack(anchor=tk.W, pady=5)
        
        # Command text area
        ttk.Label(command_frame, text="FFmpeg Command:").pack(anchor=tk.W, pady=5)
        self.command_text = scrolledtext.ScrolledText(command_frame, height=10, width=80, wrap=tk.WORD)
        self.command_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Command output log
        ttk.Label(command_frame, text="Output Log:").pack(anchor=tk.W, pady=5)
        self.output_log = scrolledtext.ScrolledText(command_frame, height=10, width=80, wrap=tk.WORD)
        self.output_log.pack(fill=tk.BOTH, expand=True, pady=5)
     
     # Continue from where the original code left off

    def select_video(self):
        """Select input video file"""
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video Files", "*.mp4 *.avi *.mkv *.mov *.webm *.flv *.wmv")]
        )
        
        if file_path:
            self.input_video_path = file_path
            self.file_path_var.set(file_path)
            
            # Load video info
            self.load_video_info()
            
            # Update UI with loaded video info
            self.update_video_info_ui()
            
            # Reset any encoded video
            self.encoded_video_path = None
            self.encoded_size_var.set("N/A")
            self.encoded_res_var.set("N/A")
            self.size_reduction_var.set("N/A")
            
            # Stop any ongoing playback
            self.stop_playback()
    
    def load_video_info(self):
        """Load input video information using FFprobe"""
        if not self.input_video_path:
            return
            
        try:
            self.status_var.set("Loading media information...")
            
            # Run FFprobe to get JSON output with media information
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", "-show_format", self.input_video_path
            ]
            
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            media_info = json.loads(result.stdout)
            
            # Extract video and audio stream information
            self.video_info = {}
            self.audio_info = {}
            
            for stream in media_info.get("streams", []):
                if stream.get("codec_type") == "video" and not self.video_info:
                    self.video_info = stream
                elif stream.get("codec_type") == "audio" and not self.audio_info:
                    self.audio_info = stream
            
            # Extract container information
            self.container_info = media_info.get("format", {})
            
            # Update file size information
            file_size = os.path.getsize(self.input_video_path)
            self.original_size_var.set(f"{file_size / (1024 * 1024):.2f} MB")
            
            # Update resolution information
            if self.video_info:
                width = self.video_info.get("width", "?")
                height = self.video_info.get("height", "?")
                self.original_res_var.set(f"{width}x{height}")
                
                # Suggest the same resolution for encoding
                self.width_var.set(str(width))
                self.height_var.set(str(height))
                
                # Update FPS information
                frame_rate = self.video_info.get("r_frame_rate", "")
                if "/" in frame_rate:
                    num, den = frame_rate.split("/")
                    if den != "0":
                        fps = round(float(num) / float(den), 2)
                        self.original_fps_var.set(f"{fps}")
                        self.fps_var.set(str(int(fps)))
            
            self.status_var.set("Ready")
            
        except Exception as e:
            print(f"Error loading video info: {e}")
            self.status_var.set(f"Error loading video info: {str(e)}")
    
    def update_video_info_ui(self):
        """Update the media info tab UI with loaded video information"""
        # Clear previous info
        self.video_info_text.delete(1.0, tk.END)
        self.audio_info_text.delete(1.0, tk.END)
        self.container_info_text.delete(1.0, tk.END)
        
        # Format and display video stream info
        if self.video_info:
            video_details = [
                f"Codec: {self.video_info.get('codec_name', 'Unknown')} ({self.video_info.get('codec_long_name', 'Unknown')})",
                f"Resolution: {self.video_info.get('width', '?')}x{self.video_info.get('height', '?')}",
                f"Bit Depth: {self.video_info.get('bits_per_raw_sample', '?')} bits",
                f"Pixel Format: {self.video_info.get('pix_fmt', 'Unknown')}",
                f"Frame Rate: {self.video_info.get('r_frame_rate', 'Unknown')}",
                f"Average Frame Rate: {self.video_info.get('avg_frame_rate', 'Unknown')}",
                f"Bitrate: {int(self.video_info.get('bit_rate', 0)) // 1000} kbps" if 'bit_rate' in self.video_info else "Bitrate: Unknown",
                f"Duration: {self.video_info.get('duration', '?')} seconds",
                f"Profile: {self.video_info.get('profile', 'Unknown')}",
                f"Level: {self.video_info.get('level', 'Unknown')}"
            ]
            self.video_info_text.insert(tk.END, "\n".join(video_details))
        else:
            self.video_info_text.insert(tk.END, "No video stream found")
        
        # Format and display audio stream info
        if self.audio_info:
            audio_details = [
                f"Codec: {self.audio_info.get('codec_name', 'Unknown')} ({self.audio_info.get('codec_long_name', 'Unknown')})",
                f"Sample Rate: {self.audio_info.get('sample_rate', '?')} Hz",
                f"Channels: {self.audio_info.get('channels', '?')}",
                f"Channel Layout: {self.audio_info.get('channel_layout', 'Unknown')}",
                f"Sample Format: {self.audio_info.get('sample_fmt', 'Unknown')}",
                f"Bitrate: {int(self.audio_info.get('bit_rate', 0)) // 1000} kbps" if 'bit_rate' in self.audio_info else "Bitrate: Unknown",
                f"Duration: {self.audio_info.get('duration', '?')} seconds"
            ]
            self.audio_info_text.insert(tk.END, "\n".join(audio_details))
        else:
            self.audio_info_text.insert(tk.END, "No audio stream found")
        
        # Format and display container info
        if self.container_info:
            container_details = [
                f"Format: {self.container_info.get('format_name', 'Unknown')} ({self.container_info.get('format_long_name', 'Unknown')})",
                f"Duration: {self.container_info.get('duration', '?')} seconds",
                f"Size: {float(self.container_info.get('size', 0)) / (1024*1024):.2f} MB",
                f"Bitrate: {int(self.container_info.get('bit_rate', 0)) // 1000} kbps" if 'bit_rate' in self.container_info else "Bitrate: Unknown",
                f"Number of Streams: {self.container_info.get('nb_streams', '?')}",
                f"Start Time: {self.container_info.get('start_time', '0')} seconds"
            ]
            self.container_info_text.insert(tk.END, "\n".join(container_details))
        else:
            self.container_info_text.insert(tk.END, "No container info available")
    
    def refresh_media_info(self):
        """Refresh the media information"""
        if self.input_video_path:
            self.load_video_info()
            self.update_video_info_ui()
    
    def update_codec_dependent_options(self, event=None):
        """Update codec-dependent UI elements when codec selection changes"""
        selected_codec = self.video_codec_var.get()
        
        # Update CRF range
        crf_range = self.codec_crf_ranges.get(selected_codec, {"min": 0, "max": 51, "default": 23})
        self.crf_scale.config(from_=crf_range["min"], to=crf_range["max"])
        self.crf_var.set(str(crf_range["default"]))
        
        # Update presets
        presets = self.codec_presets.get(selected_codec, ["medium"])
        self.preset_dropdown.config(values=presets)
        if presets:
            self.preset_var.set(presets[len(presets)//2])  # Default to middle preset
        else:
            self.preset_var.set("")
        
        # Update pixel formats
        pixel_formats = self.codec_pixel_formats.get(selected_codec, ["yuv420p"])
        self.pixel_format_dropdown.config(values=pixel_formats)
        if pixel_formats:
            self.pixel_format_var.set(pixel_formats[0])
        
        # Update profile/level options based on codec
        if selected_codec in ["libx264", "h264_nvenc"]:
            self.profile_dropdown.config(values=["", "baseline", "main", "high"])
            self.level_dropdown.config(values=["", "3.0", "3.1", "4.0", "4.1", "4.2", "5.0", "5.1", "5.2"])
        elif selected_codec in ["libx265", "hevc_nvenc"]:
            self.profile_dropdown.config(values=["", "main", "main10", "main12", "main444-8", "main444-10"])
            self.level_dropdown.config(values=["", "3.1", "4.0", "4.1", "5.0", "5.1", "5.2", "6.0", "6.1", "6.2"])
        else:
            self.profile_dropdown.config(values=[""])
            self.level_dropdown.config(values=[""])
        
        self.profile_var.set("")
        self.level_var.set("")
    
    def preview_command(self):
        """Generate and display the FFmpeg command without executing it"""
        if not self.input_video_path:
            messagebox.showwarning("No Input", "Please select an input video file first.")
            return
        
        cmd = self._build_ffmpeg_command()
        
        # Display the command in the command text area
        self.command_text.delete(1.0, tk.END)
        self.command_text.insert(tk.END, " ".join(cmd))
    
    def _build_ffmpeg_command(self):
        """Build the FFmpeg command based on current settings"""
        if not self.input_video_path:
            return []
        
        # Get output file path
        output_ext = self.container_var.get()
        output_file = os.path.join(self.temp_dir, f"encoded_output.{output_ext}")
        
        cmd = [self.ffmpeg_path, "-y", "-i", self.input_video_path]
        
        # Video codec options
        video_codec = self.video_codec_var.get()
        if video_codec:
            cmd.extend(["-c:v", video_codec])
        
        # Video quality/bitrate
        video_bitrate = self.video_bitrate_var.get()
        crf_value = self.crf_var.get()
        
        if video_bitrate:
            cmd.extend(["-b:v", video_bitrate])
        elif crf_value:
            if video_codec in ["libx264", "libx265", "h264_nvenc", "hevc_nvenc"]:
                cmd.extend(["-crf", crf_value])
            elif video_codec in ["libvpx-vp9"]:
                cmd.extend(["-crf", crf_value])
            elif video_codec in ["libaom-av1"]:
                cmd.extend(["-crf", crf_value])
        
        # Preset
        preset = self.preset_var.get()
        if preset:
            cmd.extend(["-preset", preset])
        
        # Resolution
        width = self.width_var.get()
        height = self.height_var.get()
        if width and height:
            cmd.extend(["-vf", f"scale={width}:{height}"])
        
        # FPS
        fps = self.fps_var.get()
        if fps:
            if width and height:
                # Update the scale filter to include fps
                cmd[-1] = f"scale={width}:{height},fps={fps}"
            else:
                cmd.extend(["-vf", f"fps={fps}"])
        
        # Pixel format
        pixel_format = self.pixel_format_var.get()
        if pixel_format:
            cmd.extend(["-pix_fmt", pixel_format])
        
        # Profile and level
        profile = self.profile_var.get()
        if profile:
            cmd.extend(["-profile:v", profile])
        
        level = self.level_var.get()
        if level:
            cmd.extend(["-level", level])
        
        # GOP size (keyframe interval)
        gop = self.gop_var.get()
        if gop:
            cmd.extend(["-g", gop])
        
        # Audio codec options
        audio_codec = self.audio_codec_var.get()
        if audio_codec:
            cmd.extend(["-c:a", audio_codec])
        
        # Audio bitrate
        audio_bitrate = self.audio_bitrate_var.get()
        if audio_bitrate:
            cmd.extend(["-b:a", audio_bitrate])
        
        # Audio sample rate
        sample_rate = self.sample_rate_var.get()
        if sample_rate:
            cmd.extend(["-ar", sample_rate])
        
        # Audio channels
        channels = self.channels_var.get()
        if channels:
            cmd.extend(["-ac", channels])
        
        # Audio sample format
        sample_format = self.sample_format_var.get()
        if sample_format:
            cmd.extend(["-sample_fmt", sample_format])
        
        # Additional parameters
        additional_params = self.additional_params_var.get()
        if additional_params:
            cmd.extend(additional_params.split())
        
        cmd.append(output_file)
        return cmd
    
    def encode_video(self):
        """Encode the video with the selected settings"""
        if not self.input_video_path:
            messagebox.showwarning("No Input", "Please select an input video file first.")
            return
        
        # Stop any existing playback
        self.stop_playback()
        
        # Build the FFmpeg command
        cmd = self._build_ffmpeg_command()
        
        # Update status
        self.status_var.set("Encoding in progress...")
        
        # Clear the output log
        self.output_log.delete(1.0, tk.END)
        
        # Switch to the command tab to show progress
        self.notebook.select(3)  # Index of the command tab
        
        # Update the command preview
        self.command_text.delete(1.0, tk.END)
        self.command_text.insert(tk.END, " ".join(cmd))
        
        # Run encoding in a separate thread
        encoding_thread = threading.Thread(target=self._run_encoding, args=(cmd,))
        encoding_thread.daemon = True
        encoding_thread.start()

    def _run_encoding(self, cmd):
        """Run the FFmpeg encoding process and handle output"""
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.output_log.insert(tk.END, output)
                    self.output_log.see(tk.END)
            
            return_code = process.poll()
            if return_code == 0:
                self.root.after(0, self._encoding_finished_success)
            else:
                error_message = process.stderr.read()
                self.root.after(0, self._encoding_finished_error, return_code, error_message)
                
        except Exception as e:
            self.root.after(0, self._encoding_finished_exception, e)

    def _encoding_finished_success(self):
        """Handle successful encoding"""
        self.status_var.set("Encoding completed successfully!")
        messagebox.showinfo("Encoding Complete", "Video encoding completed!")
        
        # Get file sizes and calculate percentage change
        original_size = os.path.getsize(self.input_video_path)
        encoded_size = os.path.getsize(self.encoded_video_path)
        percentage_change = ((encoded_size - original_size) / original_size) * 100
        
        # Update UI elements
        self.original_size_var.set(f"{original_size / (1024 * 1024):.2f} MB")
        self.encoded_size_var.set(f"{encoded_size / (1024 * 1024):.2f} MB")
        self.size_reduction_var.set(f"{percentage_change:.2f} %")

        self.load_video_info()
        self.update_video_info_ui()
        self.load_and_display_frames()
    
    def load_and_display_frames(self):
        """Load the first frame of the original and encoded videos and display them"""

        if not self.input_video_path or not self.encoded_video_path:
            messagebox.showwarning("No Input/Output", "Please select both input and output video files.")
            return

        try:
            # Open video files
            self.cap_original = cv2.VideoCapture(self.input_video_path)
            self.cap_encoded = cv2.VideoCapture(self.encoded_video_path)

            # Read the first frame from each video
            ret_original, original_frame = self.cap_original.read()
            ret_encoded, encoded_frame = self.cap_encoded.read()

            if not ret_original or not ret_encoded:
                messagebox.showerror("Error", "Could not read frames from one or both video files.")
                return

            # Convert frames to PIL images
            original_frame_rgb = cv2.cvtColor(original_frame, cv2.COLOR_BGR2RGB)
            encoded_frame_rgb = cv2.cvtColor(encoded_frame, cv2.COLOR_BGR2RGB)
            original_frame_pil = Image.fromarray(original_frame_rgb)
            encoded_frame_pil = Image.fromarray(encoded_frame_rgb)

            # Resize frames to fit canvases while preserving aspect ratio
            self.original_img = original_frame_pil
            self.encoded_img = encoded_frame_pil

            self.resize_video_frame(self.original_canvas.winfo_geometry(), self.original_canvas, self.original_img)
            self.resize_video_frame(self.encoded_canvas.winfo_geometry(), self.encoded_canvas, self.encoded_img)

            # Update canvases with the first frames
            #self.original_photo = ImageTk.PhotoImage(original_frame_pil)
            #self.original_canvas.create_image(0, 0, image=self.original_photo, anchor=tk.NW)
            #self.encoded_photo = ImageTk.PhotoImage(encoded_frame_pil)
            #self.encoded_canvas.create_image(0, 0, image=self.encoded_photo, anchor=tk.NW)

            # Update play button state
            self.play_btn.config(state=tk.NORMAL)
            self.reset_btn.config(state=tk.NORMAL)

        except Exception as e:
            print(f"Error loading and displaying frames: {e}")
            messagebox.showerror("Error", f"Could not load and display video frames: {e}")

    def _encoding_finished_error(self, return_code, error_message):
        """Handle encoding error"""
        self.status_var.set(f"Encoding failed with code {return_code}")
        self.output_log.insert(tk.END, f"\nFFmpeg Error (Code {return_code}):\n{error_message}")
        messagebox.showerror("Encoding Error", f"Video encoding failed! See output log for details. (Error Code: {return_code})")

    def _encoding_finished_exception(self, e):
        """Handle unexpected encoding exception"""

        print(f"Encoding error: {e}")
        self.status_var.set(f"Encoding failed: {e}")
        messagebox.showerror("Encoding Error", f"An error occurred during encoding: {e}")
    
    def _run_encoding(self, cmd):
        """Run the FFmpeg encoding process"""
        try:
            # Ensure the output directory exists
            os.makedirs(os.path.dirname(cmd[-1]), exist_ok=True)
            
            # Start the FFmpeg process
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # Read and display output
            for line in process.stderr:
                self.output_log.insert(tk.END, line)
                self.output_log.see(tk.END)  # Scroll to the bottom
                self.root.update_idletasks()
            
            # Wait for the process to finish
            process.wait()
            
            # Update encoded video path
            self.encoded_video_path = cmd[-1]
            
            # Update encoded video stats
            if os.path.exists(self.encoded_video_path):
                encoded_size = os.path.getsize(self.encoded_video_path)
                self.encoded_size_var.set(f"{encoded_size / (1024 * 1024):.2f} MB")
                
                # Calculate size reduction
                original_size = os.path.getsize(self.input_video_path)
                reduction_percent = ((original_size - encoded_size) / original_size) * 100
                self.size_reduction_var.set(f"{reduction_percent:.2f}%")
                
                # Get encoded video resolution
                cap = cv2.VideoCapture(self.encoded_video_path)
                if cap.isOpened():
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    self.encoded_res_var.set(f"{width}x{height}")
                    cap.release()
                
                # Enable video playback
                self.status_var.set("Encoding complete. Ready for playback.")
                
                # Switch back to the main tab
                self.notebook.select(0)  # Index of the main tab
                
                # Load videos for playback
                self.load_videos_for_playback()
            else:
                self.status_var.set("Encoding failed. Check the output log.")
        
        except Exception as e:
            error_msg = f"Encoding error: {str(e)}"
            print(error_msg)
            self.output_log.insert(tk.END, f"\n{error_msg}")
            self.status_var.set(error_msg)
    
    def load_videos_for_playback(self):
        """Load both original and encoded videos for playback"""
        # Close any existing video captures
        if self.cap_original and self.cap_original.isOpened():
            self.cap_original.release()
        
        if self.cap_encoded and self.cap_encoded.isOpened():
            self.cap_encoded.release()
        
        # Open video captures
        if self.input_video_path and os.path.exists(self.input_video_path):
            self.cap_original = cv2.VideoCapture(self.input_video_path)
        
        if self.encoded_video_path and os.path.exists(self.encoded_video_path):
            self.cap_encoded = cv2.VideoCapture(self.encoded_video_path)
        
        # Reset playback state
        self.is_playing = False
        self.play_btn.config(text="Play")
    
    def toggle_playback(self):
        """Toggle video playback state"""
        if not self.input_video_path or not self.encoded_video_path:
            messagebox.showinfo("Playback", "Please encode a video first.")
            return
        
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()
    
    def start_playback(self):
        """Start video playback"""
        if self.is_playing:
            return
            
        # Make sure video captures are open
        if (not self.cap_original or not self.cap_original.isOpened() or 
            not self.cap_encoded or not self.cap_encoded.isOpened()):
            self.load_videos_for_playback()
            
        # Start playback thread
        self.is_playing = True
        self.play_btn.config(text="Pause")
        
        if not self.playing_thread or not self.playing_thread.is_alive():
            self.playing_thread = threading.Thread(target=self._playback_thread)
            self.playing_thread.daemon = True
            self.playing_thread.start()
    
    def stop_playback(self):
        """Stop video playback"""
        self.is_playing = False
        self.play_btn.config(text="Play")
        
        # Wait for thread to finish
        if self.playing_thread and self.playing_thread.is_alive():
            self.playing_thread.join(0.5)
    
    def reset_playback(self):
        """Reset video playback to the beginning"""
        self.stop_playback()
        
        if self.cap_original and self.cap_original.isOpened():
            self.cap_original.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
        if self.cap_encoded and self.cap_encoded.isOpened():
            self.cap_encoded.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
        # Display the first frame
        self._display_frame()
    
    def _playback_thread(self):
        """Thread function for video playback"""
        try:
            # Get FPS for timing
            fps = self.cap_original.get(cv2.CAP_PROP_FPS)
            if fps <= 0:
                fps = 30  # Default to 30fps if we can't determine it
                
            frame_time = 1.0 / fps
            
            while self.is_playing:
                start_time = time.time()
                
                # Read and display frames
                orig_ret, orig_frame = self.cap_original.read()
                enc_ret, enc_frame = self.cap_encoded.read()
                
                # Check if we've reached the end of either video
                if not orig_ret or not enc_ret:
                    # Reset to beginning
                    self.cap_original.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    self.cap_encoded.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                # Display frames
                if orig_ret and enc_ret:
                    # Convert from BGR to RGB
                    orig_frame_rgb = cv2.cvtColor(orig_frame, cv2.COLOR_BGR2RGB)
                    enc_frame_rgb = cv2.cvtColor(enc_frame, cv2.COLOR_BGR2RGB)
                    
                    # Create PILImage objects
                    orig_img = Image.fromarray(orig_frame_rgb)
                    enc_img = Image.fromarray(enc_frame_rgb)
                    
                    # Resize to fit canvas
                    orig_img = self._resize_image_to_canvas(orig_img, self.original_canvas)
                    enc_img = self._resize_image_to_canvas(enc_img, self.encoded_canvas)
                    
                    # Convert to PhotoImage objects
                    orig_photo = ImageTk.PhotoImage(image=orig_img)
                    enc_photo = ImageTk.PhotoImage(image=enc_img)
                    
                    # Update images on canvas
                    self.original_canvas.create_image(
                        self.original_canvas.winfo_width() // 2,
                        self.original_canvas.winfo_height() // 2,
                        image=orig_photo, anchor=tk.CENTER
                    )
                    
                    self.encoded_canvas.create_image(
                        self.encoded_canvas.winfo_width() // 2,
                        self.encoded_canvas.winfo_height() // 2,
                        image=enc_photo, anchor=tk.CENTER
                    )
                    
                    # Keep references to prevent garbage collection
                    self.original_canvas.image = orig_photo
                    self.encoded_canvas.image = enc_photo
                    
                    # Calculate time to sleep for proper frame rate
                    elapsed = time.time() - start_time
                    sleep_time = max(0, frame_time - elapsed)
                    time.sleep(sleep_time)
                    
                    # Update UI
                    self.root.update_idletasks()
        
        except Exception as e:
            print(f"Playback error: {e}")
            self.status_var.set(f"Playback error: {str(e)}")
            self.is_playing = False
            self.play_btn.config(text="Play")
    
    def _display_frame(self):
        """Display the current frame of both videos"""
        try:
            # Read frames
            if self.cap_original and self.cap_original.isOpened():
                orig_ret, orig_frame = self.cap_original.read()
                if orig_ret:
                    # Convert and display
                    orig_frame_rgb = cv2.cvtColor(orig_frame, cv2.COLOR_BGR2RGB)
                    orig_img = Image.fromarray(orig_frame_rgb)
                    orig_img = self._resize_image_to_canvas(orig_img, self.original_canvas)
                    orig_photo = ImageTk.PhotoImage(image=orig_img)
                    
                    self.original_canvas.create_image(
                        self.original_canvas.winfo_width() // 2,
                        self.original_canvas.winfo_height() // 2,
                        image=orig_photo, anchor=tk.CENTER
                    )
                    self.original_canvas.image = orig_photo
            
            if self.cap_encoded and self.cap_encoded.isOpened():
                enc_ret, enc_frame = self.cap_encoded.read()
                if enc_ret:
                    # Convert and display
                    enc_frame_rgb = cv2.cvtColor(enc_frame, cv2.COLOR_BGR2RGB)
                    enc_img = Image.fromarray(enc_frame_rgb)
                    enc_img = self._resize_image_to_canvas(enc_img, self.encoded_canvas)
                    enc_photo = ImageTk.PhotoImage(image=enc_img)
                    
                    self.encoded_canvas.create_image(
                        self.encoded_canvas.winfo_width() // 2,
                        self.encoded_canvas.winfo_height() // 2,
                        image=enc_photo, anchor=tk.CENTER
                    )
                    self.encoded_canvas.image = enc_photo
        
        except Exception as e:
            print(f"Display frame error: {e}")
    
    def _resize_image_to_canvas(self, img, canvas):
        """Resize an image to fit in the canvas while maintaining aspect ratio"""
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        
        # Use default size if canvas not yet realized
        if canvas_width <= 1:
            canvas_width = 400
        if canvas_height <= 1:
            canvas_height = 300
        
        # Get image size
        img_width, img_height = img.size
        
        # Calculate aspect ratios
        width_ratio = canvas_width / img_width
        height_ratio = canvas_height / img_height
        
        # Use smaller ratio to ensure fit
        scale_factor = min(width_ratio, height_ratio)
        
        # Apply scaling
        new_width = int(img_width * scale_factor)
        new_height = int(img_height * scale_factor)
        
        return img.resize((new_width, new_height), Image.LANCZOS)
    
    def _resize_video_frame(self, event, canvas, img):
        """Resize the video frame to fit the canvas while preserving aspect ratio."""

        canvas_width = event.width if isinstance(event, int) else event.width
        canvas_height = event.height if isinstance(event, int) else event.height
        img_width, img_height = img.size

        # Calculate aspect ratio
        img_aspect = img_width / img_height
        canvas_aspect = canvas_width / canvas_height

        if img_aspect > canvas_aspect:
            # Image is wider than canvas, fit width
            display_width = canvas_width
            display_height = int(canvas_width / img_aspect)
        else:
            # Image is taller than canvas, fit height
            display_height = canvas_height
            display_width = int(canvas_height * img_aspect)

        resized_img = img.resize((display_width, display_height), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized_img)  # Keep a reference!
        canvas.delete("video_image")  # Clear previous image
        canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo, tags="video_image")
        canvas.config(width=canvas_width, height=canvas_height)  # Ensure canvas is correct size
    
    def cleanup(self):
        """Clean up resources before closing the application"""
        # Stop playback
        self.stop_playback()
        
        # Release video captures
        if self.cap_original and self.cap_original.isOpened():
            self.cap_original.release()
        
        if self.cap_encoded and self.cap_encoded.isOpened():
            self.cap_encoded.release()
        
        # Remove temporary directory
        try:
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            print(f"Error removing temp directory: {e}")
        
        # Close the window
        self.root.destroy()
    
    def toggle_fullscreen(self, event=None): # Added event parameter to handle both button and Escape key
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self.root.attributes("-fullscreen", True)
            self.fullscreen_btn.config(text="Exit Fullscreen")  # Optionally change button text
        else:
            self.root.attributes("-fullscreen", False)
            self.fullscreen_btn.config(text="Fullscreen")
    
    def resize_original_video(self, event):
        if self.original_img:  # Only resize if there's an image
            self._display_image(self.original_img, self.original_canvas)

    def resize_encoded_video(self, event):
        if self.encoded_img:
            self._display_image(self.encoded_img, self.encoded_canvas)
    
    def _display_image(self, img, canvas):
        """Helper function to resize and display the image on the canvas."""
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()
        img.thumbnail((canvas_width, canvas_height), Image.LANCZOS)  # Resize the image
        photo = ImageTk.PhotoImage(image=img)
        canvas.delete("all")  # Clear previous image
        canvas.create_image(canvas_width // 2, canvas_height // 2, image=photo, anchor=tk.CENTER)
        canvas.image = photo  # Keep a reference!

    
    def resize_video_frame(self, event, canvas, img):
        canvas_width = event.width
        canvas_height = event.height

        img_width, img_height = img.size

        # Calculate aspect ratio
        img_aspect = img_width / img_height
        canvas_aspect = canvas_width / canvas_height

        if img_aspect > canvas_aspect:
            # Image is wider than canvas, fit width
            display_width = canvas_width
            display_height = int(canvas_width / img_aspect)
        else:
            # Image is taller than canvas, fit height
            display_height = canvas_height
            display_width = int(canvas_height * img_aspect)

        resized_img = img.resize((display_width, display_height), Image.LANCZOS)
        self.photo = ImageTk.PhotoImage(resized_img)  # Keep a reference!
        canvas.delete("video_image")  # Clear previous image
        canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo, tags="video_image")
        canvas.config(width=canvas_width, height=canvas_height)  # Ensure canvas is correct size

    def enter_fullscreen(self):
        """Enter fullscreen mode"""

        # Store the current window geometry so we can restore it later
        self._normal_geometry = self.root.geometry()

        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Create a new top-level window for "fullscreen"
        self.fullscreen_window = tk.Toplevel(self.root)
        self.fullscreen_window.title("Fullscreen Video")
        self.fullscreen_window.overrideredirect(True)  # Remove window decorations
        self.fullscreen_window.geometry(f"{screen_width}x{screen_height}+0+0")  # Cover the whole screen

        # Create canvases in the fullscreen window
        self.fullscreen_original_canvas = tk.Canvas(self.fullscreen_window, bg="black")
        self.fullscreen_original_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.fullscreen_encoded_canvas = tk.Canvas(self.fullscreen_window, bg="black")
        self.fullscreen_encoded_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Copy and resize the current frames to the fullscreen canvases
        self._display_frame(
            target_original_canvas=self.fullscreen_original_canvas,
            target_encoded_canvas=self.fullscreen_encoded_canvas
        )

        # Bind escape key to exit fullscreen
        self.fullscreen_window.bind("<Escape>", self.exit_fullscreen)
        self.fullscreen_btn.config(text="Exit Fullscreen")
        self.root.withdraw()  # Hide the main window

    def exit_fullscreen(self, event=None):  # event is optional, for key binding
        """Exit fullscreen mode"""
        if hasattr(self, "fullscreen_window"):
            self.fullscreen_window.destroy()
        self.root.deiconify()  # Restore the main window
        self.root.geometry(self._normal_geometry)  # Restore main window size
        self.is_fullscreen = False
        self.fullscreen_btn.config(text="Fullscreen")

    def _display_frame(
            self,
            target_original_canvas=None,
            target_encoded_canvas=None
    ):
        """Display the current frame of both videos on the specified canvases"""
        try:
            # Use the target canvases if provided, otherwise use the main ones
            original_canvas = target_original_canvas or self.original_canvas
            encoded_canvas = target_encoded_canvas or self.encoded_canvas

            # Read frames
            if self.cap_original and self.cap_original.isOpened():
                orig_ret, orig_frame = self.cap_original.read()
                if orig_ret:
                    # Convert and display
                    orig_frame_rgb = cv2.cvtColor(orig_frame, cv2.COLOR_BGR2RGB)
                    orig_img = Image.fromarray(orig_frame_rgb)
                    orig_img = self._resize_image_to_canvas(orig_img, original_canvas)  # Use target canvas
                    orig_photo = ImageTk.PhotoImage(image=orig_img)

                    original_canvas.create_image(
                        original_canvas.winfo_width() // 2,
                        original_canvas.winfo_height() // 2,
                        image=orig_photo, anchor=tk.CENTER
                    )
                    original_canvas.image = orig_photo

            if self.cap_encoded and self.cap_encoded.isOpened():
                enc_ret, enc_frame = self.cap_encoded.read()
                if enc_ret:
                    # Convert and display
                    enc_frame_rgb = cv2.cvtColor(enc_frame, cv2.COLOR_BGR2RGB)
                    enc_img = Image.fromarray(enc_frame_rgb)
                    enc_img = self._resize_image_to_canvas(enc_img, encoded_canvas)  # Use target canvas
                    enc_photo = ImageTk.PhotoImage(image=enc_img)

                    encoded_canvas.create_image(
                        encoded_canvas.winfo_width() // 2,
                        encoded_canvas.winfo_height() // 2,
                        image=enc_photo, anchor=tk.CENTER
                    )
                    encoded_canvas.image = enc_photo

        except Exception as e:
            print(f"Display frame error: {e}")


def main():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        ffmpeg_path = "ffmpeg"
    except FileNotFoundError:
        if getattr(sys, 'frozen', False):
            # Nuitka/Pyinstaller onefile mode
            ffmpeg_path = os.path.join(sys._MEIPASS, 'ffmpeg')
        else:
            # Normal script run
            ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg')
        
        if os.name == 'nt':
            ffmpeg_path += ".exe"
        
        if not os.path.exists(ffmpeg_path):
            print("FFmpeg not found. Please install FFmpeg and make sure it's in your PATH.")
            messagebox.showerror("FFmpeg Not Found", 
                            "FFmpeg not found. Please install FFmpeg and make sure it's in your PATH.")
            return
    
    # Create the application
    root = tk.Tk()
    app = FFtester(root, ffmpeg_path)
    root.mainloop()


if __name__ == "__main__":
    main()
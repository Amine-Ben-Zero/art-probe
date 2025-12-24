 🔍 ART Probe
**Adaptive Rate Test Probe**

A professional Python tool for detecting rate limiting mechanisms in HTTP endpoints during authorized security assessments.

## ✨ Features
- **Adaptive Testing:** Establishes behavioral baselines.
- **Async Architecture:** High performance using `aiohttp`.
- **Detection:** Identifies Hard Limits (429), Blocking, and Throttling.

## 🚀 Usage
# Basic Usage
python art_probe.py https://api.example.com/login

# Custom Max Requests
python art_probe.py https://api.example.com/login --max 200

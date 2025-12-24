
## 🎯 About

**ART Probe** is a security testing tool designed to detect rate limiting mechanisms in web applications during authorized penetration testing.

Unlike brute-force tools, ART Probe uses an **adaptive approach**:
- Establishes a behavioral baseline first
- Gradually increases request density
- Stops immediately when limits are detected
- Prevents causing Denial of Service

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔄 **Adaptive Testing** | Intelligent baseline comparison |
| ⚡ **Async Architecture** | High-performance with `aiohttp` |
| 🛡️ **Safety First** | Auto-stops when limits detected |
| 📊 **Detailed Reports** | Clear verdict with metrics |

---

## 📦 Installation

```bash
git clone https://github.com/Amine-Ben-Zero/art-probe.git
cd art-probe
pip install aiohttp
🚀 Usage
Bash

# Basic test
python art_probe.py https://api.example.com/endpoint

# POST request
python art_probe.py https://api.example.com/login -m POST

# With headers
python art_probe.py https://api.example.com/endpoint -H "Authorization: Bearer token"

# Custom limit
python art_probe.py https://api.example.com/endpoint --max 200
📊 Detection Types
Type	Indicator
Hard Limit	HTTP 429 Response
Soft Limit (Blocking)	Status code shift (200→403)
Soft Limit (Throttling)	Latency > 3x baseline
⚠️ Legal Disclaimer
This tool is for AUTHORIZED SECURITY TESTING ONLY.

Only test systems you own or have permission to test
Unauthorized testing may violate laws
Use responsibly and ethically
📄 License
MIT License - See LICENSE file.

👤 Author
Amine Bensalha / amibeodhgl@gmail.com

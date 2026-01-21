<h1 align="center">SocialStudio</h1>

<p align="center">
  <strong>AI-Powered Social Media Automation & Design Platform</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#tech-stack">Tech Stack</a> •
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#api-reference">API</a> •
  <a href="#deployment">Deployment</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python"/>
  <img src="https://img.shields.io/badge/FastAPI-0.100+-green?style=flat-square&logo=fastapi"/>
  <img src="https://img.shields.io/badge/Celery-5.0+-yellow?style=flat-square"/>
  <img src="https://img.shields.io/badge/AI-OpenAI%20%7C%20Gemini-purple?style=flat-square"/>
  <img src="https://img.shields.io/badge/License-MIT-orange?style=flat-square"/>
</p>

---

## Overview

**SocialStudio** is a comprehensive social media automation platform that combines AI-powered content generation, professional design tools, and multi-platform publishing capabilities. Built for marketers, content creators, and businesses looking to streamline their social media workflow.

---

## Features

### Design Studio

- **Canvas Editor** — Professional Fabric.js-based design canvas with layers, shapes, and text tools
- **AI Design Generation** — Generate branded design variations using GPT-4o and Unsplash integration
- **Template System** — Save, load, and reuse design templates
- **Background Removal** — AI-powered background removal using rembg
- **Video Rendering** — Create and edit video content with MoviePy

### AI Content Generation

- **Smart Captions** — Generate engaging captions with hashtags using OpenAI GPT & Google Gemini
- **Image Generation** — AI-generated visuals with Gemini 2.5 Flash image model
- **Watermarking** — Automatic logo watermarking with smart placement
- **Research Integration** — Deep research capabilities with Perplexity API for product/company insights

### Multi-Platform Social Publishing

| Platform      | Status    | Features                   |
| ------------- | --------- | -------------------------- |
| **Instagram** | Supported | Feed posts, Stories, Reels |
| **Facebook**  | Supported | Pages, Feed posts          |
| **Twitter/X** | Supported | Tweets, Media uploads      |
| **LinkedIn**  | Supported | Personal & Company posts   |
| **Threads**   | Supported | Text & Media posts         |
| **TikTok**    | Supported | Video publishing           |
| **Snapchat**  | Supported | Story publishing           |

### Media Downloader

- Download videos from **YouTube, Instagram, TikTok, Twitter/X** and more
- Support for multiple quality options
- Audio extraction capabilities
- Powered by yt-dlp and Apify scrapers

### Task Management

- **Scheduled Posting** — Queue and schedule posts across platforms
- **Celery Integration** — Background task processing
- **Usage Tracking** — Monitor API usage and costs

---

## Tech Stack

| Category             | Technologies                                      |
| -------------------- | ------------------------------------------------- |
| **Backend**          | FastAPI, Python 3.10+, SQLAlchemy (Async), Celery |
| **AI/ML**            | OpenAI GPT-4o, Google Gemini, Perplexity API      |
| **Database**         | SQLite (aiosqlite), Redis                         |
| **Media Processing** | Pillow, MoviePy, OpenCV, rembg                    |
| **Frontend**         | Jinja2 Templates, Fabric.js, Vanilla JS           |
| **Deployment**       | Docker, Azure, GitHub Actions CI/CD               |

---

## Installation

### Prerequisites

- Python 3.10+
- FFmpeg (for video processing)
- Redis (optional, for Celery)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/SocialStudio.git
cd SocialStudio

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

Create a `.env` file with the following keys:

```env
# Required
OPENAI_API_KEY=your_openai_key
GEMINI_API_KEY=your_gemini_key
SECRET_KEY=your_secret_key

# Social Platform OAuth
FACEBOOK_APP_ID=...
FACEBOOK_APP_SECRET=...
INSTAGRAM_APP_ID=...
INSTAGRAM_APP_SECRET=...
TWITTER_API_KEY=...
TWITTER_API_SECRET=...
LINKEDIN_CLIENT_ID=...
LINKEDIN_CLIENT_SECRET=...

# Optional
UNSPLASH_ACCESS_KEY=...
PERPLEXITY_API_KEY=...
APIFY_API_TOKEN=...
IMG_BB_API_KEY=...
```

---

## Usage

### Start the Application

**1. Run FastAPI Server**

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**2. Run Celery Worker (for background tasks)**

```bash
# Windows (with eventlet)
celery -A celery_app worker --loglevel=info --pool=eventlet

# Or use solo pool (no monkey patching required)
celery -A celery_app worker --loglevel=info --pool=solo
```

**3. Access the Application**

- **Dashboard**: `http://localhost:8000/`
- **Design Studio**: `http://localhost:8000/canvas`
- **Settings**: `http://localhost:8000/setting`

---

## API Reference

### Content Generation

| Endpoint                | Method | Description                     |
| ----------------------- | ------ | ------------------------------- |
| `/api/generate-preview` | POST   | Generate AI captions and images |
| `/api/generate/design`  | POST   | Generate design variations      |
| `/api/task/{task_id}`   | GET    | Get task details                |

### Social Publishing

| Endpoint                    | Method | Description                    |
| --------------------------- | ------ | ------------------------------ |
| `/auth/{platform}/start`    | GET    | Start OAuth flow               |
| `/auth/{platform}/callback` | GET    | OAuth callback handler         |
| `/api/manual-post`          | POST   | Publish to connected platforms |

### Media Operations

| Endpoint            | Method | Description             |
| ------------------- | ------ | ----------------------- |
| `/api/download`     | POST   | Download media from URL |
| `/api/remove-bg`    | POST   | Remove image background |
| `/api/video/render` | POST   | Render video content    |

### Research

| Endpoint       | Method | Description                      |
| -------------- | ------ | -------------------------------- |
| `/api/reviews` | POST   | Get AI-powered research insights |

---

## Platform Setup Guides

### Facebook/Instagram Setup

1. Create a Facebook App at [developers.facebook.com](https://developers.facebook.com)
2. Add **Facebook Login** and **Instagram Graph API** products
3. Configure OAuth redirect URIs
4. Get **App ID** and **App Secret**

### Twitter/X Setup

1. Create a project at [developer.twitter.com](https://developer.twitter.com)
2. Enable **OAuth 1.0a** with read/write permissions
3. Get **API Key**, **API Secret**, **Access Token**, and **Access Secret**

### LinkedIn Setup

1. Create an app at [LinkedIn Developer Portal](https://www.linkedin.com/developers)
2. Request **Sign In with LinkedIn** and **Share on LinkedIn** products
3. Configure OAuth 2.0 redirect URLs

### Generating Access Tokens

**Long-Lived Facebook Token:**

```
https://developers.facebook.com/tools/debug/accesstoken/
```

**Facebook Page Access Token:**

```
GET https://graph.facebook.com/v24.0/me/accounts?access_token=YOUR_USER_TOKEN
```

**Instagram Business Account ID:**

```bash
curl -X GET "https://graph.facebook.com/v21.0/me?fields=instagram_business_account&access_token=YOUR_PAGE_TOKEN"
```

---

## Docker Deployment

```bash
# Build the image
docker build -t socialstudio .

# Run with docker-compose
docker-compose -f docker-compose.prod.yml up -d
```

---

## Project Structure

```
SocialStudio/
├── main.py                 # FastAPI application entry point
├── celery_app.py           # Celery configuration
├── Database.py             # SQLAlchemy models & database setup
│
├── # Core Modules
├── SocialConnect.py        # OAuth & platform connections
├── PostGen.py              # AI content generation
├── DesignBuilder.py        # AI design generation
├── MediaSnag.py            # Media downloader
├── Researcher.py           # AI research integration
│
├── # Platform Posters
├── FBPoster.py             # Facebook posting
├── LinkedInPoster.py       # LinkedIn posting
├── XPoster.py              # Twitter/X posting
├── ManualPost.py           # Multi-platform posting
│
├── # Design & Media
├── CanvaTools.py           # Canvas operations
├── VideoRender.py          # Video processing
├── ImgGen.py               # Image generation
│
├── templates/              # Jinja2 HTML templates
├── static/                 # Static assets (CSS, JS, images)
├── Fonts/                  # Custom font files
└── my_templates/           # Design templates (JSON)
```

---

## CI/CD

This project includes automated deployment via **GitHub Actions** and **Azure Pipelines**.

See:

- [CI/CD Setup Guide](./CI_CD_SETUP.md)
- [Deployment Guide](./DEPLOYMENT_GUIDE.md)
- [GitHub Actions Setup](./GITHUB_ACTIONS_SETUP.md)

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) — Modern Python web framework
- [OpenAI](https://openai.com/) — GPT models for content generation
- [Google Gemini](https://deepmind.google/technologies/gemini/) — AI image generation
- [Fabric.js](http://fabricjs.com/) — Canvas manipulation library
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Media downloading

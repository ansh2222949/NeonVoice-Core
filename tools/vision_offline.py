"""
NeonAI — Offline Vision / Resume & ATS Analyzer
Supports: Images (via Ollama vision model) AND PDFs (via text extraction + LLM).
Works fully offline — no API key required.

Resume analysis provides:
  - ATS Score (0-100)
  - Section-by-section breakdown
  - Specific improvement suggestions
"""

import requests
import base64
import os
import re


OLLAMA_URL = "http://localhost:11434/api/generate"
VISION_MODEL = "llava"  # llava for image analysis


# =====================================================
# VISION MODEL CHECK
# =====================================================

def is_vision_available():
    """Check if Ollama has a vision model available."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = r.json().get("models", [])
            vision_models = ["llava", "llama3.2-vision", "bakllava", "moondream"]
            for m in models:
                name = m.get("name", "").lower()
                for vm in vision_models:
                    if vm in name:
                        return True, name
            return False, None
        return False, None
    except Exception:
        return False, None


def _get_text_model():
    """Get the best available text LLM from Ollama for resume analysis."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = r.json().get("models", [])
            # Prefer larger/smarter models for ATS analysis (excluding Qwen as it's meant for coding)
            preferred = ["llama3.2", "llama3", "mistral", "gemma"]
            for pref in preferred:
                for m in models:
                    if pref in m.get("name", "").lower():
                        return m["name"]
            # Fallback to first available model
            if models:
                return models[0]["name"]
    except Exception:
        pass
    return "llama3.2:3b"  # default


# =====================================================
# PDF TEXT EXTRACTION
# =====================================================

def extract_text_from_pdf(pdf_base64=None, pdf_path=None):
    """
    Extract text from a PDF file using pypdf.
    Returns the extracted text string or None.
    """
    try:
        from pypdf import PdfReader
        import io

        if pdf_base64:
            # Strip data URL prefix if present
            if "," in pdf_base64:
                pdf_base64 = pdf_base64.split(",", 1)[1]
            pdf_bytes = base64.b64decode(pdf_base64)
            reader = PdfReader(io.BytesIO(pdf_bytes))
        elif pdf_path:
            if not os.path.exists(pdf_path):
                return None
            reader = PdfReader(pdf_path)
        else:
            return None

        if reader.is_encrypted:
            return None

        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"

        # Clean text
        full_text = re.sub(r"\s+", " ", full_text).strip()
        return full_text if len(full_text) > 20 else None

    except Exception as e:
        print(f"[Vision] PDF extraction error: {e}")
        return None


# =====================================================
# ATS RESUME SCORING PROMPT
# =====================================================

ATS_RESUME_PROMPT = """You are an expert ATS (Applicant Tracking System) resume analyzer and career advisor.

Your task is to analyze the following resume text for the target role: {target_role}

## RESUME TEXT:
{resume_text}

## YOUR ANALYSIS MUST INCLUDE:

### 📊 ATS SCORE: X/100
Give a realistic ATS compatibility score for the "{target_role}" position.

### 📋 Section-by-Section Breakdown:
Rate each section (1-10) and explain:
1. **Contact Information** - Is it complete? (Name, email, phone, LinkedIn)
2. **Professional Summary** - Is there a strong summary/objective?
3. **Work Experience** - Are achievements quantified? Action verbs used?
4. **Skills** - Are relevant technical and soft skills for {target_role} listed?
5. **Education** - Is it properly formatted?
6. **Keywords & ATS Compatibility** - Are industry keywords present?
7. **Formatting** - Is it clean, consistent, ATS-parseable?

### ✅ Strengths:
List 3-5 specific things the resume does well.

### ⚠️ Improvement Suggestions:
List 5-8 specific, actionable suggestions to improve the resume specifically for a {target_role} role.
Each suggestion should start with a verb (Add, Remove, Rewrite, Include, etc.)

### 🎯 Missing Keywords:
Suggest 5-10 common industry keywords for {target_role} that should be added.

### 💡 Pro Tips:
Give 2-3 expert tips for better ATS scoring.

Be honest, specific, and actionable. Do NOT be generic."""


# =====================================================
# ANALYZE IMAGE (Vision Model)
# =====================================================

def analyze_image(image_path=None, image_base64=None, query="Analyze this image in detail"):
    """
    Analyze an image using local Ollama vision model.
    For resume images, provides ATS scoring and suggestions.
    """
    import time as _time
    _start = _time.time()

    print(f"\n{'='*50}")
    print(f"📸 [Vision] Image Analysis Request")
    print(f"   Query: {query[:80]}{'...' if len(query) > 80 else ''}")

    def process_and_encode(raw_data):
        import io
        img_bytes = raw_data
        # Check size (5MB limit)
        if len(img_bytes) > 5 * 1024 * 1024:
            print(f"   ⚠️ Image > 5MB. Attempting resize...")
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(img_bytes))
                # Resize if significantly large
                img.thumbnail((1280, 1280))
                output = io.BytesIO()
                img.save(output, format="JPEG", quality=85)
                img_bytes = output.getvalue()
                print(f"   ✅ Resized to {len(img_bytes)/1024:.1f}KB")
            except Exception as e:
                print(f"   ❌ Resize failed: {e}")
        return base64.b64encode(img_bytes).decode("utf-8")

    # Get base64 data
    if image_base64:
        if "," in image_base64:
            raw_img = base64.b64decode(image_base64.split(",", 1)[1])
        else:
            raw_img = base64.b64decode(image_base64)
        img_data = process_and_encode(raw_img)
    elif image_path:
        if not os.path.exists(image_path):
            print(f"   ❌ Image file not found: {image_path}")
            return {"success": False, "response": "Image file not found.", "model": None}
        with open(image_path, "rb") as f:
            raw_img = f.read()
        img_data = process_and_encode(raw_img)
    else:
        print(f"   ❌ No image provided")
        return {"success": False, "response": "No image provided.", "model": None}

    # Check available vision model
    available, model_name = is_vision_available()
    if not available:
        print(f"   ❌ No vision model found on Ollama")
        print(f"{'='*50}")
        return {
            "success": False,
            "response": (
                "No vision model found. Please install one:\n"
                "Run: `ollama pull llava` or `ollama pull llama3.2-vision`"
            ),
            "model": None,
        }
    print(f"   Model: {model_name}")

    # Build prompt based on query type
    is_resume = any(kw in query.lower() for kw in [
        "resume", "cv", "curriculum", "job application", "work experience", "ats"
    ])

    if is_resume:
        # Extra: Extract target role from query
        role_match = re.search(r"for\s+(?:a\s+|an\s+)?(.+?)\s+(?:job|role|position|work)", query, re.I)
        target_role = role_match.group(1).strip() if role_match else "General Professional"

        full_query = (
            f"You are an expert ATS resume analyzer. Analyze this resume for a {target_role} role. "
            "Extract ALL text and evaluate:\n\n"
            "1. Give an ATS Score: X/100\n"
            "2. Rate each section (Contact, Summary, Experience, Skills, Education) 1-10\n"
            "3. List Strengths (3-5 specific points)\n"
            f"4. List Improvement Suggestions (5-8 actionable items) specifically for {target_role}\n"
            f"5. Suggest Missing Keywords for better ATS ranking in {target_role}\n"
            "6. Give Pro Tips for improvement\n\n"
            "Be specific and actionable. Do NOT be generic."
        )
    else:
        full_query = (
            f"You are NeonAI, a friendly and smart AI assistant. "
            f"Analyze this image carefully and respond to: {query}"
        )

    payload = {
        "model": model_name,
        "prompt": full_query,
        "images": [img_data],
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 1000,
        },
    }

    try:
        print(f"   ⏳ Sending to Ollama vision model...")
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if res.status_code != 200:
            return {
                "success": False,
                "response": f"Vision model request failed (HTTP {res.status_code}).",
                "model": model_name,
            }
        try:
            data = res.json()
        except Exception:
            return {
                "success": False,
                "response": "Vision model returned non-JSON response.",
                "model": model_name,
            }
        elapsed = round(_time.time() - _start, 2)

        if "response" in data:
            resp_len = len(data["response"].strip())
            print(f"   ✅ Response received ({resp_len} chars) in {elapsed}s")
            print(f"{'='*50}")
            return {
                "success": True,
                "response": data["response"].strip(),
                "model": model_name,
            }
        print(f"   ❌ Empty response from vision model ({elapsed}s)")
        print(f"{'='*50}")
        return {
            "success": False,
            "response": "Vision model returned empty response.",
            "model": model_name,
        }

    except requests.Timeout:
        print(f"   ❌ Vision analysis timed out")
        print(f"{'='*50}")
        return {"success": False, "response": "Vision analysis timed out. Try a smaller image.", "model": model_name}
    except requests.ConnectionError:
        print(f"   ❌ Cannot connect to Ollama")
        print(f"{'='*50}")
        return {"success": False, "response": "Cannot connect to Ollama. Make sure it is running.", "model": None}
    except Exception as e:
        print(f"   ❌ Vision error: {e}")
        print(f"{'='*50}")
        return {"success": False, "response": f"Vision error: {e}", "model": None}


# =====================================================
# ANALYZE PDF RESUME (Text Extraction + LLM)
# =====================================================

def analyze_pdf_resume(pdf_base64=None, pdf_path=None, query="Analyze this resume"):
    """
    Analyze a PDF resume using text extraction + local LLM.
    Returns ATS score, breakdown, and suggestions.
    """
    import time as _time
    _start = _time.time()

    print(f"\n{'='*50}")
    print(f"📄 [Vision/ATS] PDF Resume Analysis Request")
    print(f"   Query: {query[:80]}{'...' if len(query) > 80 else ''}")

    # Extract text from PDF
    resume_text = extract_text_from_pdf(pdf_base64=pdf_base64, pdf_path=pdf_path)

    if not resume_text:
        print(f"   ❌ Could not extract text from PDF")
        print(f"{'='*50}")
        return {
            "success": False,
            "response": "Could not extract text from PDF. The file may be empty, encrypted, or image-based.\n"
                        "💡 Tip: For image-based PDFs (scanned), use the image upload instead.",
            "model": None,
        }

    print(f"   Extracted text: {len(resume_text)} chars")

    # Extra: Extract target role from query
    role_match = re.search(r"for\s+(?:a\s+|an\s+)?(.+?)\s+(?:job|role|position|work)", query, re.I)
    target_role = role_match.group(1).strip() if role_match else "General Professional"

    # Truncate if too long (prevent overloading the LLM)
    if len(resume_text) > 4000:
        resume_text = resume_text[:4000] + "\n...(truncated)"

    # Build the ATS analysis prompt
    prompt = ATS_RESUME_PROMPT.format(resume_text=resume_text, target_role=target_role)

    # Use text LLM (not vision model - faster and more accurate for text)
    model_name = _get_text_model()
    print(f"   Model: {model_name}")
    print(f"   ⏳ Analyzing resume...")

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_ctx": 4096,
            "num_predict": 1000,
        },
    }

    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=120)
        if res.status_code != 200:
            return {
                "success": False,
                "response": f"Resume analysis request failed (HTTP {res.status_code}).",
                "model": model_name,
            }
        try:
            data = res.json()
        except Exception:
            return {
                "success": False,
                "response": "Resume analysis returned non-JSON response.",
                "model": model_name,
            }

        elapsed = round(_time.time() - _start, 2)
        if "response" in data:
            resp_len = len(data["response"].strip())
            print(f"   ✅ ATS analysis complete ({resp_len} chars) in {elapsed}s")
            print(f"{'='*50}")
            return {
                "success": True,
                "response": data["response"].strip(),
                "model": model_name,
            }
        print(f"   ❌ LLM returned empty response ({elapsed}s)")
        print(f"{'='*50}")
        return {
            "success": False,
            "response": "LLM returned empty response.",
            "model": model_name,
        }

    except requests.Timeout:
        print(f"   ❌ Analysis timed out")
        print(f"{'='*50}")
        return {"success": False, "response": "Analysis timed out. Try again.", "model": model_name}
    except requests.ConnectionError:
        print(f"   ❌ Cannot connect to Ollama")
        print(f"{'='*50}")
        return {"success": False, "response": "Cannot connect to Ollama. Make sure it is running.", "model": None}
    except Exception as e:
        print(f"   ❌ Analysis error: {e}")
        print(f"{'='*50}")
        return {"success": False, "response": f"Analysis error: {e}", "model": None}

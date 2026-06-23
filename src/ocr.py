import re
import random
from datetime import datetime, timezone

# Keywords to look for in text files to generate tags
KEYWORDS = {
    "invoice": "invoice",
    "receipt": "receipt",
    "report": "report",
    "contract": "contract",
    "agreement": "contract",
    "resume": "resume",
    "cv": "resume",
    "important": "urgent",
    "urgent": "urgent",
    "financial": "financial",
    "budget": "financial",
    "meeting": "meeting",
    "project": "project",
    "confidential": "confidential"
}

def process_document(bucket_name: str, file_name: str, file_size: int, content_type: str, file_content: bytes) -> dict:
    """
    Simulates OCR and metadata extraction from a document.
    
    If the file is a text file, it extracts words, searches for keywords to generate tags,
    and returns a preview. Otherwise, it generates mock/randomized metadata.
    """
    tags = []
    word_count = 0
    ocr_preview = ""
    
    # Check if the file is a text file based on content type or extension
    is_text = False
    if content_type and "text/plain" in content_type:
        is_text = True
    elif file_name.lower().endswith(".txt"):
        is_text = True

    if is_text:
        try:
            # Decode the text content
            text_str = file_content.decode("utf-8", errors="ignore")
            
            # Extract OCR text preview (first 200 characters)
            ocr_preview = text_str[:200].strip()
            
            # Simple word count using regex
            words = re.findall(r"\b\w+\b", text_str.lower())
            word_count = len(words)
            
            # Tag extraction based on keywords
            for word in words:
                if word in KEYWORDS:
                    tag = KEYWORDS[word]
                    if tag not in tags:
                        tags.append(tag)
            
            # Add text format tag
            tags.append("text-format")
            
        except Exception as e:
            # Fallback if decoding fails
            ocr_preview = f"Error reading text content: {str(e)}"
            word_count = 0
            tags = ["read-error"]
    else:
        # For non-text files, simulate OCR
        word_count = random.randint(50, 800)
        
        # Determine format tag
        ext = file_name.split(".")[-1].lower() if "." in file_name else "unknown"
        format_tag = f"{ext}-format" if ext != "unknown" else "binary-format"
        tags = ["mock-ocr", format_tag]
        
        # Create simulated OCR preview
        ocr_preview = f"[Simulated OCR Preview for non-text file '{file_name}']. Extracted {word_count} mock words."

    # If no custom tags extracted, add a general tag
    if not any(t for t in tags if t not in ["text-format", "mock-ocr", f"{file_name.split('.')[-1].lower()}-format" if "." in file_name else ""]):
        tags.append("general")

    # Construct the metadata record matching the BigQuery schema
    metadata = {
        "filename": file_name,
        "bucket": bucket_name,
        "size": file_size,
        "content_type": content_type or "application/octet-stream",
        "word_count": word_count,
        "tags": tags,
        "ocr_text_preview": ocr_preview,
        "process_timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return metadata

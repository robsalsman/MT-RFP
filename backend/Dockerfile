FROM python:3.12-slim

# Uncomment for OCR fallback on scanned RFP PDFs:
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     tesseract-ocr poppler-utils && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# For OCR, also: pip install pytesseract pdf2image

COPY app ./app
ENV MTRFP_DATA_DIR=/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

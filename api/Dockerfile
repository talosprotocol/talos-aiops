FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/

# For workspace mode, we might need to install from /mnt/workspace
# This is handled by a startup script or manual pip install if needed, 
# strictly using -e /mnt/workspace/talos-sdk-py

CMD ["python", "src/main.py"]

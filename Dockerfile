# Base imagε
FROM python:3.13-slim

# Working directory
WORKDIR /app

# Dependencies (cached layer) 
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code 
COPY . .

# ── Persistent data location 
ENV DATA_DIR=/app/data

# ── Network 
# Streamlit serves on port 8501.
EXPOSE 8501

# ── Start command 
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]

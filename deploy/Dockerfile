FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY fantasy_draft ./fantasy_draft
COPY data ./data
COPY run_dashboard.py .
# The draft files live in /state, a volume, so a rebuilt image never touches the draft
RUN mkdir /state
CMD ["python", "run_dashboard.py", "--host", "0.0.0.0", "--port", "8001", "--no-browser", \
     "--draft-file", "/state/saved_draft.json", "--mock-file", "/state/saved_mock_draft.json"]

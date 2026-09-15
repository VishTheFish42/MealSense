# Cloud Run deployment (tasks.md Phase 7). Cloud Run injects PORT at
# runtime and expects the container to listen on 0.0.0.0:$PORT — it is
# NOT necessarily 8080 in practice, so this must stay dynamic, not
# hardcoded, even though 8080 is the documented default.
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first, separately from the app code, so Docker's
# layer cache only reinstalls packages when requirements.txt actually
# changes, not on every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Shell form (not exec-form array syntax) is required here specifically
# so ${PORT:-8080} actually gets expanded — exec-form CMD does not invoke
# a shell and would pass the literal string through unexpanded.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}

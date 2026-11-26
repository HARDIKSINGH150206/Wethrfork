# Grader image for the judge rehearsal (local testing only). It is the judge image plus the official kit and requests,
# so the forecast calls are made with the organisers' own client code. The server never runs in this image: it runs in
# wethrfork-judge:py311, which has only the allowed libraries and no kit.
#   docker build -f docker/grader.Dockerfile -t wethrfork-grader:py311 vendor/
FROM wethrfork-judge:py311
COPY monsoon_r1_kit-1.0.0-py3-none-any.whl /tmp/
RUN pip install --no-cache-dir requests /tmp/monsoon_r1_kit-1.0.0-py3-none-any.whl

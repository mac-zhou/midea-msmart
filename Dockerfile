# Build step
FROM python:3.11-alpine
RUN apk add --update git
RUN pip install build
WORKDIR /msmart-build
COPY . .
RUN python -m build

# Production step
FROM python:3.11-alpine
COPY --from=0 /msmart-build/dist/*.whl /tmp
RUN pip install /tmp/*.whl
ENTRYPOINT ["/usr/local/bin/midea-discover"]
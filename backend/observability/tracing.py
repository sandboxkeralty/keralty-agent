from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from config import settings

def setup_tracing(app):
    if not settings.OTEL_ENABLED:
        return

    provider = TracerProvider()
    processor = BatchSpanProcessor(CloudTraceSpanExporter(project_id=settings.GOOGLE_CLOUD_PROJECT))
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)

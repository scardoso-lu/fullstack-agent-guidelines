---
model: sonnet
effort: high
---

# Observability — OpenTelemetry

Use when adding tracing, metrics, or structured logging to either stack, or when wiring up an observability backend (Jaeger, Grafana Tempo, Honeycomb, Datadog). Covers the OTel Collector pattern, automatic instrumentation for FastAPI and SQLAlchemy, Next.js `instrumentation.ts`, custom spans on use case boundaries, and docker-compose integration.

OpenTelemetry is the vendor-neutral CNCF standard for traces, metrics, and logs. Services emit telemetry to a local **Collector**; the Collector forwards to whichever backend you choose. Swapping backends (Jaeger → Tempo → Honeycomb) means changing the Collector config — no application code changes.

---

## The Three Signals

| Signal | What it answers | Primary tool |
|---|---|---|
| **Traces** | Where did time go? Which service/query was slow? | Spans, trace IDs |
| **Metrics** | How many? How fast? How full? | Counters, histograms, gauges |
| **Logs** | What happened at this exact moment? | Structured log lines |

Emit all three from the Collector — never wire application code directly to a monitoring backend.

---

## docker-compose Addition

Add the Collector as a service. Both backend and frontend send to it on `4317` (gRPC) or `4318` (HTTP).

**`docker-compose.yml — add to the existing services section`**
```yaml
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.100.0
    command: ["--config=/etc/otelcol/config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otelcol/config.yaml:ro
    ports:
      - "4317:4317"   # OTLP gRPC — backend
      - "4318:4318"   # OTLP HTTP — frontend / browser
    networks:
      - app-net
    restart: unless-stopped
```

```yaml
# otel-collector-config.yaml — committed to the repo root
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318
        cors:
          allowed_origins: ["http://localhost:3000"]

processors:
  batch:
    timeout: 5s
  memory_limiter:
    limit_mib: 256

exporters:
  debug:
    verbosity: detailed   # logs every span to stdout — swap for your backend

  # Example: forward to Jaeger
  # otlp/jaeger:
  #   endpoint: jaeger:4317
  #   tls:
  #     insecure: true

  # Example: forward to Grafana Tempo
  # otlp/tempo:
  #   endpoint: tempo:4317
  #   tls:
  #     insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [debug]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [debug]
    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [debug]
```

To switch observability backends, edit only `otel-collector-config.yaml` — application code never changes.

---

## Backend — Python / FastAPI

### Install

```bash
uv add \
  opentelemetry-api \
  opentelemetry-sdk \
  opentelemetry-instrumentation-fastapi \
  opentelemetry-instrumentation-sqlalchemy \
  opentelemetry-exporter-otlp-proto-grpc
```

### Telemetry Bootstrap

**`src/telemetry.py`**
```python
import os
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_telemetry(service_name: str) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    resource = Resource.create({"service.name": service_name})

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, insecure=True),
        export_interval_millis=30_000,
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
```

**`src/main.py`**
```python
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from src.telemetry import setup_telemetry
from src.config.settings import get_config

def create_app() -> FastAPI:
    config = get_config()
    setup_telemetry(service_name=config.SERVICE_NAME)

    app = FastAPI()

    # Automatic instrumentation — every HTTP request becomes a span
    FastAPIInstrumentor.instrument_app(app)

    # Automatic instrumentation — every SQL query becomes a child span
    SQLAlchemyInstrumentor().instrument(engine=engine)

    return app
```

### Custom Spans on Use Case Boundaries

Add spans at use case boundaries and on slow operations. Do not add spans inside repositories — the SQLAlchemy instrumentor already covers DB calls.

**`src/application/use_cases/product/get_by_id.py`**
```python
from opentelemetry import trace
from opentelemetry.trace import StatusCode

tracer = trace.get_tracer(__name__)


class GetProductByIdUseCase:
    def __init__(self, repo: ProductRepositoryInterface) -> None:
        self.repo = repo

    async def execute(self, product_id: int) -> ProductDto:
        with tracer.start_as_current_span("product.get_by_id") as span:
            span.set_attribute("product.id", product_id)

            product = await self.repo.get_by_id(product_id)

            if product is None:
                span.set_status(StatusCode.ERROR, "product not found")
                raise NotFoundError(f"Product {product_id} not found")

            span.set_attribute("product.name", product.name)
            return ProductDto.from_entity(product)
```

### Span Naming Convention

```
<domain>.<operation>         → product.get_by_id
<domain>.<operation>.<detail> → product.search.filtered
```

Keep span names stable and low-cardinality. Never include IDs or user data in span names — use `span.set_attribute()` for values.

### Environment Variables

**`.env.backend`**
```bash
OTEL_SERVICE_NAME=my-backend
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_TRACES_SAMPLER=parentbased_always_on   # sample all in dev; use ratio in prod
```

---

## Frontend — Next.js

Next.js 15 has stable built-in OpenTelemetry support via `instrumentation.ts`. No manual SDK wiring in page components.

### Install

```bash
npm install \
  @opentelemetry/sdk-node \
  @opentelemetry/auto-instrumentations-node \
  @opentelemetry/exporter-trace-otlp-http \
  @opentelemetry/exporter-metrics-otlp-http \
  @opentelemetry/sdk-metrics
```

### `instrumentation.ts`

```ts
// instrumentation.ts — root of the Next.js project (not inside src/)
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  const { NodeSDK } = await import("@opentelemetry/sdk-node");
  const { Resource } = await import("@opentelemetry/resources");
  const { OTLPTraceExporter } = await import(
    "@opentelemetry/exporter-trace-otlp-http"
  );
  const { OTLPMetricExporter } = await import(
    "@opentelemetry/exporter-metrics-otlp-http"
  );
  const { PeriodicExportingMetricReader } = await import(
    "@opentelemetry/sdk-metrics"
  );
  const { getNodeAutoInstrumentations } = await import(
    "@opentelemetry/auto-instrumentations-node"
  );

  const sdk = new NodeSDK({
    resource: new Resource({
      "service.name": process.env.OTEL_SERVICE_NAME ?? "my-frontend",
    }),
    traceExporter: new OTLPTraceExporter({
      url: `${process.env.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces`,
    }),
    metricReader: new PeriodicExportingMetricReader({
      exporter: new OTLPMetricExporter({
        url: `${process.env.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/metrics`,
      }),
    }),
    instrumentations: [
      getNodeAutoInstrumentations({
        "@opentelemetry/instrumentation-fs": { enabled: false }, // too noisy
      }),
    ],
  });

  sdk.start();
}
```

`instrumentation.ts` runs once when the Next.js server starts — before any route handler. Dynamic imports are required to avoid bundling server-only packages into the client.

### Custom Spans in Server Components and Route Handlers

```ts
// app/[lang]/(private)/admin/products/page.tsx
import { trace } from "@opentelemetry/api";

const tracer = trace.getTracer("frontend");

export default async function ProductsPage() {
  return tracer.startActiveSpan("products.page.load", async (span) => {
    try {
      const products = await ProductService.paged(1, 20);
      span.setAttribute("products.count", products.total);
      return <ProductListView products={products.data} />;
    } catch (err) {
      span.recordException(err as Error);
      span.setStatus({ code: SpanStatusCode.ERROR });
      throw err;
    } finally {
      span.end();
    }
  });
}
```

### Environment Variables

**`.env.frontend`**
```bash
OTEL_SERVICE_NAME=my-frontend
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318   # HTTP port for Next.js
```

---

## Trace Context Propagation

When the frontend calls the backend, pass the trace context via the `traceparent` header so both services appear in the same trace:

```ts
// src/services/api.ts
import { context, propagation } from "@opentelemetry/api";

export async function authApi<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  // Inject W3C TraceContext headers (traceparent, tracestate)
  propagation.inject(context.active(), headers);

  const response = await fetch(url, { ...options, credentials: "include", headers });
  if (!response.ok) throw new ApiError(response.status, await response.text());
  return response.json() as Promise<T>;
}
```

FastAPI's automatic instrumentation reads the `traceparent` header and continues the trace. Both the frontend span and the backend span appear under the same root trace in your observability backend.

---

## What NOT to Put in Spans

```python
# ❌ WRONG — PII and secrets in span attributes
span.set_attribute("user.password", data.password)
span.set_attribute("user.email", user.email)
span.set_attribute("jwt.token", token)

# ✅ CORRECT — identifiers only; no personal data or secrets
span.set_attribute("user.id", user.id)
span.set_attribute("user.role", user.role)
```

Span data flows to your observability backend and may be retained for months. Treat it like a log — PII and secrets must never appear.

---

## Anti-Patterns

```python
# ❌ WRONG — importing a vendor SDK directly in application code
import datadog
datadog.initialize(api_key=os.getenv("DD_API_KEY"))
# Now the whole app is coupled to Datadog — 50 files to change if you switch

# ✅ CORRECT — import opentelemetry only; configure the exporter in one place
from opentelemetry import trace
tracer = trace.get_tracer(__name__)
# Switching backends = changing otel-collector-config.yaml only

# ❌ WRONG — span per repository method; creates noise without insight
async def get_by_id(self, id: int) -> Product | None:
    with tracer.start_as_current_span("repository.get_by_id"):  # SQLAlchemy already does this
        ...

# ✅ CORRECT — span at use case boundary; DB spans come from auto-instrumentation

# ❌ WRONG — not ending spans on error
span = tracer.start_span("operation")
result = await risky_call()   # if this throws, span never ends → memory leak
# ✅ CORRECT — always use context manager or try/finally
with tracer.start_as_current_span("operation") as span:
    result = await risky_call()
```

---

## Quick Checklist

- [ ] `otel-collector` service added to `docker-compose.yml` on `app-net`
- [ ] `otel-collector-config.yaml` committed; exporter section points to your backend
- [ ] Backend: `setup_telemetry()` called before `FastAPIInstrumentor.instrument_app()`
- [ ] Backend: `SQLAlchemyInstrumentor().instrument(engine=engine)` wired at startup
- [ ] Backend: custom spans only at use case boundaries — not inside repositories
- [ ] Frontend: `instrumentation.ts` at project root (not `src/`); guarded by `NEXT_RUNTIME === "nodejs"`
- [ ] Frontend API client injects W3C `traceparent` header via `propagation.inject()`
- [ ] `OTEL_SERVICE_NAME` set in both `.env.backend` and `.env.frontend`
- [ ] Span attributes contain IDs and roles only — never PII, passwords, or tokens
- [ ] No vendor SDK imported directly in application code — OTel API only

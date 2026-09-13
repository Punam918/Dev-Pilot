"""Real OTLP HTTP exporter to a local capture endpoint, not a deployed Collector/Tempo."""
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import pytest
from devpilot.config import Settings
from devpilot.telemetry import Telemetry


def test_otlp_http_exports_only_reviewed_metadata_and_no_exception_text(tmp_path):
    pytest.importorskip('opentelemetry.sdk')
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
    payloads=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payloads.append(self.rfile.read(int(self.headers['Content-Length'])))
            self.send_response(200);self.send_header('Content-Type','application/x-protobuf');self.end_headers()
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    config=Settings(_env_file=None,workspace_dir=tmp_path/'work',data_dir=tmp_path/'state',otel_enabled=True,
        otel_endpoint=f'http://127.0.0.1:{server.server_port}/v1/traces')
    tel=Telemetry(config)
    try:
        with tel.span('model.complete',provider='openai',prompt='SECRET-PROMPT',repository='/private/path'):
            pass
        with pytest.raises(RuntimeError):
            with tel.span('mcp.tool',tool='SECRET-UNKNOWN-TOOL'):
                raise RuntimeError('SECRET-EXCEPTION')
        tel.close()
    finally:
        server.shutdown();server.server_close();worker.join(timeout=5)
    assert payloads
    spans=[]
    for payload in payloads:
        assert b'SECRET' not in payload and b'/private' not in payload
        message=ExportTraceServiceRequest.FromString(payload)
        for resource in message.resource_spans:
            for scope in resource.scope_spans:spans.extend(scope.spans)
    assert {s.name for s in spans}=={'model.complete','mcp.tool'}
    assert all(not span.events for span in spans)
    error=next(s for s in spans if s.name=='mcp.tool')
    assert error.status.code==2
    assert not error.status.message
    attrs={a.key:a.value.string_value for a in error.attributes}
    assert attrs=={'tool':'unknown'}


def test_credentials_must_be_distinct(tmp_path):
    with pytest.raises(ValueError,match='must be different'):
        Settings(_env_file=None,workspace_dir=tmp_path/'work',data_dir=tmp_path/'state',
                 api_token='x'*32,metrics_token='x'*32)

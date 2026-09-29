# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Lò Văn Long
- **MSSV:** 2A202602541
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/getlmt/K4-L3-DAY13-LoVanLong-2A202602541-Monitoring-LLMOps
- **Commit SHA cuối:** c849ae31ad6785d497bec048096c06fd9f0569cb (commit chứa toàn bộ source, config, evidence; commit sau đó chỉ ghi SHA vào report)
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-2A202602541`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.txt` (commit cuối); `evidence/01-pytest.png` (sau CP1) |
| Log validator | `evidence/02-log-validator.txt` (commit cuối); `evidence/02-log-validator.png` (sau CP1) |
| Dashboard validator | `evidence/03-dashboard-validator.txt` (commit cuối); `evidence/03-dashboard-validator.png` (sau CP1) |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview-1.png`, `evidence/11-dashboard-overview-2.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 (commit cuối, 193 record, 97 correlation ID) | Có 10 correlation ID, 0 record thiếu field, đủ enrichment |
| `validate_dashboard.py` | 6/6 panel hợp lệ | 6/6 panel hợp lệ (commit cuối) | Chỉ kiểm tra cấu trúc YAML, chưa phải dashboard runtime |
| `pytest` | 22 passed | 27 passed (commit cuối) | Thêm 2 test PII (CCCD/thẻ, passport) và 3 test tính toán dashboard; mở rộng test generation |
| Số traces hợp lệ | 10 (chỉ root, chưa có child) | hơn 100 traces có root + retrieval + generation trong project cá nhân | Mỗi trace có correlation_id, user hash, session, feature, model, env |
| Số PII leak | 0 | 0 (commit cuối) | Validator không phát hiện PII nguyên văn |
| Latency P95 / TTFT P95 | | 153 ms / 50 ms (baseline warm, dashboard) | Cold start 1.1-2.1 s chỉ ảnh hưởng vài request đầu sau restart |
| Retrieval success rate | | 100% | Chưa bật incident tool_fail |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` gọi `clear_contextvars()` đầu mỗi request, lấy header `x-request-id` hoặc sinh `req-<8 hex>`, rồi `bind_contextvars(correlation_id=...)` để mọi log trong request đều mang ID này. ID cũng được lưu ở `request.state`, trả về trong response header `x-request-id` cùng `x-response-time-ms`, và truyền vào `agent.run` để nối với trace.
- **Các metadata được ghi vào structured log:** `ts`, `level`, `service`, `event`, `correlation_id`, `user_id_hash` (SHA-256 cắt 12 ký tự, không log user_id gốc), `session_id`, `feature`, `model`, `env`; các event `response_sent` có thêm latency, ttft, tokens, cost, quality_score.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` được đặt trước `JsonlFileProcessor` trong chuỗi processor của structlog nên dữ liệu đã được che trước khi ghi file. `summarize_text` cũng scrub trước khi tạo preview. `app/pii.py` che email, số điện thoại VN, CCCD, thẻ và passport bằng `[REDACTED_<LOẠI>]`.
- **Cách kiểm chứng kết quả:** Đổi tên `data/logs.jsonl` thành `data/logs.baseline.jsonl`, chạy load test mới, rồi `python scripts/validate_logs.py` (100/100). Gửi thủ công một `/chat` chứa email, số điện thoại và CCCD, log ghi `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]` (`evidence/05-pii-redaction.png`). `curl -i /health` cho thấy header `x-request-id`. Evidence: `evidence/01` đến `05`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Trace nằm trong project `day13-k4-l3a-2A202602541` thuộc organization của tôi, dùng key của chính project này trong `.env`. Mỗi trace có `correlation_id` khớp với `x-request-id` trong response và `data/logs.jsonl`, user_id đã hash (ví dụ `105a9cef3903`), environment `dev`.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` (type agent, trace name `day13-agent-request`) có 2 con: `retrieval` (type retriever, input là `query_preview` đã scrub, output là `doc_count`) và `llm-generation` (type generation, có model `claude-sonnet-4-5`, prompt managed, usage input/output, cost input/output/total, completion start time để tính TTFT). Input/output chỉ là bản tóm tắt đã scrub PII. Ví dụ trace `962bdef351e606d682b54a77939c7830`: root 414 ms, retrieval ~0 ms, generation 152 ms, cost $0.001719, 137 tokens (`evidence/07-trace-waterfall.png`, `evidence/08-trace-metadata.png`).
- **Cách nối trace với log:** Middleware sinh `correlation_id` và truyền vào `agent.run`; root trace ghi `correlation_id` trong metadata (propagate xuống các observation con). Từ một dòng log trong `data/logs.jsonl` lấy `correlation_id`, rồi tìm trace có metadata `correlation_id` giống vậy trên Langfuse.
- **Prompt name:** `day13-chat` (text prompt, biến `{{feature}}`, `{{docs}}`, `{{message}}`).
- **Version/label baseline:** version 1, labels `baseline` + `production`.
- **Version/label candidate:** version 2 (thêm dòng `Answer in at most 3 sentences.`), label `candidate`.
- **Trace ID của mỗi version:** cùng input "How should alerts be designed?":
  - `LANGFUSE_PROMPT_LABEL=baseline` → trace `ff4878189d88fcbb78c840ce9493c1f9` (`req-baseline`, prompt_version 1).
  - `LANGFUSE_PROMPT_LABEL=candidate` → trace `ad677b77893335c96c6dc8471823f69f` (`req-candidate`, prompt_version 2).
  - Sau khi promote `production` sang v2 → trace `e40b51a5a4ce2b8aa3df2077408b428b` (`req-prod-v2`, label production, version 2).
  - Sau khi rollback `production` về v1 → trace `b09c89b9516d7648f83a75e929251372` (`req-rollback-v1`, label production, version 1).
- **Cách promote và rollback `production`:** Gắn label `production` cho v2 (Langfuse tự gỡ label khỏi v1), chạy request với `LANGFUSE_PROMPT_LABEL=production` và thấy version 2. Rollback bằng cách gắn lại `production` cho v1. Lưu ý: app cache prompt 60 giây và SDK trả bản cache cũ trong lúc refresh ngầm, nên request ngay sau rollback (`req-prod-v1`, trace `a2beb12ddb5de8d087b8db64adc26243`) vẫn dùng v2; sau khi restart app (cache sạch) request `req-rollback-v1` dùng đúng v1. Khi rollback thật cần tính đến độ trễ cache này hoặc restart/invalidate cache. Evidence: `evidence/09-prompt-versions.png`, `evidence/10-prompt-rollback.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard Streamlit (`dashboard/app.py`, chạy bằng `streamlit run dashboard/app.py`) đọc `data/logs.jsonl` và `config/dashboard.yaml`, time range 60 phút, tự refresh 30 giây. Sáu panel: (1) Latency P50/P95/P99 và TTFT P95 (ms), threshold P95 ≤ 3000 ms; (2) Traffic (requests/phút), threshold ≥ 1; (3) Error rate (%) kèm breakdown theo `error_type` và retrieval success, threshold error ≤ 2%; (4) Cost theo phút và tổng (USD), threshold ≤ 2.5; (5) Input/output tokens, threshold ≤ 50000 mỗi field; (6) Quality proxy (0-1), threshold ≥ 0.75. Mỗi panel có đơn vị và đường threshold màu đỏ. Baseline đo được: P50 152 ms, P95 153 ms, P99 435 ms, TTFT P95 50 ms, 80 request (6.15 req/phút), error 0%, retrieval success 100%, cost $0.1682, tokens 2,704 vào / 10,675 ra, quality 0.88. Evidence: `evidence/11-dashboard-overview-1.png`, `evidence/11-dashboard-overview-2.png`.
- **SLO và lý do chọn:** `fast_successful_requests`: 99.5% request trong 28 ngày phải được trả lời (`response_sent`) với `latency_ms <= 1500`. Tôi giảm ngưỡng từ 3000 ms xuống 1500 ms dựa trên baseline (P95 khoảng 153 ms khi app warm, cold start 1.1-2.1 s): 1500 ms đủ rộng để không báo động giả vì cold start đơn lẻ, nhưng đủ chặt để bắt sự cố `rag_slow` (retrieval chậm thêm 2.5 s, tổng khoảng 2.7 s) mà ngưỡng 3000 ms sẽ bỏ sót. Guardrail giữ nguyên: error rate ≤ 2%, cost ngày ≤ 2.5 USD, quality trung bình ≥ 0.75, retrieval success ≥ 90%.
- **Cách tính error budget:** Error budget = 100% - 99.5% = 0.5% tổng số request trong 28 ngày. Ví dụ 100,000 request thì được phép tối đa 500 request chậm hoặc lỗi. Burn rate = tỉ lệ request xấu thực tế / 0.5%; burn rate 1 nghĩa là dùng hết budget đúng cuối kỳ, burn rate 14 kéo dài 1 giờ nghĩa là hết budget sau khoảng 2 ngày nên cần xử lý ngay.
- **Ba alert và runbook tương ứng:** (1) `high_latency_p95` (P2): P95 latency > 1500 ms trong 5 phút, runbook `docs/alerts.md#alert-1`; (2) `high_error_rate` (P1): error rate > 2% trong 5 phút, runbook `docs/alerts.md#alert-2`; (3) `cost_per_request_spike` (P2): chi phí trung bình mỗi request > 0.005 USD trong 10 phút, runbook `docs/alerts.md#alert-3`. Cả ba dựa trên triệu chứng người dùng/SLO, có owner, kênh Slack `#day13-k4-l3a-alerts` và quy trình kiểm tra Metrics → Logs → Traces. Cấu hình ở `config/alert_rules.yaml`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 2026-09-29 09:58:00 đến 09:58:14 UTC (16:58 giờ Việt Nam), chạy `inject_incident.py` rồi `load_test.py --challenge --concurrency 5` với 5 request feature `monitoring`.
- **Triệu chứng từ metrics:** Panel Latency: P95 tăng từ 153 ms (baseline) lên 2653 ms (gấp khoảng 17 lần), P50 và P99 cũng lên 2653 ms. Các panel khác gần như không đổi: TTFT P95 vẫn 50 ms, error rate 0%, retrieval success 100%, cost mỗi request bình thường (khoảng $0.002), quality 0.84. Vậy request vẫn thành công (HTTP 200) nhưng chậm, và phần chậm không nằm ở LLM. Evidence: `evidence/12-incident-metric.png`.
- **Log line và correlation ID liên quan:** Lọc `event == "response_sent"` trong khoảng trên, request `req-ba3ba3c2` có `latency_ms: 2653`, `ttft_ms: 50`, `feature: "monitoring"`, `tokens_out: 93`, `cost_usd: 0.001497`. Cả 5 request trong đợt chạy đều có latency 2652-2653 ms. Log không có `request_failed` nào. Evidence: `evidence/13-incident-log.png`.
- **Trace ID và span gây ảnh hưởng:** Trace `3dc9c85131acc08a49f8e896b6a975e7` (metadata `correlation_id = req-ba3ba3c2`). Span tree: `lab-agent-run` 2.656 s gồm `retrieval` (retriever) 2.504 s và `llm-generation` 0.152 s. Span `retrieval` chiếm khoảng 94% thời gian request; `llm-generation` giống hệt mức baseline (0.15 s). Evidence: `evidence/14-incident-trace.png`.
- **Root cause:** Bước retrieval (vector store/RAG) chậm thêm khoảng 2.5 s mỗi request (sự cố `rag_slow`). Ba bằng chứng cùng chỉ về nguyên nhân này: metric (P95 latency 153 → 2653 ms nhưng TTFT, error và cost không đổi), log (`req-ba3ba3c2` latency 2653 ms, không có lỗi) và trace (span `retrieval` 2.504 s, `llm-generation` 0.152 s).
- **Fix action:** Tắt incident bằng `python scripts/inject_incident.py --disable` (giả lập khôi phục retrieval). Chạy lại load test: các request mới chỉ mất khoảng 0.3-0.8 s, P95 về mức bình thường.
- **Preventive measure:** Đặt timeout và fallback cho bước retrieval (quá thời gian thì trả câu trả lời không dùng retrieval); bật alert `high_latency_p95` (P95 > 1500 ms trong 5 phút, SLO `fast_successful_requests`) để phát hiện sớm, vì ngưỡng 3000 ms của dashboard sẽ bỏ sót sự cố này (2653 ms); thêm metric riêng cho thời gian retrieval để thấy ngay bước chậm mà không cần mở trace.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Hạ ngưỡng latency của SLO từ 3000 ms xuống 1500 ms (`config/slo.yaml`) thay vì giữ giá trị mặc định. Baseline warm của tôi có P95 khoảng 153 ms, cold start 1.1-2.1 s; sự cố `rag_slow` chỉ làm request mất khoảng 2.7 s, dưới 3000 ms nên với ngưỡng mặc định sẽ không bị tính là request xấu và alert không kích hoạt. Ngưỡng 1500 ms vẫn đủ rộng để bỏ qua cold start đơn lẻ nhưng bắt được sự cố. Ngưỡng 3000 ms trong `dashboard.yaml` giữ nguyên vì đó là contract.
- **Một lỗi/blocker đã gặp:** Sau khi rollback `production` về v1 trên Langfuse, request gửi ngay sau đó (`req-prod-v1`, trace `a2beb12ddb5de8d087b8db64adc26243`) vẫn dùng prompt v2. Trước đó cũng gặp `ModuleNotFoundError: No module named 'httpx'` khi chạy load test vì terminal thứ hai chưa activate `.venv`.
- **Cách tìm nguyên nhân và xử lý:** Với lỗi rollback: đọc metadata trace thấy `prompt_version` vẫn là 2 dù label `production` đã trỏ v1; xem `app/prompt_management.py` thấy `cache_ttl_seconds=60`, tức app cache prompt 60 giây. Sau khi restart app (cache sạch) request `req-rollback-v1` dùng đúng v1. Bài học: rollback prompt không tức thời, cần tính độ trễ cache hoặc restart/invalidate. Với lỗi httpx: activate `.venv` ở terminal thứ hai rồi `pip install -r requirements.txt`.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics cho biết có vấn đề ở đâu và từ lúc nào nhưng không nói request nào; trong challenge, panel Latency cho thấy P95 nhảy từ 153 lên 2653 ms trong khi TTFT, error và cost không đổi, nên tôi biết request chậm nhưng không hỏng và không phải LLM. Logs cho phép lọc các event trong khoảng đó và chọn một request cụ thể bằng `correlation_id` (`req-ba3ba3c2`). Traces mở đúng request đó theo `correlation_id` và cho thấy span nào chiếm thời gian (`retrieval` 2.504 s trong tổng 2.656 s). `correlation_id` là khóa nối ba tầng, và middleware phải sinh và truyền nó ngay từ đầu request để cả log lẫn trace đều mang cùng ID.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt là một thành phần thay đổi hành vi như code nên cần version và label để biết mỗi request đã dùng bản nào (trace ghi `prompt_name/label/version`) và có thể rollback khi chất lượng hoặc chi phí xấu đi. Token và cost là tín hiệu vận hành đặc thù của LLM: một prompt dài hơn hoặc output dài hơn làm cost mỗi request tăng dù không có lỗi, nên có alert `cost_per_request_spike`. SLO và error budget biến "chậm" thành mục tiêu đo được (99.5% request dưới 1500 ms) và cho biết khi nào cần dừng tính năng mới để ổn định hệ thống.
- **Điều quan trọng nhất đã học:** Instrument đúng ngay từ đầu (correlation ID, log có cấu trúc, span con) khiến điều tra sự cố chỉ mất vài bước; ngưỡng SLO phải dựa trên baseline đo được của chính hệ thống chứ không lấy mặc định.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Dashboard đọc file `data/logs.jsonl` nên chỉ phù hợp một instance và không có lưu trữ dài hạn; alert mới ở dạng cấu hình YAML và runbook, chưa nối thật tới Slack; LLM và retrieval là bản giả lập nên latency baseline thấp; rollback prompt bị trễ tối đa 60 giây do cache.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.

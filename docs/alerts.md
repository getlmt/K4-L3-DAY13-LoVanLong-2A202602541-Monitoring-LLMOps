# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

Cấu hình máy đọc được nằm ở [`../config/alert_rules.yaml`](../config/alert_rules.yaml). Thông báo gửi tới Slack `#day13-k4-l3a-alerts`.

## Alert 1

- Tên: `high_latency_p95` (người dùng chờ câu trả lời quá lâu)
- Severity: P2
- Duration: 5 phút
- Kênh thông báo: Slack `#day13-k4-l3a-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests` (99.5% request `response_sent` có `latency_ms <= 1500`, cửa sổ 28 ngày) và panel Latency của dashboard.
- Điều kiện và thời gian duy trì: P95 `latency_ms` của các event `response_sent` lớn hơn 1500 ms liên tục trong 5 phút. Baseline P95 khoảng 155 ms khi app đã warm nên ngưỡng này cao hơn nhiều so với bình thường; 5 phút đủ để bỏ qua vài request cold start (1.1-2.1 s) sau khi restart.
- Ảnh hưởng tới người dùng: câu trả lời chậm, có thể làm người dùng bỏ đi hoặc timeout phía client; error budget bị tiêu nhanh dù HTTP vẫn trả 200.
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Latency, xem P50/P95/P99 và TTFT P95 tăng từ phút nào. TTFT cao nghĩa là chậm ở bước LLM, TTFT bình thường mà tổng latency cao nghĩa là chậm ở bước khác.
  2. Logs: lọc `event == "response_sent"` trong khoảng thời gian đó, sắp theo `latency_ms` giảm dần, lấy `correlation_id` của vài request chậm nhất.
  3. Traces: mở trace có cùng `correlation_id` trên Langfuse, xem waterfall: span `retrieval` hay `llm-generation` chiếm phần lớn thời gian.
- Mitigation tạm thời: nếu `retrieval` chậm, tắt hoặc bỏ qua bước retrieval nặng và dùng câu trả lời fallback, kiểm tra vector store; nếu `llm-generation` chậm, giảm độ dài output hoặc chuyển model nhanh hơn. Sau khi xử lý, xác nhận P95 quay về dưới 1500 ms.
- Owner: Lò Văn Long (2A202602541)

## Alert 2

- Tên: `high_error_rate` (người dùng nhận lỗi 500)
- Severity: P1
- Duration: 5 phút
- Kênh thông báo: Slack `#day13-k4-l3a-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests` (request lỗi không được tính là request tốt), guardrail `error_rate_pct_max: 2` và `retrieval_success_rate_pct_min: 90`; panel Error rate và retrieval success.
- Điều kiện và thời gian duy trì: `count(request_failed) / count(request_received) * 100 > 2` liên tục trong 5 phút.
- Ảnh hưởng tới người dùng: request thất bại với HTTP 500, người dùng không nhận được câu trả lời; đây là triệu chứng nghiêm trọng nhất nên đặt P1.
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Error rate và bảng breakdown theo `error_type` để biết lỗi nào chiếm đa số; xem Retrieval success có giảm cùng lúc không.
  2. Logs: lọc `event == "request_failed"`, đọc `error_type`, `tool_name`, `payload.detail`, lấy `correlation_id` của một request lỗi.
  3. Traces: mở trace có `correlation_id` đó, xem span nào lỗi (thường là `retrieval`) và thời điểm lỗi bắt đầu.
- Mitigation tạm thời: khôi phục hoặc restart dịch vụ retrieval/vector store; nếu chưa khắc phục được, cho request đi qua nhánh fallback không cần retrieval; thông báo người dùng. Xác nhận error rate về dưới 2%.
- Owner: Lò Văn Long (2A202602541)

## Alert 3

- Tên: `cost_per_request_spike` (chi phí mỗi request tăng bất thường)
- Severity: P2
- Duration: 10 phút
- Kênh thông báo: Slack `#day13-k4-l3a-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5` và panel Cost/Tokens của dashboard.
- Điều kiện và thời gian duy trì: chi phí trung bình `avg(cost_usd)` mỗi request `response_sent` lớn hơn 0.005 USD liên tục trong 10 phút. Baseline khoảng 0.002 USD/request; ngưỡng gấp ~2.5 lần. Dùng 10 phút vì chi phí biến động theo độ dài output.
- Ảnh hưởng tới người dùng: người dùng chưa thấy triệu chứng trực tiếp nhưng chi phí vận hành tăng nhanh, có thể vượt ngân sách ngày và buộc phải giới hạn dịch vụ.
- Ba bước kiểm tra đầu tiên:
  1. Metrics: mở panel Cost và Tokens, xem input hay output token tăng; so với traffic có tăng không.
  2. Logs: lọc `response_sent` có `tokens_out` hoặc `cost_usd` cao nhất, kiểm tra `feature` và `model` để khoanh vùng, lấy `correlation_id`.
  3. Traces: mở trace tương ứng, xem `llm-generation` có usage/cost bất thường và prompt version nào đang chạy (có thể do đổi version prompt).
- Mitigation tạm thời: giảm `max_tokens` hoặc rút gọn prompt, rollback `production` về prompt version trước nếu do đổi prompt, đặt giới hạn rate cho feature tốn kém. Xác nhận cost/request về mức baseline.
- Owner: Lò Văn Long (2A202602541)

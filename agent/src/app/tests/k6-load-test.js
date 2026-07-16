import http from 'k6/http';
import { check, sleep } from 'k6';

// Test configuration: Ramp up virtual users (VUs) and configure performance thresholds
export const options = {
  stages: [
    { duration: '5s', target: 5 },   // Ramp up to 5 users
    { duration: '10s', target: 10 }, // Stay at 10 users
    { duration: '5s', target: 0 },   // Ramp down to 0
  ],
  thresholds: {
    // 1. Error rate must be less than 1%
    http_req_failed: ['rate<0.01'],
    // 2. 95% of requests must complete under 200ms
    http_req_duration: ['p(95)<200'],
  },
};

export default function () {
  // Read target URL from environment or default to local agent container address
  const targetUrl = __ENV.TARGET_URL || 'http://localhost:8000';

  const res = http.get(`${targetUrl}/health`);

  // Assertions
  check(res, {
    'status is 200': (r) => r.status === 200,
    'response has status field': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.status === 'healthy' || body.status === 'degraded';
      } catch (e) {
        return false;
      }
    },
  });

  // Pacing: Wait 500ms between requests per virtual user
  sleep(0.5);
}

/** API client for Protección Inteligente 360° backend. */

interface ChatResponse {
  reply: string;
  timestamp: string;
  session_id: string;
  model: string;
  buttons?: Array<{ label: string; value: string }>;
}

interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  database: string;
  environment: string;
}

class ApiClient {
  private baseUrl: string;
  private sessionId: string | null;

  constructor(baseUrl = "/api") {
    this.baseUrl = baseUrl;
    this.sessionId = null;
  }

  async sendMessage(message: string): Promise<ChatResponse> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (this.sessionId) {
      headers["X-Session-Id"] = this.sessionId;
    }
    const res = await fetch(`${this.baseUrl}/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({ message }),
    });
    if (!res.ok) {
      throw new Error(`Chat API error: ${res.status} ${res.statusText}`);
    }
    const data: ChatResponse = await res.json();
    if (data.session_id) {
      this.sessionId = data.session_id;
    }
    return data;
  }

  async checkHealth(): Promise<HealthResponse> {
    const res = await fetch(`${this.baseUrl}/health`);
    if (!res.ok) {
      throw new Error(`Health API error: ${res.status} ${res.statusText}`);
    }
    return res.json() as Promise<HealthResponse>;
  }
}

export type { ChatResponse, HealthResponse };
export { ApiClient };

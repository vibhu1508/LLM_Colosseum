import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  CompareRequest,
  CompareResponse,
  EvaluationRequest,
  GlobalRunItem,
  ModelsResponse,
} from '../models/contracts';

@Injectable({ providedIn: 'root' })
export class LabApiService {
  private readonly baseUrl = 'http://127.0.0.1:8000/api';

  constructor(private readonly http: HttpClient) {}

  getModels(): Observable<ModelsResponse> {
    return this.http.get<ModelsResponse>(`${this.baseUrl}/models`);
  }

  compare(payload: CompareRequest): Observable<CompareResponse> {
    return this.http.post<CompareResponse>(`${this.baseUrl}/compare`, payload);
  }

  streamCompare(
    payload: CompareRequest,
    onEvent: (event: Record<string, unknown>) => void,
    onError: (error: string) => void,
    onDone: () => void,
  ): AbortController {
    const controller = new AbortController();

    fetch(`${this.baseUrl}/compare/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          throw new Error(`Stream failed with status ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const messages = buffer.split('\n\n');
          buffer = messages.pop() || '';

          for (const message of messages) {
            const dataLine = message
              .split('\n')
              .find((line) => line.startsWith('data: '));

            if (!dataLine) {
              continue;
            }

            const jsonPayload = dataLine.replace('data: ', '');
            try {
              onEvent(JSON.parse(jsonPayload) as Record<string, unknown>);
            } catch {
              onError('Unable to parse stream message');
            }
          }
        }

        onDone();
      })
      .catch((error: Error) => {
        if (controller.signal.aborted) {
          return;
        }
        onError(error.message);
      });

    return controller;
  }

  getGlobalRuns(savedOnly = true): Observable<GlobalRunItem[]> {
    return this.http.get<GlobalRunItem[]>(`${this.baseUrl}/runs?saved_only=${savedOnly}`);
  }

  submitEvaluation(payload: EvaluationRequest): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.baseUrl}/evaluate`, payload);
  }
}

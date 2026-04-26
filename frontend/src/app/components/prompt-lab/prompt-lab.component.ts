import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { forkJoin } from 'rxjs';

import {
  CompareResponse,
  GlobalRunItem,
  ModelOutputResponse,
  ModelSelection,
  PromptType,
} from '../../models/contracts';
import { LabApiService } from '../../services/lab-api.service';

@Component({
  selector: 'app-prompt-lab',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './prompt-lab.component.html',
  styleUrl: './prompt-lab.component.css',
})
export class PromptLabComponent implements OnInit {
  readonly domain = 'Healthcare Information Assistant (non-diagnostic)';
  readonly promptTypes: PromptType[] = [
    'zero-shot',
    'one-shot',
    'few-shot',
    'role-based',
    'json-based',
    'chain-of-thought',
  ];
  readonly failureTags = [
    'hallucination',
    'ambiguity',
    'bias-or-ethical-concern',
    'over-generalization',
    'incorrect-assumptions',
  ];

  models: ModelSelection[] = [];
  selectedModelIds = new Set<string>();
  compareResult: CompareResponse | null = null;
  latestOutputs: ModelOutputResponse[] = [];
  globalRuns: GlobalRunItem[] = [];
  loading = false;
  statusText = 'Ready';
  viewMode: 'composer' | 'results' = 'composer';
  liveRunId: number | null = null;
  savingEvaluations = false;
  private streamAbortController: AbortController | null = null;
  private evaluationDrafts: Record<
    string,
    { accuracy: number; clarity: number; relevance: number; failure_tags: string[]; notes: string }
  > = {};

  readonly promptForm = this.fb.group({
    promptType: this.fb.control<PromptType>('zero-shot', { validators: [Validators.required], nonNullable: true }),
    outputMode: this.fb.control<'text' | 'json'>('text', { validators: [Validators.required], nonNullable: true }),
    roleOverride: this.fb.control('', { nonNullable: true }),
    promptText: this.fb.control('', { nonNullable: true }),
    example1Input: this.fb.control('', { nonNullable: true }),
    example1Output: this.fb.control('', { nonNullable: true }),
    example2Input: this.fb.control('', { nonNullable: true }),
    example2Output: this.fb.control('', { nonNullable: true }),
    example3Input: this.fb.control('', { nonNullable: true }),
    example3Output: this.fb.control('', { nonNullable: true }),
    inputText: this.fb.control('', { validators: [Validators.required, Validators.minLength(2)], nonNullable: true }),
  });

  constructor(
    private readonly fb: FormBuilder,
    private readonly api: LabApiService,
  ) {}

  ngOnInit(): void {
    this.loadModels();
    this.loadGlobalRuns();
  }

  loadModels(): void {
    this.api.getModels().subscribe({
      next: (data) => {
        this.models = data.models;
        this.selectedModelIds = new Set(this.models.slice(0, 3).map((m) => m.id));
      },
      error: () => {
        this.statusText = 'Failed to load models';
      },
    });
  }

  loadGlobalRuns(): void {
    this.api.getGlobalRuns(true).subscribe({
      next: (rows) => {
        this.globalRuns = rows;
      },
      error: () => {
        this.statusText = 'Failed to load activity log';
      },
    });
  }

  toggleModel(modelId: string, checked: boolean): void {
    if (checked) {
      this.selectedModelIds.add(modelId);
      return;
    }
    this.selectedModelIds.delete(modelId);
  }

  runComparison(): void {
    if (this.promptForm.invalid || this.selectedModelIds.size === 0) {
      this.promptForm.markAllAsTouched();
      this.statusText = 'Add prompt text, input text, and at least one model';
      return;
    }

    const selectedModels = this.models.filter((m) => this.selectedModelIds.has(m.id));
    const instruction = this.promptForm.controls.promptText.value.trim();
    const composedPrompt = instruction || 'Respond with concise educational healthcare information.';

    this.latestOutputs = selectedModels.map((model) => ({
      output_id: 0,
      model_name: model.name,
      model_symbol: model.symbol,
      provider_name: model.provider,
      raw_response: '',
      parsed_json: undefined,
      is_json_valid: false,
      latency_ms: undefined,
    }));
    this.evaluationDrafts = {};
    for (const model of selectedModels) {
      this.evaluationDrafts[model.name] = {
        accuracy: 3,
        clarity: 3,
        relevance: 3,
        failure_tags: [],
        notes: '',
      };
    }

    this.viewMode = 'results';
    this.liveRunId = null;
    this.loading = true;
    this.statusText = 'Streaming model answers...';

    const activeRoleOverride =
      this.promptForm.controls.promptType.value === 'role-based'
        ? this.promptForm.controls.roleOverride.value.trim()
        : '';

    this.streamAbortController?.abort();
    this.streamAbortController = this.api.streamCompare(
      {
        prompt_type: this.promptForm.controls.promptType.value,
        output_mode: this.promptForm.controls.outputMode.value,
        prompt_text: composedPrompt,
        input_text: this.promptForm.controls.inputText.value,
        role_override: activeRoleOverride || undefined,
        examples: this.getStudentExamples(),
        models: selectedModels,
      },
      (event) => this.handleStreamEvent(event),
      (error) => {
        this.statusText = `Comparison failed: ${error}`;
        this.loading = false;
      },
      () => {
        this.loading = false;
        this.loadGlobalRuns();
      },
    );
  }

  openComposerView(): void {
    this.streamAbortController?.abort();
    this.loading = false;
    this.viewMode = 'composer';
    this.statusText = 'Ready';
  }

  private handleStreamEvent(event: Record<string, unknown>): void {
    const type = String(event['type'] || '');

    if (type === 'run_started') {
      this.liveRunId = Number(event['run_id']);
      this.statusText = `Run #${this.liveRunId} started`;
      return;
    }

    if (type === 'model_started') {
      const modelId = String(event['model_id'] || '');
      const output = this.findOutputByModelId(modelId);
      if (output) {
        output.raw_response = 'Generating response...\n';
      }
      return;
    }

    if (type === 'model_chunk') {
      const modelId = String(event['model_id'] || '');
      const chunk = String(event['chunk'] || '');
      const output = this.findOutputByModelId(modelId);
      if (output) {
        output.raw_response = output.raw_response === 'Generating response...\n' ? chunk : output.raw_response + chunk;
      }
      return;
    }

    if (type === 'model_completed') {
      const modelId = String(event['model_id'] || '');
      const payload = event['output'] as ModelOutputResponse;
      const idx = this.latestOutputs.findIndex((item) => {
        const m = this.models.find((model) => model.name === item.model_name);
        return m?.id === modelId;
      });
      if (idx >= 0) {
        this.latestOutputs[idx] = payload;
      }
      return;
    }

    if (type === 'done') {
      this.statusText = `Run #${this.liveRunId ?? ''} completed`;
      return;
    }
  }

  private findOutputByModelId(modelId: string): ModelOutputResponse | undefined {
    const model = this.models.find((item) => item.id === modelId);
    if (!model) {
      return undefined;
    }
    return this.latestOutputs.find((item) => item.model_name === model.name);
  }

  saveAllEvaluations(): void {
    const completedOutputs = this.latestOutputs.filter((output) => output.output_id > 0);
    if (completedOutputs.length === 0) {
      this.statusText = 'No completed outputs to save yet';
      return;
    }

    this.savingEvaluations = true;
    const requests = completedOutputs.map((output) => {
      const draft = this.getDraft(output.model_name);
      return this.api.submitEvaluation({
        output_id: output.output_id,
        accuracy: draft.accuracy,
        clarity: draft.clarity,
        relevance: draft.relevance,
        failure_tags: draft.failure_tags,
        notes: draft.notes || undefined,
      });
    });

    forkJoin(requests).subscribe({
      next: () => {
        this.statusText = `Saved evaluation for run #${this.liveRunId ?? ''}`;
        this.loadGlobalRuns();
        this.savingEvaluations = false;
      },
      error: () => {
        this.statusText = 'Failed to save run evaluation';
        this.savingEvaluations = false;
      },
    });
  }

  getDraft(modelName: string): { accuracy: number; clarity: number; relevance: number; failure_tags: string[]; notes: string } {
    if (!this.evaluationDrafts[modelName]) {
      this.evaluationDrafts[modelName] = {
        accuracy: 3,
        clarity: 3,
        relevance: 3,
        failure_tags: [],
        notes: '',
      };
    }
    return this.evaluationDrafts[modelName];
  }

  updateDraftScore(modelName: string, field: 'accuracy' | 'clarity' | 'relevance', value: string): void {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return;
    }
    const bounded = Math.max(1, Math.min(5, parsed));
    this.getDraft(modelName)[field] = bounded;
  }

  toggleDraftTag(modelName: string, tag: string, checked: boolean): void {
    const draft = this.getDraft(modelName);
    if (checked && !draft.failure_tags.includes(tag)) {
      draft.failure_tags = [...draft.failure_tags, tag];
      return;
    }
    if (!checked) {
      draft.failure_tags = draft.failure_tags.filter((item) => item !== tag);
    }
  }

  updateDraftNotes(modelName: string, notes: string): void {
    this.getDraft(modelName).notes = notes;
  }

  asJson(raw: string): string {
    try {
      return JSON.stringify(JSON.parse(raw), null, 2);
    } catch {
      return raw;
    }
  }

  renderOutputHtml(raw: string): string {
    const normalized = this.escapeHtml(raw).replace(/\r\n/g, '\n').replace(/â¢/g, '* ');
    const lines = normalized.split('\n');
    const html: string[] = [];
    let listItems: string[] = [];

    const flushList = () => {
      if (listItems.length > 0) {
        html.push(`<ul>${listItems.map((item) => `<li>${item}</li>`).join('')}</ul>`);
        listItems = [];
      }
    };

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed) {
        flushList();
        continue;
      }

      const bulletMatch = trimmed.match(/^(?:\*|-|•)\s+(.*)$/);
      if (bulletMatch) {
        listItems.push(this.formatInlineMarkdown(bulletMatch[1]));
      } else {
        flushList();
        html.push(`<p>${this.formatInlineMarkdown(trimmed)}</p>`);
      }
    }

    flushList();
    return html.join('');
  }

  private formatInlineMarkdown(text: string): string {
    return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  }

  private escapeHtml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  isRoleBasedSelected(): boolean {
    return this.promptForm.controls.promptType.value === 'role-based';
  }

  isOneShotSelected(): boolean {
    return this.promptForm.controls.promptType.value === 'one-shot';
  }

  isFewShotSelected(): boolean {
    return this.promptForm.controls.promptType.value === 'few-shot';
  }

  getPromptPreview(): string {
    const promptType = this.promptForm.controls.promptType.value;
    const outputMode = this.promptForm.controls.outputMode.value;
    const instruction = this.promptForm.controls.promptText.value.trim();
    const inputText = this.promptForm.controls.inputText.value.trim();
    const role = this.promptForm.controls.roleOverride.value.trim();
    const examples = this.getStudentExamples();

    const parts: string[] = [
      `Prompt Type: ${promptType}`,
      outputMode === 'json' ? 'Mode Rule: Return JSON object output.' : 'Mode Rule: Return concise text output.',
    ];

    if (promptType === 'one-shot') {
      if (examples.length > 0) {
        parts.push('One-shot example:');
        parts.push(this.formatPreviewExample(examples[0].input, examples[0].output, 1));
      } else {
        parts.push('One-shot example: <add your own example input/output>');
      }
    } else if (promptType === 'few-shot') {
      if (examples.length > 0) {
        parts.push('Few-shot examples:');
        examples.forEach((example, idx) => {
          parts.push(this.formatPreviewExample(example.input, example.output, idx + 1));
        });
      } else {
        parts.push('Few-shot examples: <add your own examples>');
      }
    } else if (promptType === 'chain-of-thought') {
      parts.push('Instruction: Reason internally step-by-step; output concise final answer only.');
    }

    if (promptType === 'role-based' && role) {
      parts.push(`Temporary Role: ${role}`);
    }

    parts.push(`Prompt Instructions: ${instruction || 'Respond with concise educational healthcare information.'}`);
    parts.push(`Input: ${inputText || '<waiting for input>'}`);
    return parts.join('\n\n');
  }

  private getStudentExamples(): Array<{ input: string; output: string }> {
    const raw = [
      {
        input: this.promptForm.controls.example1Input.value.trim(),
        output: this.promptForm.controls.example1Output.value.trim(),
      },
      {
        input: this.promptForm.controls.example2Input.value.trim(),
        output: this.promptForm.controls.example2Output.value.trim(),
      },
      {
        input: this.promptForm.controls.example3Input.value.trim(),
        output: this.promptForm.controls.example3Output.value.trim(),
      },
    ];

    return raw.filter((example) => example.input && example.output);
  }

  private formatPreviewExample(input: string, output: string, index: number): string {
    return `Example ${index} Input: ${input}\nExample Output: ${output}`;
  }
}

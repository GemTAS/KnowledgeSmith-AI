import { ConceptSummary, ConceptDetail, GraphResponse, EvaluationData, ValidationData } from './types';

const API_BASE = '/api';

export async function fetchConcepts(q?: string, type?: string): Promise<ConceptSummary[]> {
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (type) params.set('type', type);
  const res = await fetch(`${API_BASE}/concepts?${params.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch concepts');
  const data = await res.json();
  return data.concepts;
}

export async function fetchConcept(id: string): Promise<ConceptDetail> {
  const res = await fetch(`${API_BASE}/concepts/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(`Failed to fetch concept ${id}`);
  return res.json();
}

export async function fetchGraph(): Promise<GraphResponse> {
  const res = await fetch(`${API_BASE}/graph`);
  if (!res.ok) throw new Error('Failed to fetch knowledge graph');
  return res.json();
}

export async function fetchEvaluation(): Promise<EvaluationData> {
  const res = await fetch(`${API_BASE}/evaluation`);
  if (!res.ok) throw new Error('Failed to fetch evaluation metrics');
  return res.json();
}

export async function fetchValidation(): Promise<ValidationData> {
  const res = await fetch(`${API_BASE}/validation`);
  if (!res.ok) throw new Error('Failed to fetch validation issues');
  return res.json();
}

export async function runPipeline(inputDir: string, outputDir: string, useLlm: boolean) {
  const res = await fetch(`${API_BASE}/pipeline/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input_dir: inputDir, output_dir: outputDir, use_llm: useLlm }),
  });
  if (!res.ok) throw new Error('Pipeline execution failed');
  return res.json();
}

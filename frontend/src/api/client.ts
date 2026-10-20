export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(
      response.status,
      body?.code ?? 'unknown',
      body?.message ?? `Request failed (${response.status})`,
    )
  }
  return body as T
}

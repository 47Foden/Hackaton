export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly uncertain: boolean;
  constructor(
    message: string,
    status: number,
    code: string,
    uncertain = false,
  ) { super(message); this.name = 'ApiError'; this.status = status; this.code = code; this.uncertain = uncertain; }
}

export function asApiError(error: unknown, isOrder = false): ApiError {
  return error instanceof ApiError ? error
    : new ApiError('통신에 실패했어요.', 0, 'NETWORK_ERROR', isOrder);
}

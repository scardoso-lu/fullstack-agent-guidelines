// Description: Service layer pattern — TypedResponse<T>, authApi/api wrappers, domain service object
// ─────────────────────────────────────────────────────────────────────────────
// PATTERN: src/services/ is the ONLY place that calls fetch().
// Components and pages receive typed data — they never see raw Response or fetch().
//
// Auth model: JWT is stored in an HttpOnly SameSite=Strict cookie.
// The browser sends it automatically — no JS reads the cookie value.
// credentials: "include" ensures it is forwarded on every same-origin request.
// ─────────────────────────────────────────────────────────────────────────────

// ── Generic response types ────────────────────────────────────────────────────

// Extends Response with a typed .json() method — callers get T, not `any`
export type TypedResponse<T> = Response & {
  json(): Promise<T>;
};

// Standard paginated list shape expected from the backend
export type PaginationResponse<TData> = {
  data: TData[];
  total: number;
  page: number;
  size: number;
};

// ── Error class ───────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Base fetch wrappers ───────────────────────────────────────────────────────

// authApi — credentials:"include" forwards the HttpOnly SameSite=Strict cookie.
// The backend authenticates from the cookie; no Authorization header is needed.
export async function authApi<T>(
  url: string,
  options: RequestInit = {}
): Promise<TypedResponse<T>> {
  const response = await fetch(url, {
    credentials: "include",   // sends HttpOnly cookie automatically — JS never reads it
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  }) as TypedResponse<T>;

  if (!response.ok) {
    if (response.status === 401) {
      // Cookie is HttpOnly — cannot clear it from JS. Redirect; server clears on login.
      window.location.href = "/en/login";
      throw new ApiError(401, "Session expired");
    }
    const body = await response.json().catch(() => ({ detail: "Unknown error" })) as { detail?: string };
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }

  return response;
}

// api — unauthenticated (login, register, public endpoints)
export async function api<T>(
  url: string,
  options: RequestInit = {}
): Promise<TypedResponse<T>> {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  }) as TypedResponse<T>;

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Unknown error" })) as { detail?: string };
    throw new ApiError(response.status, body.detail ?? "Request failed");
  }

  return response;
}

// ── Domain types ──────────────────────────────────────────────────────────────

export type DrugDataItem = {
  id: number;
  inn: string;
  atc_code: string;
  form: string;
  strength: string;
};

export type CreateDrugPayload = Omit<DrugDataItem, "id">;

// ── Domain service object ─────────────────────────────────────────────────────
// Export a plain object — no class instantiation, no `new DrugService()`
// Every method is async and returns typed data, never raw Response

const BASE = process.env.NEXT_PUBLIC_API_URL;

export const DrugService = {
  async paged(
    page: number,
    size: number,
    search?: string
  ): Promise<PaginationResponse<DrugDataItem>> {
    const params = new URLSearchParams({ page: String(page), size: String(size) });
    if (search) params.set("q", search);
    const res = await authApi<PaginationResponse<DrugDataItem>>(
      `${BASE}/drugs?${params}`
    );
    return res.json();
  },

  async getById(id: number): Promise<DrugDataItem> {
    const res = await authApi<DrugDataItem>(`${BASE}/drugs/${id}`);
    return res.json();
  },

  async create(payload: CreateDrugPayload): Promise<DrugDataItem> {
    const res = await authApi<DrugDataItem>(`${BASE}/drugs`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return res.json();
  },

  async delete(id: number): Promise<void> {
    await authApi<void>(`${BASE}/drugs/${id}`, { method: "DELETE" });
  },
};

// ─────────────────────────────────────────────────────────────────────────────
// ANTI-PATTERNS:
//
// 1. Reading the token from JS to attach it manually:
//
//   import Cookies from "js-cookie";
//   const token = Cookies.get("x-access-token");    // ← requires non-HttpOnly cookie
//   headers: { Authorization: `Bearer ${token}` }   // ← exposes token to XSS
//
//   Use credentials:"include" instead — the browser forwards the cookie and JS
//   never touches the token value.
//
// 2. Raw fetch inside a component:
//
//   const [drugs, setDrugs] = useState([]);
//   useEffect(() => {
//     fetch("/api/drugs").then(r => r.json()).then(setDrugs);  // ← raw fetch, no types
//   }, []);
//
//   Put the fetch in a service. Use React Query in the component.
// ─────────────────────────────────────────────────────────────────────────────

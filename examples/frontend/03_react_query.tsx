// Description: React Query — useQuery for reads, useMutation for writes, queryKey hierarchy
// ─────────────────────────────────────────────────────────────────────────────
// PATTERN: React Query is the cache for all client-side server state.
// useQuery handles loading/error/stale automatically.
// useMutation + invalidateQueries keeps the cache consistent after writes.
// ─────────────────────────────────────────────────────────────────────────────

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useQueryState } from "nuqs";
import { useState } from "react";
import { DrugService, type DrugDataItem, type CreateDrugPayload } from "@/services/drugs";
import { ApiError } from "@/services/api";

// ── queryKey convention ───────────────────────────────────────────────────────
// ["entity"]                      → all entity queries (for broad invalidation)
// ["entity", "operation"]         → specific operation
// ["entity", "operation", params] → parameterised query
//
// invalidateQueries({ queryKey: ["drugs"] }) clears ALL drug entries in the cache

const DRUG_KEYS = {
  all: ["drugs"] as const,
  paged: (page: number, search: string) => ["drugs", "paged", page, search] as const,
  detail: (id: number) => ["drugs", "detail", id] as const,
  search: (q: string) => ["drugs", "search", q] as const,
};

// ── useQuery — read data ──────────────────────────────────────────────────────

export function DrugList({ initialData }: { initialData?: DrugDataItem[] }) {
  // URL state: ?q= and ?page= survive navigation and are shareable
  const [search, setSearch] = useQueryState("q", { defaultValue: "" });
  const [page, setPage] = useQueryState("page", { defaultValue: "1" });
  const pageNum = parseInt(page, 10);

  const { data, isLoading, isError, isFetching } = useQuery({
    queryKey: DRUG_KEYS.paged(pageNum, search),
    queryFn: () => DrugService.paged(pageNum, 20, search),
    placeholderData: (prev) => prev,   // keep previous results while new page loads
    staleTime: 30_000,                  // 30 s before background refetch
  });

  return (
    <div>
      <input
        value={search}
        onChange={(e) => { setSearch(e.target.value); setPage("1"); }}
        placeholder="Search…"
      />

      {/* isFetching shows a subtle indicator while background-refreshing */}
      {isFetching && <span className="text-xs text-muted-foreground">Refreshing…</span>}

      {isLoading && <p>Loading drugs…</p>}
      {isError && <p className="text-red-500">Failed to load. Try again.</p>}

      {data?.data.map((drug) => (
        <DrugRow key={drug.id} drug={drug} />
      ))}
    </div>
  );
}

// ── Single-item query ─────────────────────────────────────────────────────────

export function DrugDetail({ drugId }: { drugId: number }) {
  const { data: drug, isLoading } = useQuery({
    queryKey: DRUG_KEYS.detail(drugId),
    queryFn: () => DrugService.getById(drugId),
    staleTime: 60_000,
  });

  if (isLoading) return <div>Loading…</div>;
  if (!drug) return null;

  return (
    <div>
      <h2>{drug.inn}</h2>
      <p>ATC: {drug.atc_code}</p>
      <p>Form: {drug.form} — {drug.strength}</p>
    </div>
  );
}

// ── useMutation — write data ──────────────────────────────────────────────────

export function CreateDrugForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const { mutate, isPending } = useMutation({
    mutationFn: (payload: CreateDrugPayload) => DrugService.create(payload),
    onSuccess: () => {
      // Invalidate ALL drug queries — list and search results become stale
      queryClient.invalidateQueries({ queryKey: DRUG_KEYS.all });
      onClose();
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Unexpected error");
      }
    },
  });

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    mutate({
      inn: fd.get("inn") as string,
      atc_code: fd.get("atc_code") as string,
      form: fd.get("form") as string,
      strength: fd.get("strength") as string,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <input name="inn" placeholder="INN" required />
      <input name="atc_code" placeholder="ATC code" required />
      <input name="form" placeholder="Form" required />
      <input name="strength" placeholder="Strength" required />

      {error && <p className="text-sm text-red-500">{error}</p>}

      <button type="submit" disabled={isPending}>
        {isPending ? "Creating…" : "Create Drug"}
      </button>
    </form>
  );
}

// ── Optimistic delete ─────────────────────────────────────────────────────────

export function DrugDeleteButton({ drug }: { drug: DrugDataItem }) {
  const queryClient = useQueryClient();

  const { mutate, isPending } = useMutation({
    mutationFn: () => DrugService.delete(drug.id),
    // Optimistic update — remove from cache immediately, restore on error
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: DRUG_KEYS.all });
      const snapshot = queryClient.getQueryData(DRUG_KEYS.all);
      // mutate cache here if desired
      return { snapshot };
    },
    onError: (_err, _vars, context) => {
      if (context?.snapshot) {
        queryClient.setQueryData(DRUG_KEYS.all, context.snapshot);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: DRUG_KEYS.all });
    },
  });

  return (
    <button onClick={() => mutate()} disabled={isPending} className="text-red-500">
      {isPending ? "Deleting…" : "Delete"}
    </button>
  );
}

// Helper component referenced above
function DrugRow({ drug }: { drug: DrugDataItem }) {
  return (
    <div className="flex items-center justify-between p-3 border-b">
      <span>{drug.inn}</span>
      <span className="text-sm text-muted-foreground">{drug.atc_code}</span>
      <DrugDeleteButton drug={drug} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ANTI-PATTERNS:
//
//   const [drugs, setDrugs] = useState([]);
//   useEffect(() => { DrugService.paged(1,20).then(r => setDrugs(r.data)) }, []);
//   ↑ no cache, no dedup, no error state, doesn't cancel on unmount
//
//   After mutation: setDrugs((prev) => prev.filter(d => d.id !== id))
//   ↑ manual local state sync — diverges from server truth; use invalidateQueries
// ─────────────────────────────────────────────────────────────────────────────

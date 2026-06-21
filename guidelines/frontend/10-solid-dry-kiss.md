# SOLID, DRY, KISS, and YAGNI — Applied to Next.js

Use when designing a component, hook, or Zod schema. Frontend-specific SOLID/DRY/KISS/YAGNI: one-concern-per-component (S), composition over prop-drilling (O), schema-first Zod for DRY, and YAGNI on hooks.

These principles were coined for OOP but apply directly to React/Next.js. The primitives change (components and hooks instead of classes), but the intent is identical: small, focused units with clear responsibilities that are easy to change.

---

## SOLID

### S — Single Responsibility Principle

Each component, hook, or service does exactly one thing.

**Violated — one component that fetches, validates, submits, and renders:**
```tsx
// ❌ AdminDrugPage does everything
"use client";
export default function AdminDrugPage() {
  const [drugs, setDrugs] = useState([]);
  const [form, setForm] = useState({ inn: "", atc: "" });
  const [error, setError] = useState("");

  useEffect(() => { DrugService.paged(1, 20).then(r => setDrugs(r.data)); }, []);

  const validate = () => { if (!form.inn) { setError("Required"); return false; } return true; };
  const submit = async () => { if (!validate()) return; await DrugService.create(form); };

  return (
    <div>
      {drugs.map(d => <div key={d.id}>{d.inn}</div>)}
      <input value={form.inn} onChange={e => setForm({ ...form, inn: e.target.value })} />
      {error && <p>{error}</p>}
      <button onClick={submit}>Add</button>
    </div>
  );
}
```

**Fixed — each unit has one job:**
```tsx
// Server Component — fetches
export default async function DrugPage() {
  const drugs = await DrugService.paged(1, 20);
  return (
    <>
      <DrugList drugs={drugs.data} />   {/* renders */}
      <CreateDrugForm />                {/* form logic */}
    </>
  );
}

// useDrugForm — validation and submission only
function useDrugForm(onSuccess: () => void) {
  const form = useForm<DrugFormData>({ resolver: zodResolver(DrugSchema) });
  const submit = form.handleSubmit(async (data) => {
    const result = await createDrugAction(data);    // Server Action — see frontend/16
    if (result.status === "ok") onSuccess();
    // map result.fieldErrors back onto the form on error (omitted here)
  });
  return { form, submit };
}

// CreateDrugForm — renders the form, delegates logic to the hook
function CreateDrugForm() {
  const { form, submit } = useDrugForm(() => {});
  return <form onSubmit={submit}>{/* fields */}</form>;
}
```

---

### O — Open/Closed Principle

Open for extension, closed for modification. Add new behaviour without editing existing code.

**Violated — every new status needs editing the same function:**
```tsx
// ❌ Adding a new status requires modifying this function
function getDrugStatusLabel(status: string) {
  if (status === "approved") return "Approved";
  if (status === "pending") return "Pending Review";
  if (status === "rejected") return "Rejected";
  // must edit here every time
}
```

**Fixed — configuration object:**
```tsx
// ✅ Adding a new status = adding one entry to the map, nothing else changes
const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  approved: { label: "Approved", className: "bg-green-100 text-green-800" },
  pending:  { label: "Pending Review", className: "bg-yellow-100 text-yellow-800" },
  rejected: { label: "Rejected", className: "bg-red-100 text-red-800" },
  archived: { label: "Archived", className: "bg-gray-100 text-gray-800" },  // new — zero other changes
};

function DrugStatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] ?? { label: status, className: "bg-gray-100" };
  return <span className={`rounded px-2 py-0.5 text-xs ${config.className}`}>{config.label}</span>;
}
```

---

### L — Liskov Substitution Principle

Components implementing the same interface should be swappable. In React this means: if two components accept the same props shape, the consumer must not know or care which is rendered.

```tsx
// Define a shared interface
type DataTableProps<TRow> = {
  rows: TRow[];
  columns: ColumnDef<TRow>[];
  isLoading?: boolean;
};

// Two implementations of the same props shape
function ServerDataTable<TRow>({ rows, columns, isLoading }: DataTableProps<TRow>) { /* ... */ }
function VirtualizedDataTable<TRow>({ rows, columns, isLoading }: DataTableProps<TRow>) { /* ... */ }

// Consumer doesn't know which it gets — swap without touching the page
const DataTable = largeDataset ? VirtualizedDataTable : ServerDataTable;
<DataTable rows={drugs} columns={drugColumns} />
```

---

### I — Interface Segregation Principle

Small, focused props interfaces. Don't force consumers to receive props they don't use.

**Violated:**
```tsx
// ❌ Everything lumped together — most consumers ignore most fields
type ButtonProps = {
  label: string;
  onClick: () => void;
  icon?: React.ReactNode;
  isLoading?: boolean;
  isDestructive?: boolean;
  tooltipText?: string;
  analyticsEvent?: string;
  dropdownItems?: MenuItem[];   // only relevant for split-buttons
};
```

**Fixed — compose narrow interfaces:**
```tsx
// ✅ Base interface — every button has these
type BaseButtonProps = {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
};

// Extended only when needed
type LoadingButtonProps = BaseButtonProps & { isLoading?: boolean };
type DestructiveButtonProps = BaseButtonProps & { confirmMessage: string };
type SplitButtonProps = BaseButtonProps & { dropdownItems: MenuItem[] };

// Components accept only what they need
function LoadingButton({ children, onClick, isLoading, disabled }: LoadingButtonProps) { ... }
function SplitButton({ children, onClick, dropdownItems }: SplitButtonProps) { ... }
```

---

### D — Dependency Inversion Principle

High-level components should depend on abstractions (interfaces), not concrete implementations.

In React this means: pass behaviour as props or hooks, not baked-in service calls.

**Violated:**
```tsx
// ❌ DrugCard is tightly coupled to DrugService
"use client";
function DrugCard({ id }: { id: number }) {
  const [drug, setDrug] = useState<DrugDataItem | null>(null);
  useEffect(() => {
    DrugService.getById(id).then(setDrug);          // concrete dependency
  }, [id]);
  return <div>{drug?.inn}</div>;
}
```

**Fixed — dependency is injected:**
```tsx
// ✅ DrugCard depends on a function (interface), not DrugService
"use client";
type DrugCardProps = {
  id: number;
  fetchDrug: (id: number, opts: { signal: AbortSignal }) => Promise<DrugDataItem>;
};

function DrugCard({ id, fetchDrug }: DrugCardProps) {
  const [drug, setDrug] = useState<DrugDataItem | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    fetchDrug(id, { signal: ctrl.signal }).then(setDrug).catch(() => {});
    return () => ctrl.abort();
  }, [id, fetchDrug]);
  return <div>{drug?.inn}</div>;
}

// Real usage
<DrugCard id={42} fetchDrug={DrugService.getById} />

// Test usage — no network, no mocking module imports
<DrugCard id={42} fetchDrug={async () => ({ id: 42, inn: "Paracetamol", atc_code: "N02BE01", form: "tablet", strength: "500mg" })} />
```

---

## DRY — Don't Repeat Yourself

### Shared Zod building blocks

```ts
// lib/schemas.ts — defined once, composed everywhere
export const validators = {
  email: z.string().email("Invalid email"),
  password: z.string().min(8, "Min 8 characters"),
  atcCode: z.string().regex(/^[A-Z]\d{2}[A-Z]{2}\d{2}$/, "Invalid ATC code"),
  positiveInt: z.number().int().positive("Must be positive"),
};

// No copy-paste of regex strings across forms
const LoginSchema = z.object({ email: validators.email, password: validators.password });
const RegisterSchema = z.object({ email: validators.email, password: validators.password, name: z.string() });
```

### `cn()` — the only way to merge Tailwind classes

```ts
// lib/utils.ts — single definition
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Usage — never concatenate strings manually
<div className={cn("base-class", isActive && "active-class", className)} />
```

### Shared API base URL

```ts
// Never hardcode base URLs in service files
const BASE = process.env.NEXT_PUBLIC_API_URL;   // defined once
export const DrugService = { paged: () => authApi(`${BASE}/drugs`) };
export const CatalogService = { list: () => authApi(`${BASE}/catalogs`) };
```

---

## KISS — Keep It Simple

**Violated — over-engineered state machine for a toggle:**
```tsx
// ❌ 4 useReducer cases for open/close
type State = { status: "idle" | "opening" | "open" | "closing" };
function reducer(state: State, action: { type: "open" | "close" }): State { ... }
```

**Fixed:**
```tsx
// ✅ One useState — nothing more
const [open, setOpen] = useState(false);
```

**Violated — generic render-prop table for a one-off list:**
```tsx
// ❌ Premature abstraction
<DataTable
  renderHeader={({ col }) => <CustomHeader col={col} />}
  renderRow={({ row }) => <CustomRow row={row} />}
  renderFooter={() => <Footer />}
  sortConfig={{ ... }}
  filterConfig={{ ... }}
/>
```

**Fixed:** Write the list directly. Abstract only when the pattern repeats in 3+ places.

---

## YAGNI — You Aren't Gonna Need It

Common YAGNI violations AI systems make:

```tsx
// ❌ Building a theming system for a single color
const theme = { colors: { primary: "#000", secondary: "#fff" } };
<Button style={{ color: theme.colors.primary }}>Submit</Button>

// ✅ Just use the Tailwind class
<Button className="text-black">Submit</Button>

// ❌ Internationalization for a product that ships in English only
const t = useTranslation("common");
<Button>{t("submitButton")}</Button>

// ✅ Write the string
<Button>Submit</Button>

// ❌ Plugin architecture for 2 chart types
const ChartFactory = { create: (type: string) => chartRegistry[type]() };
const chart = ChartFactory.create("bar");

// ✅ Just import and use both
import BarChart from "@/components/charts/bar-chart";
```

When a feature is requested by a real user or a real sprint, build it. Not before.

---

## Quick Checklist

- [ ] **S** — Each component/hook has one job: data fetch OR form logic OR render — not all three
- [ ] **O** — New variants added via configuration objects, not `if/else` chains inside components
- [ ] **L** — Components with the same props interface are interchangeable — consumer doesn't know which
- [ ] **I** — Props interfaces are small and focused; optional groupings use composition
- [ ] **D** — Service calls are injected via props or hooks — components don't import services directly
- [ ] **DRY** — Zod validators, `cn()`, and the API base URL are each defined once
- [ ] **KISS** — `useState(false)` for a toggle, not a state machine
- [ ] **YAGNI** — No theming system, no plugin architecture, no i18n until the feature is needed

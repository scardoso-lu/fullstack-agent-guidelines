---
model: sonnet
effort: high
---

# Forms and Validation — React Hook Form + Zod

Use when building a form. Covers the Zod schema → TypeScript type → zodResolver pattern, mapping server errors back to fields, cross-field validation with .refine(), and root-level error display for non-field API errors.

Every form in the application uses **React Hook Form** for state management and **Zod** for schema validation. This combination is type-safe end-to-end: the Zod schema infers the TypeScript type, the resolver connects them to the form, and invalid data never reaches the submit handler.

---

## The Pattern

```
Zod schema → TypeScript type (inferred) → useForm with zodResolver → input registration → submit handler
```

### 1. Define the Schema First

```ts
// src/components/app/login-form.tsx (or a shared schemas file)
import { z } from "zod";

const LoginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type LoginFormData = z.infer<typeof LoginSchema>;
// Equivalent to: { email: string; password: string }
```

The schema is the single source of truth — no separate `interface LoginFormData` that can drift.

### 2. Connect to the Form

```tsx
// src/components/app/login-form.tsx
"use client";  // forms require interactivity

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const LoginSchema = z.object({
  email: z.string().email("Invalid email address"),
  password: z.string().min(8, "Password must be at least 8 characters"),
});

type LoginFormData = z.infer<typeof LoginSchema>;

export function LoginForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<LoginFormData>({
    resolver: zodResolver(LoginSchema),
  });

  const onSubmit = async (data: LoginFormData) => {
    try {
      await AuthService.login(data.email, data.password);
      router.push("/en/admin");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("root", { message: "Invalid email or password" });
      }
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
      <div className="form-control">
        <label className="label" htmlFor="email">
          <span className="label-text">Email</span>
        </label>
        <input
          id="email"
          {...register("email")}
          type="email"
          placeholder="you@example.com"
          className={`input input-bordered w-full ${errors.email ? "input-error" : ""}`}
        />
        {errors.email && (
          <label className="label">
            <span className="label-text-alt text-error">{errors.email.message}</span>
          </label>
        )}
      </div>

      <div className="form-control">
        <label className="label" htmlFor="password">
          <span className="label-text">Password</span>
        </label>
        <input
          id="password"
          {...register("password")}
          type="password"
          placeholder="••••••••"
          className={`input input-bordered w-full ${errors.password ? "input-error" : ""}`}
        />
        {errors.password && (
          <label className="label">
            <span className="label-text-alt text-error">{errors.password.message}</span>
          </label>
        )}
      </div>

      {errors.root && (
        <div className="alert alert-error text-sm">{errors.root.message}</div>
      )}

      <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
        {isSubmitting ? (
          <><span className="loading loading-spinner loading-sm" />Signing in…</>
        ) : "Sign in"}
      </button>
    </form>
  );
}
```

---

## Complex Schemas

### Optional fields and transforms

```ts
const UserProfileSchema = z.object({
  display_name: z.string().min(1, "Name is required"),
  bio: z.string().max(500).optional(),
  website: z
    .string()
    .url("Must be a valid URL")
    .optional()
    .or(z.literal("")),      // allow empty string (blank = no website)
  age: z
    .string()
    .transform((val) => parseInt(val, 10))  // input is string; store as number
    .refine((val) => val >= 18, "Must be 18 or older"),
});
```

### Dependent validation (password confirmation)

```ts
const ChangePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Required"),
    new_password: z.string().min(8, "Minimum 8 characters"),
    confirm_password: z.string().min(1, "Required"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],   // attach error to confirm_password field
  });
```

---

## daisyUI Form Components

daisyUI is a Tailwind CSS plugin — there are no React component imports. Apply daisyUI class names directly on native HTML elements alongside `{...register(...)}`. No `npx shadcn add`, no copied component files.

### Installation

```bash
npm install daisyui
```

```ts
// tailwind.config.ts
import type { Config } from "tailwindcss";
import daisyui from "daisyui";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  plugins: [daisyui],
  daisyui: {
    themes: ["light", "dark"],
    logs: false,
  },
};

export default config;
```

### Field Pattern

```tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

export function DrugForm({ onSuccess }: { onSuccess: () => void }) {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<DrugFormData>({
    resolver: zodResolver(DrugSchema),
    defaultValues: { inn: "", atc_code: "", form: "" },
  });

  return (
    <form onSubmit={handleSubmit(onSuccess)} className="flex flex-col gap-4">

      <div className="form-control">
        <label className="label" htmlFor="inn">
          <span className="label-text">INN</span>
        </label>
        <input
          id="inn"
          type="text"
          placeholder="Paracetamol"
          className={`input input-bordered w-full ${errors.inn ? "input-error" : ""}`}
          {...register("inn")}
        />
        {errors.inn && (
          <label className="label">
            <span className="label-text-alt text-error">{errors.inn.message}</span>
          </label>
        )}
      </div>

      <div className="form-control">
        <label className="label" htmlFor="atc_code">
          <span className="label-text">ATC Code</span>
        </label>
        <input
          id="atc_code"
          type="text"
          placeholder="N02BE01"
          className={`input input-bordered w-full ${errors.atc_code ? "input-error" : ""}`}
          {...register("atc_code")}
        />
        {errors.atc_code && (
          <label className="label">
            <span className="label-text-alt text-error">{errors.atc_code.message}</span>
          </label>
        )}
      </div>

      <button
        type="submit"
        className="btn btn-primary"
        disabled={isSubmitting}
      >
        {isSubmitting ? (
          <><span className="loading loading-spinner loading-sm" />Saving…</>
        ) : "Save"}
      </button>

    </form>
  );
}
```

### daisyUI Class Reference for Forms

| Element | Classes |
|---|---|
| Field wrapper | `form-control` |
| Label row | `label` + `label-text` |
| Text input | `input input-bordered w-full` |
| Input with error | add `input-error` |
| Textarea | `textarea textarea-bordered w-full` |
| Select | `select select-bordered w-full` |
| Error message | `label` + `label-text-alt text-error` |
| Root/API error | `alert alert-error` |
| Submit button | `btn btn-primary` |
| Loading spinner | `loading loading-spinner loading-sm` |

---

## Combining with Server Actions

For most write paths the action's own `useActionState` (per `frontend/16-server-actions`) is enough — the action validates with the same Zod schema server-side and returns errors as state. Use React Hook Form's client validation as a **pre-submit gate** so invalid data never crosses the wire and the user gets per-field feedback synchronously, then forward to the Server Action on success:

```tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

import { createDrugAction } from "@/app/(app)/drugs/_actions";

export function CreateDrugForm({ onClose }: { onClose: () => void }) {
  const form = useForm<DrugFormData>({
    resolver: zodResolver(DrugSchema),
    defaultValues: { inn: "", atc_code: "" },
  });

  const onSubmit = form.handleSubmit(async (data) => {
    const result = await createDrugAction(data);          // Server Action — see frontend/16
    if (result.status === "error") {
      // The action returns server-side validation errors / domain errors as data,
      // never as a thrown HTTPException; map them back onto the form.
      if (result.fieldErrors) {
        for (const [field, message] of Object.entries(result.fieldErrors)) {
          form.setError(field as keyof DrugFormData, { type: "server", message });
        }
        return;
      }
      form.setError("root", { type: "server", message: result.formError });
      return;
    }
    onClose();                                            // revalidateTag inside the action refreshes the list
  });

  return (
    <form onSubmit={onSubmit}>
      {/* fields */}
      <button type="submit" disabled={form.formState.isSubmitting}>
        {form.formState.isSubmitting ? "Creating…" : "Create"}
      </button>
    </form>
  );
}
```

Two non-negotiables:

1. **The same Zod schema runs on both sides.** Client validation is UX; the Server Action's server-side `safeParse` is the real gate. Define `DrugSchema` once and import it into both the form and the action.
2. **Server errors return as data, not thrown exceptions.** The action's return type (`status: "ok" | "error"`) is part of the contract — the form pattern above relies on it. Don't throw from the action and hope `error.tsx` will catch it; map errors back onto the form fields.

For genuinely client-driven submissions that need optimistic UI, retries, or background polling, write a small in-repo hook around `fetch` + `AbortController` rather than reaching for a library on the first occurrence.

---

## Anti-Pattern: Manual State Validation

```tsx
// ❌ WRONG — manual state for every field, manual validation
"use client";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [emailError, setEmailError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!email.includes("@")) {        // duplicates Zod's logic
      setEmailError("Invalid email");
      return;
    }
    // ...
  };

  return (
    <form>
      <input value={email} onChange={(e) => setEmail(e.target.value)} />
      {emailError && <p>{emailError}</p>}
    </form>
  );
}
```

This approach scales to 50+ lines for a 3-field form. Every field needs its own `useState`, every rule is duplicated logic, there's no shared schema that can be reused for server-side validation. Use Zod + React Hook Form instead.

---

## Quick Checklist

- [ ] Every form has a Zod schema defined before `useForm` is called
- [ ] TypeScript form type is `z.infer<typeof Schema>` — never a hand-written `interface`
- [ ] `zodResolver(Schema)` is passed to `useForm({ resolver: ... })`
- [ ] API errors are attached via `setError("root", { message: ... })` and rendered as `{errors.root?.message}`
- [ ] `isSubmitting` or `isPending` disables the submit button and shows a loading label
- [ ] `input-error` class applied to the input when `errors.fieldName` is set
- [ ] Error messages use `label-text-alt text-error` inside a second `<label className="label">` — daisyUI standard placement
- [ ] Error-state inputs have `aria-invalid` and `aria-describedby` wired to the error message element (see `frontend/15-accessibility`)
- [ ] No `useState` + manual validation logic — let Zod handle it

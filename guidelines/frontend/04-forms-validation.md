# Forms and Validation — React Hook Form + Zod

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
      <div>
        <input
          {...register("email")}
          type="email"
          placeholder="Email"
          className="input"
        />
        {errors.email && (
          <p className="text-sm text-red-500">{errors.email.message}</p>
        )}
      </div>

      <div>
        <input
          {...register("password")}
          type="password"
          placeholder="Password"
        />
        {errors.password && (
          <p className="text-sm text-red-500">{errors.password.message}</p>
        )}
      </div>

      {errors.root && (
        <p className="text-sm text-red-500">{errors.root.message}</p>
      )}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Signing in…" : "Sign in"}
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

## shadcn/ui Form Components

When using shadcn/ui's `<Form>` components, the integration is slightly different:

```tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function DrugForm({ onSuccess }: { onSuccess: () => void }) {
  const form = useForm<DrugFormData>({
    resolver: zodResolver(DrugSchema),
    defaultValues: { inn: "", atc_code: "", form: "" },
  });

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
        <FormField
          control={form.control}
          name="inn"
          render={({ field }) => (
            <FormItem>
              <FormLabel>INN</FormLabel>
              <FormControl>
                <Input placeholder="Paracetamol" {...field} />
              </FormControl>
              <FormMessage />  {/* renders errors.inn.message automatically */}
            </FormItem>
          )}
        />

        <Button type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Saving…" : "Save"}
        </Button>
      </form>
    </Form>
  );
}
```

`<FormMessage />` reads from `formState.errors[name]` automatically — no manual `{errors.inn && <p>...}` needed.

---

## Combining with React Query Mutations

```tsx
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";

export function CreateDrugForm({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();

  const { mutate, isPending } = useMutation({
    mutationFn: DrugService.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drugs"] });
      onClose();
    },
  });

  const form = useForm<DrugFormData>({
    resolver: zodResolver(DrugSchema),
    defaultValues: { inn: "", atc_code: "" },
  });

  const onSubmit = (data: DrugFormData) => mutate(data);
  //               ^ only called if schema validation passes

  return (
    <form onSubmit={form.handleSubmit(onSubmit)}>
      {/* fields */}
      <button type="submit" disabled={isPending}>
        {isPending ? "Creating…" : "Create"}
      </button>
    </form>
  );
}
```

The schema validation gate runs before `mutate` — invalid data never hits the network.

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
- [ ] shadcn/ui `<FormMessage />` is used inside `<FormField>` — no manual error rendering
- [ ] No `useState` + manual validation logic — let Zod handle it

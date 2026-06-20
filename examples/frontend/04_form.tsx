// Description: React Hook Form + Zod — schema-first validation, zodResolver, error display
// ─────────────────────────────────────────────────────────────────────────────
// PATTERN: Define the Zod schema first. Infer the TypeScript type from it.
// Pass zodResolver to useForm. Errors flow from the schema automatically.
// Never write manual validation logic — let Zod handle it.
// ─────────────────────────────────────────────────────────────────────────────

"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
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
import { DrugService } from "@/services/drugs";
import { ApiError } from "@/services/api";

// ── 1. Schema first — single source of truth ─────────────────────────────────

const DrugSchema = z.object({
  inn: z
    .string()
    .min(2, "INN must be at least 2 characters")
    .max(200, "INN is too long"),
  atc_code: z
    .string()
    .regex(/^[A-Z]\d{2}[A-Z]{2}\d{2}$/, "Invalid ATC code format (e.g. A10BA02)"),
  form: z.enum(["tablet", "capsule", "syrup", "injection", "cream"], {
    errorMap: () => ({ message: "Select a valid form" }),
  }),
  strength: z.string().min(1, "Strength is required"),
  notes: z.string().max(500).optional(),
});

// ── 2. Infer TypeScript type from schema — never write a duplicate interface ──
type DrugFormData = z.infer<typeof DrugSchema>;

// ── 3. Form component ─────────────────────────────────────────────────────────

type DrugFormProps = {
  defaultValues?: Partial<DrugFormData>;
  onSuccess: () => void;
};

export function DrugForm({ defaultValues, onSuccess }: DrugFormProps) {
  const queryClient = useQueryClient();

  // ── Connect schema to form ────────────────────────────────────────────────
  const form = useForm<DrugFormData>({
    resolver: zodResolver(DrugSchema),       // Zod validates on every submit
    defaultValues: {
      inn: "",
      atc_code: "",
      form: "tablet",
      strength: "",
      notes: "",
      ...defaultValues,
    },
  });

  // ── Wire mutation ─────────────────────────────────────────────────────────
  const { mutate, isPending } = useMutation({
    mutationFn: DrugService.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drugs"] });
      onSuccess();
    },
    onError: (err) => {
      if (err instanceof ApiError) {
        // Map server errors back to specific fields when possible
        if (err.status === 409) {
          form.setError("inn", { message: "This INN already exists" });
        } else {
          form.setError("root", { message: err.message });
        }
      }
    },
  });

  // handleSubmit only calls onSubmit when ALL schema validations pass
  const onSubmit = (data: DrugFormData) => mutate(data);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">

        {/* shadcn/ui FormField — renders label, control, and error message */}
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

        <FormField
          control={form.control}
          name="atc_code"
          render={({ field }) => (
            <FormItem>
              <FormLabel>ATC Code</FormLabel>
              <FormControl>
                <Input placeholder="N02BE01" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="form"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Pharmaceutical Form</FormLabel>
              <FormControl>
                <select {...field} className="select">
                  <option value="tablet">Tablet</option>
                  <option value="capsule">Capsule</option>
                  <option value="syrup">Syrup</option>
                  <option value="injection">Injection</option>
                  <option value="cream">Cream</option>
                </select>
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="strength"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Strength</FormLabel>
              <FormControl>
                <Input placeholder="500mg" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        {/* Root-level error for non-field API errors */}
        {form.formState.errors.root && (
          <p className="text-sm text-red-500">
            {form.formState.errors.root.message}
          </p>
        )}

        <Button type="submit" disabled={isPending || form.formState.isSubmitting}>
          {isPending ? "Saving…" : "Save Drug"}
        </Button>
      </form>
    </Form>
  );
}

// ── Cross-field validation example ────────────────────────────────────────────

const ChangePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Required"),
    new_password: z.string().min(8, "Minimum 8 characters"),
    confirm_password: z.string().min(1, "Required"),
  })
  .refine((d) => d.new_password === d.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],   // attach error to the confirm field
  });

type ChangePasswordData = z.infer<typeof ChangePasswordSchema>;

export function ChangePasswordForm() {
  const form = useForm<ChangePasswordData>({
    resolver: zodResolver(ChangePasswordSchema),
  });

  return (
    <form onSubmit={form.handleSubmit(console.log)} className="space-y-4">
      <input {...form.register("current_password")} type="password" placeholder="Current password" />
      <input {...form.register("new_password")} type="password" placeholder="New password" />
      <input {...form.register("confirm_password")} type="password" placeholder="Confirm new password" />
      {form.formState.errors.confirm_password && (
        <p className="text-sm text-red-500">
          {form.formState.errors.confirm_password.message}
        </p>
      )}
      <button type="submit">Change password</button>
    </form>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// ANTI-PATTERN — manual state + manual validation:
//
//   const [inn, setInn] = useState("");
//   const [innError, setInnError] = useState("");
//
//   const validate = () => {
//     if (inn.length < 2) { setInnError("Too short"); return false; }
//     return true;
//   };
//
// For every field you need a useState + an error useState + manual checks.
// Use Zod + zodResolver — one schema, zero duplicated logic.
// ─────────────────────────────────────────────────────────────────────────────

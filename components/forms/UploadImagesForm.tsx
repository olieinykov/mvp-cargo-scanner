"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";

import { buildAnalyzeSignsFormData } from "@/utils/form-helpers";
import { uploadImagesSchema, type UploadImagesSchema } from "@/lib/validations/upload";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export type UploadImagesFormValues = UploadImagesSchema;

export function UploadImagesForm() {
  const [responseText, setResponseText] = React.useState<string>("");
  const [submitError, setSubmitError] = React.useState<string>("");
  const [fileInputsKey, setFileInputsKey] = React.useState<number>(0);

  const form = useForm<UploadImagesFormValues>({
    resolver: zodResolver(uploadImagesSchema),
    defaultValues: {
      bolPhoto: undefined as unknown as File,
      markerPhoto: undefined as unknown as File,
      cargoPhoto: undefined as unknown as File,
    },
    mode: "onSubmit",
  });

  const isSubmitting = form.formState.isSubmitting;

  async function onSubmit(values: UploadImagesFormValues) {
    setSubmitError("");
    setResponseText("");

    try {
      const formData = buildAnalyzeSignsFormData(values);

      const res = await fetch("http://127.0.0.1:8000/analyze-image", {
        method: "POST",
        body: formData,
      });

      const contentType = res.headers.get("content-type") ?? "";
      const text = contentType.includes("application/json")
        ? JSON.stringify(await res.json(), null, 2)
        : await res.text();

      if (!res.ok) {
        setSubmitError(text || `HTTP ${res.status}`);
        return;
      }

      setResponseText(text || "OK");
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "Unknown error");
    }
  }

  return (
    <Card className="w-full max-w-xl">
      <CardHeader>
        <CardTitle>Upload images</CardTitle>
        <CardDescription>Загрузите 3 изображения: BOL, marker и cargo. Все поля обязательны.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-5">
            <FormField
              control={form.control}
              name="bolPhoto"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>BOL photo</FormLabel>
                  <FormControl>
                    <Input
                      key={`bol-${fileInputsKey}`}
                      type="file"
                      accept="image/*"
                      onChange={(e) => field.onChange(e.target.files?.[0] ?? undefined)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="markerPhoto"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Marker photo</FormLabel>
                  <FormControl>
                    <Input
                      key={`marker-${fileInputsKey}`}
                      type="file"
                      accept="image/*"
                      onChange={(e) => field.onChange(e.target.files?.[0] ?? undefined)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="cargoPhoto"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Cargo photo</FormLabel>
                  <FormControl>
                    <Input
                      key={`cargo-${fileInputsKey}`}
                      type="file"
                      accept="image/*"
                      onChange={(e) => field.onChange(e.target.files?.[0] ?? undefined)}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {submitError ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/40 dark:text-red-300">
                {submitError}
              </div>
            ) : null}

            <div className="flex items-center gap-3">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Sending..." : "Send"}
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  form.reset();
                  setFileInputsKey((k) => k + 1);
                  setResponseText("");
                  setSubmitError("");
                }}
                disabled={isSubmitting}
              >
                Reset
              </Button>
            </div>
          </form>
        </Form>

        <div className="space-y-2">
          <div className="text-sm font-medium">Response</div>
          <Textarea readOnly value={responseText} placeholder="Ответ сервера появится здесь..." />
        </div>
      </CardContent>
    </Card>
  );
}


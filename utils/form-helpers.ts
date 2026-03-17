import type { UploadImagesSchema } from "@/lib/validations/upload";

export function buildAnalyzeSignsFormData(values: UploadImagesSchema) {
  const fd = new FormData();
  fd.append("bolPhoto", values.bolPhoto);
  fd.append("markerPhoto", values.markerPhoto);
  fd.append("cargoPhoto", values.cargoPhoto);
  return fd;
}


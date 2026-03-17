import { z } from "zod";

const imageFileSchema = z
  .instanceof(File, { message: "Файл обязателен" })
  .refine((file) => file.size > 0, { message: "Файл обязателен" })
  .refine((file) => file.type.startsWith("image/"), { message: "Допустимы только изображения" });

export const uploadImagesSchema = z.object({
  bolPhoto: imageFileSchema,
  markerPhoto: imageFileSchema,
  cargoPhoto: imageFileSchema,
});

export type UploadImagesSchema = z.infer<typeof uploadImagesSchema>;


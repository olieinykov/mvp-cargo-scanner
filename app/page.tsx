import { UploadImagesForm } from "@/components/forms/UploadImagesForm";

export default async function Page() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <UploadImagesForm />
    </div>
  );
}

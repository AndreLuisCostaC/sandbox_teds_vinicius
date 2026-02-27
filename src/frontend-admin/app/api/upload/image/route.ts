import { NextResponse } from "next/server";
import { assertCsrf } from "@/lib/csrf";
import { safeJsonFromResponse } from "@/lib/safe-json";

export async function POST(request: Request) {
  try {
    await assertCsrf(request);
  } catch {
    return NextResponse.json({ detail: "CSRF validation failed." }, { status: 403 });
  }
  const formData = await request.formData();
  const file = formData.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ detail: "Image file is required." }, { status: 400 });
  }

  const cloudName = process.env.CLOUDINARY_CLOUD_NAME;
  const uploadPreset = process.env.CLOUDINARY_UPLOAD_PRESET;
  if (!cloudName || !uploadPreset) {
    return NextResponse.json(
      {
        detail:
          "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME and CLOUDINARY_UPLOAD_PRESET.",
      },
      { status: 500 }
    );
  }

  const uploadBody = new FormData();
  uploadBody.append("file", file);
  uploadBody.append("upload_preset", uploadPreset);
  uploadBody.append("folder", "prodgrade-products");

  const cloudinaryResponse = await fetch(
    `https://api.cloudinary.com/v1_1/${cloudName}/image/upload`,
    {
      method: "POST",
      body: uploadBody,
    }
  );

  const payload = await safeJsonFromResponse<{
    secure_url?: string;
    error?: { message?: string };
  }>(cloudinaryResponse, { error: { message: "Upload failed" } });
  if (!cloudinaryResponse.ok || !payload.secure_url) {
    return NextResponse.json(
      { detail: payload.error?.message ?? "Cloudinary upload failed." },
      { status: 502 }
    );
  }

  return NextResponse.json({ imageUrl: payload.secure_url }, { status: 200 });
}

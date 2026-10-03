import { authRequest, AuthRequestError } from "./auth";

export const RESEND_MESSAGE =
  "If an unverified AXIOM account exists for that address, a verification email will be sent.";
export type VerificationResult = {
  kind: "success" | "invalid" | "error";
  message: string;
};
export async function verifyEmail(
  token: string | null,
): Promise<VerificationResult> {
  if (!token)
    return {
      kind: "invalid",
      message:
        "This verification link is missing its token. Request another email.",
    };
  if (!/^[A-Za-z0-9_-]{43}$/.test(token))
    return {
      kind: "invalid",
      message: "This verification link is invalid. Request another email.",
    };
  try {
    await authRequest("/auth/verify-email", "POST", { token });
    return { kind: "success", message: "Email verified successfully." };
  } catch (error) {
    if (error instanceof AuthRequestError && [400, 422].includes(error.status))
      return {
        kind: "invalid",
        message:
          "This link is invalid, expired, already used or replaced by a newer link. Sign in if you already verified, or request another email.",
      };
    return {
      kind: "error",
      message:
        error instanceof AuthRequestError && error.status === 429
          ? "Too many requests. Wait a minute before retrying."
          : "Verification is unavailable. Please retry or request another email.",
    };
  }
}
export async function resendVerification(email: string): Promise<string> {
  await authRequest("/auth/resend-verification", "POST", { email });
  return RESEND_MESSAGE;
}

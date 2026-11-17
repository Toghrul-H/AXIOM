import { authRequest, AuthRequestError } from "./auth";

export const PASSWORD_RESET_REQUEST_MESSAGE =
  "If an eligible account exists for that email address, password reset instructions will be sent.";

export type PasswordResetResult =
  | { kind: "success"; message: string }
  | { kind: "invalid"; message: string }
  | { kind: "error"; message: string };

export async function requestPasswordReset(email: string): Promise<string> {
  await authRequest("/auth/forgot-password", "POST", { email });
  return PASSWORD_RESET_REQUEST_MESSAGE;
}

export async function resetPassword(
  token: string | null,
  password: string,
): Promise<PasswordResetResult> {
  if (!token || !/^[A-Za-z0-9_-]{43}$/.test(token)) {
    return {
      kind: "invalid",
      message: "This password reset link is invalid or has expired.",
    };
  }
  try {
    await authRequest("/auth/reset-password", "POST", { token, password });
    return {
      kind: "success",
      message: "Your password has been reset. You can now sign in.",
    };
  } catch (error) {
    if (error instanceof AuthRequestError && [400, 422].includes(error.status))
      return {
        kind: "invalid",
        message: "This password reset link is invalid or has expired.",
      };
    return {
      kind: "error",
      message: "Password reset is unavailable. Please request another link.",
    };
  }
}

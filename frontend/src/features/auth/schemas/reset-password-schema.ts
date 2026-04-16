// Runtime validation lives in ResetPasswordForm.tsx so error messages can be
// resolved through next-intl. Only the form data type is exported here.
export type ResetPasswordFormData = {
  code: string;
  newPassword: string;
  confirmPassword: string;
};

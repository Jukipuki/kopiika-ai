// Runtime validation lives in ForgotPasswordForm.tsx so error messages can be
// resolved through next-intl. Only the form data type is exported here.
export type ForgotPasswordFormData = {
  email: string;
};

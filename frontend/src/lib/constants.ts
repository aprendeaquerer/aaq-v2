export const API_URL = (process.env.NEXT_PUBLIC_API_URL || '/api/backend')
  .replace(/\\n/g, '')
  .trim()
  .replace(/\/$/, '');

export const LANGUAGES = ['es', 'en', 'ru'] as const;
export type Language = (typeof LANGUAGES)[number];

export const ATTACHMENT_STYLES = ['secure', 'anxious', 'avoidant', 'disorganized'] as const;
export type AttachmentStyle = (typeof ATTACHMENT_STYLES)[number];

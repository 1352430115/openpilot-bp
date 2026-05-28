import en from '../../locales/en.json'

export type TranslationKey = keyof typeof en

export type Translations = Record<TranslationKey, string>

export const DEFAULT_LANGUAGE = 'en'

export const SUPPORTED_LANGUAGES = [
  'en',
  'de',
  'fr',
  'pt-BR',
  'es',
  'tr',
  'uk',
  'th',
  'zh-CHT',
  'zh-CHS',
  'ko',
  'ja',
] as const

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]

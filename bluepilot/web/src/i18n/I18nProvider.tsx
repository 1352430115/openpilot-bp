import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import en from '../../locales/en.json'
import {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  type SupportedLanguage,
  type TranslationKey,
  type Translations,
} from './types'

interface I18nContextValue {
  language: SupportedLanguage
  ready: boolean
  t: (key: TranslationKey, vars?: Record<string, string | number>) => string
  reload: () => Promise<void>
}

const I18nContext = createContext<I18nContextValue | null>(null)

const bundledEn = en as Translations

function interpolate(text: string, vars?: Record<string, string | number>): string {
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = vars[name]
    return value === undefined ? `{${name}}` : String(value)
  })
}

function normalizeLanguage(code: string | null | undefined): SupportedLanguage {
  if (!code) return DEFAULT_LANGUAGE
  const cleaned = code.replace(/^main_/, '').trim()
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(cleaned)
    ? (cleaned as SupportedLanguage)
    : DEFAULT_LANGUAGE
}

async function fetchDeviceLanguage(): Promise<SupportedLanguage> {
  try {
    const response = await fetch('/api/system/device-info')
    if (!response.ok) return DEFAULT_LANGUAGE
    const data = await response.json()
    return normalizeLanguage(data.language)
  } catch {
    return DEFAULT_LANGUAGE
  }
}

async function loadTranslations(language: SupportedLanguage): Promise<Translations> {
  if (language === DEFAULT_LANGUAGE) {
    return bundledEn
  }

  try {
    const response = await fetch(`/locales/${language}.json`)
    if (response.ok) {
      return (await response.json()) as Translations
    }
  } catch {
    // fall through to English
  }

  return bundledEn
}

interface I18nProviderProps {
  children: ReactNode
}

export function I18nProvider({ children }: I18nProviderProps) {
  const [language, setLanguage] = useState<SupportedLanguage>(DEFAULT_LANGUAGE)
  const [messages, setMessages] = useState<Translations>(bundledEn)
  const [ready, setReady] = useState(false)

  const applyLanguage = useCallback(async (lang: SupportedLanguage) => {
    const loaded = await loadTranslations(lang)
    setLanguage(lang)
    setMessages(loaded)
    document.documentElement.lang = lang === 'zh-CHS' ? 'zh-Hans' : lang === 'zh-CHT' ? 'zh-Hant' : lang.split('-')[0]
  }, [])

  const reload = useCallback(async () => {
    const lang = await fetchDeviceLanguage()
    await applyLanguage(lang)
    setReady(true)
  }, [applyLanguage])

  useEffect(() => {
    void reload()
  }, [reload])

  useEffect(() => {
    const onParamUpdated = (event: Event) => {
      const detail = (event as CustomEvent<{ key?: string }>).detail
      if (detail?.key === 'LanguageSetting') {
        void reload()
      }
    }
    window.addEventListener('bp-language-changed', onParamUpdated)
    return () => window.removeEventListener('bp-language-changed', onParamUpdated)
  }, [reload])

  const t = useCallback(
    (key: TranslationKey, vars?: Record<string, string | number>) => {
      const text = messages[key] ?? bundledEn[key] ?? key
      return interpolate(text, vars)
    },
    [messages],
  )

  const value = useMemo(
    () => ({ language, ready, t, reload }),
    [language, ready, t, reload],
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext)
  if (!ctx) {
    throw new Error('useI18n must be used within I18nProvider')
  }
  return ctx
}

export function useTranslation() {
  const { t, language, ready } = useI18n()
  return { t, language, ready }
}

import { useState, useEffect } from 'react'
import { Icon } from './Icon'
import { useTranslation } from '@/i18n'
import './WarningBanners.css'

export const WarningBanners = () => {
  const { t } = useTranslation()
  const [showCellular, setShowCellular] = useState(false)
  const [showFirefox, setShowFirefox] = useState(false)

  useEffect(() => {
    // Check if Firefox
    const isFirefox = navigator.userAgent.toLowerCase().includes('firefox')
    if (isFirefox) {
      setShowFirefox(true)
    }

    // Check for cellular connection (placeholder - would need backend support)
    // setShowCellular(checkCellularStatus())
  }, [])

  if (!showCellular && !showFirefox) {
    return null
  }

  return (
    <>
      {showCellular && (
        <div className="cellular-warning">
          <div className="cellular-warning-content">
            <Icon name="warning" size={24} />
            <div className="cellular-warning-text">
              <strong>{t('banner.cellularTitle')}</strong>
              <span>{t('banner.cellularMsg')}</span>
            </div>
            <button className="cellular-warning-close" onClick={() => setShowCellular(false)} title={t('banner.dismiss')}>
              <Icon name="close" size={20} />
            </button>
          </div>
        </div>
      )}

      {showFirefox && (
        <div className="firefox-warning">
          <div className="firefox-warning-content">
            <Icon name="info" size={24} />
            <div className="firefox-warning-text">
              <strong>{t('banner.firefoxTitle')}</strong>
              <span>{t('banner.firefoxMsg')}</span>
            </div>
            <button className="firefox-warning-close" onClick={() => setShowFirefox(false)} title={t('banner.dismiss')}>
              <Icon name="close" size={20} />
            </button>
          </div>
        </div>
      )}
    </>
  )
}

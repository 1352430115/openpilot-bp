import { useEffect, useState, useMemo, useCallback } from 'react'
import { Header } from '@/components/layout/Header'
import { useParamsStore } from '@/stores/useParamsStore'
import { LoadingSpinner, Button, Modal, ToastContainer, ToggleSwitch, BackToTop } from '@/components/common'
import type { Parameter, DeviceStatus } from '@/types'
import { formatParamValueForDisplay } from '@/utils/params'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n'
import './ParametersView.css'

interface ParametersViewProps {
  deviceStatus?: DeviceStatus
}

type SortColumn = 'key' | 'value' | 'type' | 'category' | 'last_modified'
type SortDirection = 'asc' | 'desc'

const SORT_COLUMNS: SortColumn[] = ['key', 'value', 'type', 'category', 'last_modified']

const SORT_LABEL_KEYS: Record<SortColumn, TranslationKey> = {
  key: 'parameters.sort.key',
  value: 'parameters.sort.value',
  type: 'parameters.sort.type',
  category: 'parameters.sort.category',
  last_modified: 'parameters.sort.lastModified',
}

const NUMERIC_TYPES = new Set(['number', 'int', 'float'])
const BOOLEAN_TYPES = new Set(['boolean', 'bool'])

const getSortValue = (param: Parameter, column: SortColumn): string | number | boolean | null | undefined => {
  switch (column) {
    case 'key':
      return param.key
    case 'value':
      return param.value
    case 'type':
      return param.type
    case 'category':
      return param.category ?? ''
    case 'last_modified':
      return param.last_modified ?? 0
    default:
      return ''
  }
}

export const ParametersView = ({ deviceStatus = 'checking' }: ParametersViewProps) => {
  const { t } = useTranslation()
  const { params, loading, fetchParams, updateParam, searchQuery, setSearchQuery, getFilteredParams } =
    useParamsStore()
  const [editingParam, setEditingParam] = useState<Parameter | null>(null)
  const [editValue, setEditValue] = useState<string>('')
  const [editMode, setEditMode] = useState(false)
  const [sortColumn, setSortColumn] = useState<SortColumn>('key')
  const [sortDirection, setSortDirection] = useState<SortDirection>('asc')
  const [viewValueModal, setViewValueModal] = useState<Parameter | null>(null)
  const [toasts, setToasts] = useState<Array<{ id: string; message: string; type?: 'success' | 'error' | 'info' }>>([])

  useEffect(() => {
    fetchParams()
  }, [fetchParams])

  useEffect(() => {
    const onLanguageChanged = () => {
      fetchParams()
    }
    window.addEventListener('bp-language-changed', onLanguageChanged)
    return () => window.removeEventListener('bp-language-changed', onLanguageChanged)
  }, [fetchParams])

  const formatLastModified = useCallback(
    (timestamp?: number): string => {
      if (!timestamp) return t('parameters.lastModified.never')

      const date = new Date(timestamp * 1000)
      const now = new Date()
      const diffMs = now.getTime() - date.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      const diffHours = Math.floor(diffMs / 3600000)
      const diffDays = Math.floor(diffMs / 86400000)

      if (diffMins < 1) return t('parameters.lastModified.justNow')
      if (diffMins < 60) return t('parameters.lastModified.minutesAgo', { count: diffMins })
      if (diffHours < 24) return t('parameters.lastModified.hoursAgo', { count: diffHours })
      if (diffDays < 7) return t('parameters.lastModified.daysAgo', { count: diffDays })
      return date.toLocaleDateString()
    },
    [t],
  )

  const sortedParams = useMemo(() => {
    const filtered = getFilteredParams()
      .filter((param) => param.key && param.key !== 'null' && param.key !== 'undefined')

    return filtered.sort((a, b) => {
      let aVal = getSortValue(a, sortColumn)
      let bVal = getSortValue(b, sortColumn)

      if (aVal === undefined || aVal === null) aVal = ''
      if (bVal === undefined || bVal === null) bVal = ''

      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase()
      }
      if (typeof bVal === 'string') {
        bVal = bVal.toLowerCase()
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1
      return 0
    })
  }, [params, searchQuery, getFilteredParams, sortColumn, sortDirection])

  const toggleSortDirection = () => {
    setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'))
  }

  const handleEdit = (param: Parameter) => {
    setEditingParam(param)
    setEditValue(String(param.value))
  }

  const handleSave = async () => {
    if (!editingParam) return

    let value: string | number | boolean = editValue
    const type = editingParam.type?.toLowerCase()

    if (type && NUMERIC_TYPES.has(type)) {
      const parsed = Number(editValue)
      value = Number.isNaN(parsed) ? 0 : parsed
    } else if (type && BOOLEAN_TYPES.has(type)) {
      value = editValue === 'true'
    }

    await updateParam(editingParam.key, value)
    setEditingParam(null)
  }

  const handleViewValue = (param: Parameter) => {
    setViewValueModal(param)
  }

  const addToast = (message: string, type: 'success' | 'error' | 'info' = 'success') => {
    const id = `${Date.now()}-${Math.random()}`
    setToasts((prev) => [...prev, { id, message, type }])
  }

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id))
  }

  const copyToClipboard = (text: string, labelKey: 'parameters.label.key' | 'parameters.label.value') => {
    const label = t(labelKey)
    navigator.clipboard
      .writeText(text)
      .then(() => {
        addToast(t('parameters.copiedToClipboard', { label }), 'success')
      })
      .catch(() => {
        addToast(t('parameters.copyFailed'), 'error')
      })
  }

  const formattedModalValue = viewValueModal ? formatParamValueForDisplay(viewValueModal) : null
  const modalValueDisplay = (() => {
    if (!formattedModalValue) return '—'
    if (formattedModalValue.isBinary) {
      if (formattedModalValue.decodedString) return formattedModalValue.decodedString
      if (viewValueModal?.raw_value) return viewValueModal.raw_value
    }
    return formattedModalValue.display || formattedModalValue.raw || '—'
  })()
  const modalCopyValue = formattedModalValue?.raw ?? modalValueDisplay

  if (loading && Object.keys(params).length === 0) {
    return (
      <>
        <Header deviceStatus={deviceStatus} />
        <div className="loading">
          <LoadingSpinner size="large" message={t('parameters.loading')} />
        </div>
      </>
    )
  }

  return (
    <>
      <Header deviceStatus={deviceStatus} subtitle={t('parameters.subtitle')} />
      <ToastContainer toasts={toasts} onRemove={removeToast} />
      <div className="params-manager">
        <div className="params-header">
          <div className="params-controls">
            <div className="params-sort-controls">
              <label htmlFor="params-sort">{t('parameters.sort')}</label>
              <select
                id="params-sort"
                value={sortColumn}
                onChange={(e) => setSortColumn(e.target.value as SortColumn)}
              >
                {SORT_COLUMNS.map((column) => (
                  <option key={column} value={column}>
                    {t(SORT_LABEL_KEYS[column])}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="sort-direction-btn"
                onClick={toggleSortDirection}
                title={
                  sortDirection === 'asc'
                    ? t('parameters.sort.switchToDescending')
                    : t('parameters.sort.switchToAscending')
                }
              >
                {sortDirection === 'asc' ? t('parameters.sort.asc') : t('parameters.sort.desc')}
              </button>
            </div>
            <ToggleSwitch
              checked={editMode}
              onChange={setEditMode}
              label={t('parameters.editMode')}
              size="compact"
              alignLabel="start"
              className={`params-edit-toggle ${editMode ? 'active' : ''}`}
              title={t('parameters.enableEditing')}
            />
            <input
              type="text"
              id="params-search"
              placeholder={t('parameters.search')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
        <div className="params-content">
          {sortedParams.length === 0 ? (
            <div className="empty-state">
              <p>{t('parameters.noResults')}</p>
            </div>
          ) : (
            <div className="params-list">
              {sortedParams.map((param) => {
                const formattedValue = formatParamValueForDisplay(param)
                const trimmed = formattedValue.display.trim()
                const preview =
                  trimmed.length > 260 ? `${trimmed.substring(0, 257).trimEnd()}…` : trimmed || '—'
                const formatBadge = formattedValue.formatLabel?.toUpperCase()
                const typeBadge = param.type ? param.type.toUpperCase() : null
                const attributeBadges = param.attributes || []

                return (
                  <div className="param-row" key={param.key}>
                    <div className="param-row__header">
                      <div className="param-row__title-block">
                        <div className="param-row__title-line">
                          <span className="param-key" title={param.key}>
                            {param.key}
                          </span>
                          <div className="param-row__status-chips">
                            {param.category && (
                              <span className={`param-badge category ${param.category.toLowerCase()}`}>
                                {param.category}
                              </span>
                            )}
                            {param.readonly && (
                              <span className="param-badge readonly">{t('parameters.badge.readonly')}</span>
                            )}
                            {param.critical && (
                              <span className="param-badge critical">{t('parameters.badge.critical')}</span>
                            )}
                          </div>
                        </div>
                        <div className="param-last-modified">
                          {t('parameters.lastModified', { time: formatLastModified(param.last_modified) })}
                        </div>
                        {param.description && (
                          <p className="param-row__description">{param.description}</p>
                        )}
                      </div>
                      <div className="param-row__actions">
                        {param.readonly ? (
                          <Button size="small" variant="ghost" className="param-edit-btn" disabled>
                            {t('parameters.readOnly')}
                          </Button>
                        ) : (
                          <Button
                            size="small"
                            variant="primary"
                            className="param-edit-btn"
                            onClick={() => handleEdit(param)}
                            disabled={!editMode || param.type === 'bytes'}
                            title={param.type === 'bytes' ? t('parameters.binaryViewOnly') : undefined}
                          >
                            {t('parameters.edit')}
                          </Button>
                        )}
                      </div>
                    </div>
                    <div
                      className="param-row__value"
                      title={t('parameters.viewFullValue')}
                      onClick={() => handleViewValue(param)}
                    >
                      <div className="param-row__value-header">
                        <span className="value-label">{t('parameters.value')}</span>
                        <div className="value-pill-group">
                          {typeBadge && <span className="value-pill value-pill--type">{typeBadge}</span>}
                          {attributeBadges.map((attr) => (
                            <span key={attr} className="value-pill value-pill--attribute">{attr}</span>
                          ))}
                          {formatBadge && formatBadge !== typeBadge && (
                            <span className="value-pill">{formatBadge}</span>
                          )}
                          {param.type === 'bytes' && param.byte_length !== undefined && (
                            <span className="value-pill value-pill--outline">
                              {t('parameters.bytes', { count: param.byte_length })}
                            </span>
                          )}
                        </div>
                      </div>
                      <pre className="value-code-block">
                        <code>{preview}</code>
                      </pre>
                      <span className="value-footer-hint">{t('parameters.inspectHint')}</span>
                    </div>
                    {param.critical && (
                      <div className="critical-flag">
                        <span>⚠️ {t('parameters.criticalFlag')}</span>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      <Modal
        isOpen={editingParam !== null}
        onClose={() => setEditingParam(null)}
        title={t('parameters.editTitle')}
        size="small"
      >
        {editingParam && (
          <div className="edit-param-modal-new">
            <div className="edit-param-header">
              <div className="edit-param-key-section">
                <span className="param-key-label">{t('parameters.paramKey')}</span>
                <code className="param-key-value-edit">{editingParam.key}</code>
              </div>
              <div className="edit-param-type">
                <span className={`param-badge ${editingParam.type}`}>{editingParam.type}</span>
              </div>
            </div>

            {editingParam.description && (
              <div className="edit-param-description">
                <span className="description-label">{t('parameters.description')}</span>
                <p>{editingParam.description}</p>
              </div>
            )}

            <div className="edit-param-input-section">
              <label htmlFor="edit-param-value" className="input-label">
                {t('parameters.newValue')}
              </label>
              {editingParam.type && BOOLEAN_TYPES.has(editingParam.type.toLowerCase()) ? (
                <select
                  id="edit-param-value"
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="edit-input-new"
                  autoFocus
                >
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              ) : (
                <input
                  id="edit-param-value"
                  type={editingParam.type && NUMERIC_TYPES.has(editingParam.type.toLowerCase()) ? 'number' : 'text'}
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  className="edit-input-new"
                  placeholder={t('parameters.enterValue', { type: editingParam.type ?? '' })}
                  autoFocus
                />
              )}
            </div>

            {editingParam.critical && (
              <div className="edit-warning-banner">
                <span className="warning-icon">⚠️</span>
                <div className="warning-content">
                  <strong>{t('parameters.criticalWarningTitle')}</strong>
                  <p>{t('parameters.criticalWarningMsg')}</p>
                </div>
              </div>
            )}

            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setEditingParam(null)}>
                {t('common.cancel')}
              </Button>
              <Button variant="primary" onClick={handleSave}>
                {t('parameters.saveChanges')}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        isOpen={viewValueModal !== null}
        onClose={() => setViewValueModal(null)}
        title={t('parameters.detailsTitle')}
        size="large"
      >
        {viewValueModal && (
          <div className="param-modal-simple">
            <div className="param-modal-simple__header">
              <span className="param-key-label">{t('parameters.paramKey')}</span>
              <div className="param-key-value-wrapper">
                <code className="param-key-value">{viewValueModal.key}</code>
                <button
                  className="icon-btn"
                  onClick={() => copyToClipboard(viewValueModal.key, 'parameters.label.key')}
                  title={t('parameters.copyKey')}
                >
                  📋
                </button>
              </div>
            </div>

            <div className="param-modal-simple__value">
              <div className="value-pill-group">
                {viewValueModal.type && (
                  <span className="value-pill value-pill--type">{viewValueModal.type.toUpperCase()}</span>
                )}
                {viewValueModal.attributes?.map((attr) => (
                  <span key={attr} className="value-pill value-pill--attribute">{attr}</span>
                ))}
                {formattedModalValue?.formatLabel && (
                  <span className="value-pill">{formattedModalValue.formatLabel.toUpperCase()}</span>
                )}
                {viewValueModal.type === 'bytes' && viewValueModal.byte_length !== undefined && (
                  <span className="value-pill value-pill--outline">
                    {t('parameters.bytes', { count: viewValueModal.byte_length })}
                  </span>
                )}
              </div>
              <pre
                className={`value-code-block value-code-block--modal ${
                  formattedModalValue?.isBinary ? 'binary-value' : 'text-value'
                }`}
              >
                <code>{modalValueDisplay}</code>
              </pre>
            </div>

            <div className="param-modal-simple__actions">
              <Button
                variant="secondary"
                onClick={() => {
                  if (formattedModalValue) {
                    copyToClipboard(modalCopyValue, 'parameters.label.value')
                  }
                }}
              >
                {t('parameters.copyValue')}
              </Button>
              <Button
                variant="secondary"
                onClick={() => copyToClipboard(viewValueModal.key, 'parameters.label.key')}
              >
                {t('parameters.copyKey')}
              </Button>
              <Button variant="primary" onClick={() => setViewValueModal(null)}>
                {t('common.close')}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <BackToTop />
    </>
  )
}

import { useRef, useState } from 'react';
import { Check, Download, FileText, Trash2, Upload } from 'lucide-react';
import { api, download } from './api';
import { Badge, display, Empty, ErrorNotice, humanize, Notice, PageTitle, Spinner, Success, useResource } from './ui';

const DOCUMENT_FIELDS = {
  identity_proof: ['full_name', 'date_of_birth'],
  birth_certificate: ['full_name', 'date_of_birth'],
  income_certificate: ['full_name', 'annual_family_income'],
  residence_proof: ['full_name', 'state'],
  category_certificate: ['full_name', 'social_category'],
  student_certificate: ['full_name', 'student_status'],
  disability_certificate: ['full_name', 'disability_status'],
  employment_certificate: ['full_name', 'employment_status'],
  bank_statement: ['full_name', 'has_bank_account'],
};
const BOOLEAN_FIELDS = new Set(['student_status', 'disability_status', 'has_bank_account']);
const CORRECTION_ENUMS = {
  social_category: ['general', 'obc', 'sc', 'st', 'ews'],
  employment_status: ['employed', 'unemployed', 'self_employed', 'retired', 'student', 'homemaker'],
};

export function Documents() {
  const resource = useResource('/documents'), [busy, setBusy] = useState(false), [error, setError] = useState(''), [success, setSuccess] = useState(''), [selected, setSelected] = useState(null), [confirmDelete, setConfirmDelete] = useState(null); const input = useRef(null);
  const docs = Array.isArray(resource.data) ? resource.data : resource.data?.items || [];
  async function upload(e) { e.preventDefault(); const file = input.current.files[0]; if (!file) return; setError(''); setSuccess(''); if (file.size > 10 * 1024 * 1024) { setError('The demo upload limit is 10 MB. Choose a smaller file.'); return; } setBusy(true); const data = new FormData(); data.append('file', file); try { const doc = await api('/documents', { method: 'POST', body: data }); setSuccess(`Uploaded ${file.name}. Review the processing outcome below.`); input.current.value = ''; setSelected(doc); resource.reload(); } catch (e) { setError(e.message); } finally { setBusy(false); } }
  async function remove(id) { setBusy(true); setError(''); try { await api(`/documents/${id}`, { method: 'DELETE' }); setConfirmDelete(null); if (selected?.id === id) setSelected(null); resource.reload(); setSuccess('Document and associated private extraction data deleted.'); } catch (e) { setError(e.message); } finally { setBusy(false); } }
  return <><PageTitle eyebrow="MY DOCUMENTS" title="Your paperwork, in one place.">Upload synthetic documents, review what was extracted, and resolve inconsistencies.</PageTitle><Notice>These checks compare information; they do not authenticate government documents. Use only synthetic demo files. Images and scanned PDFs need manual review when OCR is unavailable.</Notice><section className="panel upload-panel"><div className="upload-icon"><Upload size={25}/></div><div><h2>Add a document</h2><p>PDF, JPEG or PNG · Up to 10 MB · Text-based PDFs support extraction</p></div><form onSubmit={upload}><label><span className="sr-only">Choose a document</span><input ref={input} type="file" aria-label="Choose a document" accept=".pdf,.jpg,.jpeg,.png" required/></label><button className="button" disabled={busy}><Upload size={16}/>{busy ? 'Processing…' : 'Upload document'}</button></form></section><ErrorNotice error={error || resource.error} retry={resource.error ? resource.reload : undefined}/><Success>{success}</Success><div className="documents-layout"><section><div className="section-heading"><h2>Uploaded documents</h2><span className="muted">{docs.length} files</span></div>{resource.loading ? <Spinner/> : docs.length ? <div className="document-list">{docs.map(doc => <article key={doc.id} className={`document-row ${selected?.id === doc.id ? 'selected' : ''}`}><FileText size={23}/><button className="document-name" onClick={() => setSelected(doc)}><strong>{doc.original_filename}</strong><span>{humanize(doc.document_type || 'Unclassified')}</span></button><Badge value={doc.status}/><button className="icon-button" aria-label={`Download ${doc.original_filename}`} onClick={() => download(`/documents/${doc.id}/download`, doc.original_filename).catch(e => setError(e.message))}><Download size={17}/></button><button className="icon-button danger" aria-label={`Delete ${doc.original_filename}`} onClick={() => setConfirmDelete(doc.id)}><Trash2 size={17}/></button>{confirmDelete === doc.id && <div className="delete-confirm" role="alert"><span>Delete this private document and its extraction?</span><button className="button danger-button" disabled={busy} onClick={() => remove(doc.id)}>Confirm delete</button><button className="button secondary" onClick={() => setConfirmDelete(null)}>Cancel</button></div>}</article>)}</div> : !resource.error && <Empty title="No documents yet">Start with a synthetic identity or income PDF. You can inspect every extracted field.</Empty>}</section><section>{selected ? <DocumentResult key={selected.id} doc={selected} onSaved={doc => { setSelected(doc); resource.reload(); }}/> : <div className="panel document-placeholder"><FileText size={32}/><h3>Every detail, explained.</h3><p>Select a document to see extracted information, page evidence, and consistency results.</p></div>}</section></div></>;
}
function DocumentResult({ doc, onSaved }) {
  const [changes, setChanges] = useState({}), [confirmed, setConfirmed] = useState(false), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const fields = doc.fields || {};
  const knownFields = DOCUMENT_FIELDS[doc.document_type] || [];
  const canCorrect = knownFields.length > 0 && ['PROCESSED', 'NEEDS_MANUAL_REVIEW'].includes(doc.status);
  async function correct(e) {
    e.preventDefault();
    if (!canCorrect || !confirmed) return;
    setBusy(true); setError('');
    try {
      const filtered = Object.fromEntries(Object.entries(changes)
        .filter(([key, value]) => knownFields.includes(key) && value !== '')
        .map(([key, value]) => [key, BOOLEAN_FIELDS.has(key) ? value === 'true' : key === 'annual_family_income' ? Number(value) : value]));
      const saved = await api(`/documents/${doc.id}/corrections`, { method: 'PATCH', body: { fields: filtered, confirmed: true } });
      onSaved(saved); setChanges({}); setConfirmed(false);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <article className="panel document-detail">
    <div className="panel-heading"><h2>Document review</h2><Badge value={doc.status}/></div>
    <p className="muted text-sm">{doc.original_filename}</p>
    <ErrorNotice error={doc.error}/>
    <h3>Extracted information</h3>
    {Object.keys(fields).length ? <dl className="field-list">{Object.entries(fields).map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{display(value?.value ?? value)}</dd></div>)}</dl> : <p className="muted">No usable text fields were extracted. This is not a successful content check.</p>}
    <p className="fine-print">Extraction method: {display(doc.method)}</p>
    {doc.evidence && <details><summary>Page and text evidence</summary><pre className="evidence">{JSON.stringify(doc.evidence, null, 2)}</pre></details>}
    <h3>Profile comparisons</h3>
    {doc.checks?.length ? <div className="comparison-list">{doc.checks.map((check, i) => <div key={i}><div><strong>{humanize(check.field)}</strong><Badge value={check.status}/></div><small>Profile: {display(check.profile_value)} · Document: {display(check.document_value)}</small></div>)}</div> : <p className="muted">Comparisons are unknown until both sides have usable information.</p>}
    {Object.keys(doc.corrections || {}).length > 0 && <details open><summary>User-confirmed corrections</summary><pre className="evidence">{JSON.stringify(doc.corrections, null, 2)}</pre><p className="fine-print">These corrections are supplied by you, not independently verified.</p></details>}
    {canCorrect ? <details className="correction-details"><summary>Correct or add information</summary><form onSubmit={correct}>
      <p className="fine-print">Original extraction is preserved. Your profile is never automatically changed. Only fields supported by this document type can be corrected.</p>
      {knownFields.map(field => <label key={field}>{humanize(field)}
        {BOOLEAN_FIELDS.has(field) || CORRECTION_ENUMS[field] ? <select value={changes[field] ?? ''} onChange={e => setChanges({ ...changes, [field]: e.target.value })}>
          <option value="">Keep the current value</option>
          {(BOOLEAN_FIELDS.has(field) ? [['true', 'Yes'], ['false', 'No']] : CORRECTION_ENUMS[field].map(value => [value, humanize(value)])).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select> : <input type={field === 'date_of_birth' ? 'date' : field === 'annual_family_income' ? 'number' : 'text'} min={field === 'annual_family_income' ? 0 : undefined} step={field === 'annual_family_income' ? '0.01' : undefined} maxLength={200} value={changes[field] ?? ''} placeholder="Leave blank to keep the current value" onChange={e => setChanges({ ...changes, [field]: e.target.value })}/>}
      </label>)}
      <label className="checkbox-label"><input type="checkbox" checked={confirmed} required onChange={e => setConfirmed(e.target.checked)}/>I confirm these synthetic document details.</label>
      <ErrorNotice error={error}/>
      <button className="button" disabled={busy || !confirmed || !Object.values(changes).some(value => value !== '')}><Check size={16}/>{busy ? 'Saving…' : 'Save corrections'}</button>
    </form></details> : <p className="fine-print">Corrections are available only for recognized synthetic document templates with usable text. Upload a supported text-based PDF to continue.</p>}
  </article>;
}

import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, ArrowRight, BookOpen, CheckCircle2, FileText, LoaderCircle, RotateCcw } from 'lucide-react';
import { api, safeUrl } from './api';

export function useResource(path) {
  const [data, setData] = useState(null), [error, setError] = useState(''), [loading, setLoading] = useState(true), [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion(v => v + 1), []);
  useEffect(() => { if (!path) { setLoading(false); return; } const controller = new AbortController(); setLoading(true); setError('');
    api(path, { signal: controller.signal }).then(setData).catch(e => { if (e.name !== 'AbortError') setError(e.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [path, version]);
  return { data, error, loading, reload, setData };
}
export function Spinner({ label = 'Loading your information…' }) { return <div className="loading" role="status"><LoaderCircle className="spin" size={22}/>{label}</div>; }
export function ErrorNotice({ error, retry }) { return error ? <div className="notice error" role="alert"><AlertCircle size={18}/><div>{error}</div>{retry && <button className="text-button" onClick={retry}><RotateCcw size={15}/> Try again</button>}</div> : null; }
export function Notice({ children }) { return <div className="notice"><BookOpen size={17}/><div>{children}</div></div>; }
export function Success({ children }) { return children ? <div className="notice success" role="status"><CheckCircle2 size={18}/>{children}</div> : null; }
export function Empty({ title, children, action }) { return <div className="empty"><FileText size={32}/><h3>{title}</h3><p>{children}</p>{action}</div>; }
export function PageTitle({ eyebrow, title, children, action }) { return <header className="page-title"><div><div className="eyebrow">{eyebrow || 'YOUR WELFARE COMPANION'}</div><h1>{title}</h1>{children && <p>{children}</p>}</div>{action}</header>; }
export function humanize(value) { return String(value ?? 'Not supplied').replaceAll('_', ' ').toLowerCase().replace(/^./, c => c.toUpperCase()); }
export function display(value) { if (value === true) return 'Yes'; if (value === false) return 'No'; if (value === null || value === undefined || value === '') return 'Not supplied'; if (Array.isArray(value)) return value.map(display).join(', '); if (typeof value === 'object') return JSON.stringify(value); return String(value); }
export function Badge({ value }) { const status = String(value || 'UNKNOWN'); return <span className={`badge ${['ELIGIBLE', 'PASS', 'MATCH', 'READY', 'SATISFIED', 'PROCESSED'].includes(status) ? 'positive' : ['FAIL', 'NOT_ELIGIBLE', 'MISMATCH', 'FAILED'].includes(status) ? 'negative' : 'neutral'}`}>{humanize(status)}</span>; }
export function Source({ source, fictional }) { const url = safeUrl(source?.url); return <div className="source"><BookOpen size={14}/><span>{fictional ? 'Fictional academic fixture · ' : ''}{url ? <a href={url} target="_blank" rel="noreferrer">{source.title || 'View source'} ↗</a> : (source?.title || source?.reference || 'Source not supplied')}{source?.retrieved_at && <small>Retrieved {source.retrieved_at}</small>}</span></div>; }
export function SchemeCard({ scheme }) {
  const eligibility = scheme.eligibility;
  return <article className="scheme-card"><div className="card-top"><span className="category">{humanize(scheme.category)}</span>{scheme.is_fictional && <span className="fixture-label">DEMO SCHEME</span>}</div><h3><Link to={`/schemes/${scheme.id}`}>{scheme.name}</Link></h3><p className="description">{scheme.description}</p><div className="scheme-location">{display(scheme.jurisdiction || 'India')}</div>{eligibility && <div className="eligibility-summary"><Badge value={eligibility.status}/>{scheme.score !== undefined && <span>Relevance {Number(scheme.score).toFixed(0)}/100</span>}</div>}<div className="card-bottom"><span>{eligibility?.missing_information?.length ? `${eligibility.missing_information.length} profile details needed` : `Rule version ${scheme.version ?? 1}`}</span><Link className="card-link" to={`/schemes/${scheme.id}`}>View scheme <ArrowRight size={16}/></Link></div></article>;
}
export function Trace({ trace }) {
  if (!trace) return null;
  if (Array.isArray(trace)) return <div className="trace-list">{trace.map((x, i) => <Trace key={i} trace={x}/>)}</div>;
  const children = trace.children || trace.results;
  return <div className="trace"><div className="trace-heading"><Badge value={trace.status || trace.result}/><strong>{trace.explanation || trace.message || trace.reason || (trace.field ? humanize(trace.field) : `${(trace.type || trace.group || trace.operator || 'Requirements').toUpperCase()} group`)}</strong></div>{trace.field && <div className="muted text-sm">Your value: {display(trace.value ?? trace.actual ?? trace.actual_value ?? trace.value_used)} · Requirement: {trace.op || trace.operator} {display(trace.expected ?? trace.value)}</div>}{trace.source_reference && <small className="muted">Source: {display(trace.source_reference)}</small>}{children && <Trace trace={children}/>}</div>;
}


"use client";

import { useEffect, useRef, useState } from "react";
import { useLocale, useTranslations } from "next-intl";
import { Users, BarChart2, ShieldCheck, Settings, Loader2, RefreshCw, BookOpen, Upload, Trash2, FileText, CheckCircle, PenLine, Check, Pencil, X } from "lucide-react";
import { apiFetch as apiRequest, apiJson, UnauthorizedError } from "@/lib/api";

interface UserRecord {
  user_id: string;
  email?: string;
  name?: string;
  picture?: string;
  role?: string;
  updated_at?: string;
}

interface Metrics {
  users: number;
  sessions: number;
  messages: number;
  audit_events: number;
}

interface AuditEntry {
  event_id: string;
  user_email_hash: string;
  action: string;
  resource_type: string;
  resource_id: string;
  timestamp: string;
}

interface Configs {
  [key: string]: boolean | string;
}

interface KBDoc {
  doc_id: string;
  filename: string;
  filetype: string;
  chunk_count: number;
  ingested_at: string;
  status: string;
  gcs_path: string;
}

interface SignatureRecord {
  signature_id: string;
  label: string;
  content: string;
  logo_url?: string;
}

type Tab = "metrics" | "users" | "audit" | "kb" | "config" | "signatures";

export default function AdminPage() {
  const t = useTranslations("admin");
  const locale = useLocale();
  const adminEnabled = process.env.NEXT_PUBLIC_ADMIN_ENABLED === "true";

  const [tab, setTab] = useState<Tab>("metrics");
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [configs, setConfigs] = useState<Configs>({});
  const [kbDocs, setKbDocs] = useState<KBDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Signatures tab state (per-user data — endpoints are not admin-gated)
  const [signatures, setSignatures] = useState<SignatureRecord[]>([]);
  const [activeSigId, setActiveSigId] = useState<string | null>(null);
  const [sigEditingId, setSigEditingId] = useState<string | null>(null); // "new" for the create form
  const [sigLabel, setSigLabel] = useState("");
  const [sigContent, setSigContent] = useState("");
  const [sigLogoUrl, setSigLogoUrl] = useState("");
  const [sigLogoUploading, setSigLogoUploading] = useState(false);
  const [sigSaving, setSigSaving] = useState(false);
  const [sigError, setSigError] = useState("");
  const sigLogoInputRef = useRef<HTMLInputElement>(null);

  const load = async (activeTab: Tab) => {
    setLoading(true);
    setError("");
    try {
      if (activeTab === "users") {
        const data = await apiJson<{ users?: UserRecord[] }>("/admin/users");
        setUsers(data.users || []);
      } else if (activeTab === "metrics") {
        const data = await apiJson<{ metrics: Metrics }>("/admin/metrics");
        setMetrics(data.metrics);
      } else if (activeTab === "audit") {
        const data = await apiJson<{ logs?: AuditEntry[] }>("/admin/audit?limit=50");
        setAudit(data.logs || []);
      } else if (activeTab === "kb") {
        const data = await apiJson<{ documents?: KBDoc[] }>("/knowledge/documents");
        setKbDocs(data.documents || []);
      } else if (activeTab === "config") {
        const data = await apiJson<{ configs?: Configs }>("/admin/configs");
        setConfigs(data.configs || {});
      } else if (activeTab === "signatures") {
        const data = await apiJson<{ signatures?: SignatureRecord[]; active_signature_id?: string | null }>("/api/signatures");
        setSignatures(data.signatures || []);
        setActiveSigId(data.active_signature_id ?? null);
      }
    } catch (e: unknown) {
      if (e instanceof UnauthorizedError) return;
      setError(e instanceof Error ? e.message : t("errorLoadingData"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (adminEnabled) load(tab);
  }, [tab]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!adminEnabled) {
    return (
      <div className="p-8 max-w-4xl mx-auto w-full text-center">
        <h1 className="text-2xl font-bold text-red-600">{t("accessDenied")}</h1>
        <p className="text-[var(--color-text-muted)] mt-2">{t("accessDeniedMessage")}</p>
      </div>
    );
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await apiRequest(`/knowledge/documents`, { method: "POST", body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || t("uploadFailed"));
      setUploadMsg(`✓ ${t("uploadSuccess", { filename: data.filename, count: data.chunk_count })}`);
      load("kb");
    } catch (err: unknown) {
      if (err instanceof UnauthorizedError) return;
      setUploadMsg(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      const res = await apiRequest(`/knowledge/documents/${docId}`, { method: "DELETE" });
      if (!res.ok) return;
      setKbDocs((prev) => prev.filter((d) => d.doc_id !== docId));
    } catch (err) {
      if (!(err instanceof UnauthorizedError)) console.error(err);
    }
  };

  const sigStartEdit = (s: SignatureRecord | null) => {
    setSigError("");
    setSigEditingId(s ? s.signature_id : "new");
    setSigLabel(s?.label || "");
    setSigContent(s?.content || "");
    setSigLogoUrl(s?.logo_url || "");
  };

  const handleSigLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSigLogoUploading(true);
    setSigError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await apiRequest("/api/signatures/logo", { method: "POST", body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || t("sigLogoError"));
      setSigLogoUrl(data.logo_url);
    } catch (err) {
      if (err instanceof UnauthorizedError) return;
      setSigError(err instanceof Error ? err.message : t("sigLogoError"));
    } finally {
      setSigLogoUploading(false);
      if (sigLogoInputRef.current) sigLogoInputRef.current.value = "";
    }
  };

  const handleSigSave = async () => {
    if (!sigLabel.trim() || !sigContent.trim() || sigSaving) return;
    setSigSaving(true);
    setSigError("");
    try {
      const body = JSON.stringify({ label: sigLabel.trim(), content: sigContent, logo_url: sigLogoUrl });
      if (sigEditingId === "new") {
        await apiJson("/api/signatures", { method: "POST", headers: { "Content-Type": "application/json" }, body });
      } else {
        await apiJson(`/api/signatures/${sigEditingId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body });
      }
      setSigEditingId(null);
      await load("signatures");
    } catch (err) {
      if (err instanceof UnauthorizedError) return;
      setSigError(err instanceof Error ? err.message : t("sigError"));
    } finally {
      setSigSaving(false);
    }
  };

  const handleSigDelete = async (signatureId: string) => {
    if (!window.confirm(t("sigConfirmDelete"))) return;
    try {
      await apiJson(`/api/signatures/${signatureId}`, { method: "DELETE" });
      await load("signatures");
    } catch (err) {
      if (!(err instanceof UnauthorizedError)) setSigError(err instanceof Error ? err.message : t("sigError"));
    }
  };

  const handleSigSetActive = async (signatureId: string | null) => {
    try {
      await apiJson("/api/signatures/active", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ signature_id: signatureId }),
      });
      setActiveSigId(signatureId);
    } catch (err) {
      if (!(err instanceof UnauthorizedError)) setSigError(err instanceof Error ? err.message : t("sigError"));
    }
  };

  const tabs: { id: Tab; label: string; Icon: typeof Users }[] = [
    { id: "metrics", label: t("tabMetrics"), Icon: BarChart2 },
    { id: "users", label: t("tabUsers"), Icon: Users },
    { id: "kb", label: t("tabKb"), Icon: BookOpen },
    { id: "signatures", label: t("tabSignatures"), Icon: PenLine },
    { id: "audit", label: t("tabAudit"), Icon: ShieldCheck },
    { id: "config", label: t("tabConfig"), Icon: Settings },
  ];

  return (
    <div className="p-6 max-w-6xl mx-auto w-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[var(--color-navy)]">{t("title")}</h1>
        <button
          onClick={() => load(tab)}
          className="flex items-center gap-2 text-sm px-3 py-2 text-[var(--color-primary)] hover:bg-[var(--color-primary-light)] rounded-[8px] transition-colors"
        >
          <RefreshCw size={15} /> {t("refresh")}
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-[var(--color-border)] mb-6">
        {tabs.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === id
                ? "border-[var(--color-primary)] text-[var(--color-primary)]"
                : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-navy)]"
            }`}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>

      {/* Loading / error */}
      {loading && (
        <div className="flex items-center gap-2 text-[var(--color-text-muted)] text-sm py-8 justify-center">
          <Loader2 size={16} className="animate-spin" /> {t("loading")}
        </div>
      )}
      {error && (
        <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-[8px] px-4 py-3 mb-4">
          Error: {error}
        </div>
      )}

      {/* ── Metrics ── */}
      {!loading && tab === "metrics" && metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: t("metricUsers"), value: metrics.users, color: "text-[var(--color-primary)]" },
            { label: t("metricSessions"), value: metrics.sessions, color: "text-[var(--color-navy)]" },
            { label: t("metricMessages"), value: metrics.messages, color: "text-green-600" },
            { label: t("metricAuditEvents"), value: metrics.audit_events, color: "text-orange-500" },
          ].map((m) => (
            <div
              key={m.label}
              className="bg-white border border-[var(--color-border)] rounded-[12px] p-5 shadow-sm text-center"
            >
              <p className={`text-4xl font-bold ${m.color}`}>{m.value}</p>
              <p className="text-xs text-[var(--color-text-muted)] uppercase mt-1">{m.label}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Users ── */}
      {!loading && tab === "users" && (
        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm overflow-hidden">
          {users.length === 0 ? (
            <p className="p-8 text-center text-[var(--color-text-muted)] text-sm">{t("noUsers")}</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-background)] border-b border-[var(--color-border)]">
                <tr>
                  {[t("colUser"), t("colEmail"), t("colRole"), t("colLastActivity")].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-[var(--color-text-muted)] uppercase">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {users.map((u) => (
                  <tr key={u.user_id} className="hover:bg-[var(--color-background)] transition-colors">
                    <td className="px-4 py-3 flex items-center gap-2">
                      {u.picture ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={u.picture} alt="" className="w-7 h-7 rounded-full" />
                      ) : (
                        <div className="w-7 h-7 rounded-full bg-[var(--color-primary-light)] flex items-center justify-center text-xs font-bold text-[var(--color-primary)]">
                          {(u.name || u.email || "?")[0].toUpperCase()}
                        </div>
                      )}
                      <span className="font-medium text-[var(--color-navy)]">{u.name || "—"}</span>
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">{u.email || u.user_id}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        u.role === "admin"
                          ? "bg-[var(--color-primary-light)] text-[var(--color-primary)]"
                          : "bg-gray-100 text-gray-600"
                      }`}>
                        {u.role || "user"}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--color-text-muted)]">
                      {u.updated_at
                        ? new Date(u.updated_at).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" })
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Audit log ── */}
      {!loading && tab === "audit" && (
        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm overflow-hidden">
          {audit.length === 0 ? (
            <p className="p-8 text-center text-[var(--color-text-muted)] text-sm">{t("noAuditEvents")}</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-background)] border-b border-[var(--color-border)]">
                <tr>
                  {[t("colDate"), t("colAction"), t("colType"), t("colResource"), t("colUserHash")].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-[var(--color-text-muted)] uppercase">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {audit.map((e) => (
                  <tr key={e.event_id} className="hover:bg-[var(--color-background)] transition-colors">
                    <td className="px-4 py-2.5 text-[var(--color-text-muted)] whitespace-nowrap">
                      {new Date(e.timestamp).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" })}
                    </td>
                    <td className="px-4 py-2.5">
                      <ActionBadge action={e.action} />
                    </td>
                    <td className="px-4 py-2.5 text-[var(--color-text-muted)]">{e.resource_type}</td>
                    <td className="px-4 py-2.5 font-mono text-xs text-[var(--color-text-muted)] max-w-[180px] truncate">
                      {e.resource_id}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-[var(--color-text-muted)]">
                      {e.user_email_hash.slice(0, 12)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Knowledge Base ── */}
      {!loading && tab === "kb" && (
        <div className="space-y-4">
          {/* Upload card */}
          <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-5">
            <h3 className="font-semibold text-[var(--color-navy)] mb-3 flex items-center gap-2">
              <Upload size={16} /> {t("uploadTitle")}
            </h3>
            <p className="text-xs text-[var(--color-text-muted)] mb-3">
              {t("formatsHelp")}
            </p>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.doc,.txt,.csv,.md"
                onChange={handleUpload}
                className="hidden"
                id="kb-file-input"
              />
              <label
                htmlFor="kb-file-input"
                className={`flex items-center gap-2 px-4 py-2 rounded-[8px] text-sm font-medium cursor-pointer transition-colors ${
                  uploading
                    ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                    : "bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-dark)]"
                }`}
              >
                {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                {uploading ? t("processing") : t("selectFile")}
              </label>
              {uploadMsg && (
                <span className={`text-sm flex items-center gap-1 ${uploadMsg.startsWith("✓") ? "text-green-600" : "text-red-600"}`}>
                  {uploadMsg.startsWith("✓") && <CheckCircle size={14} />}
                  {uploadMsg}
                </span>
              )}
            </div>
          </div>

          {/* Document list */}
          <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
              <h3 className="font-semibold text-[var(--color-navy)] flex items-center gap-2">
                <FileText size={15} /> {t("indexedDocuments", { count: kbDocs.length })}
              </h3>
            </div>
            {kbDocs.length === 0 ? (
              <p className="p-8 text-center text-[var(--color-text-muted)] text-sm">
                {t("noDocuments")}
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-[var(--color-background)] border-b border-[var(--color-border)]">
                  <tr>
                    {[t("colFile"), t("colFileType"), t("colChunks"), t("colIndexed"), ""].map((h) => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-[var(--color-text-muted)] uppercase">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {kbDocs.map((doc) => (
                    <tr key={doc.doc_id} className="hover:bg-[var(--color-background)] transition-colors">
                      <td className="px-4 py-3 font-medium text-[var(--color-navy)]">{doc.filename}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--color-primary-light)] text-[var(--color-primary)] font-medium uppercase">
                          {doc.filetype}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[var(--color-text-muted)]">{doc.chunk_count}</td>
                      <td className="px-4 py-3 text-[var(--color-text-muted)]">
                        {doc.ingested_at
                          ? new Date(doc.ingested_at).toLocaleString(locale, { dateStyle: "short", timeStyle: "short" })
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDeleteDoc(doc.doc_id)}
                          className="p-1.5 rounded text-red-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                          title={t("deleteDocument")}
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {/* ── Signatures (per-user) ── */}
      {!loading && tab === "signatures" && (
        <div className="space-y-4 max-w-3xl">
          <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-5">
            <h3 className="font-semibold text-[var(--color-navy)] mb-1 flex items-center gap-2">
              <PenLine size={16} /> {t("sigTitle")}
            </h3>
            <p className="text-xs text-[var(--color-text-muted)]">{t("sigHelp")}</p>
          </div>

          {sigError && (
            <div className="text-red-600 text-sm bg-red-50 border border-red-200 rounded-[8px] px-4 py-2">{sigError}</div>
          )}

          {/* "No signature" option */}
          <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-4 flex items-center gap-3">
            <button
              type="button"
              onClick={() => handleSigSetActive(null)}
              className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 transition-colors ${activeSigId === null ? "bg-[var(--color-primary)] border-[var(--color-primary)] text-white" : "border-gray-300 hover:border-[var(--color-primary)]"}`}
              title={t("sigSetActive")}
            >
              {activeSigId === null && <Check size={12} />}
            </button>
            <span className="text-sm text-[var(--color-text-secondary)]">{t("sigNoActive")}</span>
          </div>

          {signatures.length === 0 && (
            <p className="text-sm text-[var(--color-text-muted)] px-1">{t("sigEmpty")}</p>
          )}

          {signatures.map((s) => (
            <div key={s.signature_id} className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-4">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => handleSigSetActive(s.signature_id)}
                  className={`w-5 h-5 rounded-full border flex items-center justify-center shrink-0 transition-colors ${activeSigId === s.signature_id ? "bg-[var(--color-primary)] border-[var(--color-primary)] text-white" : "border-gray-300 hover:border-[var(--color-primary)]"}`}
                  title={t("sigSetActive")}
                >
                  {activeSigId === s.signature_id && <Check size={12} />}
                </button>
                <span className="font-medium text-sm text-[var(--color-navy)]">{s.label}</span>
                {activeSigId === s.signature_id && (
                  <span className="text-[10px] uppercase tracking-wide bg-[var(--color-primary-light)] text-[var(--color-primary)] px-2 py-0.5 rounded-full">{t("sigActive")}</span>
                )}
                <div className="ml-auto flex items-center gap-1">
                  <button type="button" onClick={() => sigStartEdit(s)} className="p-1.5 text-gray-400 hover:text-[var(--color-navy)]" title={t("sigEdit")}>
                    <Pencil size={14} />
                  </button>
                  <button type="button" onClick={() => handleSigDelete(s.signature_id)} className="p-1.5 text-gray-400 hover:text-red-500" title={t("sigDelete")}>
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              <pre className="mt-2 ml-8 text-xs whitespace-pre-wrap text-[var(--color-text-secondary)] font-sans">{s.content}</pre>
              {s.logo_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={s.logo_url} alt="" className="mt-2 ml-8 max-h-[50px]" />
              )}
            </div>
          ))}

          {/* Create / edit form */}
          {sigEditingId !== null ? (
            <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm p-5 space-y-3">
              <h3 className="font-semibold text-[var(--color-navy)] text-sm">
                {sigEditingId === "new" ? t("sigCreateTitle") : t("sigEdit")}
              </h3>
              <div>
                <label className="text-xs text-[var(--color-text-muted)]">{t("sigLabel")}</label>
                <input
                  value={sigLabel}
                  onChange={(e) => setSigLabel(e.target.value)}
                  maxLength={60}
                  placeholder={t("sigLabelPlaceholder")}
                  className="mt-1 w-full text-sm border border-[var(--color-border)] rounded-[8px] px-3 py-2"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--color-text-muted)]">{t("sigContent")}</label>
                <textarea
                  value={sigContent}
                  onChange={(e) => setSigContent(e.target.value)}
                  maxLength={1000}
                  rows={4}
                  placeholder={t("sigContentPlaceholder")}
                  className="mt-1 w-full text-sm border border-[var(--color-border)] rounded-[8px] px-3 py-2"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--color-text-muted)]">{t("sigLogo")}</label>
                <div className="mt-1 flex items-center gap-3">
                  <input ref={sigLogoInputRef} type="file" accept=".png,.jpg,.jpeg" onChange={handleSigLogoUpload} className="hidden" id="sig-logo-input" />
                  <label htmlFor="sig-logo-input" className="inline-flex items-center gap-2 text-xs border border-[var(--color-border)] rounded-[8px] px-3 py-2 cursor-pointer hover:bg-gray-50">
                    {sigLogoUploading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                    {sigLogoUploading ? t("sigUploading") : t("sigChooseLogo")}
                  </label>
                  {sigLogoUrl && (
                    <>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={sigLogoUrl} alt="" className="max-h-[40px]" />
                      <button type="button" onClick={() => setSigLogoUrl("")} className="p-1 text-gray-400 hover:text-red-500" title={t("sigRemoveLogo")}>
                        <X size={14} />
                      </button>
                    </>
                  )}
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  type="button"
                  onClick={handleSigSave}
                  disabled={!sigLabel.trim() || !sigContent.trim() || sigSaving || sigLogoUploading}
                  className="inline-flex items-center gap-2 text-sm bg-[var(--color-primary)] text-white px-4 py-2 rounded-[8px] hover:bg-[var(--color-primary-dark)] disabled:opacity-50"
                >
                  {sigSaving ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}
                  {sigEditingId === "new" ? t("sigCreate") : t("sigSave")}
                </button>
                <button type="button" onClick={() => setSigEditingId(null)} className="text-sm px-4 py-2 rounded-[8px] border border-[var(--color-border)] hover:bg-gray-50">
                  {t("sigCancel")}
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => sigStartEdit(null)}
              className="inline-flex items-center gap-2 text-sm bg-[var(--color-primary)] text-white px-4 py-2 rounded-[8px] hover:bg-[var(--color-primary-dark)]"
            >
              <PenLine size={14} /> {t("sigCreateTitle")}
            </button>
          )}
        </div>
      )}

      {/* ── Config ── */}
      {!loading && tab === "config" && (
        <div className="bg-white border border-[var(--color-border)] rounded-[12px] shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-background)] border-b border-[var(--color-border)]">
              <tr>
                {[t("colVariable"), t("colValue")].map((h) => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-[var(--color-text-muted)] uppercase">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {Object.entries(configs).map(([key, val]) => (
                <tr key={key} className="hover:bg-[var(--color-background)] transition-colors">
                  <td className="px-4 py-2.5 font-mono text-xs text-[var(--color-navy)]">{key}</td>
                  <td className="px-4 py-2.5">
                    {typeof val === "boolean" ? (
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        val ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                      }`}>
                        {val ? "true" : "false"}
                      </span>
                    ) : (
                      <span className="text-xs text-[var(--color-text-muted)]">{String(val)}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const ACTION_COLORS: Record<string, string> = {
  login:        "bg-blue-100 text-blue-700",
  docs_create:  "bg-green-100 text-green-700",
  docs_update:  "bg-teal-100 text-teal-700",
  email_send:   "bg-purple-100 text-purple-700",
  hitl_approved:"bg-emerald-100 text-emerald-700",
  hitl_rejected:"bg-red-100 text-red-700",
};

function ActionBadge({ action }: { action: string }) {
  const cls = ACTION_COLORS[action] ?? "bg-gray-100 text-gray-600";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{action}</span>
  );
}

import { useState, useEffect, useRef } from 'react';
import type { FormEvent, ChangeEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import type { Call } from '../api/types';

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-gray-500 text-gray-100',
  uploaded: 'bg-blue-600 text-blue-100',
  processing: 'bg-yellow-600 text-yellow-100',
  done: 'bg-green-700 text-green-100',
  failed: 'bg-red-700 text-red-100',
};

function formatDuration(seconds?: number) {
  if (!seconds) return '-';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatDateTime(dt: string) {
  return new Date(dt).toLocaleString();
}

export default function CallsList() {
  const navigate = useNavigate();
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [clientNameFilter, setClientNameFilter] = useState('');
  const [operatorNameFilter, setOperatorNameFilter] = useState('');

  // Debounced values for text search filters
  const [debouncedClientName, setDebouncedClientName] = useState('');
  const [debouncedOperatorName, setDebouncedOperatorName] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedClientName(clientNameFilter), 400);
    return () => clearTimeout(timer);
  }, [clientNameFilter]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedOperatorName(operatorNameFilter), 400);
    return () => clearTimeout(timer);
  }, [operatorNameFilter]);

  // New call modal
  const [showModal, setShowModal] = useState(false);
  const [newClientId, setNewClientId] = useState('');
  const [creating, setCreating] = useState(false);

  // Quick upload modal
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadLang, setUploadLang] = useState('ru');
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchCalls = async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string> = {};
      if (from) params.from = from;
      if (to) params.to = to;
      if (statusFilter) params.status = statusFilter;
      if (debouncedClientName) params.client_name = debouncedClientName;
      if (debouncedOperatorName) params.operator_name = debouncedOperatorName;
      const { data } = await api.get('/api/calls/', { params });
      setCalls(Array.isArray(data) ? data : data.results ?? []);
    } catch {
      setError('Failed to load calls');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCalls();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [from, to, statusFilter, debouncedClientName, debouncedOperatorName]);

  const handleCreateCall = async (e: FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const payload: Record<string, unknown> = {};
      if (newClientId) payload.client = parseInt(newClientId);
      const { data } = await api.post('/api/calls/', payload);
      setShowModal(false);
      setNewClientId('');
      navigate(`/calls/${data.id}`);
    } catch {
      setError('Failed to create call');
    } finally {
      setCreating(false);
    }
  };

  const handleQuickUpload = async (e: FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('language_hint', uploadLang);
      const { data } = await api.post('/api/intake/audio/', formData);
      setShowUploadModal(false);
      setUploadFile(null);
      setUploadLang('ru');
      await fetchCalls();
      navigate(`/calls/${data.call.id}`);
    } catch {
      setError('Failed to upload recording');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Calls</h2>
        <div className="flex gap-2">
          <button
            onClick={() => setShowUploadModal(true)}
            className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
          >
            ⬆ Quick Upload
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
          >
            + New Call
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6 flex flex-wrap gap-4">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">From</label>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">To</label>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">Status</label>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400">
            <option value="">All</option>
            <option value="new">New</option>
            <option value="uploaded">Uploaded</option>
            <option value="processing">Processing</option>
            <option value="done">Done</option>
            <option value="failed">Failed</option>
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">Client name</label>
          <input type="text" value={clientNameFilter} onChange={(e) => setClientNameFilter(e.target.value)}
            placeholder="Search by client name"
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 w-44" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-gray-500 font-medium">Operator name</label>
          <input type="text" value={operatorNameFilter} onChange={(e) => setOperatorNameFilter(e.target.value)}
            placeholder="Search by operator name"
            className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 w-44" />
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-4 py-3 mb-4">{error}</div>
      )}

      {loading ? (
        <div className="text-center text-gray-500 py-12">Loading...</div>
      ) : (
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">ID</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Client</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Operator</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Date/Time</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Duration</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {calls.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-400">No calls found</td>
                </tr>
              ) : (
                calls.map((call) => (
                  <tr
                    key={call.id}
                    onClick={() => navigate(`/calls/${call.id}`)}
                    className="hover:bg-gray-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-gray-700 font-mono">#{call.id}</td>
                    <td className="px-4 py-3 text-gray-700">
                      {call.client_detail?.full_name ?? (call.client ? `Client #${call.client}` : '—')}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {call.operator_detail?.username ?? `#${call.operator}`}
                    </td>
                    <td className="px-4 py-3 text-gray-600">{formatDateTime(call.started_at)}</td>
                    <td className="px-4 py-3 text-gray-600">{formatDuration(call.duration)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold capitalize ${STATUS_COLORS[call.status] ?? 'bg-gray-200 text-gray-700'}`}>
                        {call.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{call.category ?? '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* New Call Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">New Call</h3>
            <form onSubmit={handleCreateCall} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Client ID (optional)</label>
                <input
                  type="number"
                  value={newClientId}
                  onChange={(e) => setNewClientId(e.target.value)}
                  placeholder="Leave blank if unknown"
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
              <div className="flex gap-3 justify-end">
                <button type="button" onClick={() => setShowModal(false)}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={creating}
                  className="px-4 py-2 text-sm bg-indigo-600 hover:bg-indigo-700 text-white rounded-md font-medium transition-colors disabled:opacity-60">
                  {creating ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Quick Upload Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-sm">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Quick Upload</h3>
            <p className="text-sm text-gray-500 mb-4">
              Upload an MP3 recording. A call entry will be created and analysis queued automatically.
            </p>
            <form onSubmit={handleQuickUpload} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">MP3 File <span className="text-red-500">*</span></label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="audio/mpeg,.mp3"
                  onChange={(e: ChangeEvent<HTMLInputElement>) => setUploadFile(e.target.files?.[0] ?? null)}
                  className="w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:font-medium file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Language</label>
                <select
                  value={uploadLang}
                  onChange={(e) => setUploadLang(e.target.value)}
                  className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                >
                  <option value="ru">Russian</option>
                  <option value="kk">Kazakh</option>
                </select>
              </div>
              <div className="flex gap-3 justify-end">
                <button type="button" onClick={() => { setShowUploadModal(false); setUploadFile(null); setUploadLang('ru'); }}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors">
                  Cancel
                </button>
                <button type="submit" disabled={uploading || !uploadFile}
                  className="px-4 py-2 text-sm bg-emerald-600 hover:bg-emerald-700 text-white rounded-md font-medium transition-colors disabled:opacity-60">
                  {uploading ? 'Uploading...' : 'Upload & Analyze'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

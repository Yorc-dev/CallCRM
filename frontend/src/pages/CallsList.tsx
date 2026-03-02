import { useState, useEffect } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import type { Call } from '../api/types';
import { useAuth } from '../contexts/AuthContext';

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
  const { user } = useAuth();
  const isManager = user?.role === 'chief' || user?.role === 'admin';

  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [operatorFilter, setOperatorFilter] = useState('');

  // New call modal
  const [showModal, setShowModal] = useState(false);
  const [newClientId, setNewClientId] = useState('');
  const [creating, setCreating] = useState(false);

  const fetchCalls = async () => {
    setLoading(true);
    setError('');
    try {
      const params: Record<string, string> = {};
      if (from) params.from = from;
      if (to) params.to = to;
      if (statusFilter) params.status = statusFilter;
      if (isManager && operatorFilter) params.operator = operatorFilter;
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
  }, [from, to, statusFilter, operatorFilter]);

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

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Calls</h2>
        <button
          onClick={() => setShowModal(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors"
        >
          + New Call
        </button>
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
        {isManager && (
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">Operator ID</label>
            <input type="number" value={operatorFilter} onChange={(e) => setOperatorFilter(e.target.value)}
              placeholder="Operator ID"
              className="border border-gray-300 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 w-32" />
          </div>
        )}
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
    </div>
  );
}
